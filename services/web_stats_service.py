"""DB coverage + Glicko/Opening/Closing-backfill stats for the web UI."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(ROOT, "data", "flashscore.db")
LOG_GLICKO = os.path.join(ROOT, "logs", "backfill_glicko.log")
LOG_OPENING = os.path.join(ROOT, "logs", "backfill_opening.log")
LOG_CLOSING = os.path.join(ROOT, "logs", "backfill_closing.log")
PIPELINE_STATUS = os.path.join(ROOT, "logs", "live_pipeline_status.json")

_PROGRESS_RE = re.compile(
    r"\[(\d+)/(\d+)\]\s+loaded=(\d+)\s+no_data=(\d+)\s+errors=(\d+)"
)


def _pct(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 2)


def _connect() -> sqlite3.Connection:
    from database import connect

    return connect(DB_PATH, foreign_keys=False)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _read_pipeline_status() -> Optional[Dict[str, Any]]:
    if not os.path.exists(PIPELINE_STATUS):
        return None
    try:
        with open(PIPELINE_STATUS, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    age_s = datetime.now().timestamp() - os.path.getmtime(PIPELINE_STATUS)
    data["status_file"] = "logs/live_pipeline_status.json"
    data["status_mtime"] = datetime.fromtimestamp(
        os.path.getmtime(PIPELINE_STATUS)
    ).isoformat(timespec="seconds")
    data["running_hint"] = bool(data.get("running")) and age_s < 120
    return data


def _parse_backfill_log(path: str, kind: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None

    started = None
    last_prog = None
    for line in lines:
        if line.startswith("Started:"):
            started = line.split("Started:", 1)[1].strip()
        m = _PROGRESS_RE.search(line)
        if m:
            done, total, loaded, no_data, errors = map(int, m.groups())
            last_prog = {
                "done": done,
                "total": total,
                "loaded": loaded,
                "no_data": no_data,
                "errors": errors,
                "pct": _pct(done, total),
            }
            # optional db_glicko= from glicko log
            dm = re.search(r"db_glicko=(\d+)", line)
            if dm:
                last_prog["db_glicko"] = int(dm.group(1))

    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")
    out: Dict[str, Any] = {
        "kind": kind,
        "log": rel,
        "log_mtime": mtime,
        "started": started,
        "running_hint": False,
    }
    if last_prog:
        out.update(last_prog)
        age_s = datetime.now().timestamp() - os.path.getmtime(path)
        out["running_hint"] = age_s < 120 and last_prog["done"] < last_prog["total"]
        remaining = max(0, last_prog["total"] - last_prog["done"])
        out["eta_min"] = round(remaining / 2.0 / 60.0, 1)
    return out


def _sum_buckets(rows: List[Dict[str, Any]], key) -> Dict[Any, Dict[str, int]]:
    out: Dict[Any, Dict[str, int]] = {}
    for r in rows:
        b = out.setdefault(
            key(r),
            {"games": 0, "with_glicko": 0, "with_xg": 0, "with_closing": 0, "with_opening": 0},
        )
        for f in b:
            b[f] += r[f]
    return out


def _db_coverage(conn: sqlite3.Connection, top_n: int) -> Dict[str, Any]:
    """Alle DB-Kennzahlen mit einem Durchlauf über game_odds und einem über games."""
    games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    glicko = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
    with_xg = conn.execute(
        """
        SELECT COUNT(*) FROM game_glicko
        WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL
        """
    ).fetchone()[0]
    missing_glicko = max(0, games - glicko)

    profits_games = 0
    if _table_exists(conn, "game_profits"):
        profits_games = conn.execute(
            "SELECT COUNT(DISTINCT game_id) FROM game_profits"
        ).fetchone()[0]

    # Odds-Flags pro Spiel — ein Scan über game_odds liefert auch die Gesamtzahlen
    conn.execute("DROP TABLE IF EXISTS _tmp_odds_flags")
    conn.execute(
        """
        CREATE TEMP TABLE _tmp_odds_flags (
            game_id INTEGER PRIMARY KEY,
            has_closing INTEGER NOT NULL,
            has_opening INTEGER NOT NULL
        )
        """
    )
    if _table_exists(conn, "game_odds"):
        conn.execute(
            """
            INSERT INTO _tmp_odds_flags (game_id, has_closing, has_opening)
            SELECT
                game_id,
                MAX(CASE WHEN value IS NOT NULL THEN 1 ELSE 0 END),
                MAX(CASE WHEN opening_value IS NOT NULL AND opening_value > 0 THEN 1 ELSE 0 END)
            FROM game_odds
            WHERE game_id IS NOT NULL
            GROUP BY game_id
            """
        )
    odds_games, opening_games = conn.execute(
        "SELECT COALESCE(SUM(has_closing), 0), COALESCE(SUM(has_opening), 0) FROM _tmp_odds_flags"
    ).fetchone()

    # Ein Aggregat auf Liga × Saison; Saison- und Liga-Sicht werden daraus summiert
    ls_rows = [
        {
            "league_id": r[0],
            "season_year": int(r[1]),
            "games": int(r[2]),
            "with_glicko": int(r[3] or 0),
            "with_xg": int(r[4] or 0),
            "with_closing": int(r[5] or 0),
            "with_opening": int(r[6] or 0),
        }
        for r in conn.execute(
            """
            SELECT
                g.league_id,
                COALESCE(g.season_year, -1),
                COUNT(*),
                SUM(CASE WHEN gl.game_id IS NOT NULL THEN 1 ELSE 0 END),
                SUM(CASE WHEN gl.home_xg IS NOT NULL AND gl.away_xg IS NOT NULL THEN 1 ELSE 0 END),
                SUM(COALESCE(of.has_closing, 0)),
                SUM(COALESCE(of.has_opening, 0))
            FROM games g
            LEFT JOIN game_glicko gl ON gl.game_id = g.id
            LEFT JOIN _tmp_odds_flags of ON of.game_id = g.id
            GROUP BY g.league_id, COALESCE(g.season_year, -1)
            """
        ).fetchall()
    ]
    conn.execute("DROP TABLE IF EXISTS _tmp_odds_flags")

    names: Dict[Any, str] = {}
    if _table_exists(conn, "leagues"):
        names = {
            r[0]: r[1]
            for r in conn.execute("SELECT league_id, league_name FROM leagues").fetchall()
            if r[1] is not None
        }

    def league_label(lid: Any) -> Optional[str]:
        return names.get(lid) or (None if lid is None else str(lid))

    # —— Abdeckung pro Season / Jahr ——
    by_season: List[Dict[str, Any]] = []
    seasons = _sum_buckets(ls_rows, lambda r: r["season_year"])
    for yr in sorted(seasons, reverse=True):
        b = seasons[yr]
        gcount = b["games"]
        by_season.append(
            {
                "season_year": None if yr < 0 else yr,
                "label": "unbekannt" if yr < 0 else str(yr),
                "games": gcount,
                "with_glicko": b["with_glicko"],
                "with_xg": b["with_xg"],
                "with_closing": b["with_closing"],
                "with_opening": b["with_opening"],
                "glicko_pct": _pct(b["with_glicko"], gcount),
                "xg_pct": _pct(b["with_xg"], gcount),
                "closing_pct": _pct(b["with_closing"], gcount),
                "opening_pct": _pct(b["with_opening"], gcount),
            }
        )

    # —— Top Ligen: Glicko + Opening % ——
    leagues = _sum_buckets(ls_rows, lambda r: r["league_id"])
    top_ids = sorted(
        leagues, key=lambda lid: leagues[lid]["games"] - leagues[lid]["with_glicko"], reverse=True
    )[:top_n]
    top_leagues: List[Dict[str, Any]] = []
    for lid in top_ids:
        b = leagues[lid]
        gcount = b["games"]
        top_leagues.append(
            {
                "league_id": lid,
                "league": league_label(lid),
                "games": gcount,
                "with_glicko": b["with_glicko"],
                "missing_glicko": gcount - b["with_glicko"],
                "with_opening": b["with_opening"],
                "coverage_pct": _pct(b["with_glicko"], gcount),
                "opening_pct": _pct(b["with_opening"], gcount),
            }
        )

    # —— Liga × Season (Top fehlendes Glicko) ——
    missing_ls = sorted(
        (r for r in ls_rows if r["games"] > r["with_glicko"]),
        key=lambda r: r["games"] - r["with_glicko"],
        reverse=True,
    )[: top_n * 2]
    by_league_season: List[Dict[str, Any]] = []
    for r in missing_ls:
        gcount = r["games"]
        yr = r["season_year"]
        by_league_season.append(
            {
                "league_id": r["league_id"],
                "league": league_label(r["league_id"]),
                "season_year": None if yr < 0 else yr,
                "games": gcount,
                "with_glicko": r["with_glicko"],
                "missing_glicko": gcount - r["with_glicko"],
                "with_opening": r["with_opening"],
                "coverage_pct": _pct(r["with_glicko"], gcount),
                "opening_pct": _pct(r["with_opening"], gcount),
            }
        )

    return {
        "coverage": {
            "games": games,
            "glicko": glicko,
            "glicko_pct": _pct(glicko, games),
            "xg": with_xg,
            "xg_pct": _pct(with_xg, games),
            "missing_glicko": missing_glicko,
            "odds_games": odds_games,
            "odds_pct": _pct(odds_games, games),
            "opening_games": opening_games,
            "opening_pct": _pct(opening_games, games),
            "profits_games": profits_games,
            "profits_pct": _pct(profits_games, games),
        },
        "by_season": by_season,
        "top_missing_glicko": top_leagues,
        "by_league_season": by_league_season,
    }


# Die Stats-Seite pollt alle 15 s; DB-Kennzahlen ändern sich langsam → kurz cachen.
# Lock: parallele Polls warten auf eine Berechnung statt jede selbst zu starten.
_COVERAGE_TTL_S = 120
_coverage_cache: Dict[int, Tuple[float, str, Dict[str, Any]]] = {}
_coverage_lock = threading.Lock()


def _cached_coverage(top_n: int) -> Tuple[str, Dict[str, Any]]:
    with _coverage_lock:
        hit = _coverage_cache.get(top_n)
        if hit and time.time() - hit[0] < _COVERAGE_TTL_S:
            return hit[1], hit[2]
        conn = _connect()
        try:
            data = _db_coverage(conn, top_n)
        finally:
            conn.close()
        computed_at = datetime.now().isoformat(timespec="seconds")
        _coverage_cache[top_n] = (time.time(), computed_at, data)
        return computed_at, data


def get_stats(top_n: int = 12) -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"ok": False, "error": "DB missing", "db": "data/flashscore.db"}

    computed_at, coverage = _cached_coverage(top_n)
    return {
        "ok": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "coverage_computed_at": computed_at,
        "db": "data/flashscore.db",
        "db_size_mb": round(os.path.getsize(DB_PATH) / (1024 * 1024), 1),
        **coverage,
        # Logs + Pipeline-Status bleiben bei jedem Poll aktuell
        "backfill": _parse_backfill_log(LOG_GLICKO, "glicko"),
        "backfill_opening": _parse_backfill_log(LOG_OPENING, "opening"),
        "backfill_closing": _parse_backfill_log(LOG_CLOSING, "closing"),
        "live_pipeline": _read_pipeline_status(),
    }
