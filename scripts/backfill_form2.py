"""Backfill Form2 (saisonale xG/Tore-Avgs) in game_form2.

Nur Meisterschaften (keine UEFA / WM). Pro Liga + Saison von vorne.

Examples:
  python scripts/backfill_form2.py
  python scripts/backfill_form2.py --league-id 39
  python scripts/backfill_form2.py --season-year 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import DatabaseManager
from services.form2_service import backfill_all, ensure_form2_schema


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill Form2 season averages into game_form2")
    p.add_argument("--db", default="data/flashscore.db", help="SQLite DB path")
    p.add_argument("--league-id", type=int, default=0, help="Only this league_id (0 = all)")
    p.add_argument("--season-year", type=int, default=0, help="Only this season_year (0 = all)")
    p.add_argument("--progress-every", type=int, default=25, help="Log every N league-seasons")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    db = DatabaseManager(args.db)
    conn = db.get_connection()
    ensure_form2_schema(conn)
    totals = backfill_all(
        conn,
        league_id=args.league_id or None,
        season_year=args.season_year or None,
        progress_every=args.progress_every,
        log=print,
    )
    print(
        f"done: pairs={totals['pairs']} written={totals['written']} "
        f"match_updates={totals['updated_teams']} skipped_euro={totals['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
