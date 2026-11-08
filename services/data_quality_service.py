"""Datenqualität: automatische Prüfungen auf Lücken, Unstimmigkeiten und Look-ahead.

Jede Prüfung liefert {key, group, title, level (ok|warn|error|info), count, total, detail, examples}.
Ein Lauf dauert je nach DB 10–60 s und läuft darum im Hintergrund; das letzte Ergebnis liegt in
logs/data_quality.json und wird sofort angezeigt (Web: DB Statistik → Datenqualität).
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(ROOT, "data", "flashscore.db")
RESULT_PATH = os.path.join(ROOT, "logs", "data_quality.json")

FINISHED = (7, 8, 9, 10)  # wie services/match_status.py: Penalty, Finished, nach Verlängerung/Elfmetern
EXAMPLES = 8

_lock = threading.Lock()
_running = {"active": False, "started_at": None}


def _connect() -> sqlite3.Connection:
    from database import connect

    conn = connect(DB_PATH, foreign_keys=False)
    conn.execute("PRAGMA query_only = 1")
    return conn


def _utc(days: float = 0, hours: float = 0) -> str:
    """Zeitgrenze im Format von games.date (UTC, ISO mit +00:00)."""
    t = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _scope(alias: str = "g") -> str:
    """Lücken-Prüfungen nur für die beobachteten Ligen (Tab Ligen); Kleinligen ohne Pinnacle-Angebot verzerren sonst."""
    from services.league_scope import active_league_ids

    ids = active_league_ids()
    return f" AND {alias}.league_id IN ({','.join(str(int(i)) for i in sorted(ids))})" if ids else ""


def _level(count: int, total: int, warn_pct: float, error_pct: float) -> str:
    if not count:
        return "ok"
    pct = 100.0 * count / total if total else 100.0
    return "error" if pct >= error_pct else "warn" if pct >= warn_pct else "info"


def _game_examples(conn: sqlite3.Connection, ids: List[int], extra: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""SELECT id, date, country_name, league_name, home_team_name, away_team_name,
                   home_ft_result, away_ft_result, status_name
            FROM games WHERE id IN ({ph}) ORDER BY date DESC""",
        ids,
    ).fetchall()
    out = []
    for r in rows:
        score = f"{r[6]}:{r[7]}" if r[6] is not None else ""
        out.append({
            "game_id": r[0],
            "date": r[1],
            "league": f"{r[2] or ''} · {r[3] or ''}".strip(" ·"),
            "match": f"{r[4]} – {r[5]}",
            "info": " · ".join(x for x in (score, r[8], (extra or {}).get(r[0], "")) if x),
        })
    return out


def _check(key: str, group: str, title: str, detail: str, count: int, total: int,
           level: str, examples: Optional[List[Dict[str, Any]]] = None, **extra) -> Dict[str, Any]:
    return {"key": key, "group": group, "title": title, "detail": detail, "count": int(count),
            "total": int(total), "level": level, "examples": examples or [], **extra}


# --- Look-ahead -----------------------------------------------------------------------------

