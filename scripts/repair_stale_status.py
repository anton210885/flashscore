"""Spiele, die im Ergebnis-Bestand noch als „live“ stehen (z. B. 17.10.), neu von sstats laden.

Aktualisiert gezielt nur Status, Spielstand und fehlendes xG — kein INSERT OR REPLACE, damit Quoten,
Glicko & Co. (ON DELETE CASCADE) erhalten bleiben. Danach: Form2 der betroffenen Liga-Saisons neu
berechnen und Verifikations-Wetten auf diesen Spielen neu abrechnen.

  python -u scripts/repair_stale_status.py            # reparieren
  python -u scripts/repair_stale_status.py --dry-run  # nur anzeigen, was sich ändern würde
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.sstats_client import SStatsClient
from config import config as cfg
from database import connect
from services.form2_service import recompute_league_season, upsert_upcoming_for_league_season
from services.live_pipeline_service import LivePipelineService
from services.match_status import FINISHED_STATUS_CODES
from services import verification_service


def _int(v):
    return None if v is None else int(v)


def main() -> int:
    p = argparse.ArgumentParser(description="Live-Status im Ergebnis-Bestand reparieren")
    p.add_argument("--db", default="data/flashscore.db")
    p.add_argument("--delay", type=float, default=0.6)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    conn = connect(args.db, foreign_keys=False)
    conn.execute("PRAGMA busy_timeout = 30000")
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    ph = ",".join("?" * len(FINISHED_STATUS_CODES))
    rows = conn.execute(
        f"""SELECT id, league_id, season_year, status_name, home_ft_result, away_ft_result,
                   calculated_xg_home, home_team_name, away_team_name
            FROM games WHERE (status IS NULL OR status NOT IN ({ph})) AND date < ? ORDER BY date""",
        (*FINISHED_STATUS_CODES, cutoff),
    ).fetchall()
    print(f"{len(rows)} Spiele mit Live-Status im Ergebnis-Bestand", flush=True)

    fixed, changed_score, not_finished, errors = 0, 0, [], 0
    touched, repaired_ids = set(), []
    for i, (gid, lid, yr, old_status, old_h, old_a, old_xg, home, away) in enumerate(rows, start=1):
        try:
            full = client.get_game(int(gid))
            data = full.get("data") if isinstance(full.get("data"), dict) else full
            g = data.get("game", data)
            status = _int(g.get("status"))
            name = str(g.get("statusName") or "")
            finished = status in FINISHED_STATUS_CODES or "finished" in name.lower()
            if not finished:
                not_finished.append(f"{gid} {home} – {away}: {name}")
                continue
            h = g.get("homeFTResult") if g.get("homeFTResult") is not None else g.get("homeResult")
            a = g.get("awayFTResult") if g.get("awayFTResult") is not None else g.get("awayResult")
            if h is None or a is None:
                not_finished.append(f"{gid} {home} – {away}: {name}, kein Endstand")
                continue
            h, a = int(h), int(a)
            xh, xa = LivePipelineService._extract_match_xg(full)
            if (old_h, old_a) != (h, a):
                changed_score += 1
                print(f"  {gid} {home} – {away}: {old_h}:{old_a} ({old_status}) → {h}:{a} ({name})", flush=True)
            if not args.dry_run:
                tg = h + a
                conn.execute(
                    """UPDATE games SET status = ?, status_name = ?, elapsed = ?, extra_minutes = ?,
                           home_result = ?, away_result = ?, home_ht_result = ?, away_ht_result = ?,
                           home_ft_result = ?, away_ft_result = ?,
                           total_goals = ?, over_25 = ?, over_35 = ?, over_45 = ?,
                           calculated_xg_home = COALESCE(calculated_xg_home, ?),
                           calculated_xg_away = COALESCE(calculated_xg_away, ?),
                           updated_at = ?
                       WHERE id = ?""",
                    (status, name, g.get("elapsed"), g.get("extraMinutes"),
                     _int(g.get("homeResult")), _int(g.get("awayResult")),
                     _int(g.get("homeHTResult")), _int(g.get("awayHTResult")),
                     h, a, tg, int(tg > 2.5), int(tg > 3.5), int(tg > 4.5),
                     xh, xa, datetime.now().isoformat(), gid),
                )
                conn.commit()
            fixed += 1
            repaired_ids.append(int(gid))
            if lid is not None and yr is not None:
                touched.add((int(lid), int(yr)))
        except Exception as e:
            errors += 1
            print(f"  Fehler {gid}: {e}", flush=True)
            if "429" in str(e):
                time.sleep(30)
        time.sleep(args.delay)
        if i % 50 == 0:
            print(f"[{i}/{len(rows)}] repariert={fixed} geänderter_Stand={changed_score} fehler={errors}", flush=True)

    print(f"Repariert: {fixed} · davon Endstand geändert: {changed_score} · nicht beendet laut API: "
          f"{len(not_finished)} · Fehler: {errors}", flush=True)
    for line in not_finished[:20]:
        print(f"  nicht beendet: {line}", flush=True)
    if args.dry_run or not repaired_ids:
        return 0

    for lid, yr in sorted(touched):
        recompute_league_season(conn, lid, yr)
        upsert_upcoming_for_league_season(conn, lid, yr)
    print(f"Form2 neu berechnet für {len(touched)} Liga-Saisons.", flush=True)

    # Verifikations-Wetten auf diesen Spielen mit dem richtigen Endstand neu abrechnen
    reset = 0
    for i in range(0, len(repaired_ids), 500):
        chunk = repaired_ids[i:i + 500]
        cur = conn.execute(
            f"""UPDATE verification_bets SET settled_at = NULL, won = NULL, profit = NULL,
                    home_score = NULL, away_score = NULL
                WHERE game_id IN ({','.join('?' * len(chunk))})""",
            chunk,
        )
        reset += cur.rowcount
    conn.commit()
    res = verification_service.settle(conn) if reset else {}
    print(f"Verifikation: {reset} Wetten neu abgerechnet {res}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
