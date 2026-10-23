"""Dauerhafter Pipeline-Daemon: Upcoming-Sync → Pre-match Odds → Post-match xG/Glicko.

Jobs mit eigenen Intervallen in einem Prozess:

1. sync    – Today-API + Promotion finished → games
2. results – Endergebnis für Spiele mit vergangenem Anstoß, Match-xG nachladen,
             danach Form2-Tabellen der betroffenen Liga-Saisons neu berechnen
3. odds    – Opening/Closing für anstehende Spiele nachladen
4. enrich  – Glicko/xG für kürzlich beendete Spiele ohne xG
5. catchup – fehlende Spiele der laufenden Saison pro Liga

Erfolglose Abfragen landen in `fetch_attempts` und werden erst nach einer
wachsenden Wartezeit erneut versucht — so blockieren Spiele ohne Daten
nicht jeden Lauf.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from services.match_status import FINISHED_STATUS_CODES
from services import strategy_service as strat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_STATUS_PATH = os.path.join(ROOT, "logs", "live_pipeline_status.json")
PINNACLE = 4

FETCH_ATTEMPTS_SQL = """
CREATE TABLE IF NOT EXISTS fetch_attempts (
    game_id INTEGER NOT NULL,
    job TEXT NOT NULL,
    tries INTEGER NOT NULL DEFAULT 0,
    last_try TEXT,
    next_try TEXT,
    PRIMARY KEY (game_id, job)
)
"""

# Wartezeit in Minuten nach dem n-ten erfolglosen Versuch (letzter Wert gilt danach weiter)
BACKOFF_MINUTES: Dict[str, List[int]] = {
    "result": [15, 15, 30, 60, 120, 360, 720, 1440],
    "xg": [15, 30, 60, 120, 360, 720],
    "glicko": [30, 60, 120, 360, 720],
    "odds_close": [30, 60, 120, 240],
    "odds_open": [30, 60, 120, 240],
}
# Danach wird ein Spiel für diesen Job nicht mehr abgefragt (None = nur Zeitfenster begrenzt)
MAX_TRIES: Dict[str, Optional[int]] = {
    "result": 12,
    "xg": 8,
    "glicko": 10,
    "odds_close": None,
    "odds_open": None,
}


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
    """Aktive Ligen (data/tracked_leagues.json) + Liga128 + European.

    Ohne Liste: alle Ligen aus der DB — das wächst mit jedem Sync (Schneeball).
    """
    from services.league_scope import active_league_ids

    active = active_league_ids()
    ids: Set[int] = set(active) if active is not None else set()
    if active is None:
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
        results_interval: int = 600,
        results_batch: int = 40,
        result_after_minutes: int = 150,
        xg_lookback_days: int = 3,
        tables_batch: int = 15,
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
        self.results_interval = max(120, int(results_interval))
        self.results_batch = max(5, int(results_batch))
        self.result_after_minutes = max(105, int(result_after_minutes))
        self.xg_lookback_days = max(1, int(xg_lookback_days))
        self.tables_batch = max(1, int(tables_batch))
        self.status_path = status_path
        self.all_leagues = bool(all_leagues)
        self._log = log or (lambda m: print(m, flush=True))
        self.running = False
        self.started_at: Optional[str] = None
        self._catchup_idx = 0
        self._jobs: Dict[str, Dict[str, Any]] = {
            "sync": {},
            "results": {},
            "odds": {},
            "enrich": {},
            "catchup": {},
        }
        conn = self.db.get_connection()
        conn.execute(FETCH_ATTEMPTS_SQL)
        conn.commit()

    def log(self, msg: str) -> None:
        self._log(f"[{_now_iso()}] {msg}")

    def _sleep_api(self) -> None:
        time.sleep(self.api_delay)

    # ── Wiederholungssperre (fetch_attempts) ──────────────────────────

    def _due_clause(self, id_col: str, job: str) -> Tuple[str, List[Any]]:
        """SQL-Bedingung: Spiel ist für `job` fällig (keine Wartezeit offen, Limit nicht erreicht)."""
        max_tries = MAX_TRIES.get(job) or 1_000_000_000
        sql = (
            "NOT EXISTS (SELECT 1 FROM fetch_attempts fa "
            f"WHERE fa.game_id = {id_col} AND fa.job = ? "
            "AND (fa.next_try > ? OR fa.tries >= ?))"
        )
        return sql, [job, _now_iso(), max_tries]

    def _record_attempt(self, game_id: int, job: str, ok: bool) -> None:
        """Erfolg → Eintrag löschen; sonst Versuch zählen und nächste Abfrage nach hinten schieben."""
        conn = self.db.get_connection()
        if ok:
            conn.execute(
                "DELETE FROM fetch_attempts WHERE game_id = ? AND job = ?", (int(game_id), job)
            )
            conn.commit()
            return
        row = conn.execute(
            "SELECT tries FROM fetch_attempts WHERE game_id = ? AND job = ?", (int(game_id), job)
        ).fetchone()
        tries = (int(row[0]) if row else 0) + 1
        steps = BACKOFF_MINUTES[job]
        wait = steps[min(tries, len(steps)) - 1]
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO fetch_attempts (game_id, job, tries, last_try, next_try)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(game_id, job) DO UPDATE SET
                tries = excluded.tries,
                last_try = excluded.last_try,
                next_try = excluded.next_try
            """,
            (
                int(game_id),
                job,
                tries,
                now.isoformat(timespec="seconds"),
                (now + timedelta(minutes=wait)).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()

    def _write_status(self, extra: Optional[Dict[str, Any]] = None) -> None:
        os.makedirs(os.path.dirname(self.status_path), exist_ok=True)
        payload = {
            "running": self.running,
            "started_at": self.started_at,
            "updated_at": _now_iso(),
            "intervals": {
                "sync_s": self.sync_interval,
                "results_s": self.results_interval,
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

    # ── Job 2: Endergebnis + Match-xG, danach Tabellen ────────────────

    @staticmethod
    def _league_scope_sql(col: str) -> Tuple[str, List[Any]]:
        """`AND col IN (...)` für aktive Ligen (data/tracked_leagues.json); leer = alle Ligen."""
        from services.league_scope import active_league_ids

        active = active_league_ids()
        if active is None:
            return "", []
        ids = sorted(active)
        return f"AND {col} IN ({','.join('?' * len(ids))})", ids

    @staticmethod
    def _extract_match_xg(full: Dict[str, Any]) -> Tuple[Any, Any]:
        """Match-xG aus /Games/{id} — gleiche Quelle wie DatabaseManager.save_game."""
        data = full.get("data") if isinstance(full.get("data"), dict) else full
        game = data.get("game", data) if isinstance(data, dict) else {}
        stats = data.get("statistics") or (game.get("statistics") if isinstance(game, dict) else None) or {}
        home = stats.get("calculatedXgHome")
        away = stats.get("calculatedXgAway")
        if home is None:
            home = stats.get("expectedGoalsHome")
        if away is None:
            away = stats.get("expectedGoalsAway")
        return home, away

    def _api_error(self, stats: Dict[str, Any], tag: str, gid: int, e: Exception) -> bool:
        """Fehler loggen; True = Rate-Limit (Versuch nicht zählen)."""
        stats["errors"] += 1
        msg = str(e)
        if "429" in msg:
            self.log(f"{tag}: Rate-Limit — 20s Pause")
            time.sleep(20)
            return True
        if stats["errors"] <= 5:
            self.log(f"{tag}: Fehler {gid}: {msg[:80]}")
        return False

    def job_results(self) -> Dict[str, Any]:
        """Endergebnis für alle Spiele mit vergangenem Anstoß — auch wenn sie nicht
        mehr in der Today-Liste stehen. Danach fehlendes Match-xG nachladen und
        die Form2-Tabellen (xG/xGA-Schnitte) der betroffenen Liga-Saisons neu berechnen.
        """
        stats: Dict[str, Any] = {
            "cleaned": 0,
            "checked": 0,
            "promoted": 0,
            "not_finished": 0,
            "xg_checked": 0,
            "xg_loaded": 0,
            "tables_refreshed": 0,
            "errors": 0,
        }
        conn = self.db.get_connection()

        # Reste: Spiel steht schon in games, aber noch in upcoming_games
        try:
            cur = conn.execute("DELETE FROM upcoming_games WHERE id IN (SELECT id FROM games)")
            conn.commit()
            stats["cleaned"] = max(0, cur.rowcount)
        except Exception as e:
            self.log(f"results: Aufräumen fehlgeschlagen: {e}")

        # 1) Anstoß lange genug vorbei → Spiel holen, neueste zuerst
        kickoff_before = (
            datetime.now() - timedelta(minutes=self.result_after_minutes)
        ).strftime("%Y-%m-%dT%H:%M:%S")
        due_sql, due_params = self._due_clause("u.id", "result")
        scope_sql, scope_params = self._league_scope_sql("u.league_id")
        try:
            result_ids = [
                int(r[0])
                for r in conn.execute(
                    f"""
                    SELECT u.id FROM upcoming_games u
                    WHERE COALESCE(u.date, '') <> ''
                      AND substr(u.date, 1, 19) <= ?
                      AND {due_sql}
                      {scope_sql}
                    ORDER BY u.date DESC
                    LIMIT ?
                    """,
                    [kickoff_before, *due_params, *scope_params, self.results_batch],
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"results: Query-Fehler: {e}")
            result_ids = []

        for gid in result_ids:
            stats["checked"] += 1
            self._sleep_api()
            try:
                # nicht beendet → save_game aktualisiert nur upcoming_games (Status/Spielstand)
                saved = self.db.save_game(self.client.get_game(gid))
                done = (
                    conn.execute("SELECT 1 FROM games WHERE id = ?", (gid,)).fetchone()
                    is not None
                )
            except Exception as e:
                if not self._api_error(stats, "results", gid, e):
                    self._record_attempt(gid, "result", False)
                continue
            self._record_attempt(gid, "result", done)
            if done:
                stats["promoted"] += 1
            elif not saved:
                stats["errors"] += 1
            else:
                stats["not_finished"] += 1

        # 2) Fertig, aber Match-xG fehlt noch — nur in Liga-Saisons, die überhaupt xG haben
        since = (datetime.now() - timedelta(days=self.xg_lookback_days)).strftime("%Y-%m-%d")
        due_sql, due_params = self._due_clause("g.id", "xg")
        scope_sql, scope_params = self._league_scope_sql("g.league_id")
        try:
            xg_ids = [
                int(r[0])
                for r in conn.execute(
                    f"""
                    SELECT g.id FROM games g
                    WHERE substr(COALESCE(g.date, ''), 1, 10) >= ?
                      AND (g.calculated_xg_home IS NULL OR g.calculated_xg_away IS NULL)
                      AND EXISTS (
                        SELECT 1 FROM games s
                        WHERE s.league_id = g.league_id
                          AND s.season_year = g.season_year
                          AND s.calculated_xg_home IS NOT NULL
                      )
                      AND {due_sql}
                      {scope_sql}
                    ORDER BY g.date DESC
                    LIMIT ?
                    """,
                    [since, *due_params, *scope_params, self.results_batch],
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"results: xG-Query-Fehler: {e}")
            xg_ids = []

        for gid in xg_ids:
            stats["xg_checked"] += 1
            self._sleep_api()
            try:
                home_xg, away_xg = self._extract_match_xg(self.client.get_game(gid))
            except Exception as e:
                if not self._api_error(stats, "results[xg]", gid, e):
                    self._record_attempt(gid, "xg", False)
                continue
            ok = home_xg is not None and away_xg is not None
            if ok:
                # nur xG-Spalten — Quoten/Events des Spiels bleiben unangetastet
                conn.execute(
                    """
                    UPDATE games
                    SET calculated_xg_home = ?, calculated_xg_away = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (home_xg, away_xg, datetime.now().isoformat(), gid),
                )
                conn.commit()
                stats["xg_loaded"] += 1
            self._record_attempt(gid, "xg", ok)

        # 3) Tabellen nachziehen
        try:
            stats["tables_refreshed"] = self._refresh_tables()
        except Exception as e:
            stats["errors"] += 1
            self.log(f"results: Tabellen-Update fehlgeschlagen: {e}")

        self.log(
            f"results: cleaned={stats['cleaned']} checked={stats['checked']} "
            f"promoted={stats['promoted']} not_finished={stats['not_finished']} "
            f"xg={stats['xg_loaded']}/{stats['xg_checked']} "
            f"tables={stats['tables_refreshed']} err={stats['errors']}"
        )
        self._jobs["results"] = {"last_run": _now_iso(), "ok": True, "stats": stats}
        return stats

    def _refresh_tables(self) -> int:
        """Form2 für Liga-Saisons neu berechnen, deren Spiele neuer sind als ihre Form2-Werte.

        Vergleicht Zeitstempel statt sich Änderungen zu merken — erfasst so auch
        Spiele, die Backfills, GUI oder Catch-up geschrieben haben.
        """
        from services.form2_service import (
            is_form2_league,
            recompute_league_season,
            upsert_upcoming_for_league_season,
        )

        conn = self.db.get_connection()
        since = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """
            WITH recent AS (
                SELECT league_id, season_year, MAX(updated_at) AS last_game
                FROM games
                WHERE substr(COALESCE(date, ''), 1, 10) >= ?
                  AND league_id IS NOT NULL AND season_year IS NOT NULL
                GROUP BY league_id, season_year
            )
            SELECT r.league_id, r.season_year FROM recent r
            WHERE COALESCE((
                SELECT MAX(f.updated_at) FROM games g
                JOIN game_form2 f ON f.game_id = g.id
                WHERE g.league_id = r.league_id AND g.season_year = r.season_year
            ), '') < r.last_game
            ORDER BY r.last_game DESC
            """,
            (since,),
        ).fetchall()
        from services.league_scope import active_league_ids

        active = active_league_ids()
        stale = [
            (int(a), int(b))
            for a, b in rows
            if is_form2_league(a) and (active is None or int(a) in active)
        ][: self.tables_batch]
        for lid, yr in stale:
            recompute_league_season(conn, lid, yr)
            upsert_upcoming_for_league_season(conn, lid, yr)
        if stale:
            try:
                from services.web_league_service import invalidate_overview_cache

                invalidate_overview_cache()
            except Exception:
                pass
        return len(stale)

    # ── Job 3: Pre-match odds ─────────────────────────────────────────

    def job_odds(self) -> Dict[str, int]:
        stats = {"closing_loaded": 0, "opening_loaded": 0, "empty": 0, "errors": 0, "checked": 0}
        conn = self.db.get_connection()
        horizon = (
            datetime.now() + timedelta(hours=self.odds_horizon_hours)
        ).strftime("%Y-%m-%dT%H:%M:%S")
        past = (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")

        # Closing zuerst (fehlt ganz)
        due_sql, due_params = self._due_clause("u.id", "odds_close")
        try:
            missing_close = [
                int(r[0])
                for r in conn.execute(
                    f"""
                    SELECT u.id FROM upcoming_games u
                    WHERE COALESCE(u.date, '') >= ?
                      AND COALESCE(u.date, '') <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM game_odds o
                        WHERE o.game_id = u.id AND o.value IS NOT NULL
                      )
                      AND {due_sql}
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    [past, horizon, *due_params, self.odds_batch],
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
                if not r.get("errors"):
                    self._record_attempt(gid, "odds_close", bool(r.get("loaded")))
            except Exception:
                stats["errors"] += 1

        # Opening für Spiele mit Closing
        due_sql, due_params = self._due_clause("u.id", "odds_open")
        try:
            missing_open = [
                int(r[0])
                for r in conn.execute(
                    f"""
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
                      AND {due_sql}
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    [past, horizon, *due_params, self.odds_batch],
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
                if not r.get("errors"):
                    self._record_attempt(gid, "odds_open", bool(r.get("loaded")))
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
                    ok = bool(row and row[0] is not None and row[1] is not None)
                else:
                    ok = False
            except Exception as e:
                if not self._api_error(stats, f"enrich[{tag}]", gid, e):
                    self._record_attempt(gid, "glicko", False)
                continue
            self._record_attempt(gid, "glicko", ok)
            if ok:
                stats["loaded"] += 1
                if tag == "upcoming":
                    stats["upcoming_xg"] += 1
            else:
                stats["no_data"] += 1

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

        due_sql, due_params = self._due_clause("u.id", "glicko")
        try:
            upcoming_ids = [
                int(r[0])
                for r in conn.execute(
                    f"""
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
                      AND {due_sql}
                    ORDER BY u.date ASC
                    LIMIT ?
                    """,
                    [past, horizon, *due_params, up_limit],
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"enrich: Upcoming-Query-Fehler: {e}")
            upcoming_ids = []

        due_sql, due_params = self._due_clause("g.id", "glicko")
        try:
            finished_ids = [
                int(r[0])
                for r in conn.execute(
                    f"""
                    SELECT g.id FROM games g
                    LEFT JOIN game_glicko gl ON gl.game_id = g.id
                    WHERE substr(COALESCE(g.date, ''), 1, 10) >= ?
                      AND (
                        gl.game_id IS NULL
                        OR gl.home_xg IS NULL
                        OR gl.away_xg IS NULL
                      )
                      AND {due_sql}
                    ORDER BY g.date DESC
                    LIMIT ?
                    """,
                    [since, *due_params, fin_limit],
                ).fetchall()
            ]
        except Exception as e:
            self.log(f"enrich: Finished-Query-Fehler: {e}")
            finished_ids = []

        stats["upcoming_checked"] = len(upcoming_ids)
        stats["finished_checked"] = len(finished_ids)

        self._fetch_glicko_ids(upcoming_ids, stats, tag="upcoming")
        self._fetch_glicko_ids(finished_ids, stats, tag="finished")
        # Form2 rechnet mit Match-xG aus games — das zieht job_results nach, nicht Glicko

        self.log(
            f"enrich: checked={stats['checked']} "
            f"upcoming={stats['upcoming_checked']} finished={stats['finished_checked']} "
            f"xg_ok={stats['loaded']} (upcoming_xg={stats['upcoming_xg']}) "
            f"no_xg_yet={stats['no_data']} err={stats['errors']}"
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
            f"results={self.results_interval}s "
            f"odds={self.odds_interval}s enrich={self.enrich_interval}s "
            f"catchup={self.catchup_interval}s year={self.catchup_year} "
            f"delay={self.api_delay}s all_leagues={self.all_leagues}"
        )
        next_sync = 0.0
        next_results = 0.0
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
                    if now >= next_results:
                        self.job_results()
                        next_results = time.time() + self.results_interval
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