def check_glicko_leak(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Glicko nach Anpfiff geholt darf nicht besser vorhersagen als Pinnacle (sonst steckt das Ergebnis drin)."""
    rows = conn.execute(
        """
        SELECT g.date, g.home_ft_result > g.away_ft_result, gl.home_win_probability, gl.created_at,
               MAX(CASE WHEN o.name='Home' THEN o.value END),
               MAX(CASE WHEN o.name='Draw' THEN o.value END),
               MAX(CASE WHEN o.name='Away' THEN o.value END)
        FROM games g
        JOIN game_glicko gl ON gl.game_id = g.id
        JOIN game_odds o ON o.game_id = g.id AND o.market_id = 1
        WHERE g.status IN (7,8,9,10) AND g.date >= ? AND gl.home_win_probability IS NOT NULL
        GROUP BY g.id
        """,
        (_utc(days=730),),
    ).fetchall()
    buckets = {"vor": [0, 0.0, 0.0], "nach": [0, 0.0, 0.0]}  # n, brier_glicko, brier_pinnacle
    for date, y, glp, created, oh, od, oa in rows:
        if not (oh and od and oa) or min(oh, od, oa) <= 1:
            continue
        g = glp / 100.0 if glp > 1 else glp
        s = 1 / oh + 1 / od + 1 / oa
        p = (1 / oh) / s
        b = buckets["vor" if (created or "")[:19] < (date or "")[:19] else "nach"]
        b[0] += 1
        b[1] += (g - y) ** 2
        b[2] += (p - y) ** 2
    stats = {k: {"n": v[0], "brier_glicko": round(v[1] / v[0], 4) if v[0] else None,
                 "brier_pinnacle": round(v[2] / v[0], 4) if v[0] else None} for k, v in buckets.items()}
    after = stats["nach"]
    gap = (after["brier_pinnacle"] - after["brier_glicko"]) if after["n"] else 0
    # Pinnacle-Closing ist kaum zu schlagen: deutlich besseres Glicko = Ergebnis sickert ein
    level = "error" if after["n"] >= 500 and gap > 0.005 else "ok"
    detail = (
        f"Brier-Score Heimsieg (kleiner = besser). Vor Anpfiff geholt: Glicko {stats['vor']['brier_glicko']} "
        f"vs. Pinnacle {stats['vor']['brier_pinnacle']} (n={stats['vor']['n']}). Nach Anpfiff geholt: Glicko "
        f"{after['brier_glicko']} vs. Pinnacle {after['brier_pinnacle']} (n={after['n']}). "
        + ("Glicko ist nach Anpfiff deutlich besser als Pinnacle — Verdacht auf Look-ahead!"
           if level == "error" else "Kein Hinweis auf Look-ahead.")
    )
    return _check("glicko_leak", "Look-ahead", "Glicko enthält kein Ergebnis", detail,
                  1 if level == "error" else 0, after["n"], level, stats=stats)


def check_form2_order(conn: sqlite3.Connection, sample: int = 300) -> Dict[str, Any]:
    """Stichprobe: Anzahl Spiele in xG Saison (home_n) = frühere Spiele des Teams mit xG in derselben Saison."""
    ids = [r[0] for r in conn.execute(
        """SELECT f.game_id FROM game_form2 f JOIN games g ON g.id = f.game_id
           WHERE g.status IN (7,8,9,10) AND g.date >= ? AND f.home_n IS NOT NULL""",
        (_utc(days=400),),
    )]
    random.seed(42)
    picked = random.sample(ids, min(sample, len(ids)))
    bad: Dict[int, str] = {}
    for gid in picked:
        row = conn.execute(
            """SELECT g.league_id, g.season_year, g.home_team_id, g.date, f.home_n
               FROM games g JOIN game_form2 f ON f.game_id = g.id WHERE g.id = ?""",
            (gid,),
        ).fetchone()
        if not row:
            continue
        lid, yr, tid, date, home_n = row
        expected = conn.execute(
            """SELECT COUNT(*) FROM games
               WHERE league_id = ? AND season_year = ? AND (home_team_id = ? OR away_team_id = ?)
                 AND date < ? AND home_ft_result IS NOT NULL
                 AND calculated_xg_home IS NOT NULL AND calculated_xg_away IS NOT NULL""",
            (lid, yr, tid, tid, date),
        ).fetchone()[0]
        if int(home_n or 0) > expected:  # mehr Spiele als vorher möglich = aktuelles/späteres Spiel drin
            bad[gid] = f"home_n={home_n}, möglich={expected}"
    return _check(
        "form2_order", "Look-ahead", "xG Saison nutzt nur frühere Spiele",
        f"Stichprobe von {len(picked)} beendeten Spielen: Zählt „xG Saison“ mehr Heimteam-Spiele, als vor dem "
        "Anpfiff gespielt waren, steckt das Spiel selbst oder ein späteres mit drin.",
        len(bad), len(picked), "error" if bad else "ok",
        _game_examples(conn, list(bad)[:EXAMPLES], bad),
    )


# --- Quoten ---------------------------------------------------------------------------------

def _odds_1x2(conn: sqlite3.Connection, since: str) -> List[tuple]:
    return conn.execute(
        """
        SELECT o.game_id,
               MAX(CASE WHEN o.name='Home' THEN o.value END), MAX(CASE WHEN o.name='Draw' THEN o.value END),
               MAX(CASE WHEN o.name='Away' THEN o.value END),
               MAX(CASE WHEN o.name='Home' THEN o.opening_value END), MAX(CASE WHEN o.name='Draw' THEN o.opening_value END),
               MAX(CASE WHEN o.name='Away' THEN o.opening_value END)
        FROM games g JOIN game_odds o ON o.game_id = g.id AND o.market_id = 1
        WHERE g.status IN (7,8,9,10) AND g.date >= ?
        GROUP BY o.game_id
        """,
        (since,),
    ).fetchall()


def check_odds(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = _odds_1x2(conn, _utc(days=365))
    margin_bad: Dict[int, str] = {}
    range_bad: Dict[int, str] = {}
    same: List[int] = []
    for gid, h, d, a, oh, od, oa in rows:
        closing = (h, d, a)
        if any(v is None for v in closing):
            continue
        if min(closing) < 1.01 or max(closing) > 100:
            range_bad[gid] = f"Quoten {h}/{d}/{a}"
            continue
        m = 1 / h + 1 / d + 1 / a
        if not 1.0 <= m <= 1.15:
            margin_bad[gid] = f"Marge {round((m - 1) * 100, 1)}% ({h}/{d}/{a})"
        if oh and (h, d, a) == (oh, od, oa):
            same.append(gid)
    n = len(rows)
    return [
        _check("odds_margin", "Quoten", "Buchmacher-Marge plausibel (0–15 %)",
               "1X2-Closing der letzten 12 Monate. Top-Ligen liegen bei 2–5 %, Kleinligen bis ~13 %; negative "
               "oder höhere Margen deuten auf vertauschte, veraltete oder falsch zugeordnete Quoten.",
               len(margin_bad), n, _level(len(margin_bad), n, 0.1, 1.0),
               _game_examples(conn, list(margin_bad)[:EXAMPLES], margin_bad)),
        _check("odds_range", "Quoten", "Quoten im gültigen Bereich (1,01–100)",
               "1X2-Closing der letzten 12 Monate. Eine Quote von 1,0 heisst meist: nach Spielende erfasst "
               "(Ergebnis stand fest) — so ein Spiel verfälscht den Backtest.", len(range_bad), n, _level(len(range_bad), n, 0.05, 0.5),
               _game_examples(conn, list(range_bad)[:EXAMPLES], range_bad)),
        _check("odds_same", "Quoten", "Closing weicht vom Opening ab",
               "Sind Opening und Closing bei allen drei Ausgängen identisch, wurde das Closing vermutlich nie "
               "aufgefrischt (betrifft Strategien mit Closing-Quote).",
               len(same), n, _level(len(same), n, 2.0, 10.0), _game_examples(conn, same[:EXAMPLES])),
    ]


def check_missing_closing(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Beendete Spiele (letzte 30 Tage, ohne heute) in Ligen, die sonst Pinnacle-Quoten haben."""
    rows = conn.execute(
        """
        SELECT g.id FROM games g
        WHERE g.status IN (7,8,9,10) AND g.date >= ? AND g.date < ?
          AND NOT EXISTS (SELECT 1 FROM game_odds o WHERE o.game_id = g.id AND o.market_id = 1)
          AND EXISTS (SELECT 1 FROM games s JOIN game_odds so ON so.game_id = s.id AND so.market_id = 1
                      WHERE s.league_id = g.league_id AND s.season_year = g.season_year)
        """ + _scope() + " ORDER BY g.date DESC",
        (_utc(days=30), _utc(hours=6)),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM games g WHERE status IN (7,8,9,10) AND date >= ? AND date < ?" + _scope(),
        (_utc(days=30), _utc(hours=6)),
    ).fetchone()[0]
    ids = [r[0] for r in rows]
    return _check("odds_missing", "Quoten", "Beendete Spiele haben Pinnacle-Quoten",
                  "Letzte 30 Tage, beobachtete Ligen (Tab Ligen), nur Saisons, in denen es sonst Pinnacle-Quoten gibt.",
                  len(ids), total, _level(len(ids), total, 2.0, 10.0), _game_examples(conn, ids[:EXAMPLES]))


# --- Lücken ---------------------------------------------------------------------------------

def check_missing_xg(conn: sqlite3.Connection) -> Dict[str, Any]:
    since = _utc(days=365)
    ids = [r[0] for r in conn.execute(
        """
        SELECT g.id FROM games g
        WHERE g.status IN (7,8,9,10) AND g.date >= ? AND g.date < ?
          AND (g.calculated_xg_home IS NULL OR g.calculated_xg_away IS NULL)
          AND EXISTS (SELECT 1 FROM games s WHERE s.league_id = g.league_id AND s.season_year = g.season_year
                      AND s.calculated_xg_home IS NOT NULL)
        """ + _scope() + " ORDER BY g.date DESC",
        (since, _utc(hours=6)),
    )]
    total = conn.execute("SELECT COUNT(*) FROM games g WHERE status IN (7,8,9,10) AND date >= ?" + _scope(), (since,)).fetchone()[0]
    return _check("xg_missing", "Lücken", "Beendete Spiele haben Match-xG",
                  "Letzte 12 Monate, beobachtete Ligen, nur Saisons mit xG. Fehlendes xG verfälscht „xG Saison“, Power und Tempo.",
                  len(ids), total, _level(len(ids), total, 2.0, 10.0), _game_examples(conn, ids[:EXAMPLES]))


def check_missing_glicko(conn: sqlite3.Connection) -> Dict[str, Any]:
    since = _utc(days=365)
    ids = [r[0] for r in conn.execute(
        """
        SELECT g.id FROM games g
        WHERE g.status IN (7,8,9,10) AND g.date >= ? AND g.date < ?
          AND NOT EXISTS (SELECT 1 FROM game_glicko gl WHERE gl.game_id = g.id AND gl.home_rating IS NOT NULL)
          AND EXISTS (SELECT 1 FROM games s JOIN game_glicko sg ON sg.game_id = s.id
                      WHERE s.league_id = g.league_id AND s.season_year = g.season_year)
        """ + _scope() + " ORDER BY g.date DESC",
        (since, _utc(hours=6)),
    )]
    total = conn.execute("SELECT COUNT(*) FROM games g WHERE status IN (7,8,9,10) AND date >= ?" + _scope(), (since,)).fetchone()[0]
    return _check("glicko_missing", "Lücken", "Beendete Spiele haben Glicko",
                  "Letzte 12 Monate, beobachtete Ligen, nur Saisons mit Glicko.",
                  len(ids), total, _level(len(ids), total, 2.0, 10.0), _game_examples(conn, ids[:EXAMPLES]))


def check_missing_form2(conn: sqlite3.Connection) -> Dict[str, Any]:
    since = _utc(days=365)
    ids = [r[0] for r in conn.execute(
        """
        SELECT g.id FROM games g
        WHERE g.status IN (7,8,9,10) AND g.date >= ?
          AND NOT EXISTS (SELECT 1 FROM game_form2 f WHERE f.game_id = g.id)
          AND EXISTS (SELECT 1 FROM games s JOIN game_form2 sf ON sf.game_id = s.id
                      WHERE s.league_id = g.league_id AND s.season_year = g.season_year)
        """ + _scope() + " ORDER BY g.date DESC",
        (since,),
    )]
    total = conn.execute("SELECT COUNT(*) FROM games g WHERE status IN (7,8,9,10) AND date >= ?" + _scope(), (since,)).fetchone()[0]
    return _check("form2_missing", "Lücken", "Beendete Spiele haben xG Saison / Power / Tempo",
                  "Letzte 12 Monate, beobachtete Ligen, nur Saisons, für die Form2 berechnet wird.",
                  len(ids), total, _level(len(ids), total, 1.0, 5.0), _game_examples(conn, ids[:EXAMPLES]))


# --- Konsistenz -----------------------------------------------------------------------------

def check_status(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    live = [r[0] for r in conn.execute(
        "SELECT id FROM games WHERE status NOT IN (7,8,9,10) AND date < ? ORDER BY date DESC", (_utc(hours=4),)
    )]
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    stale = conn.execute(
        """SELECT id, date, country_name, league_name, home_team_name, away_team_name, status_name
           FROM upcoming_games WHERE status IN (1, 2) AND date < ? ORDER BY date DESC""",
        (_utc(hours=4),),
    ).fetchall()
    up_total = conn.execute("SELECT COUNT(*) FROM upcoming_games").fetchone()[0]
    stale_ex = [{"game_id": r[0], "date": r[1], "league": f"{r[2] or ''} · {r[3] or ''}".strip(" ·"),
                 "match": f"{r[4]} – {r[5]}", "info": r[6] or ""} for r in stale[:EXAMPLES]]
    return [
        _check("status_live_in_games", "Konsistenz", "Gespeicherte Spiele haben Endstatus",
               "Spiele im Ergebnis-Bestand, die seit über 4 Stunden noch als „live“ (1. Halbzeit, Pause, "
               "Elfmeterschiessen …) markiert sind. Das gespeicherte Ergebnis kann ein Zwischenstand sein → "
               "falsche Abrechnung in Backtest und Verifikation.",
               len(live), total, _level(len(live), total, 0.05, 0.5), _game_examples(conn, live[:EXAMPLES])),
        _check("upcoming_stale", "Konsistenz", "Keine verwaisten bevorstehenden Spiele",
               "„Not Started“ in der Vorschau, obwohl der Anpfiff über 4 Stunden vorbei ist (nie als beendet übernommen).",
               len(stale), up_total, _level(len(stale), up_total, 2.0, 10.0), stale_ex),
    ]


def check_duplicates(conn: sqlite3.Connection) -> Dict[str, Any]:
    rows = conn.execute(
        """
        SELECT GROUP_CONCAT(id), COUNT(*) FROM games
        WHERE date >= ?
        GROUP BY home_team_id, away_team_id, substr(date, 1, 10)
        HAVING COUNT(*) > 1
        """,
        (_utc(days=1100),),
    ).fetchall()
    ids = [int(x) for r in rows for x in r[0].split(",")]
    total = conn.execute("SELECT COUNT(*) FROM games WHERE date >= ?", (_utc(days=1100),)).fetchone()[0]
    return _check("duplicates", "Konsistenz", "Keine doppelten Spiele",
                  "Gleiche Paarung am gleichen Tag mit verschiedenen IDs — zählt im Backtest doppelt.",
                  len(rows), total, _level(len(rows), total, 0.01, 0.1), _game_examples(conn, ids[:EXAMPLES]))


def check_score_sanity(conn: sqlite3.Connection) -> Dict[str, Any]:
    bad: Dict[int, str] = {}
    for gid, h, a, tg, hx, ax in conn.execute(
        """SELECT id, home_ft_result, away_ft_result, total_goals, calculated_xg_home, calculated_xg_away
           FROM games WHERE status IN (7,8,9,10) ORDER BY date DESC"""
    ):
        if h is None or a is None:
            bad[gid] = "Endstand fehlt"
        elif h < 0 or a < 0 or h + a > 15:
            bad[gid] = f"Endstand {h}:{a}"
        elif tg is not None and tg != h + a:
            bad[gid] = f"Tore gesamt {tg}, nach 90 Min. {h + a}"
        elif (hx is not None and (hx < 0 or hx > 12)) or (ax is not None and (ax < 0 or ax > 12)):
            bad[gid] = f"xG {hx}/{ax}"
    total = conn.execute("SELECT COUNT(*) FROM games WHERE status IN (7,8,9,10)").fetchone()[0]
    return _check("score_sanity", "Konsistenz", "Endstand, Tore und xG plausibel",
                  "Fehlender Endstand, mehr als 15 Tore, xG unter 0 oder über 12 — oder „Tore gesamt“ zählt die "
                  "Verlängerung mit. Strategie-Backtests und Verifikation rechnen mit dem Stand nach 90 Minuten "
                  "und sind davon nicht betroffen; falsch sind nur „Tore gesamt“/Over-Serien in der Liga-Statistik.",
                  len(bad), total, _level(len(bad), total, 0.5, 2.0),
                  _game_examples(conn, list(bad)[:EXAMPLES], bad))


# --- Swisslos & Verifikation -----------------------------------------------------------------

def check_swisslos(conn: sqlite3.Connection) -> Dict[str, Any]:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='swisslos_unmatched'").fetchone():
        return _check("swisslos_match", "Swisslos", "Swisslos-Spiele zugeordnet", "Noch keine Swisslos-Daten.",
                      0, 0, "ok")
    since = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    unmatched = conn.execute(
        """SELECT sl_name, sl_league, start_time, best_score FROM swisslos_unmatched
           WHERE seen_at >= ? ORDER BY start_time DESC""",
        (since,),
    ).fetchall()
    matched = conn.execute("SELECT COUNT(*) FROM swisslos_odds WHERE updated_at >= ?", (since,)).fetchone()[0]
    total = matched + len(unmatched)
    ex = [{"game_id": None, "date": r[2], "league": r[1] or "", "match": r[0] or "",
           "info": f"beste Übereinstimmung {round(r[3], 2)}" if r[3] is not None else "kein Kandidat"}
          for r in unmatched[:EXAMPLES]]
    return _check("swisslos_match", "Swisslos", "Swisslos-Spiele zugeordnet",
                  "Letzte 7 Tage: Swisslos-Spiele, die keinem Spiel in der DB zugeordnet werden konnten "
                  "(meist abweichende Teamnamen oder Liga fehlt). Diese fehlen in SL Tipps.",
                  len(unmatched), total, _level(len(unmatched), total, 5.0, 20.0), ex)


def check_verification(conn: sqlite3.Connection) -> Dict[str, Any]:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='verification_bets'").fetchone():
        return _check("verification_open", "Verifikation", "Wetten werden abgerechnet", "Noch keine Wetten.", 0, 0, "ok")
    rows = conn.execute(
        """SELECT game_id, date, league, home, away, strategy_name FROM verification_bets
           WHERE settled_at IS NULL AND date < ? ORDER BY date DESC""",
        (_utc(hours=6),),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM verification_bets").fetchone()[0]
    ex = [{"game_id": r[0], "date": r[1], "league": r[2] or "", "match": f"{r[3]} – {r[4]}", "info": r[5] or ""}
          for r in rows[:EXAMPLES]]
    return _check("verification_open", "Verifikation", "Wetten werden abgerechnet",
                  "Offene Verifikations-Wetten, deren Anpfiff über 6 Stunden zurückliegt "
                  "(Spiel verschoben/abgesagt oder Ergebnis nie geladen).",
                  len(rows), total, _level(len(rows), total, 1.0, 5.0), ex)


CHECKS: List[Callable[[sqlite3.Connection], Any]] = [
    check_glicko_leak, check_form2_order,
    check_odds, check_missing_closing,
    check_missing_xg, check_missing_glicko, check_missing_form2,
    check_status, check_duplicates, check_score_sanity,
    check_swisslos, check_verification,
]


def run() -> Dict[str, Any]:
    t0 = time.time()
    conn = _connect()
    checks: List[Dict[str, Any]] = []
    try:
        for fn in CHECKS:
            t = time.time()
            try:
                res = fn(conn)
                for c in res if isinstance(res, list) else [res]:
                    c["seconds"] = round(time.time() - t, 1)
                    checks.append(c)
            except Exception as e:  # eine kaputte Prüfung soll die anderen nicht verhindern
                checks.append(_check(fn.__name__, "Fehler", fn.__name__, f"Prüfung fehlgeschlagen: {e}", 0, 0, "error"))
    finally:
        conn.close()
    result = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "seconds": round(time.time() - t0, 1),
        "summary": {lvl: sum(1 for c in checks if c["level"] == lvl) for lvl in ("ok", "info", "warn", "error")},
        "checks": checks,
    }
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    tmp = RESULT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RESULT_PATH)
    return result


def _run_bg() -> None:
    try:
        run()
    finally:
        with _lock:
            _running["active"] = False


def start() -> bool:
    """Prüfung im Hintergrund starten; False, wenn schon eine läuft."""
    with _lock:
        if _running["active"]:
            return False
        _running.update(active=True, started_at=datetime.now().isoformat(timespec="seconds"))
    threading.Thread(target=_run_bg, name="data-quality", daemon=True).start()
    return True


def latest() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if os.path.exists(RESULT_PATH):
        try:
            with open(RESULT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    with _lock:
        data["running"] = _running["active"]
        data["running_since"] = _running["started_at"] if _running["active"] else None
    return data


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ROOT)
    r = run()
    print(f"{r['seconds']}s  {r['summary']}")
    for c in r["checks"]:
        print(f"[{c['level']:5}] {c['title']}: {c['count']}/{c['total']}  ({c.get('seconds')}s)")
