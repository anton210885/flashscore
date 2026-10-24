"""Historie für Ligen nachladen: Spiele, Pinnacle-Quoten, Glicko und Form2.

Pro Liga und Saison:
  1. beendete Spiele inkl. Details/Match-xG (GameLoaderService, vorhandene übersprungen)
  2. Pinnacle-Closing + -Opening (load_final_odds) — für Strategien mit Opening-Quote nötig
  3. Glicko-Rating + xG-Vorhersage
  4. Form2 (xG Saison) neu berechnen

Abbrechen und neu starten ist jederzeit möglich — Erledigtes wird übersprungen.

  python -u scripts/load_league_history.py --leagues 71 72 110 --years 2022-2025
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
from services.form2_service import recompute_league_season, upsert_upcoming_for_league_season
from services.game_loader_service import GameLoaderService
from services.live_pipeline_service import ODDS_FINAL_SQL, load_final_odds


def main() -> int:
    p = argparse.ArgumentParser(description="Liga-Historie nachladen")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--leagues", type=int, nargs="+", required=True)
    p.add_argument("--years", default="2022-2025", help="z. B. 2022-2025")
    p.add_argument("--delay", type=float, default=0.6)
    args = p.parse_args()
    y0, y1 = (int(x) for x in args.years.split("-"))
    years = list(range(y0, y1 + 1))

    db = DatabaseManager(args.db)
    conn = db.get_connection()
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute(ODDS_FINAL_SQL)
    conn.commit()
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    loader = GameLoaderService(client, db, rate_limit_ms=int(args.delay * 1000))

    # 1) Spiele
    for lid in args.leagues:
        for yr in years:
            try:
                r = loader.load_games_for_league(lid, yr, load_details=True, skip_existing=True)
                print(
                    f"Spiele liga={lid} saison={yr}: gefunden={r.get('total_found')} "
                    f"neu={r.get('loaded')} vorhanden={r.get('already_exists')} fehler={r.get('errors')}",
                    flush=True,
                )
            except Exception as e:
                print(f"Spiele liga={lid} saison={yr}: FEHLER {e}", flush=True)

    ph = ",".join("?" * len(args.leagues))
    base = f"FROM games g WHERE g.league_id IN ({ph})"
    params = list(args.leagues)

    # 2) Pinnacle-Quoten (alle Saisons dieser Ligen, auch die laufende)
    ids = [int(r[0]) for r in conn.execute(
        f"SELECT g.id {base} AND NOT EXISTS (SELECT 1 FROM game_odds_final f WHERE f.game_id = g.id) ORDER BY g.date",
        params,
    )]
    ok = empty = errors = 0
    print(f"Quoten: {len(ids)} Spiele", flush=True)
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
        if i % 50 == 0 or i == len(ids):
            print(f"Quoten [{i}/{len(ids)}] ok={ok} leer={empty} fehler={errors}", flush=True)

    # 3) Glicko
    ids = [int(r[0]) for r in conn.execute(
        f"SELECT g.id {base} AND NOT EXISTS (SELECT 1 FROM game_glicko gl WHERE gl.game_id = g.id) ORDER BY g.date",
        params,
    )]
    ok = errors = 0
    print(f"Glicko: {len(ids)} Spiele", flush=True)
    for i, gid in enumerate(ids, start=1):
        try:
            if db.save_glicko(gid, client.get_game_glicko(str(gid))):
                ok += 1
        except Exception as e:
            errors += 1
            if "429" in str(e):
                time.sleep(20)
        time.sleep(args.delay)
        if i % 50 == 0 or i == len(ids):
            print(f"Glicko [{i}/{len(ids)}] ok={ok} fehler={errors}", flush=True)

    # 4) Form2 (xG Saison) für alle Saisons dieser Ligen
    for lid, yr in conn.execute(
        f"SELECT DISTINCT g.league_id, g.season_year {base} AND g.season_year IS NOT NULL", params
    ).fetchall():
        recompute_league_season(conn, int(lid), int(yr))
        upsert_upcoming_for_league_season(conn, int(lid), int(yr))
    print("Form2 neu berechnet. Fertig.", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
