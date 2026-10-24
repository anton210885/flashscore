"""Swisslos-Sporttip-Quoten (1X2, Over/Under) abholen, unseren Spielen zuordnen und speichern.

Sporttip läuft auf der Admiral-Plattform: Spiele und Quoten kommen über einen WebSocket
(wss://ws.ch.admiral.at), Nachrichten sind JSON, roh mit Deflate komprimiert.
Ablauf pro Lauf (eine Verbindung):
  connect(sportsbook) → ConfigureEnvironment → je Länderseite RetrieveSportsbookPage
  → UpdateSportsbookPage (alle Liga-Gruppen aufklappen, Märkte 1X2 + Over/Under abonnieren).

Prototyp: nicht dokumentierte Schnittstelle — kann sich ohne Vorwarnung ändern.
Gespeichert wird nur vor Anpfiff; der letzte Stand vor dem Spiel bleibt stehen.
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
import time
import unicodedata
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from services import swisslos_service

WS_URL = "wss://ws.ch.admiral.at/"
ORIGIN = "https://www.swisslos.ch"
SERVICE = {"type": "binary", "service": "sportsbook"}
# Konfigurationsknoten „Desktop“ von sporttip-ch-sl (fest, nicht pro Besucher)
CONFIG_NODE = "asw:node:admiral:device:1886b7bc-2f48-486a-ac40-4fe5828886a8"
MARKET_CONFIGS = ["asw:marketconfig:1", "asw:marketconfig:2"]  # Endergebnis, Over/Under

MT_1X2 = "asw:markettype:1"
MT_TOTAL = "asw:markettype:18"
SEL_1X2 = {"asw:selectiontype:1": "home", "asw:selectiontype:2": "draw", "asw:selectiontype:3": "away"}
SEL_TOTAL = {"asw:selectiontype:12": "over", "asw:selectiontype:13": "under"}
TOTAL_LINES = (1.5, 2.5, 3.5, 4.5)

ODDS_COLS = [
    "odd_home", "odd_draw", "odd_away",
    "odd_over_15", "odd_under_15", "odd_over_25", "odd_under_25",
    "odd_over_35", "odd_under_35", "odd_over_45", "odd_under_45",
]

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS swisslos_odds (
    game_id INTEGER PRIMARY KEY,
    event_urn TEXT,
    sl_name TEXT,
    sl_league TEXT,
    start_time TEXT,
    match_score REAL,
    {", ".join(f"{c} REAL" for c in ODDS_COLS)},
    first_seen_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS swisslos_unmatched (
    event_urn TEXT PRIMARY KEY,
    sl_name TEXT,
    sl_league TEXT,
    start_time TEXT,
    best_game_id INTEGER,
    best_score REAL,
    seen_at TEXT
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Abholen ────────────────────────────────────────────────────────────


def _pack(obj: Dict[str, Any]) -> bytes:
    c = zlib.compressobj(wbits=-15)
    return c.compress(json.dumps(obj, separators=(",", ":")).encode()) + c.flush()


def _unpack(op: int, data: bytes) -> str:
    return zlib.decompress(data, -15).decode() if op == 2 else data.decode()


def _nodes(node: Any, type_name: str, out: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("type") == type_name:
            out.append(node)
        for v in node.values():
            _nodes(v, type_name, out)
    elif isinstance(node, list):
        for v in node:
            _nodes(v, type_name, out)
    return out


class _Session:
    def __init__(self, timeout: float = 2.0):
        import websocket  # websocket-client

        self._wsmod = websocket
        # Der Handshake scheitert gelegentlich mit 502 — kurz warten und neu versuchen
        for attempt in range(3):
            try:
                self.ws = websocket.create_connection(
                    WS_URL, timeout=timeout, origin=ORIGIN, header=["User-Agent: Mozilla/5.0"]
                )
                break
            except websocket.WebSocketBadStatusException:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
        self.entities: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.pages: List[Dict[str, Any]] = []

    def send(self, payload: List[Dict[str, Any]]) -> None:
        self.ws.send_binary(_pack({"payload": payload, "properties": SERVICE}))

    def connect(self) -> None:
        self.ws.send_binary(_pack({"connect": {"headers": {}}, "properties": SERVICE}))
        end = time.time() + 15
        while time.time() < end:
            try:
                if '"connected"' in _unpack(*self.ws.recv_data()):
                    break
            except self._wsmod.WebSocketTimeoutException:
                continue
        else:
            raise RuntimeError("Swisslos: keine Verbindung (connected fehlt)")
        self.send([{
            "type": "ConfigureEnvironment", "name": "ConfigureEnvironment",
            "body": {"timeZone": "Europe/Zurich", "languageCode": "de", "configurationNodeUrn": CONFIG_NODE},
        }])
        self.pump(quiet=1.0)

    def pump(self, quiet: float = 1.5, max_seconds: float = 20.0) -> None:
        """Nachrichten lesen, bis `quiet` Sekunden nichts mehr kommt."""
        end = time.time() + max_seconds
        last = time.time()
        while time.time() < end and time.time() - last < quiet:
            try:
                op, data = self.ws.recv_data()
            except self._wsmod.WebSocketTimeoutException:
                continue
            last = time.time()
            txt = _unpack(op, data)
            if not txt.startswith('{"payload"'):
                continue
            for msg in json.loads(json.loads(txt)["payload"]):
                kind = msg.get("type")
                if kind == "SportsbookSnapshotUpdated":
                    for item in msg["body"]["snapshotUpdate"]["snapshotUpdateItems"]:
                        bucket = self.entities.setdefault(item["type"], {})
                        urn = item["entity"].get("urn")
                        if item["kind"] == 0:
                            bucket[urn] = item["entity"]
                        else:
                            bucket.pop(urn, None)
                elif kind == "SportsbookPageRetrieved":
                    self.pages.append(msg["body"])

    def load_page(self, url_part: str) -> int:
        """Länderseite laden, alle Liga-Gruppen aufklappen; gibt die Anzahl Spiele laut Seite zurück."""
        self.pages.clear()
        self.send([{
            "type": "RetrieveSportsbookPage", "name": "RetrieveSportsbookPage/RetrieveSportsbookPage",
            "body": {"urlPart": f"fussball/{url_part}", "pageScope": 1}, "requestId": url_part,
        }])
        self.pump()
        if not self.pages:
            return 0
        total = 0
        for grid in _nodes(self.pages[-1].get("viewNode"), "SportsGridViewNode", []):
            total += int(grid.get("eventCount") or 0)
            groups = [c["id"] for c in _nodes(grid, "CategoryViewNode", [])]
            self.send([{
                "type": "UpdateSportsbookPage", "name": f"{url_part}/UpdateSportsbookPage",
                "body": {
                    "sportsGridViewNodeId": grid["id"],
                    "pageSubscriptionName": "RetrieveSportsbookPage/RetrieveSportsbookPage",
                    "commandProperties": [
                        {"type": 0, "value": json.dumps(groups)},
                        {"type": 1, "value": json.dumps(MARKET_CONFIGS)},
                    ],
                },
                "requestId": url_part,
            }])
        self.pump()
        return total

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def _event_odds(ent: Dict[str, Dict[str, Dict[str, Any]]], event: Dict[str, Any]) -> Dict[str, float]:
    markets = ent.get("Market", {})
    selections = ent.get("Selection", {})
    out: Dict[str, float] = {}
    for murn in event.get("markets") or []:
        m = markets.get(murn)
        if not m or (m.get("properties") or {}).get("mode") not in (None, "prematch"):
            continue
        sels = [selections.get(u) for u in m.get("selections") or []]
        if m.get("type") == MT_1X2:
            for s in sels:
                if s and s.get("odds") and s.get("type") in SEL_1X2:
                    out[f"odd_{SEL_1X2[s['type']]}"] = float(s["odds"])
        elif m.get("type") == MT_TOTAL:
            total = (m.get("properties") or {}).get("total")
            if total not in TOTAL_LINES:
                continue
            line = str(total).replace(".", "")
            for s in sels:
                if s and s.get("odds") and s.get("type") in SEL_TOTAL:
                    out[f"odd_{SEL_TOTAL[s['type']]}_{line}"] = float(s["odds"])
    return out


def _collect(ent: Dict[str, Dict[str, Dict[str, Any]]], now: datetime, until: datetime) -> Dict[str, Dict[str, Any]]:
    cats = ent.get("Category", {})
    out: Dict[str, Dict[str, Any]] = {}
    for e in ent.get("Event", {}).values():
        start = _parse_dt(e.get("startTime"))
        if start is None or not (now < start <= until):
            continue
        name = str(e.get("name") or "").replace("&apos;", "'")
        if " : " not in name:
            continue
        odds = _event_odds(ent, e)
        if not odds:
            continue
        cat = cats.get((e.get("categories") or [None])[0]) or {}
        names = [name] + [str(v) for v in (e.get("translations") or {}).values() if " : " in str(v)]
        out[e.get("urn")] = {
            "urn": e.get("urn"),
            "name": name,
            "names": names,
            "league": str(cat.get("name") or "").replace("&apos;", "'"),
            "start": start,
            "odds": odds,
        }
    return out


def fetch_events(
    pages: Iterable[str], horizon_hours: int = 30, log: Callable[[str], None] = print
) -> List[Dict[str, Any]]:
    """Spiele der Länderseiten mit Anstoß in den nächsten `horizon_hours` Stunden, mit Quoten.

    Weiter voraus lohnt nicht: upcoming_games enthält nur die Spiele des Tages (Today-Sync).
    """
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=horizon_hours)
    events: Dict[str, Dict[str, Any]] = {}
    sess = _Session()
    try:
        sess.connect()
        for page in pages:
            try:
                sess.load_page(page)
            except Exception as e:
                log(f"swisslos: Seite {page} fehlgeschlagen: {e}")
                continue
            # Beim nächsten Seitenwechsel entfernt der Server die Spiele dieser Seite wieder
            events.update(_collect(sess.entities, now, until))
    finally:
        sess.close()
    return list(events.values())


# ── Zuordnung ──────────────────────────────────────────────────────────

# Swisslos nutzt teils englische Ortsnamen, unsere Daten die lokalen
_ALIASES = {
    "cologne": "koln", "munich": "munchen", "nuremberg": "nurnberg", "zurich": "zurich",
    "geneva": "geneve", "lisbon": "lisboa", "turin": "torino", "milan": "milano",
    "rome": "roma", "naples": "napoli", "seville": "sevilla", "prague": "praha",
    "warsaw": "warszawa", "bucharest": "bucuresti", "belgrade": "beograd", "athens": "athina",
}
_NOISE = {
    "fc", "sc", "cf", "ac", "afc", "sv", "vfl", "vfb", "fk", "sk", "cd", "ud", "ca", "club", "de",
    "the", "and", "women", "w", "u19", "u21", "u23", "calcio", "bk", "if", "ff", "aif", "kv", "krc",
    "rc", "rcd", "sd", "ssc", "as", "us", "ss", "cs", "fsv", "tsg", "spvgg", "bsc", "hsc", "osc",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [_ALIASES.get(t, t) for t in s.split()]
    toks = [t for t in toks if t not in _NOISE and not t.isdigit()]
    return " ".join(toks)


def _sim(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 1.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return max(ratio, overlap)


def _pair_score(sl_names: List[str], home: str, away: str) -> float:
    best = 0.0
    for n in sl_names:
        h, _, a = n.partition(" : ")
        sh, sa = _sim(h, home), _sim(a, away)
        if min(sh, sa) < 0.35:
            continue
        best = max(best, (sh + sa) / 2)
    return best


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _candidates(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bevorstehende Spiele der Swisslos-Ligen (nächste 10 Tage)."""
    ids = sorted(swisslos_service.swisslos_league_ids())
    if not ids:
        return []
    since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    until = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT id, date, home_team_name, away_team_name, league_id FROM upcoming_games
        WHERE league_id IN ({ph}) AND substr(date, 1, 10) BETWEEN ? AND ?
        """,
        (*ids, since, until),
    ).fetchall()
    out = []
    for r in rows:
        start = _parse_dt(r[1])
        if start is not None:
            out.append({"id": int(r[0]), "start": start, "home": r[2] or "", "away": r[3] or ""})
    return out


def match_events(
    conn: sqlite3.Connection, events: List[Dict[str, Any]], min_score: float = 0.6
) -> Tuple[List[Tuple[Dict[str, Any], int, float]], List[Tuple[Dict[str, Any], Optional[int], float]]]:
    """Swisslos-Spiel ↔ unser Spiel: gleiche Anstoßzeit (±15 Min.) + ähnliche Teamnamen.

    Nicht zugeordnet heißt: zur Anstoßzeit gibt es Kandidaten, aber kein Name passt.
    Spiele ganz ohne Kandidaten (noch nicht im Today-Sync) werden still übersprungen.
    """
    cands = _candidates(conn)
    matched, unmatched = [], []
    used: set = set()
    for ev in sorted(events, key=lambda e: e["start"]):
        best_id, best = None, 0.0
        if not any(abs((c["start"] - ev["start"]).total_seconds()) <= 15 * 60 for c in cands):
            continue
        for c in cands:
            if abs((c["start"] - ev["start"]).total_seconds()) > 15 * 60 or c["id"] in used:
                continue
            score = _pair_score(ev["names"], c["home"], c["away"])
            if score > best:
                best_id, best = c["id"], score
        if best_id is not None and best >= min_score:
            matched.append((ev, best_id, best))
            used.add(best_id)
        else:
            unmatched.append((ev, best_id, best))
    return matched, unmatched


# ── Speichern ──────────────────────────────────────────────────────────


def save(conn: sqlite3.Connection, matched, unmatched) -> Dict[str, int]:
    ensure_schema(conn)
    now = _now()
    written = 0
    for ev, game_id, score in matched:
        odds = ev["odds"]
        if not odds:
            continue
        cols = ["game_id", "event_urn", "sl_name", "sl_league", "start_time", "match_score", *ODDS_COLS,
                "first_seen_at", "updated_at"]
        vals = [game_id, ev["urn"], ev["name"], ev["league"], ev["start"].isoformat(), round(score, 3),
                *[odds.get(c) for c in ODDS_COLS], now, now]
        # Fehlende Quoten (Markt kurz gesperrt) überschreiben den letzten Stand nicht
        updates = ", ".join(
            f"{c} = COALESCE(excluded.{c}, swisslos_odds.{c})" if c in ODDS_COLS else f"{c} = excluded.{c}"
            for c in cols if c not in ("game_id", "first_seen_at")
        )
        conn.execute(
            f"INSERT INTO swisslos_odds ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
            f"ON CONFLICT(game_id) DO UPDATE SET {updates}",
            vals,
        )
        written += 1
    for ev, best_id, score in unmatched:
        conn.execute(
            """
            INSERT INTO swisslos_unmatched (event_urn, sl_name, sl_league, start_time, best_game_id, best_score, seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_urn) DO UPDATE SET best_game_id = excluded.best_game_id,
                best_score = excluded.best_score, seen_at = excluded.seen_at
            """,
            (ev["urn"], ev["name"], ev["league"], ev["start"].isoformat(), best_id, round(score, 3), now),
        )
    # Inzwischen zugeordnete Spiele nicht mehr als „nicht zugeordnet“ führen
    for ev, _, _ in matched:
        conn.execute("DELETE FROM swisslos_unmatched WHERE event_urn = ?", (ev["urn"],))
    conn.commit()
    return {"written": written, "unmatched": len(unmatched)}


def pages() -> List[str]:
    try:
        with open(swisslos_service.SWISSLOS_PATH, "r", encoding="utf-8") as f:
            return list(json.load(f).get("sporttip_pages") or [])
    except (OSError, ValueError):
        return []


def run(conn: sqlite3.Connection, log: Callable[[str], None] = print) -> Dict[str, Any]:
    """Ein kompletter Lauf: abholen, zuordnen, speichern."""
    t0 = time.time()
    events = fetch_events(pages(), log=log)
    matched, unmatched = match_events(conn, events)
    stats = save(conn, matched, unmatched)
    stats.update({"events": len(events), "matched": len(matched), "seconds": round(time.time() - t0)})
    return stats


# ── Lesen für die Verifikation ─────────────────────────────────────────

MARKET_COL = {
    "Home": "odd_home", "Draw": "odd_draw", "Away": "odd_away",
    "Over 2.5": "odd_over_25", "Under 2.5": "odd_under_25",
    "Over 3.5": "odd_over_35", "Under 3.5": "odd_under_35",
    "Over 4.5": "odd_over_45", "Under 4.5": "odd_under_45",
}


def odds_for_games(conn: sqlite3.Connection, game_ids: Iterable[Any]) -> Dict[int, Dict[str, Any]]:
    ensure_schema(conn)
    ids = sorted({int(g) for g in game_ids if g is not None})
    out: Dict[int, Dict[str, Any]] = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        ph = ",".join("?" * len(chunk))
        cur = conn.execute(f"SELECT * FROM swisslos_odds WHERE game_id IN ({ph})", chunk)
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            out[int(rec["game_id"])] = rec
    return out
