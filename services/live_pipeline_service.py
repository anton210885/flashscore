"""Dauerhafter Pipeline-Daemon: Upcoming-Sync → Pre-match Odds → Post-match xG/Glicko.

Drei Jobs mit eigenen Intervallen in einem Prozess:

1. sync   – Today-API + Promotion finished → games
2. odds   – Opening/Closing für anstehende Spiele nachladen
3. enrich – Glicko/xG für kürzlich beendete Spiele ohne xG
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from services.match_status import FINISHED_STATUS_CODES
from services import strategy_service as strat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_STATUS_PATH = os.path.join(ROOT, "logs", "live_pipeline_status.json")
PINNACLE = 4


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_finished(status: Any, status_name: Any, home_ft: Any = None, away_ft: Any = None) -> bool:
    """Nur echter Endstand — Live 0:0 / homeResult darf NICHT als Finished gelten."""
    try:
        if status is not None and int(status) in FINISHED_STATUS_CODES:
            return True
    except (TypeError, ValueError):
        pass
    sn = str(status_name or "").lower()
    if "finished" in sn or "after penalties" in sn or "after extra time" in sn:
        return True
    # Scores allein reichen nicht (API liefert oft 0:0 schon in der 1. Halbzeit)
    return False


def _league_id_from_item(item: Dict[str, Any]) -> Optional[int]:
    season = item.get("season") or {}
    if isinstance(season, dict):
        league = season.get("league") or {}
        if isinstance(league, dict) and league.get("id") is not None:
            try:
                return int(league["id"])
            except (TypeError, ValueError):
                pass
    for key in ("leagueId", "league_id"):
        if item.get(key) is not None:
            try:
                return int(item[key])
            except (TypeError, ValueError):
                pass
    return None


def tracked_league_ids(conn) -> Set[int]:
    """Ligen aus DB + Liga128 + European."""
    ids: Set[int] = set()
    try:
        for r in conn.execute(
            "SELECT DISTINCT league_id FROM games WHERE league_id IS NOT NULL"
        ).fetchall():
            ids.add(int(r[0]))
    except Exception:
        pass
    try:
        for r in conn.execute(
            "SELECT DISTINCT league_id FROM upcoming_games WHERE league_id IS NOT NULL"
        ).fetchall():
            ids.add(int(r[0]))
    except Exception:
        pass
    try:
        from services.web_league_service import liga128_ids

        ids |= {int(x) for x in liga128_ids()}
    except Exception:
        pass
    try:
        from services.european_competition_service import EURO_LEAGUE_IDS

        ids |= {int(x) for x in EURO_LEAGUE_IDS}
    except Exception:
        pass
    return ids


class LivePipelineService:
    def __init__(
        self,
        client,
        db_manager,
        *,
        sync_interval: int = 180,
        odds_interval: int = 900,
        enrich_interval: int = 600,
        api_delay: float = 0.55,
        enrich_lookback_days: int = 5,
        odds_horizon_hours: int = 48,
        enrich_batch: int = 40,
        odds_batch: int = 35,
        catchup_interval: int = 600,
        catchup_leagues_per_tick: int = 3,
        catchup_year: Optional[int] = None,
        status_path: str = DEFAULT_STATUS_PATH,
        all_leagues: bool = False,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.client = client
        self.db = db_manager
        self.sync_interval = max(60, int(sync_interval))
        self.odds_interval = max(120, int(odds_interval))
        self.enrich_interval = max(120, int(enrich_interval))
        self.catchup_interval = max(300, int(catchup_interval))
        self.catchup_leagues_per_tick = max(1, min(int(catchup_leagues_per_tick), 5))
        self.catchup_year = int(catchup_year) if catchup_year else int(datetime.now().year)
        self.api_delay = max(0.2, float(api_delay))
        self.enrich_lookback_days = max(1, int(enrich_lookback_days))
        self.odds_horizon_hours = max(6, int(odds_horizon_hours))
        self.enrich_batch = max(5, int(enrich_batch))
        self.odds_batch = max(5, int(odds_batch))
        self.status_path = status_path
        self.all_leagues = bool(all_leagues)
        self._log = log or (lambda m: print(m, flush=True))
        self.running = False
        self.started_at: Optional[str] = None
        self._catchup_idx = 0
        self._jobs: Dict[str, Dict[str, Any]] = {
            "sync": {},
            "odds": {},
            "enrich": {},
            "catchup": {},
        }

    def log(self, msg: str) -> None:
        self._log(f"[{_now_iso()}] {msg}")

    def _sleep_api(self) -> None:
        time.sleep(self.api_delay)

    def _write_status(self, extra: Optional[Dict[str, Any]] = None) -> None:
        os.makedirs(os.path.dirname(self.status_path), exist_ok=True)
        payload = {
            "running": self.running,
            "started_at": self.started_at,
            "updated_at": _now_iso(),
            "intervals": {
                "sync_s": self.sync_interval,
                "odds_s": self.odds_interval,
                "enrich_s": self.enrich_interval,
                "catchup_s": self.catchup_interval,
            },
            "jobs": self._jobs,
            "queue": self._queue_snapshot(),
        }
        if extra:
            payload.update(extra)
        tmp = self.status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.status_path)

    def _queue_snapshot(self) -> Dict[str, int]:
        conn = self.db.get_connection()
        out = {
            "missing_xg_recent": 0,
            "upcoming_open": 0,
            "upcoming_no_closing": 0,
            "upcoming_no_opening": 0,
        }
        try:
            since = (datetime.now() - timedelta(days=self.enrich_lookback_days)).strftime(
                "%Y-%m-%d"
            )
            out["missing_xg_recent"] = conn.execute(
                """
                SELECT COUNT(*) FROM games g
                LEFT JOIN game_glicko gl ON gl.game_id = g.id
                WHERE substr(COALESCE(g.date, ''), 1, 10) >= ?
                  AND (
                    gl.game_id IS NULL
                    OR gl.home_xg IS NULL
                    OR gl.away_xg IS NULL
                  )
                """,
                (since,),
            ).fetchone()[0]
        except Exception:
            pass
        try:
            out["upcoming_open"] = conn.execute(
                """
                SELECT COUNT(*) FROM upcoming_games
                WHERE home_ft_result IS NULL OR away_ft_result IS NULL
                """
            ).fetchone()[0]
        except Exception:
            pass
        try:
            out["upcoming_no_closing"] = conn.execute(
                """
                SELECT COUNT(*) FROM upcoming_games u
                WHERE NOT EXISTS (
                    SELECT 1 FROM game_odds o
                    WHERE o.game_id = u.id AND o.value IS NOT NULL
                )
                """
            ).fetchone()[0]
            out["upcoming_no_opening"] = conn.execute(
                """
                SELECT COUNT(*) FROM upcoming_games u
                WHERE EXISTS (
                    SELECT 1 FROM game_odds o
                    WHERE o.game_id = u.id AND o.value IS NOT NULL
                )
                AND NOT EXISTS (
                    SELECT 1 FROM game_odds o
                    WHERE o.game_id = u.id
                      AND o.opening_value IS NOT NULL
                      AND o.opening_value > 0
                )
                """
            ).fetchone()[0]
        except Exception:
            pass
        return out

    # ── Job 1: Sync Today + promote finished ───────────────────────────

    def job_sync(self) -> Dict[str, int]:
        stats = {
            "api_today": 0,
            "upcoming_upsert": 0,
            "finished_promoted": 0,
            "skipped_league": 0,
            "errors": 0,
        }
        conn = self.db.get_connection()
        tracked = set() if self.all_leagues else tracked_league_ids(conn)

        try:
            params: Dict[str, Any] = {"Today": True}
            try:
                from config import config as cfg

                params["TimeZone"] = getattr(cfg, "TIMEZONE", 2)
            except Exception:
                pass
            raw = self.client.get_games(params) or []
        except Exception as e:
            self.log(f"sync: Today-API Fehler: {e}")
            stats["errors"] += 1
            self._jobs["sync"] = {"last_run": _now_iso(), "ok": False, "stats": stats, "error": str(e)}
            return stats

        stats["api_today"] = len(raw)
        for item in raw:
            if not isinstance(item, dict):
                continue
            gid = item.get("id") or item.get("gameId")
            if not gid:
                continue
            try:
                gid = int(gid)
            except (TypeError, ValueError):
                continue

            lid = _league_id_from_item(item)
            if tracked and lid is not None and lid not in tracked:
                stats["skipped_league"] += 1
                continue

            status = item.get("status")
            status_name = item.get("statusName") or item.get("status_name")
            finished = _is_finished(status, status_name)

            try:
                if finished:
                    already = conn.execute(
                        "SELECT id FROM games WHERE id = ?", (gid,)
                    ).fetchone()
                    if already is None:
                        self._sleep_api()
                        full = self.client.get_game(gid)
                        if self.db.save_game(full):
                            stats["finished_promoted"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        conn.execute("DELETE FROM upcoming_games WHERE id = ?", (gid,))
                        conn.commit()
                else:
                    if self.db.save_upcoming_game(item):
                        stats["upcoming_upsert"] += 1
                    else:
                        stats["errors"] += 1
            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] <= 5:
                    self.log(f"sync: Fehler Spiel {gid}: {e}")

        # Stuck finished rows still in upcoming_games
        try:
            stuck = conn.execute(
                """
                SELECT id FROM upcoming_games
                WHERE status IN (7, 8, 9, 10)
                   OR lower(COALESCE(status_name, '')) LIKE '%finished%'
                   OR lower(COALESCE(status_name, '')) LIKE '%after penalties%'
                   OR lower(COALESCE(status_name, '')) LIKE '%after extra time%'
                LIMIT 30
                """
            ).fetchall()
            for (gid,) in stuck:
                try:
                    exists = conn.execute(
                        "SELECT id FROM games WHERE id = ?", (int(gid),)
                    ).fetchone()
                    if exists:
                        conn.execute("DELETE FROM upcoming_games WHERE id = ?", (int(gid),))
                        conn.commit()
                        continue
                    self._sleep_api()
                    full = self.client.get_game(int(gid))
                    if self.db.save_game(full):
                        stats["finished_promoted"] += 1
                except Exception:
                    stats["errors"] += 1
        except Exception:
            pass

        self.log(
            f"sync: today={stats['api_today']} upcoming+={stats['upcoming_upsert']} "
            f"promoted={stats['finished_promoted']} skip_league={stats['skipped_league']} "
            f"err={stats['errors']}"
        )
        self._jobs["sync"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
        return stats

    # ── Job 2: Pre-match odds ─────────────────────────────────────────

    def job_odds(self) -> Dict[str, int]:
        stats = {"closing_loaded": 0, "opening_loaded": 0, "empty": 0, "errors": 0, "checked": 0}
        conn = self.db.get_connection()
        horizon = (
            datetime.now() + timedelta(hours=self.odds_horizon_hours)
        ).strftime("%Y-%m-%dT%H:%M:%S")
        past = (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")

        # Closing zuerst (fehlt ganz)
        try:
            missing_close = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT u.id FROM upcoming_games u
                    WHERE COALESCE(u.date, '') >= ?
                      AND COALESCE(u.date, '') <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM game_odds o
                        WHERE o.game_id = u.id AND o.value IS NOT NULL
                      )
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    (past, horizon, self.odds_batch),
                ).fetchall()
            ]
        except Exception:
            missing_close = []

        for gid in missing_close:
            stats["checked"] += 1
            self._sleep_api()
            try:
                r = strat.backfill_closing_odds(
                    self.client, self.db, [gid], bookmaker_id=PINNACLE, delay=0
                )
                stats["closing_loaded"] += r.get("loaded", 0)
                stats["empty"] += r.get("empty", 0)
                stats["errors"] += r.get("errors", 0)
            except Exception:
                stats["errors"] += 1

        # Opening für Spiele mit Closing
        try:
            missing_open = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT u.id FROM upcoming_games u
                    WHERE COALESCE(u.date, '') >= ?
                      AND COALESCE(u.date, '') <= ?
                      AND EXISTS (
                        SELECT 1 FROM game_odds o
                        WHERE o.game_id = u.id AND o.value IS NOT NULL
                      )
                      AND NOT EXISTS (
                        SELECT 1 FROM game_odds o
                        WHERE o.game_id = u.id
                          AND o.opening_value IS NOT NULL
                          AND o.opening_value > 0
                      )
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    (past, horizon, self.odds_batch),
                ).fetchall()
            ]
        except Exception:
            missing_open = []

        for gid in missing_open:
            stats["checked"] += 1
            self._sleep_api()
            try:
                r = strat.backfill_opening_odds(
                    self.client, self.db, [gid], bookmaker_id=PINNACLE, delay=0
                )
                stats["opening_loaded"] += r.get("loaded", 0)
                stats["empty"] += r.get("empty", 0)
                stats["errors"] += r.get("errors", 0)
            except Exception:
                stats["errors"] += 1

        self.log(
            f"odds: checked={stats['checked']} close+={stats['closing_loaded']} "
            f"open+={stats['opening_loaded']} empty={stats['empty']} err={stats['errors']}"
        )
        self._jobs["odds"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
        return stats

    # ── Job 3: Glicko / xG (Upcoming zuerst, dann fertige) ────────────

    def _fetch_glicko_ids(self, ids: List[int], stats: Dict[str, int], *, tag: str) -> None:
        conn = self.db.get_connection()
        for gid in ids:
            stats["checked"] += 1
            self._sleep_api()
            try:
                glicko_data = self.client.get_game_glicko(str(gid))
                if self.db.save_glicko(gid, glicko_data):
                    row = conn.execute(
                        """
                        SELECT home_xg, away_xg FROM game_glicko WHERE game_id = ?
                        """,
                        (gid,),
                    ).fetchone()
                    if row and row[0] is not None and row[1] is not None:
                        stats["loaded"] += 1
                        if tag == "upcoming":
                            stats["upcoming_xg"] += 1
                    else:
                        stats["no_data"] += 1
                else:
                    stats["no_data"] += 1
            except Exception as e:
                stats["errors"] += 1
                msg = str(e)
                if "429" in msg:
                    self.log(f"enrich[{tag}]: Rate-Limit — 20s Pause")
                    time.sleep(20)
                elif stats["errors"] <= 5:
                    self.log(f"enrich[{tag}]: Fehler {gid}: {msg[:80]}")

    def job_enrich(self) -> Dict[str, int]:
        """Parallel zum Historien-Backfill: Upcoming + kürzlich fertige ohne xG."""
        stats = {
            "loaded": 0,
            "no_data": 0,
            "errors": 0,
            "checked": 0,
            "upcoming_xg": 0,
            "finished_checked": 0,
            "upcoming_checked": 0,
        }
        conn = self.db.get_connection()
        since = (datetime.now() - timedelta(days=self.enrich_lookback_days)).strftime(
            "%Y-%m-%d"
        )
        # Upcoming: nächste Tage ohne Glicko/xG — unabhängig von Historien-Backfill
        horizon = (
            datetime.now() + timedelta(hours=self.odds_horizon_hours)
        ).strftime("%Y-%m-%dT%H:%M:%S")
        past = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        # Hälfte Batch für Upcoming priorisieren
        up_limit = max(10, self.enrich_batch // 2 + self.enrich_batch % 2)
        fin_limit = max(10, self.enrich_batch // 2)

        try:
            upcoming_ids = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT u.id FROM upcoming_games u
                    LEFT JOIN game_glicko gl ON gl.game_id = u.id
                    WHERE COALESCE(u.date, '') >= ?
                      AND COALESCE(u.date, '') <= ?
                      AND (u.home_ft_result IS NULL OR u.away_ft_result IS NULL)
                      AND IFNULL(u.status, 0) NOT IN (7, 8, 9, 10)
                      AND (
                        gl.game_id IS NULL
                        OR gl.home_xg IS NULL
                        OR gl.away_xg IS NULL
                      )
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    (past, horizon, up_limit),
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"enrich: Upcoming-Query-Fehler: {e}")
            upcoming_ids = []

        try:
            finished_ids = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT g.id FROM games g
                    LEFT JOIN game_glicko gl ON gl.game_id = g.id
                    WHERE substr(COALESCE(g.date, ''), 1, 10) >= ?
                      AND (
                        gl.game_id IS NULL
                        OR gl.home_xg IS NULL
                        OR gl.away_xg IS NULL
                      )
                    ORDER BY g.date DESC
                    LIMIT ?
                    """,
                    (since, fin_limit),
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"enrich: Finished-Query-Fehler: {e}")
            finished_ids = []

        stats["upcoming_checked"] = len(upcoming_ids)
        stats["finished_checked"] = len(finished_ids)

        self._fetch_glicko_ids(upcoming_ids, stats, tag="upcoming")
        self._fetch_glicko_ids(finished_ids, stats, tag="finished")

        # Form2: Liga-Saison der fertigen Spiele neu berechnen (Match-xG→Avgs)
        form2_ok = 0
        form2_err = 0
        if finished_ids:
            try:
                from services.form2_service import refresh_for_game

                seen_keys = set()
                for gid in finished_ids:
                    try:
                        row = conn.execute(
                            "SELECT league_id, season_year FROM games WHERE id = ?",
                            (int(gid),),
                        ).fetchone()
                        if not row or row[0] is None or row[1] is None:
                            continue
                        key = (int(row[0]), int(row[1]))
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        refresh_for_game(conn, int(gid))
                        form2_ok += 1
                    except Exception:
                        form2_err += 1
            except Exception as e:
                self.log(f"enrich: Form2-Update-Fehler: {e}")
                form2_err += 1
        stats["form2_seasons"] = form2_ok
        stats["form2_errors"] = form2_err

        self.log(
            f"enrich: checked={stats['checked']} "
            f"upcoming={stats['upcoming_checked']} finished={stats['finished_checked']} "
            f"xg_ok={stats['loaded']} (upcoming_xg={stats['upcoming_xg']}) "
            f"no_xg_yet={stats['no_data']} err={stats['errors']} "
            f"form2_seasons={form2_ok}"
        )
        self._jobs["enrich"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
        return stats

    # ── Job 4: Saison-Catch-up (fehlende Finished jenseits von Today) ─

    def _catchup_league_ids(self) -> List[int]:
        """Meisterschaften (+ Liga128), ohne UEFA/WM — Round-Robin."""
        conn = self.db.get_connection()
        ids = set(tracked_league_ids(conn))
        try:
            from services.european_competition_service import EURO_LEAGUE_IDS
            from services.world_cup_service import WORLD_CUP_LEAGUE_ID

            ids -= set(int(x) for x in EURO_LEAGUE_IDS)
            ids.discard(int(WORLD_CUP_LEAGUE_ID))
        except Exception:
            pass
        return sorted(ids)

    def job_catchup(self) -> Dict[str, Any]:
        """Lädt fehlende beendete Spiele der laufenden Saison pro Liga nach.

        Today-Sync allein sieht nur Spiele von heute — deshalb periodisch
        leagueid+year nachladen (skip existing).
        """
        from services.game_loader_service import GameLoaderService

        stats: Dict[str, Any] = {
            "year": self.catchup_year,
            "leagues": [],
            "loaded": 0,
            "already_exists": 0,
            "errors": 0,
            "total_found": 0,
        }
        leagues = self._catchup_league_ids()
        if not leagues:
            self._jobs["catchup"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
            return stats

        n = len(leagues)
        start = self._catchup_idx % n
        batch = [leagues[(start + i) % n] for i in range(min(self.catchup_leagues_per_tick, n))]
        self._catchup_idx = (start + len(batch)) % n

        loader = GameLoaderService(
            self.client,
            self.db,
            rate_limit_ms=max(250, int(self.api_delay * 1000)),
        )
        for lid in batch:
            try:
                r = loader.load_games_for_league(
                    int(lid),
                    int(self.catchup_year),
                    load_details=True,
                    skip_existing=True,
                )
                loaded = int(r.get("loaded") or 0)
                stats["loaded"] += loaded
                stats["already_exists"] += int(r.get("already_exists") or 0)
                stats["errors"] += int(r.get("errors") or 0)
                stats["total_found"] += int(r.get("total_found") or 0)
                stats["leagues"].append(
                    {
                        "league_id": int(lid),
                        "loaded": loaded,
                        "found": int(r.get("total_found") or 0),
                    }
                )
                if loaded > 0:
                    try:
                        from services.form2_service import recompute_league_season

                        recompute_league_season(
                            self.db.get_connection(), int(lid), int(self.catchup_year)
                        )
                    except Exception:
                        pass
                    try:
                        from services.web_league_service import invalidate_overview_cache

                        invalidate_overview_cache()
                    except Exception:
                        pass
            except Exception as e:
                stats["errors"] += 1
                stats["leagues"].append({"league_id": int(lid), "error": str(e)[:120]})
                self.log(f"catchup: Liga {lid} Fehler: {e}")

        self.log(
            f"catchup: year={self.catchup_year} leagues={batch} "
            f"loaded={stats['loaded']} exists={stats['already_exists']} "
            f"err={stats['errors']} next_idx={self._catchup_idx}/{n}"
        )
        self._jobs["catchup"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
        return stats

    # ── Main loop ─────────────────────────────────────────────────────

    def run_forever(self) -> None:
        self.running = True
        self.started_at = _now_iso()
        self.log(
            f"Live-Pipeline gestartet | sync={self.sync_interval}s "
            f"odds={self.odds_interval}s enrich={self.enrich_interval}s "
            f"catchup={self.catchup_interval}s year={self.catchup_year} "
            f"delay={self.api_delay}s all_leagues={self.all_leagues}"
        )
        next_sync = 0.0
        next_odds = 0.0
        next_enrich = 0.0
        next_catchup = 0.0
        self._write_status()

        try:
            while self.running:
                now = time.time()
                try:
                    if now >= next_sync:
                        self.job_sync()
                        next_sync = time.time() + self.sync_interval
                        self._write_status()
                    if now >= next_odds:
                        self.job_odds()
                        next_odds = time.time() + self.odds_interval
                        self._write_status()
                    if now >= next_enrich:
                        self.job_enrich()
                        next_enrich = time.time() + self.enrich_interval
                        self._write_status()
                    if now >= next_catchup:
                        self.job_catchup()
                        next_catchup = time.time() + self.catchup_interval
                        self._write_status()
                except Exception as e:
                    self.log(f"Loop-Fehler: {e}")
                    self._write_status({"last_error": str(e)})
                    time.sleep(10)
                time.sleep(5)
        except KeyboardInterrupt:
            self.log("Stop (KeyboardInterrupt)")
        finally:
            self.running = False
            self._write_status()
            self.log("Live-Pipeline beendet")

    def stop(self) -> None:
        self.running = False
