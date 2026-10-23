"""Backfill missing Glicko / xG for games already in the DB.

Only requests /games/glicko/{id} for games without a game_glicko row
(or optionally without xG). Safe to re-run; resumes automatically.

Examples:
  python scripts/backfill_glicko.py
  python scripts/backfill_glicko.py --delay 0.5 --limit 500
  python scripts/backfill_glicko.py --league-id 8
  python scripts/backfill_glicko.py --missing-xg
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill missing Glicko/xG into game_glicko")
    p.add_argument("--db", default="data/flashscore.db", help="SQLite DB path")
    p.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    p.add_argument("--limit", type=int, default=0, help="Max games to process (0 = all)")
    p.add_argument("--league-id", type=int, default=0, help="Only this league_id (0 = all)")
    p.add_argument(
        "--missing-xg",
        action="store_true",
        help="Also re-fetch rows that exist but lack home_xg/away_xg",
    )
    p.add_argument(
        "--order",
        choices=("date_desc", "date_asc", "id_desc", "id_asc"),
        default="date_desc",
        help="Processing order (newest first by default)",
    )
    p.add_argument("--progress-every", type=int, default=25, help="Log every N games")
    return p.parse_args()


def _order_sql(order: str) -> str:
    return {
        "date_desc": "g.date DESC, g.id DESC",
        "date_asc": "g.date ASC, g.id ASC",
        "id_desc": "g.id DESC",
        "id_asc": "g.id ASC",
    }[order]


def _missing_game_ids(conn: sqlite3.Connection, args: argparse.Namespace) -> list[int]:
    where = []
    params: list = []

    if args.missing_xg:
        where.append(
            """(
                gl.game_id IS NULL
                OR gl.home_xg IS NULL
                OR gl.away_xg IS NULL
            )"""
        )
    else:
        where.append("gl.game_id IS NULL")

    if args.league_id:
        where.append("g.league_id = ?")
        params.append(args.league_id)

    sql = f"""
        SELECT g.id
        FROM games g
        LEFT JOIN game_glicko gl ON gl.game_id = g.id
        WHERE {' AND '.join(where)}
        ORDER BY {_order_sql(args.order)}
    """
    if args.limit and args.limit > 0:
        sql += " LIMIT ?"
        params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    return [int(r[0]) for r in rows]


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1

    db = DatabaseManager(str(db_path))
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    conn = db.get_connection()

    total_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    have_glicko = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
    missing_ids = _missing_game_ids(conn, args)
    total = len(missing_ids)

    est_min = (total * max(args.delay, 0.05)) / 60.0
    print("=" * 70)
    print("Glicko / xG Backfill")
    print("=" * 70)
    print(f"DB:              {db_path}")
    print(f"Games total:     {total_games}")
    print(f"Have Glicko:     {have_glicko}")
    print(f"To fetch:        {total}")
    print(f"Delay:           {args.delay}s")
    print(f"Est. duration:   ~{est_min:.0f} min")
    print(f"Started:         {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)

    if total == 0:
        print("Nothing to do.")
        db.close()
        return 0

    loaded = 0
    no_data = 0
    errors = 0
    t0 = time.time()
    last_req = 0.0

    for idx, game_id in enumerate(missing_ids, start=1):
        elapsed = time.time() - last_req
        if elapsed < args.delay:
            time.sleep(args.delay - elapsed)
        last_req = time.time()

        try:
            glicko_data = client.get_game_glicko(str(game_id))
            if db.save_glicko(game_id, glicko_data):
                loaded += 1
            else:
                no_data += 1
        except Exception as e:
            errors += 1
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg:
                wait = 15
                print(f"\n[{idx}/{total}] Rate limit @ {game_id} — sleep {wait}s")
                time.sleep(wait)
                try:
                    glicko_data = client.get_game_glicko(str(game_id))
                    if db.save_glicko(game_id, glicko_data):
                        loaded += 1
                        errors -= 1
                    else:
                        no_data += 1
                        errors -= 1
                except Exception as e2:
                    print(f"  retry failed: {e2}")
            elif idx % args.progress_every == 0 or errors <= 5:
                print(f"[{idx}/{total}] error game {game_id}: {msg[:80]}")

        if idx % args.progress_every == 0 or idx == total:
            rate = idx / max(time.time() - t0, 1e-6)
            eta_min = (total - idx) / max(rate, 1e-6) / 60.0
            have_now = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
            print(
                f"[{idx}/{total}] loaded={loaded} no_data={no_data} errors={errors} "
                f"db_glicko={have_now} rate={rate:.2f}/s eta~{eta_min:.0f}m"
            )

    have_final = conn.execute("SELECT COUNT(*) FROM game_glicko").fetchone()[0]
    with_xg = conn.execute(
        "SELECT COUNT(*) FROM game_glicko WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL"
    ).fetchone()[0]

    print()
    print("=" * 70)
    print("Done")
    print("=" * 70)
    print(f"Loaded:          {loaded}")
    print(f"No data:         {no_data}")
    print(f"Errors:          {errors}")
    print(f"Glicko in DB:    {have_final}")
    print(f"With xG:         {with_xg}")
    print(f"Elapsed:         {(time.time() - t0) / 60.0:.1f} min")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
