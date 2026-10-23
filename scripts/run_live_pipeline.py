"""Startet den Dauer-Daemon: Sync → Odds → Post-match xG/Glicko.

Examples:
  python -u scripts/run_live_pipeline.py
  python -u scripts/run_live_pipeline.py --sync-interval 120 --enrich-interval 300
  python -u scripts/run_live_pipeline.py --once
  python -u scripts/run_live_pipeline.py --all-leagues
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager
from services.live_pipeline_service import LivePipelineService


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live Pipeline Daemon")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--sync-interval", type=int, default=180, help="Sekunden (Today-Sync)")
    p.add_argument("--odds-interval", type=int, default=900, help="Sekunden (Pre-match Odds)")
    p.add_argument("--enrich-interval", type=int, default=600, help="Sekunden (xG/Glicko)")
    p.add_argument("--api-delay", type=float, default=0.55)
    p.add_argument("--enrich-lookback-days", type=int, default=5)
    p.add_argument("--odds-horizon-hours", type=int, default=48)
    p.add_argument("--enrich-batch", type=int, default=40)
    p.add_argument("--odds-batch", type=int, default=35)
    p.add_argument(
        "--all-leagues",
        action="store_true",
        help="Today-Sync ohne Filter auf bekannte Ligen",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Jeden Job einmal ausführen und beenden",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1

    db = DatabaseManager(str(db_path))
    try:
        db.get_connection().execute("PRAGMA busy_timeout = 30000")
    except Exception:
        pass

    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    pipe = LivePipelineService(
        client,
        db,
        sync_interval=args.sync_interval,
        odds_interval=args.odds_interval,
        enrich_interval=args.enrich_interval,
        api_delay=args.api_delay,
        enrich_lookback_days=args.enrich_lookback_days,
        odds_horizon_hours=args.odds_horizon_hours,
        enrich_batch=args.enrich_batch,
        odds_batch=args.odds_batch,
        all_leagues=args.all_leagues,
    )

    if args.once:
        pipe.running = True
        pipe.started_at = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        pipe.job_sync()
        pipe.job_odds()
        pipe.job_enrich()
        pipe.running = False
        pipe._write_status()
        db.close()
        return 0

    pipe.run_forever()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
