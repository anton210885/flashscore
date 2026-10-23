"""API-fähige Liga-Statistiken (ohne Tkinter). Wiederverwendet DB + Euro-Service."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from services.match_status import SQL_FILTER_STILL_PENDING
from services.european_competition_service import (
    EURO_COMPETITIONS,
    EURO_LEAGUE_IDS,
    EURO_PHASES,
    encode_row_id,
    fetch_today_games,
    stats_for_league_year,
    today_counts_by_phase,
)

DB_PATH = "data/flashscore.db"
DEFAULT_YEARS = ("2022", "2023", "2024", "2025", "2026")
EURO_YEARS = ("2024", "2025", "2026")
CURRENT_YEAR = "2026"

LEAGUE_NAME_FIXES = {
    307: "Saudi Pro League",
    308: "Saudi Division 1",
    303: "UAE Division 1",
    301: "UAE Pro League",
    39: "Premier League",
    40: "Championship",
    41: "League One",
    42: "League Two",
    179: "Scottish Premiership",
    180: "Scottish Championship",
    61: "Ligue 1",
    62: "Ligue 2",
    63: "National 1",
    140: "La Liga",
    141: "Segunda División",
    274: "Liga 1",
    275: "Liga 2",
    190: "A-League Women",
    207: "Swiss Super League",
    208: "Swiss Challenge League",
    218: "Austrian Bundesliga",
    219: "Austrian 2. Liga",
}


def _conn() -> sqlite3.Connection:
    from database import connect

    return connect(DB_PATH)


def _pct(count: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(count / total * 100.0):.1f}%"


def _parse_pct(val: Any) -> Optional[float]:
    if val is None or val in ("", "N/A", "Error", "–", "-"):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def liga128_ids() -> set:
    """Kalenderjahr-Meisterschaften (Start+Ende im gleichen Jahr, z. B. 2026)."""
    try:
        import json
        import os

        path = os.path.join("data", "liga128_leagues.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {int(x) for x in data}
            if isinstance(data, dict) and "league_ids" in data:
                return {int(x) for x in data["league_ids"]}
    except Exception:
        pass
    return {128}


def exclusive_overview_ids() -> set:
    """Aus Meisterschaften (26/27) ausblenden: Liga-128 + European."""
    return set(int(x) for x in EURO_LEAGUE_IDS) | liga128_ids()


def _leagues_from_ids(include_ids: Optional[set] = None, exclude_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    conn = _conn()
    clauses = ["league_id IS NOT NULL"]
    params: List[Any] = []
    if include_ids:
        placeholders = ",".join("?" * len(include_ids))
        clauses.append(f"league_id IN ({placeholders})")
        params.extend(sorted(include_ids))
    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        clauses.append(f"league_id NOT IN ({placeholders})")
        params.extend(sorted(exclude_ids))
    where = " AND ".join(clauses)

    rows_games = conn.execute(
        f"""
        SELECT DISTINCT league_id,
               COALESCE(league_name, 'Unknown League') as league_name,
               COALESCE(country_name, 'Unknown') as country_name
        FROM games
        WHERE {where}
        """,
        tuple(params),
    ).fetchall()
    rows_table = conn.execute(
        f"""
        SELECT league_id,
               COALESCE(league_name, 'Unknown League') as league_name,
               COALESCE(country_name, 'Unknown') as country_name
        FROM leagues
        WHERE {where}
        """,
        tuple(params),
    ).fetchall()

    by_id: Dict[int, Any] = {}
    for r in rows_games:
        by_id[int(r["league_id"])] = r
    for r in rows_table:
        lid = int(r["league_id"])
        if lid not in by_id:
            by_id[lid] = r

    # Platzhalter für konfigurierte Liga-128-IDs ohne Spiele
    if include_ids:
        for lid in include_ids:
            if int(lid) not in by_id:
                by_id[int(lid)] = {
                    "league_id": int(lid),
                    "league_name": f"League {lid}",
                    "country_name": "Unknown",
                }

    def _field(row, key, default=""):
        try:
            return row[key] if row[key] is not None else default
        except Exception:
            return (row.get(key) if isinstance(row, dict) else default) or default

    leagues = []
    for lid, r in sorted(
        by_id.items(),
        key=lambda x: (_field(x[1], "country_name"), _field(x[1], "league_name")),
    ):
        name = LEAGUE_NAME_FIXES.get(lid, _field(r, "league_name") or f"League {lid}")
        leagues.append({"id": lid, "name": name, "country": _field(r, "country_name") or "Unknown"})
    return leagues


def list_leagues() -> List[Dict[str, Any]]:
    """Meisterschaften Saison 26/27 (ohne Liga-128 und European)."""
    return _leagues_from_ids(exclude_ids=exclusive_overview_ids())


def list_liga128_leagues() -> List[Dict[str, Any]]:
    """Kalenderjahr-Ligen aus liga128_leagues.json."""
    return _leagues_from_ids(include_ids=liga128_ids())


def league_year_stats(conn, league_id: int, year: int) -> Dict[str, Any]:
    # Nur wirklich beendete Spiele (kein Live 0:0) — neueste zuerst
    games = conn.execute(
        """
        SELECT home_ft_result, away_ft_result
        FROM games
        WHERE league_id=? AND season_year=?
          AND home_ft_result IS NOT NULL AND away_ft_result IS NOT NULL
          AND (
            status IN (7, 8, 9, 10)
            OR lower(COALESCE(status_name, '')) LIKE '%finished%'
            OR lower(COALESCE(status_name, '')) LIKE '%after penalties%'
            OR lower(COALESCE(status_name, '')) LIKE '%after extra time%'
          )
        ORDER BY date DESC, id DESC
        """,
        (league_id, year),
    ).fetchall()
    total_all = len(games)
    totals = []
    for g in games:
        h, a = g["home_ft_result"], g["away_ft_result"]
        if h is None or a is None:
            continue
        totals.append(float(h) + float(a))
    n = len(totals)

    def over_line(line: float) -> Dict[str, Any]:
        over_n = sum(1 for t in totals if t > line)
        last10 = totals[:10]
        last20 = totals[:20]
        # Aktuelle Under-Serie ab dem neuesten Spiel (wie Tkinter: 1,2,3…; 0 wenn letztes Over)
        streak = 0
        for t in totals:
            if t <= line:
                streak += 1
            else:
                break
        key = str(line).replace(".", "")
        return {
            f"over{key}": _pct(over_n, n),
            f"last10_over{key}": _pct(sum(1 for t in last10 if t > line), len(last10)) if last10 else "0.0%",
            f"last20_over{key}": _pct(sum(1 for t in last20 if t > line), len(last20)) if last20 else "0.0%",
            f"streak{key}": streak,
        }

    out: Dict[str, Any] = {
        "total": int(total_all or 0),
        "total_finished": n,
        "n": n,
    }
    for line in (2.5, 3.5, 4.5):
        out.update(over_line(line))
    return out


def today_pending_counts() -> Dict[int, int]:
    conn = _conn()
    today_str = datetime.now().strftime("%Y-%m-%d")
    pending = SQL_FILTER_STILL_PENDING
    rows = conn.execute(
        f"""
        SELECT league_id, COUNT(*) AS cnt FROM (
            SELECT league_id, id FROM upcoming_games
            WHERE league_id IS NOT NULL AND substr(date, 1, 10) = ? {pending}
            UNION
            SELECT league_id, id FROM games
            WHERE league_id IS NOT NULL AND substr(date, 1, 10) = ? {pending}
        ) AS t
        GROUP BY league_id
        """,
        (today_str, today_str),
    ).fetchall()
    return {int(r["league_id"]): int(r["cnt"] or 0) for r in rows}


def enrich_league(
    league: Dict[str, Any],
    years: Sequence[str],
    today: Dict[int, int],
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    own_conn = conn is None
    if own_conn:
        conn = _conn()
    try:
        lid = int(league["id"])
        row = dict(league)
        row["today"] = int(today.get(lid, 0))
        hist_vals_25: List[float] = []
        hist_vals_35: List[float] = []
        hist_vals_45: List[float] = []

        for y in years:
            st = league_year_stats(conn, lid, int(y))
            row[f"games_{y}"] = st.get("total", 0)
            for key in (
                "over25",
                "over35",
                "over45",
                "last10_over25",
                "last10_over35",
                "last10_over45",
                "last20_over25",
                "last20_over35",
                "last20_over45",
                "streak25",
                "streak35",
                "streak45",
            ):
                row[f"{key}_{y}"] = st.get(key, "0.0%" if "streak" not in key else 0)
            if y != CURRENT_YEAR:
                for vals, k in (
                    (hist_vals_25, "over25"),
                    (hist_vals_35, "over35"),
                    (hist_vals_45, "over45"),
                ):
                    p = _parse_pct(st.get(k))
                    if p is not None:
                        vals.append(p)

        def avg_and_diff(hist: List[float], current_key: str) -> None:
            metric = current_key.replace("_2026", "").replace("over", "")
            if hist:
                avg = sum(hist) / len(hist)
                row[f"avg_over{metric}"] = f"{avg:.1f}%"
                cur = _parse_pct(row.get(current_key))
                row[f"diff_over{metric}"] = None if cur is None else round(cur - avg, 1)
            else:
                row[f"avg_over{metric}"] = "N/A"
                row[f"diff_over{metric}"] = None

        avg_and_diff(hist_vals_25, "over25_2026")
        avg_and_diff(hist_vals_35, "over35_2026")
        avg_and_diff(hist_vals_45, "over45_2026")
        return row
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


_OVERVIEW_CACHE: Dict[str, Any] = {}
_OVERVIEW_CACHE_TTL_SEC = 90.0


def invalidate_overview_cache() -> None:
    _OVERVIEW_CACHE.clear()


def _overview_cached(cache_key: str, builder) -> Dict[str, Any]:
    import time

    now = time.time()
    hit = _OVERVIEW_CACHE.get(cache_key)
    if hit and now - hit["ts"] < _OVERVIEW_CACHE_TTL_SEC:
        return hit["data"]
    data = builder()
    _OVERVIEW_CACHE[cache_key] = {"ts": now, "data": data}
    return data


def overview(years: Optional[Sequence[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    years = list(years or DEFAULT_YEARS)
    cache_key = f"meisterschaften|{','.join(years)}|{limit}"

    def _build() -> Dict[str, Any]:
        leagues = list_leagues()
        if limit:
            leagues = leagues[: int(limit)]
        today = today_pending_counts()
        conn = _conn()
        try:
            # Ein Conn für alle Ligen — vorher öffnete jede Liga eine neue Verbindung (~300×)
            enriched = [enrich_league(l, years, today, conn) for l in leagues]
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return {
            "group": "meisterschaften",
            "label": "Meisterschaften (Saison 26/27)",
            "years": years,
            "current_year": CURRENT_YEAR,
            "leagues": enriched,
            "count": len(enriched),
        }

    return _overview_cached(cache_key, _build)


def liga128_overview(years: Optional[Sequence[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    years = list(years or DEFAULT_YEARS)
    cache_key = f"liga128|{','.join(years)}|{limit}"

    def _build() -> Dict[str, Any]:
        leagues = list_liga128_leagues()
        if limit:
            leagues = leagues[: int(limit)]
        today = today_pending_counts()
        conn = _conn()
        try:
            enriched = [enrich_league(l, years, today, conn) for l in leagues]
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return {
            "group": "liga128",
            "label": "Liga 128 (Kalenderjahr 2026)",
            "years": years,
            "current_year": CURRENT_YEAR,
            "leagues": enriched,
            "count": len(enriched),
        }

    return _overview_cached(cache_key, _build)


def european_overview() -> Dict[str, Any]:
    conn = _conn()
    years = list(EURO_YEARS)
    today_map: Dict[int, Dict[str, int]] = {}
    for lid in EURO_LEAGUE_IDS:
        today_map[int(lid)] = today_counts_by_phase(conn, int(lid))

    rows = []
    for comp in EURO_COMPETITIONS:
        lid = int(comp["id"])
        for phase_key, phase_label in EURO_PHASES:
            indent = "" if phase_key == "all" else "    "
            name = comp["name"] if phase_key == "all" else f"{indent}{phase_label}"
            row: Dict[str, Any] = {
                "id": encode_row_id(lid, phase_key),
                "source_id": lid,
                "phase": phase_key,
                "country": comp["short"],
                "name": name,
                "today": int((today_map.get(lid) or {}).get(phase_key, 0)),
            }
            hist_25: List[float] = []
            for y in years:
                st = stats_for_league_year(conn, lid, int(y), phase_key)
                row[f"games_{y}"] = st.get("n", 0)
                for k in ("over25", "over35", "over45", "over55",
                          "last10_over25", "last10_over35", "last10_over45", "last10_over55",
                          "last20_over25", "last20_over35", "last20_over45", "last20_over55",
                          "streak25", "streak35", "streak45", "streak55"):
                    row[f"{k}_{y}"] = st.get(k, "0.0%" if "streak" not in k else 0)
                if y != CURRENT_YEAR:
                    p = _parse_pct(st.get("over25"))
                    if p is not None:
                        hist_25.append(p)
            if hist_25:
                avg = sum(hist_25) / len(hist_25)
                row["avg_over25"] = f"{avg:.1f}%"
                cur = _parse_pct(row.get("over25_2026"))
                row["diff_over25"] = None if cur is None else round(cur - avg, 1)
            else:
                row["avg_over25"] = "N/A"
                row["diff_over25"] = None
            rows.append(row)

    return {
        "group": "european",
        "label": "European Competitions",
        "years": years,
        "current_year": CURRENT_YEAR,
        "competitions": list(EURO_COMPETITIONS),
        "phases": [{"key": k, "label": lbl} for k, lbl in EURO_PHASES],
        "leagues": rows,
        "count": len(rows),
    }


def _available_season_years(conn: sqlite3.Connection, league_id: int) -> List[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT season_year, COUNT(*) AS cnt
        FROM games
        WHERE league_id = ?
          AND season_year IS NOT NULL
          AND home_ft_result IS NOT NULL
          AND away_ft_result IS NOT NULL
          AND (
            status IN (7, 8, 9, 10)
            OR lower(COALESCE(status_name, '')) LIKE '%finished%'
            OR lower(COALESCE(status_name, '')) LIKE '%after penalties%'
            OR lower(COALESCE(status_name, '')) LIKE '%after extra time%'
          )
        GROUP BY season_year
        ORDER BY season_year DESC
        """,
        (int(league_id),),
    ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]


