"""Reparatur: Pinnacle-Closing/-Opening für beendete Spiele neu laden.

Bis 24.10.2026 hat save_game nach Spielende alle Quoten durch die gerundeten Werte
aus /Games ersetzt (anderer Buchmacher, ohne Opening). Betroffen: Spiele seit
Start der Live-Pipeline (09.10.). Bereits reparierte Spiele (game_odds_final)
werden übersprungen — das Skript kann jederzeit abgebrochen und neu gestartet werden.

  python -u scripts/repair_odds_since.py --since 2026-10-09
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import DatabaseManager
from services.live_pipeline_service import ODDS_FINAL_SQL, load_final_odds


def main() -> int:
    p = argparse.ArgumentParser(description="Pinnacle-Quoten beendeter Spiele reparieren")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--since", default="2026-10-09", help="ab Datum (YYYY-MM-DD)")
    p.add_argument("--delay", type=float, default=0.6)
    args = p.parse_args()

    db = DatabaseManager(args.db)
    conn = db.get_connection()
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute(ODDS_FINAL_SQL)
    conn.commit()
    ids = [
        int(r[0])
        for r in conn.execute(
            """
            SELECT g.id FROM games g
            WHERE substr(COALESCE(g.date, ''), 1, 10) >= ?
              AND NOT EXISTS (SELECT 1 FROM game_odds_final f WHERE f.game_id = g.id)
            ORDER BY g.date ASC
            """,
            (args.since,),
        ).fetchall()
    ]
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    total = len(ids)
    ok = empty = errors = 0
    print(f"Reparatur: {total} Spiele seit {args.since}", flush=True)
    for i, gid in enumerate(ids, start=1):
        try:
            if load_final_odds(client, db, gid, delay=args.delay) == "ok":
                ok += 1
            else:
                empty += 1
        except Exception as e:
            errors += 1
            if "429" in str(e):
                time.sleep(20)
        time.sleep(args.delay)
        if i % 50 == 0 or i == total:
            print(f"[{i}/{total}] ok={ok} leer={empty} fehler={errors}", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
