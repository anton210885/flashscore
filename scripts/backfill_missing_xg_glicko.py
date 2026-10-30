"""Ältere Lücken einmalig nachladen: Match-xG, danach Glicko — neueste Spiele zuerst.

Die Pipeline lädt fehlende Werte nur für die letzten 3 (xG) bzw. 5 Tage (Glicko) nach.
Dieses Skript fragt ältere Spiele einmal neu ab. Jedes Spiel wird pro Teil nur einmal
versucht (Merker in fetch_attempts, Jobs backfill_xg / backfill_glicko) — abbrechen und
neu starten ist jederzeit möglich. xG wird nur für bereits beendete Spiele geholt.
Der Fortschritt steht in logs/backfill_missing_xg_glicko_status.json (Web: DB Statistik). Am Ende wird Form2 (xG Saison, Power, Tempo) für alle
Liga-Saisons neu berechnet, in denen neues xG dazukam.

  python -u scripts/backfill_missing_xg_glicko.py
  python -u scripts/backfill_missing_xg_glicko.py --only xg
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager
from services.form2_service import recompute_league_season, upsert_upcoming_for_league_season
from services.live_pipeline_service import FETCH_ATTEMPTS_SQL, LivePipelineService

STATUS_PATH = Path(__file__).resolve().parent.parent / "logs" / "backfill_missing_xg_glicko_status.json"
_status: dict = {}


def _write_status(**fields) -> None:
    """Fortschritt für die Web-Oberfläche (atomar ersetzen, damit nie halbe Dateien gelesen werden)."""
    _status.update(fields, pid=os.getpid(), updated_at=datetime.now().isoformat(timespec="seconds"))
    try:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATUS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(_status, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATUS_PATH)
    except OSError:
        pass


def _mark(conn, gid: int, job: str) -> None:
    conn.execute(
        """
        INSERT INTO fetch_attempts (game_id, job, tries, last_try, next_try) VALUES (?, ?, 1, ?, NULL)
        ON CONFLICT(game_id, job) DO UPDATE SET tries = tries + 1, last_try = excluded.last_try
        """,
        (gid, job, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def _sleep_on_error(e: Exception) -> None:
    if "429" in str(e):
        time.sleep(30)


def backfill_xg(conn, client, delay: float, limit: int = 0) -> set:
    """Match-xG für beendete Spiele ohne xG in Liga-Saisons, die sonst xG haben."""
    ids = [(int(r[0]), r[1], r[2]) for r in conn.execute(
        """
        SELECT g.id, g.league_id, g.season_year FROM games g
        WHERE (g.calculated_xg_home IS NULL OR g.calculated_xg_away IS NULL)
          AND g.home_ft_result IS NOT NULL
          AND g.date <= strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
          AND EXISTS (
            SELECT 1 FROM games s
            WHERE s.league_id = g.league_id AND s.season_year = g.season_year
              AND s.calculated_xg_home IS NOT NULL
          )
          AND NOT EXISTS (SELECT 1 FROM fetch_attempts f WHERE f.game_id = g.id AND f.job = 'backfill_xg')
        ORDER BY g.date DESC
        """
    )][: limit or None]
    print(f"xG: {len(ids)} Spiele", flush=True)
    touched: set = set()
    ok = errors = 0
    _write_status(phase="xg", done=0, total=len(ids), new=0, errors=0)
    for i, (gid, lid, yr) in enumerate(ids, start=1):
        try:
            home, away = LivePipelineService._extract_match_xg(client.get_game(gid))
            if home is not None and away is not None:
                conn.execute(
                    "UPDATE games SET calculated_xg_home = ?, calculated_xg_away = ?, updated_at = ? WHERE id = ?",
                    (home, away, datetime.now().isoformat(), gid),
                )
                conn.commit()
                ok += 1
                if lid is not None and yr is not None:
                    touched.add((int(lid), int(yr)))
            _mark(conn, gid, "backfill_xg")
        except Exception as e:
            errors += 1
            _sleep_on_error(e)
        time.sleep(delay)
        if i % 5 == 0 or i == len(ids):
            _write_status(done=i, new=ok, errors=errors)
        if i % 100 == 0 or i == len(ids):
            print(f"xG [{i}/{len(ids)}] neu={ok} fehler={errors} saisons={len(touched)}", flush=True)
    return touched


def backfill_glicko(conn, db, client, delay: float, limit: int = 0) -> None:
    ids = [int(r[0]) for r in conn.execute(
        """
        SELECT g.id FROM games g
        WHERE NOT EXISTS (SELECT 1 FROM game_glicko gl WHERE gl.game_id = g.id AND gl.home_xg IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM fetch_attempts f WHERE f.game_id = g.id AND f.job = 'backfill_glicko')
        ORDER BY g.date DESC
        """
    )][: limit or None]
    print(f"Glicko: {len(ids)} Spiele", flush=True)
    ok = errors = 0
    _write_status(phase="glicko", done=0, total=len(ids), new=0, errors=0)
    for i, gid in enumerate(ids, start=1):
        try:
            if db.save_glicko(gid, client.get_game_glicko(str(gid))):
                row = conn.execute("SELECT home_xg FROM game_glicko WHERE game_id = ?", (gid,)).fetchone()
                ok += bool(row and row[0] is not None)
            _mark(conn, gid, "backfill_glicko")
        except Exception as e:
            errors += 1
            _sleep_on_error(e)
        time.sleep(delay)
        if i % 5 == 0 or i == len(ids):
            _write_status(done=i, new=ok, errors=errors)
        if i % 100 == 0 or i == len(ids):
            print(f"Glicko [{i}/{len(ids)}] mit_xG={ok} fehler={errors}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Ältere fehlende xG- und Glicko-Werte nachladen")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--delay", type=float, default=0.6)
    p.add_argument("--only", choices=["xg", "glicko"], default=None)
    p.add_argument("--limit", type=int, default=0, help="nur die ersten N Spiele je Teil (Test)")
    args = p.parse_args()

    db = DatabaseManager(args.db)
    conn = db.get_connection()
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute(FETCH_ATTEMPTS_SQL)
    conn.commit()
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    _write_status(running=True, started_at=datetime.now().isoformat(timespec="seconds"),
                  finished_at=None, only=args.only)

    try:
        _run(conn, db, client, args)
    finally:
        _write_status(running=False, finished_at=datetime.now().isoformat(timespec="seconds"))
    print("Fertig.", flush=True)
    db.close()
    return 0


def _run(conn, db, client, args) -> None:
    if args.only in (None, "xg"):
        touched = backfill_xg(conn, client, args.delay, args.limit)
        _write_status(phase="form2", done=0, total=len(touched))
        for i, (lid, yr) in enumerate(sorted(touched), start=1):
            recompute_league_season(conn, lid, yr)
            upsert_upcoming_for_league_season(conn, lid, yr)
            _write_status(done=i)
        print(f"Form2 neu berechnet für {len(touched)} Liga-Saisons.", flush=True)
    if args.only in (None, "glicko"):
        backfill_glicko(conn, db, client, args.delay, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
