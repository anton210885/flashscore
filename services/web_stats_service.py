"""DB coverage + Glicko/Opening/Closing-backfill stats for the web UI."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


def get_stats(top_n: int = 12) -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"ok": False, "error": "DB missing", "db": "data/flashscore.db"}

    conn = _connect()
    try:
        games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        glicko = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
        with_xg = conn.execute(
            """
            SELECT COUNT(*) FROM game_glicko
            WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL
            """
        ).fetchone()[0]
        missing_glicko = max(0, games - glicko)

        odds_games = 0
        opening_games = 0
        if _table_exists(conn, "game_odds"):
            odds_games = conn.execute(
                "SELECT COUNT(DISTINCT game_id) FROM game_odds WHERE value IS NOT NULL"
            ).fetchone()[0]
            opening_games = conn.execute(
                """
                SELECT COUNT(DISTINCT game_id) FROM game_odds
                WHERE opening_value IS NOT NULL AND opening_value > 0
                """
            ).fetchone()[0]

        profits_games = 0
        if _table_exists(conn, "game_profits"):
            profits_games = conn.execute(
                "SELECT COUNT(DISTINCT game_id) FROM game_profits"
            ).fetchone()[0]

        # Odds-Flags einmal voraggregieren (viel schneller als EXISTS pro Zeile)
        conn.execute("DROP TABLE IF EXISTS _tmp_odds_flags")
        conn.execute(
            """
            CREATE TEMP TABLE _tmp_odds_flags AS
            SELECT
                game_id,
                MAX(CASE WHEN value IS NOT NULL THEN 1 ELSE 0 END) AS has_closing,
                MAX(CASE WHEN opening_value IS NOT NULL AND opening_value > 0 THEN 1 ELSE 0 END) AS has_opening
            FROM game_odds
            GROUP BY game_id
            """
        )

        has_leagues = _table_exists(conn, "leagues")
        league_join = (
            "LEFT JOIN leagues l ON l.league_id = g.league_id" if has_leagues else ""
        )
        league_name = (
            "COALESCE(l.league_name, CAST(g.league_id AS TEXT))"
            if has_leagues
            else "CAST(g.league_id AS TEXT)"
        )

        # —— Abdeckung pro Season / Jahr ——
        by_season: List[Dict[str, Any]] = []
        season_rows = conn.execute(
            """
            SELECT
                COALESCE(g.season_year, -1) AS season_year,
                COUNT(*) AS games,
                SUM(CASE WHEN gl.game_id IS NOT NULL THEN 1 ELSE 0 END) AS with_glicko,
                SUM(CASE WHEN gl.home_xg IS NOT NULL AND gl.away_xg IS NOT NULL THEN 1 ELSE 0 END) AS with_xg,
                SUM(COALESCE(of.has_closing, 0)) AS with_closing,
                SUM(COALESCE(of.has_opening, 0)) AS with_opening
            FROM games g
            LEFT JOIN game_glicko gl ON gl.game_id = g.id
            LEFT JOIN _tmp_odds_flags of ON of.game_id = g.id
            GROUP BY COALESCE(g.season_year, -1)
            ORDER BY season_year DESC
            """
        ).fetchall()
        for r in season_rows:
            gcount = int(r["games"])
            wg = int(r["with_glicko"] or 0)
            wx = int(r["with_xg"] or 0)
            wc = int(r["with_closing"] or 0)
            wo = int(r["with_opening"] or 0)
            yr = int(r["season_year"])
            by_season.append(
                {
                    "season_year": None if yr < 0 else yr,
                    "label": "unbekannt" if yr < 0 else str(yr),
                    "games": gcount,
                    "with_glicko": wg,
                    "with_xg": wx,
                    "with_closing": wc,
                    "with_opening": wo,
                    "glicko_pct": _pct(wg, gcount),
                    "xg_pct": _pct(wx, gcount),
                    "closing_pct": _pct(wc, gcount),
                    "opening_pct": _pct(wo, gcount),
                }
            )

        # —— Top Ligen: Glicko + Opening % ——
        top_leagues: List[Dict[str, Any]] = []
        rows = conn.execute(
            f"""
            SELECT
                g.league_id AS league_id,
                {league_name} AS league,
                COUNT(*) AS games,
                SUM(CASE WHEN gl.game_id IS NOT NULL THEN 1 ELSE 0 END) AS with_glicko,
                SUM(CASE WHEN gl.game_id IS NULL THEN 1 ELSE 0 END) AS missing_glicko,
                SUM(COALESCE(of.has_opening, 0)) AS with_opening
            FROM games g
            LEFT JOIN game_glicko gl ON gl.game_id = g.id
            LEFT JOIN _tmp_odds_flags of ON of.game_id = g.id
            {league_join}
            GROUP BY g.league_id
            ORDER BY missing_glicko DESC
            LIMIT ?
            """,
            (top_n,),
        ).fetchall()
        for r in rows:
            gcount = int(r["games"])
            wg = int(r["with_glicko"] or 0)
            wo = int(r["with_opening"] or 0)
            miss = int(r["missing_glicko"] or 0)
            top_leagues.append(
                {
                    "league_id": r["league_id"],
                    "league": r["league"],
                    "games": gcount,
                    "with_glicko": wg,
                    "missing_glicko": miss,
                    "with_opening": wo,
                    "coverage_pct": _pct(wg, gcount),
                    "opening_pct": _pct(wo, gcount),
                }
            )

        # —— Liga × Season (Top fehlendes Glicko) ——
        by_league_season: List[Dict[str, Any]] = []
        ls_rows = conn.execute(
            f"""
            SELECT
                g.league_id AS league_id,
                {league_name} AS league,
                COALESCE(g.season_year, -1) AS season_year,
                COUNT(*) AS games,
                SUM(CASE WHEN gl.game_id IS NOT NULL THEN 1 ELSE 0 END) AS with_glicko,
                SUM(CASE WHEN gl.game_id IS NULL THEN 1 ELSE 0 END) AS missing_glicko,
                SUM(COALESCE(of.has_opening, 0)) AS with_opening
            FROM games g
            LEFT JOIN game_glicko gl ON gl.game_id = g.id
            LEFT JOIN _tmp_odds_flags of ON of.game_id = g.id
            {league_join}
            GROUP BY g.league_id, COALESCE(g.season_year, -1)
            HAVING missing_glicko > 0
            ORDER BY missing_glicko DESC
            LIMIT ?
            """,
            (top_n * 2,),
        ).fetchall()
        for r in ls_rows:
            gcount = int(r["games"])
            wg = int(r["with_glicko"] or 0)
            yr = int(r["season_year"])
            by_league_season.append(
                {
                    "league_id": r["league_id"],
                    "league": r["league"],
                    "season_year": None if yr < 0 else yr,
                    "games": gcount,
                    "with_glicko": wg,
                    "missing_glicko": int(r["missing_glicko"] or 0),
                    "with_opening": int(r["with_opening"] or 0),
                    "coverage_pct": _pct(wg, gcount),
                    "opening_pct": _pct(int(r["with_opening"] or 0), gcount),
                }
            )

        db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 1)

        return {
            "ok": True,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "db": "data/flashscore.db",
            "db_size_mb": db_size_mb,
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
            "backfill": _parse_backfill_log(LOG_GLICKO, "glicko"),
            "backfill_opening": _parse_backfill_log(LOG_OPENING, "opening"),
            "backfill_closing": _parse_backfill_log(LOG_CLOSING, "closing"),
            "live_pipeline": _read_pipeline_status(),
        }
    finally:
        conn.close()
