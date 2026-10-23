"""Backfill missing Closing-Odds (Pinnacle) into game_odds.value.

Safe to run in parallel with Glicko / Opening backfills (same /Odds endpoint
family; use a slightly higher delay if rate-limited).

Examples:
  python -u scripts/backfill_closing_odds.py
  python -u scripts/backfill_closing_odds.py --delay 0.4 --prefer-glicko
  python -u scripts/backfill_closing_odds.py --bookmaker-id 4 --limit 500
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager
from services import strategy_service as strat


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill Closing odds into value")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--delay", type=float, default=0.4)
    p.add_argument("--limit", type=int, default=0, help="0 = all missing")
    p.add_argument("--bookmaker-id", type=int, default=4, help="Pinnacle=4")
    p.add_argument("--progress-every", type=int, default=25)
    p.add_argument(
        "--prefer-glicko",
        action="store_true",
        help="Zuerst Spiele mit Glicko ohne Closing, danach Rest",
    )
    return p.parse_args()


def _missing_ids(conn, limit: int, prefer_glicko: bool) -> list[int]:
    """Games with no closing value at all (no row or all value NULL)."""
    base_where = """
        NOT EXISTS (
            SELECT 1 FROM game_odds o
            WHERE o.game_id = g.id AND o.value IS NOT NULL
        )
    """
    ids: list[int] = []
    if prefer_glicko:
        sql_g = f"""
            SELECT g.id FROM games g
            INNER JOIN game_glicko gl ON gl.game_id = g.id
            WHERE {base_where}
            ORDER BY g.id DESC
        """
        ids.extend(int(r[0]) for r in conn.execute(sql_g).fetchall())
        seen = set(ids)
        sql_rest = f"""
            SELECT g.id FROM games g
            WHERE {base_where}
            ORDER BY g.id DESC
        """
        for r in conn.execute(sql_rest).fetchall():
            gid = int(r[0])
            if gid not in seen:
                ids.append(gid)
                seen.add(gid)
    else:
        sql = f"""
            SELECT g.id FROM games g
            WHERE {base_where}
            ORDER BY g.id DESC
        """
        ids = [int(r[0]) for r in conn.execute(sql).fetchall()]

    if limit and limit > 0:
        return ids[: int(limit)]
    return ids


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1

    db = DatabaseManager(str(db_path))
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    conn = db.get_connection()

    view_sql = Path(__file__).resolve().parent.parent / "database" / "create_odds_view.sql"
    if view_sql.exists():
        try:
            conn.executescript(view_sql.read_text(encoding="utf-8"))
            conn.commit()
        except Exception:
            pass

    ids = _missing_ids(conn, args.limit, args.prefer_glicko)
    total = len(ids)
    est = (total * max(args.delay, 0.05)) / 60.0
    print("=" * 70)
    print("Closing-Odds Backfill (Pinnacle)")
    print("=" * 70)
    print(f"To fetch:      {total}")
    print(f"Bookmaker:     {args.bookmaker_id}")
    print(f"Delay:         {args.delay}s")
    print(f"Prefer glicko: {args.prefer_glicko}")
    print(f"Est. duration: ~{est:.0f} min")
    print(f"Started:       {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)
    if total == 0:
        print("Nothing to do.")
        db.close()
        return 0

    loaded = empty = errors = 0
    t0 = time.time()
    last = 0.0
    for idx, gid in enumerate(ids, start=1):
        elapsed = time.time() - last
        if elapsed < args.delay:
            time.sleep(args.delay - elapsed)
        last = time.time()
        try:
            stats = strat.backfill_closing_odds(
                client,
                db,
                [gid],
                bookmaker_id=args.bookmaker_id,
                delay=0,
            )
            loaded += stats.get("loaded", 0)
            empty += stats.get("empty", 0)
            errors += stats.get("errors", 0)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  error {gid}: {e}")
        if idx % args.progress_every == 0 or idx == total:
            rate = idx / max(time.time() - t0, 1e-6)
            eta = (total - idx) / max(rate, 1e-6) / 60.0
            print(
                f"[{idx}/{total}] loaded={loaded} no_data={empty} errors={errors} "
                f"rate={rate:.2f}/s eta~{eta:.0f}m"
            )

    print()
    print("=" * 70)
    print("Done")
    print(f"Loaded:  {loaded}")
    print(f"No data: {empty}")
    print(f"Errors:  {errors}")
    print(f"Elapsed: {(time.time() - t0) / 60:.1f} min")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
