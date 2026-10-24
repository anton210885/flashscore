"""Verifikation: Strategie-Treffer vor dem Spiel festhalten und nach dem Spiel abrechnen.

Ab dem ersten Scan wird jedes bevorstehende Spiel, das zu einer gespeicherten Strategie
passt, mit Quote und Strategie-Einstellungen gespeichert (wie eine platzierte Wette).
Passt es später nicht mehr (z. B. Quote verschoben), bleibt es drin — still_matches = 0.
Nach dem Spiel kommt das Endergebnis aus `games`; abgerechnet wird mit der Quote,
die die Strategie verwendet (odds_type opening/closing).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import strategy_service as strat
from services import swisslos_odds_service
from services import swisslos_service as swisslos

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS verification_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT,
    filters_json TEXT,
    game_id INTEGER NOT NULL,
    market TEXT NOT NULL,
    date TEXT,
    country TEXT,
    league TEXT,
    home TEXT,
    away TEXT,
    odds_type TEXT,
    odds_first REAL,
    odds_opening REAL,
    odds_closing REAL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    still_matches INTEGER NOT NULL DEFAULT 1,
    home_score INTEGER,
    away_score INTEGER,
    won INTEGER,
    profit REAL,
    settled_at TEXT,
    UNIQUE(strategy_id, game_id, market)
);
CREATE INDEX IF NOT EXISTS idx_verification_open ON verification_bets(settled_at, game_id);
CREATE TABLE IF NOT EXISTS verification_strategy_stats (
    strategy_id TEXT PRIMARY KEY,
    strategy_name TEXT,
    backtest_n INTEGER,
    backtest_roi REAL,
    updated_at TEXT
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(verification_strategy_stats)")}
    if "history_json" not in cols:
        conn.execute("ALTER TABLE verification_strategy_stats ADD COLUMN history_json TEXT")
    conn.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _not_started(date: Any) -> bool:
    try:
        ko = datetime.fromisoformat(str(date))
    except (TypeError, ValueError):
        return False
    if ko.tzinfo is None:
        return ko >= datetime.now()
    return ko >= datetime.now(timezone.utc)


def record_upcoming(conn: sqlite3.Connection, presets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bevorstehende Treffer aller Strategien eintragen bzw. Quoten aktualisieren."""
    from services import web_strategy_service as web_strat

    ensure_schema(conn)
    stats: Dict[str, Any] = {"strategies": 0, "new": 0, "updated": 0, "no_longer_matching": 0, "errors": []}
    now = _now()
    for p in presets or []:
        sid, name, filters = p.get("id"), p.get("name"), p.get("filters") or {}
        if not sid:
            continue
        try:
            a = web_strat.analyze(filters, limit_results=200)
        except Exception as e:
            stats["errors"].append(f"{name}: {e}")
            continue
        if not a.get("ok"):
            stats["errors"].append(f"{name}: {a.get('error')}")
            continue
        stats["strategies"] += 1
        m = a.get("metrics") or {}
        conn.execute(
            """
            INSERT INTO verification_strategy_stats
                (strategy_id, strategy_name, backtest_n, backtest_roi, history_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_id) DO UPDATE SET
                strategy_name = excluded.strategy_name,
                backtest_n = excluded.backtest_n,
                backtest_roi = excluded.backtest_roi,
                history_json = excluded.history_json,
                updated_at = excluded.updated_at
            """,
            (
                sid, name, int(m.get("n") or 0), m.get("roi_pct"),
                json.dumps(web_strat.history_stats(m)), now,
            ),
        )
        up = a.get("upcoming") or {}
        if up.get("skipped"):
            continue
        odds_type = str(filters.get("odds_type") or "closing")
        filters_json = json.dumps(filters, ensure_ascii=False, sort_keys=True)
        seen = set()
        for x in up.get("matches") or []:
            if not _not_started(x.get("date")) or x.get("game_id") is None:
                continue
            key = (int(x["game_id"]), str(x.get("market")))
            seen.add(key)
            known = conn.execute(
                "SELECT 1 FROM verification_bets WHERE strategy_id = ? AND game_id = ? AND market = ?",
                (sid, key[0], key[1]),
            ).fetchone()
            cur = conn.execute(
                """
                INSERT INTO verification_bets (
                    strategy_id, strategy_name, filters_json, game_id, market, date, country,
                    league, home, away, odds_type, odds_first, odds_opening, odds_closing,
                    first_seen_at, last_seen_at, still_matches
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(strategy_id, game_id, market) DO UPDATE SET
                    date = excluded.date,
                    odds_opening = COALESCE(excluded.odds_opening, verification_bets.odds_opening),
                    odds_closing = COALESCE(excluded.odds_closing, verification_bets.odds_closing),
                    last_seen_at = excluded.last_seen_at,
                    still_matches = 1
                WHERE verification_bets.settled_at IS NULL
                """,
                (
                    sid, name, filters_json, key[0], key[1], x.get("date"), x.get("country"),
                    x.get("league"), x.get("home"), x.get("away"), odds_type, x.get("odds"),
                    x.get("odds_opening"), x.get("odds_closing"), now, now,
                ),
            )
            if cur.rowcount:
                stats["updated" if known else "new"] += 1
        # Noch offene, nicht angepfiffene Einträge, die diesmal nicht mehr passen: behalten, markieren
        for gid, market, date in conn.execute(
            """
            SELECT game_id, market, date FROM verification_bets
            WHERE strategy_id = ? AND settled_at IS NULL AND still_matches = 1
            """,
            (sid,),
        ).fetchall():
            if (int(gid), str(market)) not in seen and _not_started(date):
                conn.execute(
                    "UPDATE verification_bets SET still_matches = 0 WHERE strategy_id = ? AND game_id = ? AND market = ?",
                    (sid, gid, market),
                )
                stats["no_longer_matching"] += 1
        conn.commit()
    return stats