def _finished_games_for_year(
    conn: sqlite3.Connection,
    league_id: int,
    year: int,
    *,
    phase: str = "all",
) -> List[Dict[str, Any]]:
    """Beendete Spiele einer Liga/Saison — wie Tkinter show_games_list."""
    lid = int(league_id)
    yr = int(year)
    # Nur wirklich beendete Spiele (nicht Live mit 0:0)
    finished_sql = """
        AND (
            status IN (7, 8, 9, 10)
            OR lower(COALESCE(status_name, '')) LIKE '%finished%'
            OR lower(COALESCE(status_name, '')) LIKE '%after penalties%'
            OR lower(COALESCE(status_name, '')) LIKE '%after extra time%'
        )
        AND home_ft_result IS NOT NULL
        AND away_ft_result IS NOT NULL
    """
    rows = conn.execute(
        f"""
        SELECT id, date, home_team_name, away_team_name,
               home_ft_result, away_ft_result, status_name, season_year,
               calculated_xg_home, calculated_xg_away, round_name,
               over_25, over_35, over_45, total_goals
        FROM games
        WHERE league_id = ?
          AND season_year = ?
          {finished_sql}
        ORDER BY date DESC, id DESC
        """,
        (lid, yr),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            f"""
            SELECT id, date, home_team_name, away_team_name,
                   home_ft_result, away_ft_result, status_name, season_year,
                   calculated_xg_home, calculated_xg_away, round_name,
                   over_25, over_35, over_45, total_goals
            FROM games
            WHERE league_id = ?
              AND substr(COALESCE(date, ''), 1, 4) = ?
              {finished_sql}
            ORDER BY date DESC, id DESC
            """,
            (lid, str(yr)),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        g = dict(r)
        # Euro-Phase optional filtern
        if lid in EURO_LEAGUE_IDS and phase and phase != "all":
            from services.european_competition_service import classify_uefa_phase

            if classify_uefa_phase(g.get("round_name")) != phase:
                continue
        hg = g.get("home_ft_result")
        ag = g.get("away_ft_result")
        total = g.get("total_goals")
        if total is None and hg is not None and ag is not None:
            try:
                total = int(hg) + int(ag)
            except (TypeError, ValueError):
                total = None
        out.append(
            {
                "id": g.get("id"),
                "date": g.get("date"),
                "round": g.get("round_name"),
                "home": g.get("home_team_name"),
                "away": g.get("away_team_name"),
                "home_score": hg,
                "away_score": ag,
                "total_goals": total,
                "xg_home": g.get("calculated_xg_home"),
                "xg_away": g.get("calculated_xg_away"),
                "over_25": int(g["over_25"]) if g.get("over_25") is not None else (
                    1 if total is not None and total > 2.5 else (0 if total is not None else None)
                ),
                "over_35": int(g["over_35"]) if g.get("over_35") is not None else (
                    1 if total is not None and total > 3.5 else (0 if total is not None else None)
                ),
                "over_45": int(g["over_45"]) if g.get("over_45") is not None else (
                    1 if total is not None and total > 4.5 else (0 if total is not None else None)
                ),
                "status": g.get("status_name") or "Finished",
                "season_year": g.get("season_year"),
            }
        )

    # Under-Streaks „in Folge“ vom Neuesten (wie Tkinter): 1,2,3… / 0 bei Over
    s25 = s35 = s45 = 0
    for g in out:
        total = g.get("total_goals")
        if total is None:
            g["streak25"] = 0
            g["streak35"] = 0
            g["streak45"] = 0
            continue
        t = float(total)
        s25 = s25 + 1 if t <= 2 else 0
        s35 = s35 + 1 if t <= 3 else 0
        s45 = s45 + 1 if t <= 4 else 0
        g["streak25"] = s25
        g["streak35"] = s35
        g["streak45"] = s45
        # Farbstufe für UI (höchste zutreffende Linie)
        if t > 4.5:
            g["goals_band"] = "o45"
        elif t > 3.5:
            g["goals_band"] = "o35"
        elif t > 2.5:
            g["goals_band"] = "o25"
        else:
            g["goals_band"] = "u25"
    return out


def sync_league_season(league_id: int, year: Optional[int] = None) -> Dict[str, Any]:
    """Fehlende beendete Spiele einer Liga/Saison von der API nachladen."""
    from config import config as cfg
    from api.sstats_client import SStatsClient
    from database import DatabaseManager
    from services.game_loader_service import GameLoaderService

    yr = int(year) if year is not None else int(CURRENT_YEAR)
    lid = int(league_id)
    db = DatabaseManager(DB_PATH)
    client = SStatsClient(base_url=cfg.BASE_URL, api_key=getattr(cfg, "API_KEY", None))
    loader = GameLoaderService(client, db, rate_limit_ms=300)
    try:
        stats = loader.load_games_for_league(lid, yr, load_details=True, skip_existing=True)
    finally:
        try:
            db.close()
        except Exception:
            pass
    invalidate_overview_cache()
    try:
        from services.form2_service import recompute_league_season

        recompute_league_season(_conn(), lid, yr)
    except Exception:
        pass
    return {
        "ok": True,
        "league_id": lid,
        "year": yr,
        **stats,
    }


def league_detail(
    league_id: int,
    phase: str = "all",
    year: Optional[int] = None,
) -> Dict[str, Any]:
    conn = _conn()
    years = list(EURO_YEARS) if league_id in EURO_LEAGUE_IDS else list(DEFAULT_YEARS)
    available_years = _available_season_years(conn, league_id)
    series = []
    for y in years:
        if league_id in EURO_LEAGUE_IDS:
            st = stats_for_league_year(conn, league_id, int(y), phase)
        else:
            st = league_year_stats(conn, league_id, int(y))
        series.append(
            {
                "year": y,
                "games": st.get("n") or st.get("total_finished") or 0,
                "over25": _parse_pct(st.get("over25")),
                "over35": _parse_pct(st.get("over35")),
                "over45": _parse_pct(st.get("over45")),
                "over55": _parse_pct(st.get("over55")),
            }
        )
    today_games = []
    if league_id in EURO_LEAGUE_IDS:
        today_games = fetch_today_games(conn, league_id, phase)
    else:
        today_str = datetime.now().strftime("%Y-%m-%d")
        pending = SQL_FILTER_STILL_PENDING
        rows = conn.execute(
            f"""
            SELECT id, date, round_name, home_team_name, away_team_name, status_name
            FROM (
                SELECT id, date, round_name, home_team_name, away_team_name, status_name,
                       status, home_ft_result, away_ft_result
                FROM upcoming_games
                WHERE league_id=? AND substr(date,1,10)=? {pending}
                UNION
                SELECT id, date, round_name, home_team_name, away_team_name, status_name,
                       status, home_ft_result, away_ft_result
                FROM games
                WHERE league_id=? AND substr(date,1,10)=? {pending}
            ) ORDER BY date ASC
            """,
            (league_id, today_str, league_id, today_str),
        ).fetchall()
        today_games = [dict(r) for r in rows]

    # Saison für Spiele-Liste: Query-Jahr, sonst neueste mit Daten, sonst CURRENT_YEAR
    if year is not None:
        games_year = int(year)
    elif available_years:
        games_year = int(available_years[0])
    else:
        games_year = int(CURRENT_YEAR)

    games = _finished_games_for_year(conn, league_id, games_year, phase=phase)

    return {
        "league_id": league_id,
        "phase": phase,
        "years": years,
        "available_years": available_years,
        "games_year": games_year,
        "games": games,
        "games_n": len(games),
        "series": series,
        "today_games": [
            {
                "id": g.get("id"),
                "date": g.get("date"),
                "round": g.get("round_name") or g.get("round"),
                "home": g.get("home_team_name"),
                "away": g.get("away_team_name"),
                "status": g.get("status_name") or "Upcoming",
            }
            for g in today_games
        ],
    }