def settle(conn: sqlite3.Connection) -> Dict[str, int]:
    """Offene Einträge mit Endergebnis aus `games` abrechnen."""
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT v.id, v.market, v.odds_type, v.odds_first, v.odds_opening, v.odds_closing,
               g.home_ft_result, g.away_ft_result
        FROM verification_bets v
        JOIN games g ON g.id = v.game_id
        WHERE v.settled_at IS NULL
          AND g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
        """
    ).fetchall()
    settled = 0
    now = _now()
    for vid, market, odds_type, o_first, o_open, o_close, h, a in rows:
        odds = (o_open if odds_type == "opening" else o_close) or o_first
        profit = strat.settle_market(market, h, a, odds)
        if profit is None:
            continue
        conn.execute(
            """
            UPDATE verification_bets
            SET home_score = ?, away_score = ?, won = ?, profit = ?, settled_at = ?
            WHERE id = ?
            """,
            (int(h), int(a), 1 if profit > 0 else 0, float(profit), now, vid),
        )
        settled += 1
    conn.commit()
    return {"settled": settled, "open_with_result": len(rows)}


def _live_info(conn: sqlite3.Connection, bet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Stand eines offenen Spiels: läuft (Minute, Zwischenstand) oder beendet, aber noch nicht abgerechnet.

    Quelle: upcoming_games (Sync alle 3 Min.) bzw. games nach Spielende — keine API-Abfrage.
    """
    from services.match_status import FINISHED_STATUS_CODES, LIVE_STATUS_CODES

    gid = bet["game_id"]
    g = conn.execute(
        "SELECT home_ft_result, away_ft_result FROM games WHERE id = ?", (gid,)
    ).fetchone()
    if g and g[0] is not None and g[1] is not None:
        h, a, phase, minute, label = int(g[0]), int(g[1]), "finished", None, "beendet"
    else:
        u = conn.execute(
            """
            SELECT status, status_name, elapsed, home_result, away_result
            FROM upcoming_games WHERE id = ?
            """,
            (gid,),
        ).fetchone()
        if not u:
            return None
        status, status_name, elapsed, h, a = u
        try:
            code = int(status) if status is not None else None
        except (TypeError, ValueError):
            code = None
        # Statuscode allein ist unzuverlässig (Code 2 kommt auch als „Not Started“)
        if _not_started(bet.get("date")) or "not started" in str(status_name or "").lower():
            return {"phase": "scheduled", "label": status_name or None}
        if code in FINISHED_STATUS_CODES:
            phase = "finished"
        elif code in LIVE_STATUS_CODES:
            phase = "live"
        else:
            return {"phase": "scheduled", "label": status_name or None}
        minute, label = elapsed, status_name
        if h is None or a is None:
            return {"phase": phase, "label": label, "minute": minute}
    odds = bet.get("odds_used") or 2.0
    profit = strat.settle_market(bet["market"], h, a, odds)
    return {
        "phase": phase,
        "label": label,
        "minute": minute,
        "home": h,
        "away": a,
        "winning": None if profit is None else profit > 0,
    }


def _forward_stats(done: List[Dict[str, Any]]) -> Dict[str, Any]:
    st = strat.compute_streaks(done)
    return {
        "losing_streak": st["current_losing_streak"],
        "winning_streak": st["current_winning_streak"],
        "max_losing_streak": st["max_losing_streak"],
        "max_winning_streak": st["max_winning_streak"],
        "median_losing_streak": st["median_losing_streak"],
        "median_winning_streak": st["median_winning_streak"],
        "n_losing_streaks": st["n_losing_streaks"],
        "n_winning_streaks": st["n_winning_streaks"],
    }


def report(
    conn: sqlite3.Connection,
    strategy_id: Optional[str] = None,
    presets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Alle Einträge + Zusammenfassung pro Strategie.

    Mit `presets` stehen auch gespeicherte Strategien ohne Treffer in der Zusammenfassung
    (0 Wetten) — sonst taucht eine neue Strategie erst nach ihrem ersten Treffer auf.
    """
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    where, params = ("WHERE strategy_id = ?", [strategy_id]) if strategy_id else ("", [])
    bets = [
        {k: r[k] for k in r.keys() if k != "filters_json"}
        for r in conn.execute(f"SELECT * FROM verification_bets {where} ORDER BY date ASC, strategy_name ASC", params)
    ]
    league_of = swisslos.league_ids_for_games(conn, (b["game_id"] for b in bets))
    sl_odds = swisslos_odds_service.odds_for_games(conn, (b["game_id"] for b in bets))
    for b in bets:
        b["swisslos"] = swisslos.is_swisslos(league_of.get(int(b["game_id"])))
        # Letzte Swisslos-Quote vor Anpfiff (Prototyp) und Profit, wenn dort gewettet
        col = swisslos_odds_service.MARKET_COL.get(b["market"])
        b["odds_swisslos"] = (sl_odds.get(int(b["game_id"])) or {}).get(col) if col else None
        b["profit_swisslos"] = (
            None if b["settled_at"] is None or not b["odds_swisslos"]
            else (b["odds_swisslos"] - 1.0 if b["won"] == 1 else -1.0)
        )
        b["odds_used"] = (
            (b["odds_opening"] if b["odds_type"] == "opening" else b["odds_closing"]) or b["odds_first"]
        )
        b["status"] = "offen" if b["settled_at"] is None else ("gewonnen" if b["won"] == 1 else "verloren")
        b["live"] = _live_info(conn, b) if b["settled_at"] is None else None
    backtest = {
        r["strategy_id"]: dict(r) for r in conn.execute("SELECT * FROM verification_strategy_stats")
    }
    by_strategy: Dict[str, List[Dict[str, Any]]] = {}
    for b in bets:
        by_strategy.setdefault(b["strategy_id"], []).append(b)
    names = {sid: items[-1]["strategy_name"] for sid, items in by_strategy.items()}
    for p in presets or []:
        sid = p.get("id")
        if sid and sid not in by_strategy and (not strategy_id or sid == strategy_id):
            by_strategy[sid] = []
            names[sid] = p.get("name")
    summary = []
    for sid, items in by_strategy.items():
        done = [b for b in items if b["settled_at"] is not None]
        wins = sum(1 for b in done if b["won"] == 1)
        profit = sum(float(b["profit"] or 0) for b in done)
        bt = backtest.get(sid) or {}
        try:
            history = json.loads(bt.get("history_json") or "null")
        except ValueError:
            history = None
        summary.append(
            {
                "strategy_id": sid,
                "strategy": names[sid],
                "bets": len(items),
                "open": len(items) - len(done),
                "settled": len(done),
                "won": wins,
                "lost": len(done) - wins,
                "win_rate": (wins / len(done) * 100.0) if done else None,
                "profit": profit,
                "roi_pct": (profit / len(done) * 100.0) if done else None,
                "backtest_n": bt.get("backtest_n"),
                "backtest_roi": bt.get("backtest_roi"),
                "backtest": history,
                **_forward_stats(done),
            }
        )
    summary.sort(key=lambda s: str(s["strategy"] or ""))
    return {"ok": True, "bets": bets, "summary": summary}
