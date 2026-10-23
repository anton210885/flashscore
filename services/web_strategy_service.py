"""Strategie-Backtest für die Web-API (gleiche Logik wie Tkinter StrategyTab)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services import strategy_service as strat

DB_PATH = "data/flashscore.db"


def _conn() -> sqlite3.Connection:
    # Schema inkl. Form2 richtet connect() einmal pro Prozess ein
    from database import connect

    return connect(DB_PATH, foreign_keys=False)


def _fnum(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _season_n_map(conn: sqlite3.Connection, league_ids: List[int], years: List[int]) -> Dict[Tuple[int, int, int], List[Tuple[str, int]]]:
    """Pro (league, season, team_id) chronologische game_ids für Saison-Spielnr."""
    if not league_ids or not years:
        return {}
    ph_l = ",".join("?" * len(league_ids))
    ph_y = ",".join("?" * len(years))
    rows = conn.execute(
        f"""
        SELECT id, league_id, season_year, date, home_team_id, away_team_id
        FROM games
        WHERE league_id IN ({ph_l})
          AND season_year IN ({ph_y})
          AND home_ft_result IS NOT NULL
          AND away_ft_result IS NOT NULL
          AND home_team_id IS NOT NULL
          AND away_team_id IS NOT NULL
        ORDER BY date ASC, id ASC
        """,
        (*league_ids, *years),
    ).fetchall()
    counts: Dict[Tuple[int, int, int], int] = {}
    game_team_n: Dict[Tuple[int, str], int] = {}

    for r in rows:
        lid = int(r["league_id"])
        yr = int(r["season_year"])
        gid = int(r["id"])
        for side, tid in (("h", int(r["home_team_id"])), ("a", int(r["away_team_id"]))):
            key = (lid, yr, tid)
            counts[key] = counts.get(key, 0) + 1
            game_team_n[(gid, side)] = counts[key]
    return game_team_n  # type: ignore[return-value]


def analyze(
    filters: Dict[str, Any],
    *,
    limit_results: int = 300,
    include_metric_rank: bool = False,
    rank_min_n: int = 40,
    skip_upcoming: bool = False,
    collect_results_out: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    markets = strat.selected_markets_from_filters(filters)
    if not markets:
        return {"ok": False, "error": "Mindestens einen Markt wählen.", "results": [], "metrics": {}}

    need_season = any(
        filters.get(k)
        for k in (
            "season_games_home_min",
            "season_games_home_max",
            "season_games_away_min",
            "season_games_away_max",
        )
    )

    query = """
        SELECT
            g.game_id, g.date, g.country_name, g.league_name, g.league_id, g.season_year,
            g.home_team_name, g.away_team_name, g.home_team_id, g.away_team_id,
            g.home_ft_result, g.away_ft_result,
            g.home_rating, g.away_rating,
            g.home_rd, g.away_rd,
            g.home_volatility, g.away_volatility,
            g.xg_home, g.xg_away, g.xg_glicko_home, g.xg_glicko_away,
            g.home_win_probability, g.away_win_probability, g.draw_probability,
            g.chance_home_win, g.chance_home_draw, g.chance_home_lose,
            g.chance_home_over_25, g.chance_home_under_25,
            g.chance_home_over_35, g.chance_home_under_35,
            g.chance_home_over_45, g.chance_home_under_45,
            g.games_count_home_win,
            f2.home_xg AS xg_form2_home,
            f2.away_xg AS xg_form2_away,
            f2.home_n AS form2_home_n,
            f2.away_n AS form2_away_n,
            f2.home_avg_xg AS form2_home_avg_xg,
            f2.home_avg_xga AS form2_home_avg_xga,
            f2.home_avg_gf AS form2_home_avg_gf,
            f2.home_avg_ga AS form2_home_avg_ga,
            f2.away_avg_xg AS form2_away_avg_xg,
            f2.away_avg_xga AS form2_away_avg_xga,
            f2.away_avg_gf AS form2_away_avg_gf,
            f2.away_avg_ga AS form2_away_avg_ga,
            f2.hometeam_home_n, f2.hometeam_home_xg, f2.hometeam_home_xga,
            f2.hometeam_home_gf, f2.hometeam_home_ga,
            f2.hometeam_away_n, f2.hometeam_away_xg, f2.hometeam_away_xga,
            f2.hometeam_away_gf, f2.hometeam_away_ga,
            f2.awayteam_home_n, f2.awayteam_home_xg, f2.awayteam_home_xga,
            f2.awayteam_home_gf, f2.awayteam_home_ga,
            f2.awayteam_away_n, f2.awayteam_away_xg, f2.awayteam_away_xga,
            f2.awayteam_away_gf, f2.awayteam_away_ga,
            f2.hometeam_pred_xg, f2.awayteam_pred_xg,
            o.odd_home, o.odd_draw, o.odd_away,
            o.odd_over_25, o.odd_under_25,
            o.odd_over_35, o.odd_under_35,
            o.odd_over_45, o.odd_under_45,
            o.odd_open_home, o.odd_open_draw, o.odd_open_away,
            o.odd_open_over_25, o.odd_open_under_25,
            o.odd_open_over_35, o.odd_open_under_35,
            o.odd_open_over_45, o.odd_open_under_45
        FROM game_details_view g
        LEFT JOIN game_odds_pivoted o ON g.game_id = o.game_id
        LEFT JOIN game_form2 f2 ON g.game_id = f2.game_id
        WHERE g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
    """
    params: List[Any] = []

    def add_ge(col: str, key: str):
        nonlocal query, params
        v = _fnum(filters.get(key))
        if v is not None:
            query += f" AND {col} >= ?"
            params.append(v)

    def add_le(col: str, key: str):
        nonlocal query, params
        v = _fnum(filters.get(key))
        if v is not None:
            query += f" AND {col} <= ?"
            params.append(v)

    rating_keys = ("glicko_home_min", "glicko_home_max", "glicko_away_min", "glicko_away_max")
    if any(filters.get(k) for k in rating_keys):
        query += " AND home_rating IS NOT NULL AND away_rating IS NOT NULL"
    add_ge("home_rating", "glicko_home_min")
    add_le("home_rating", "glicko_home_max")
    add_ge("away_rating", "glicko_away_min")
    add_le("away_rating", "glicko_away_max")

    rd_keys = (
        "glicko_rd_home_min", "glicko_rd_home_max",
        "glicko_rd_away_min", "glicko_rd_away_max",
    )
    if any(filters.get(k) for k in rd_keys):
        query += " AND home_rd IS NOT NULL AND away_rd IS NOT NULL"
    add_ge("home_rd", "glicko_rd_home_min")
    add_le("home_rd", "glicko_rd_home_max")
    add_ge("away_rd", "glicko_rd_away_min")
    add_le("away_rd", "glicko_rd_away_max")

    vol_keys = (
        "glicko_vol_home_min", "glicko_vol_home_max",
        "glicko_vol_away_min", "glicko_vol_away_max",
    )
    if any(filters.get(k) for k in vol_keys):
        query += " AND home_volatility IS NOT NULL AND away_volatility IS NOT NULL"
    add_ge("home_volatility", "glicko_vol_home_min")
    add_le("home_volatility", "glicko_vol_home_max")
    add_ge("away_volatility", "glicko_vol_away_min")
    add_le("away_volatility", "glicko_vol_away_max")

    # P(Win) in DB als 0–1; UI kann % liefern → in Python-Filter via normalize_chance
    # SQL nur setzen wenn klar 0–1 Werte
    def _prob_sql(col: str, min_key: str, max_key: str):
        nonlocal query, params
        vmin, vmax = _fnum(filters.get(min_key)), _fnum(filters.get(max_key))
        if vmin is not None:
            if vmin > 1.0:
                vmin = vmin / 100.0
            query += f" AND {col} IS NOT NULL AND {col} >= ?"
            params.append(vmin)
        if vmax is not None:
            if vmax > 1.0:
                vmax = vmax / 100.0
            query += f" AND {col} IS NOT NULL AND {col} <= ?"
            params.append(vmax)

    _prob_sql("home_win_probability", "glicko_p_home_min", "glicko_p_home_max")
    _prob_sql("draw_probability", "glicko_p_draw_min", "glicko_p_draw_max")
    _prob_sql("away_win_probability", "glicko_p_away_min", "glicko_p_away_max")

    xg_keys = (
        "xg_glicko_home_min",
        "xg_glicko_home_max",
        "xg_glicko_away_min",
        "xg_glicko_away_max",
    )
    if any(filters.get(k) for k in xg_keys):
        query += " AND xg_glicko_home IS NOT NULL AND xg_glicko_away IS NOT NULL"
    add_ge("xg_glicko_home", "xg_glicko_home_min")
    add_le("xg_glicko_home", "xg_glicko_home_max")
    add_ge("xg_glicko_away", "xg_glicko_away_min")
    add_le("xg_glicko_away", "xg_glicko_away_max")

    xg_match_keys = (
        "xg_match_home_min",
        "xg_match_home_max",
        "xg_match_away_min",
        "xg_match_away_max",
    )
    if any(filters.get(k) for k in xg_match_keys):
        query += " AND xg_home IS NOT NULL AND xg_away IS NOT NULL"
    add_ge("xg_home", "xg_match_home_min")
    add_le("xg_home", "xg_match_home_max")
    add_ge("xg_away", "xg_match_away_min")
    add_le("xg_away", "xg_match_away_max")

    if filters.get("country_filter"):
        query += " AND country_name LIKE ?"
        params.append(f"%{filters['country_filter']}%")
    if filters.get("league_filter"):
        query += " AND league_name LIKE ?"
        params.append(f"%{filters['league_filter']}%")
    if filters.get("date_from"):
        query += " AND date(g.date) >= date(?)"
        params.append(filters["date_from"])
    if filters.get("date_to"):
        query += " AND date(g.date) <= date(?)"
        params.append(filters["date_to"])

    mg = _fnum(filters.get("min_games_count"))
    if mg is not None and mg > 0:
        query += " AND games_count_home_win >= ?"
        params.append(mg)

    query += " ORDER BY g.date DESC LIMIT 12000"

    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        season_map: Dict[Any, int] = {}
        if rows and (need_season or True):
            lids = sorted({int(r["league_id"]) for r in rows if r.get("league_id") is not None})
            years = sorted({int(r["season_year"]) for r in rows if r.get("season_year") is not None})
            season_map = _season_n_map(conn, lids, years)  # type: ignore[assignment]
    finally:
        conn.close()

    for r in rows:
        gid = int(r["game_id"])
        r["home_season_n"] = season_map.get((gid, "h"))
        r["away_season_n"] = season_map.get((gid, "a"))

    if need_season:
        filtered = []
        for r in rows:
            if not strat.passes_season_game_no(
                filters, r.get("home_season_n"), r.get("away_season_n")
            ):
                continue
            filtered.append(r)
        rows = filtered

    odds_type = filters.get("odds_type") or "closing"
    chance_by_market = {
        "Home": "chance_home_win",
        "Draw": "chance_home_draw",
        "Away": "chance_home_lose",
        "Over 2.5": "chance_home_over_25",
        "Under 2.5": "chance_home_under_25",
        "Over 3.5": "chance_home_over_35",
        "Under 3.5": "chance_home_under_35",
        "Over 4.5": "chance_home_over_45",
        "Under 4.5": "chance_home_under_45",
    }

    results: List[Dict[str, Any]] = []
    for rd in rows:
        home_score = rd.get("home_ft_result")
        away_score = rd.get("away_ft_result")
        xg_ctx = {
            "xg_h": rd.get("xg_home"),  # tatsächliche Match-xG
            "xg_a": rd.get("xg_away"),
            "xg_glicko_h": rd.get("xg_glicko_home"),  # Glicko-Vorhersage
            "xg_glicko_a": rd.get("xg_glicko_away"),
            "xg_form2_h": rd.get("xg_form2_home"),
            "xg_form2_a": rd.get("xg_form2_away"),
            "form2_home_avg_xg": rd.get("form2_home_avg_xg"),
            "form2_home_avg_xga": rd.get("form2_home_avg_xga"),
            "form2_home_avg_gf": rd.get("form2_home_avg_gf"),
            "form2_home_avg_ga": rd.get("form2_home_avg_ga"),
            "form2_away_avg_xg": rd.get("form2_away_avg_xg"),
            "form2_away_avg_xga": rd.get("form2_away_avg_xga"),
            "form2_away_avg_gf": rd.get("form2_away_avg_gf"),
            "form2_away_avg_ga": rd.get("form2_away_avg_ga"),
            "hometeam_home_xg": rd.get("hometeam_home_xg"),
            "hometeam_home_xga": rd.get("hometeam_home_xga"),
            "hometeam_home_gf": rd.get("hometeam_home_gf"),
            "hometeam_home_ga": rd.get("hometeam_home_ga"),
            "hometeam_away_xg": rd.get("hometeam_away_xg"),
            "hometeam_away_xga": rd.get("hometeam_away_xga"),
            "hometeam_away_gf": rd.get("hometeam_away_gf"),
            "hometeam_away_ga": rd.get("hometeam_away_ga"),
            "awayteam_home_xg": rd.get("awayteam_home_xg"),
            "awayteam_home_xga": rd.get("awayteam_home_xga"),
            "awayteam_home_gf": rd.get("awayteam_home_gf"),
            "awayteam_home_ga": rd.get("awayteam_home_ga"),
            "awayteam_away_xg": rd.get("awayteam_away_xg"),
            "awayteam_away_xga": rd.get("awayteam_away_xga"),
            "awayteam_away_gf": rd.get("awayteam_away_gf"),
            "awayteam_away_ga": rd.get("awayteam_away_ga"),
            "hometeam_pred_xg": rd.get("hometeam_pred_xg"),
            "awayteam_pred_xg": rd.get("awayteam_pred_xg"),
            "rating_h": rd.get("home_rating"),
            "rating_a": rd.get("away_rating"),
            "rd_h": rd.get("home_rd"),
            "rd_a": rd.get("away_rd"),
            "vol_h": rd.get("home_volatility"),
            "vol_a": rd.get("away_volatility"),
            "p_home": rd.get("home_win_probability"),
            "p_draw": rd.get("draw_probability"),
            "p_away": rd.get("away_win_probability"),
        }
        if not strat.passes_ft_outcome(filters, home_score, away_score):
            continue
        for market in markets:
            odds = strat.pick_odds(rd, market, odds_type)
            if odds is None or odds <= 1.0:
                continue
            profit = strat.settle_market(market, home_score, away_score, odds)
            if profit is None:
                continue
            chance = rd.get(chance_by_market.get(market, ""), None)
            if not strat.match_prematch_filters(
                filters,
                market=market,
                odds=odds,
                chance=chance,
                rating_h=rd.get("home_rating"),
                rating_a=rd.get("away_rating"),
                country=rd.get("country_name"),
                league=rd.get("league_name"),
                games_count=rd.get("games_count_home_win"),
                xg_ctx=xg_ctx,
                home_season_n=rd.get("home_season_n"),
                away_season_n=rd.get("away_season_n"),
            ):
                continue
            o_open = strat.pick_odds(rd, market, "opening")
            o_close = strat.pick_odds(rd, market, "closing")
            xroi_pct = strat.compute_xroi_pct(o_open, o_close)
            if not strat.passes_xroi_range(filters, xroi_pct):
                continue
            if not strat.passes_bet_roi_range(filters, profit):
                continue
            results.append(
                {
                    "game_id": rd.get("game_id"),
                    "date": rd.get("date"),
                    "home": rd.get("home_team_name"),
                    "away": rd.get("away_team_name"),
                    "league": rd.get("league_name"),
                    "country": rd.get("country_name"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "market": market,
                    "odds": odds,
                    "odds_opening": o_open,
                    "odds_closing": o_close,
                    "xroi_pct": xroi_pct,
                    "profit": profit,
                    "chance": chance,
                    "home_quote": strat.pick_odds(rd, "Home", odds_type),
                    "draw_quote": strat.pick_odds(rd, "Draw", odds_type),
                    "away_quote": strat.pick_odds(rd, "Away", odds_type),
                    "over_25_quote": strat.pick_odds(rd, "Over 2.5", odds_type),
                    "under_25_quote": strat.pick_odds(rd, "Under 2.5", odds_type),
                    "odd_home": rd.get("odd_home"),
                    "odd_draw": rd.get("odd_draw"),
                    "odd_away": rd.get("odd_away"),
                    "odd_over_25": rd.get("odd_over_25"),
                    "odd_under_25": rd.get("odd_under_25"),
                    "rating_h": rd.get("home_rating"),
                    "rating_a": rd.get("away_rating"),
                    "rd_h": rd.get("home_rd"),
                    "rd_a": rd.get("away_rd"),
                    "vol_h": rd.get("home_volatility"),
                    "vol_a": rd.get("away_volatility"),
                    "xg_glicko_h": rd.get("xg_glicko_home"),
                    "xg_glicko_a": rd.get("xg_glicko_away"),
                    "xg_form2_h": rd.get("xg_form2_home"),
                    "xg_form2_a": rd.get("xg_form2_away"),
                    "form2_home_n": rd.get("form2_home_n"),
                    "form2_away_n": rd.get("form2_away_n"),
                    "form2_home_avg_xg": rd.get("form2_home_avg_xg"),
                    "form2_home_avg_xga": rd.get("form2_home_avg_xga"),
                    "form2_home_avg_gf": rd.get("form2_home_avg_gf"),
                    "form2_home_avg_ga": rd.get("form2_home_avg_ga"),
                    "form2_away_avg_xg": rd.get("form2_away_avg_xg"),
                    "form2_away_avg_xga": rd.get("form2_away_avg_xga"),
                    "form2_away_avg_gf": rd.get("form2_away_avg_gf"),
                    "form2_away_avg_ga": rd.get("form2_away_avg_ga"),
                    "hometeam_home_n": rd.get("hometeam_home_n"),
                    "hometeam_home_xg": rd.get("hometeam_home_xg"),
                    "hometeam_home_xga": rd.get("hometeam_home_xga"),
                    "hometeam_home_gf": rd.get("hometeam_home_gf"),
                    "hometeam_home_ga": rd.get("hometeam_home_ga"),
                    "hometeam_away_n": rd.get("hometeam_away_n"),
                    "hometeam_away_xg": rd.get("hometeam_away_xg"),
                    "hometeam_away_xga": rd.get("hometeam_away_xga"),
                    "hometeam_away_gf": rd.get("hometeam_away_gf"),
                    "hometeam_away_ga": rd.get("hometeam_away_ga"),
                    "awayteam_home_n": rd.get("awayteam_home_n"),
                    "awayteam_home_xg": rd.get("awayteam_home_xg"),
                    "awayteam_home_xga": rd.get("awayteam_home_xga"),
                    "awayteam_home_gf": rd.get("awayteam_home_gf"),
                    "awayteam_home_ga": rd.get("awayteam_home_ga"),
                    "awayteam_away_n": rd.get("awayteam_away_n"),
                    "awayteam_away_xg": rd.get("awayteam_away_xg"),
                    "awayteam_away_xga": rd.get("awayteam_away_xga"),
                    "awayteam_away_gf": rd.get("awayteam_away_gf"),
                    "awayteam_away_ga": rd.get("awayteam_away_ga"),
                    "hometeam_pred_xg": rd.get("hometeam_pred_xg"),
                    "awayteam_pred_xg": rd.get("awayteam_pred_xg"),
                    "xg_h": rd.get("xg_home"),
                    "xg_a": rd.get("xg_away"),
                    "xg_match_h": rd.get("xg_home"),
                    "xg_match_a": rd.get("xg_away"),
                    "p_home": rd.get("home_win_probability"),
                    "p_draw": rd.get("draw_probability"),
                    "p_away": rd.get("away_win_probability"),
                    "home_season_n": rd.get("home_season_n"),
                    "away_season_n": rd.get("away_season_n"),
                }
            )

    n_before_pct = len(results)
    pct_info: Dict[str, Any] = {
        "enabled": False,
        "percentile": None,
        "metric": None,
        "threshold": None,
        "n_before": n_before_pct,
        "n_after": n_before_pct,
    }
    if filters.get("use_percentile"):
        try:
            pct = float(filters.get("percentile_value") or 10)
        except (TypeError, ValueError):
            pct = 10.0
        metric = str(filters.get("percentile_metric") or "chance")
        thr = strat.percentile_threshold(results, pct, metric)
        results = strat.apply_percentile_filter(results, pct, metric)
        pct_info = {
            "enabled": True,
            "percentile": pct,
            "metric": metric,
            "threshold": thr,
            "n_before": n_before_pct,
            "n_after": len(results),
            "look_ahead": metric == "profit",
        }

    metrics = strat.compute_strategy_metrics(results)
    metrics["percentile"] = pct_info
    if collect_results_out is not None:
        collect_results_out.clear()
        collect_results_out.extend(results)
    # Pro-Markt auf denselben Spielen wie die Strategie-Treffer (nicht neu filtern)
    matched_gids = {r.get("game_id") for r in results if r.get("game_id") is not None}
    game_by_id: Dict[Any, Dict[str, Any]] = {}
    for rd in rows:
        gid = rd.get("game_id")
        if gid in matched_gids and gid not in game_by_id:
            game_by_id[gid] = rd
    alt_markets = strat.compute_per_market_stats(
        list(game_by_id.values()),
        filters,
        selected_markets=markets,
        odds_type=odds_type,
        only_unselected=False,
        skip_prematch_filters=True,
    )
    # Gewählte Märkte oben
    alt_markets.sort(key=lambda r: (0 if r.get("selected") else 1, r.get("market") or ""))
    out = {
        "ok": True,
        "markets": markets,
        "odds_type": odds_type,
        "scanned_rows": len(rows),
        "n": len(results),
        "metrics": metrics,
        "results": results[: max(1, min(int(limit_results), 1000))],
        "truncated": len(results) > limit_results,
        "percentile": pct_info,
        "alt_markets": alt_markets,
    }
    if include_metric_rank:
        mn = max(20, min(int(rank_min_n or 40), max(20, len(results) // 10 or 20)))
        out["metric_rank"] = strat.rank_metrics_influence(
            results, min_n=mn, sort_by="roi"
        )
    if skip_upcoming:
        out["upcoming"] = {
            "ok": True,
            "matches": [],
            "n": 0,
            "xroi_n": 0,
            "skipped": True,
            "skip_reason": "metric_rank_only",
            "message": "Upcoming bei Metric-Ranking übersprungen.",
        }
        return out
    # Upcoming nur ohne Look-ahead-Filter (FT-Ergebnis / Einzelwetten-ROI)
    if strat.upcoming_blocked_by_lookahead(filters):
        if strat.match_xg_filter_active(filters):
            reason = "match_xg"
            msg = (
                "Bevorstehende Spiele ausgeblendet: Match-xG-Filter braucht die im Spiel "
                "erzielten xG (erst nach dem Match bekannt)."
            )
        elif strat.bet_roi_filter_active(filters):
            reason = "roi"
            msg = "Bevorstehende Spiele ausgeblendet: ROI-Filter braucht Settlement (Endstand)."
        else:
            reason = "ft_outcome"
            msg = (
                "Bevorstehende Spiele ausgeblendet: Ergebnis-Filter (Home/Draw/Away/O-U) braucht Endstand."
            )
        out["upcoming"] = {
            "ok": True,
            "matches": [],
            "n": 0,
            "xroi_n": 0,
            "skipped": True,
            "skip_reason": reason,
            "error": None,
            "message": msg,
        }
        return out
    try:
        upcoming = find_upcoming(filters, limit=min(300, int(limit_results) + 100))
        # Prematch-Percentile-Schwelle auch auf Upcoming anwenden
        if (
            pct_info.get("enabled")
            and pct_info.get("threshold") is not None
            and pct_info.get("metric") in strat.PREMATCH_PERCENTILE_METRICS
            and upcoming.get("ok")
        ):
            matched = strat.filter_by_metric_threshold(
                upcoming.get("matches") or [],
                str(pct_info["metric"]),
                float(pct_info["threshold"]),
            )
            xrois = [m["xroi_pct"] for m in matched if m.get("xroi_pct") is not None]
            xroi_n = len(xrois)
            upcoming = {
                **upcoming,
                "n": len(matched),
                "matches": matched,
                "avg_xroi_pct": (sum(xrois) / xroi_n) if xroi_n else None,
                "xroi_n": xroi_n,
                "truncated": False,
                "percentile_applied": True,
                "percentile_threshold": pct_info["threshold"],
            }
        out["upcoming"] = upcoming
    except Exception as e:
        out["upcoming"] = {"ok": False, "error": str(e), "matches": [], "n": 0, "xroi_n": 0}
    return out


def _upcoming_rows_from_db(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bevorstehende Spiele ab gestern — ohne Join auf fertige games-Zeilen."""
    since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    until = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    # Zuerst IDs/Ligen laden, Form2-Snapshots nachziehen, dann mit JOIN lesen
    base_rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT u.id AS game_id, u.league_id, u.season_year,
                   u.home_team_id, u.away_team_id
            FROM upcoming_games u
            WHERE substr(replace(COALESCE(u.date, ''), 'T', ' '), 1, 10) BETWEEN ? AND ?
              AND (u.home_ft_result IS NULL OR u.away_ft_result IS NULL)
              AND IFNULL(u.status, 0) NOT IN (7, 8, 9, 10, 15)
            LIMIT 4000
            """,
            (since, until),
        ).fetchall()
    ]
    try:
        from services.form2_service import ensure_form2_for_upcoming_rows

        ensure_form2_for_upcoming_rows(conn, base_rows)
    except Exception:
        pass

    sql = """
        SELECT
            u.id AS game_id,
            COALESCE(u.date, u.date_utc) AS date,
            u.status, u.status_name,
            u.country_name, u.league_name, u.league_id,
            u.home_team_name, u.away_team_name,
            u.home_team_id, u.away_team_id, u.season_year,
            gl.home_rating, gl.home_rd, gl.home_volatility,
            gl.away_rating, gl.away_rd, gl.away_volatility,
            gl.home_xg AS xg_glicko_home, gl.away_xg AS xg_glicko_away,
            gl.home_win_probability, gl.away_win_probability, gl.draw_probability,
            f2.home_xg AS xg_form2_home,
            f2.away_xg AS xg_form2_away,
            f2.home_n AS form2_home_n,
            f2.away_n AS form2_away_n,
            f2.home_avg_xg AS form2_home_avg_xg,
            f2.home_avg_xga AS form2_home_avg_xga,
            f2.home_avg_gf AS form2_home_avg_gf,
            f2.home_avg_ga AS form2_home_avg_ga,
            f2.away_avg_xg AS form2_away_avg_xg,
            f2.away_avg_xga AS form2_away_avg_xga,
            f2.away_avg_gf AS form2_away_avg_gf,
            f2.away_avg_ga AS form2_away_avg_ga,
            f2.hometeam_home_n, f2.hometeam_home_xg, f2.hometeam_home_xga,
            f2.hometeam_home_gf, f2.hometeam_home_ga,
            f2.hometeam_away_n, f2.hometeam_away_xg, f2.hometeam_away_xga,
            f2.hometeam_away_gf, f2.hometeam_away_ga,
            f2.awayteam_home_n, f2.awayteam_home_xg, f2.awayteam_home_xga,
            f2.awayteam_home_gf, f2.awayteam_home_ga,
            f2.awayteam_away_n, f2.awayteam_away_xg, f2.awayteam_away_xga,
            f2.awayteam_away_gf, f2.awayteam_away_ga,
            f2.hometeam_pred_xg, f2.awayteam_pred_xg,
            o.odd_home, o.odd_draw, o.odd_away,
            o.odd_over_25, o.odd_under_25,
            o.odd_over_35, o.odd_under_35,
            o.odd_over_45, o.odd_under_45,
            o.odd_open_home, o.odd_open_draw, o.odd_open_away,
            o.odd_open_over_25, o.odd_open_under_25,
            o.odd_open_over_35, o.odd_open_under_35,
            o.odd_open_over_45, o.odd_open_under_45
        FROM upcoming_games u
        LEFT JOIN game_glicko gl ON gl.game_id = u.id
        LEFT JOIN game_form2 f2 ON f2.game_id = u.id
        LEFT JOIN game_odds_pivoted o ON o.game_id = u.id
        WHERE substr(replace(COALESCE(u.date, ''), 'T', ' '), 1, 10) BETWEEN ? AND ?
          AND (u.home_ft_result IS NULL OR u.away_ft_result IS NULL)
          AND IFNULL(u.status, 0) NOT IN (7, 8, 9, 10, 15)
          AND (
                lower(COALESCE(u.status_name, '')) LIKE '%not started%'
                OR lower(COALESCE(u.status_name, '')) LIKE '%scheduled%'
                OR IFNULL(u.status, 0) IN (0, 1)
              )
          AND lower(COALESCE(u.status_name, '')) NOT LIKE '%finished%'
          AND lower(COALESCE(u.status_name, '')) NOT LIKE '%cancelled%'
          AND lower(COALESCE(u.status_name, '')) NOT LIKE '%1st half%'
          AND lower(COALESCE(u.status_name, '')) NOT LIKE '%2nd half%'
        ORDER BY date ASC
        LIMIT 4000
    """
    return [dict(r) for r in conn.execute(sql, (since, until)).fetchall()]


def metric_rank(
    filters: Dict[str, Any],
    *,
    min_n: int = 40,
    sort_by: str = "roi",
) -> Dict[str, Any]:
    """Welche Metric-Schwellen ROI oder Profit vs. Baseline am stärksten verbessern."""
    analysis = analyze(
        filters or {},
        limit_results=500,
        include_metric_rank=True,
        rank_min_n=min_n,
        skip_upcoming=True,
    )
    if not analysis.get("ok"):
        return analysis
    report = analysis.get("metric_rank") or {"baseline": {}, "ranked": [], "min_n": min_n}
    # Neu sortieren falls Client sort_by=profit will (analyze speichert default ROI)
    ranked = list(report.get("ranked") or [])
    sb = (sort_by or "roi").strip().lower()
    if sb in ("profit", "profit_delta", "delta_profit"):
        ranked.sort(
            key=lambda x: (
                float(x.get("profit_delta") or 0),
                float(x.get("roi_delta") or 0),
                int(x.get("n") or 0),
            ),
            reverse=True,
        )
        sort_mode = "profit"
    else:
        ranked.sort(
            key=lambda x: (
                float(x.get("roi_delta") or 0),
                float(x.get("profit_delta") or 0),
                int(x.get("n") or 0),
            ),
            reverse=True,
        )
        sort_mode = "roi"
    return {
        "ok": True,
        "n": analysis.get("n") or 0,
        "markets": analysis.get("markets") or [],
        "baseline": report.get("baseline") or analysis.get("metrics") or {},
        "ranked": ranked,
        "min_n": report.get("min_n") or min_n,
        "sort_by": sort_mode,
        "metrics": analysis.get("metrics") or {},
    }


def optimize_params(
    filters: Dict[str, Any],
    *,
    min_n: int = 25,
    max_params: int = 2,
    top_k: int = 15,
) -> Dict[str, Any]:
    """Findet 1–2 Parameter (inkl. optimale Quote) mit maximalem Profit vs. Baseline-Filtern."""
    buf: List[Dict[str, Any]] = []
    analysis = analyze(
        filters or {},
        limit_results=500,
        skip_upcoming=True,
        collect_results_out=buf,
    )
    if not analysis.get("ok"):
        return analysis
    markets = analysis.get("markets") or strat.selected_markets_from_filters(filters or {})
    report = strat.optimize_two_params(
        buf,
        markets=markets,
        min_n=max(5, int(min_n or 25)),
        max_params=max(1, min(int(max_params or 2), 2)),
        top_k=max(1, min(int(top_k or 15), 40)),
    )
    return {
        "ok": True,
        "n": len(buf),
        "markets": markets,
        "baseline": report.get("baseline") or analysis.get("metrics") or {},
        **report,
    }


def metric_buckets(
    filters: Dict[str, Any],
    *,
    metric: str = "rating_diff",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    step: Optional[float] = None,
    target_bins: int = 16,
) -> Dict[str, Any]:
    """Profit/ROI je Parameter-Bin (Grafik) — gleicher Baustein wie Desktop Bucket-Analyse."""
    metric = str(metric or "rating_diff").strip()
    if metric.startswith("xg_match") or metric in ("xg_home_match", "xg_away_match"):
        return {
            "ok": False,
            "error": "Match-xG ist Look-ahead und nicht in der Parameter-Grafik verfügbar.",
            "bins": [],
        }
    allowed = set(strat.RANKABLE_METRICS) | set(strat.BUCKET_METRICS)
    if metric not in allowed:
        return {"ok": False, "error": f"Unbekannte Metrik: {metric}", "bins": []}
    buf: List[Dict[str, Any]] = []
    analysis = analyze(
        filters or {},
        limit_results=100,
        skip_upcoming=True,
        collect_results_out=buf,
    )
    if not analysis.get("ok"):
        return analysis
    report = strat.auto_bucket_metric(
        buf,
        metric,
        vmin=vmin,
        vmax=vmax,
        step=step,
        target_bins=max(4, min(int(target_bins or 16), 40)),
    )
    if not report.get("ok"):
        return {
            "ok": False,
            "error": report.get("error") or "Bucket-Analyse fehlgeschlagen.",
            "n": len(buf),
            "metric": metric,
            "bins": [],
        }
    return {
        "ok": True,
        "n": len(buf),
        "markets": analysis.get("markets") or [],
        "baseline": analysis.get("metrics") or {},
        **report,
    }


def find_upcoming(filters: Dict[str, Any], *, limit: int = 200) -> Dict[str, Any]:
    """Bevorstehende Spiele, die zu den Strategie-Filtern passen (+ Open/Close/xROI)."""
    if strat.upcoming_blocked_by_lookahead(filters):
        reason = "roi" if strat.bet_roi_filter_active(filters) else "ft_outcome"
        return {
            "ok": True,
            "matches": [],
            "n": 0,
            "xroi_n": 0,
            "skipped": True,
            "skip_reason": reason,
            "message": (
                "Bevorstehende Spiele ausgeblendet: ROI-Filter braucht Settlement (Endstand)."
                if reason == "roi"
                else "Bevorstehende Spiele ausgeblendet: Ergebnis-Filter braucht Endstand."
            ),
        }
    markets = strat.selected_markets_from_filters(filters)
    if not markets:
        return {
            "ok": False,
            "error": "Mindestens einen Markt wählen.",
            "matches": [],
            "n": 0,
            "xroi_n": 0,
        }

    odds_type = filters.get("odds_type") or "closing"
    conn = _conn()
    try:
        rows = _upcoming_rows_from_db(conn)
    finally:
        conn.close()

    # Today-API ergänzen (Quoten oft nur dort), falls DB dünn
    try:
        from services.web_games_service import _fetch_today_from_api

        api_games = _fetch_today_from_api()
        by_id = {int(r["game_id"]): r for r in rows}
        for g in api_games:
            gid = int(g["id"])
            if gid in by_id:
                rd = by_id[gid]
                # fehlende Closing aus API füllen
                if rd.get("odd_home") is None and g.get("odd_home") is not None:
                    rd["odd_home"] = g.get("odd_home")
                    rd["odd_draw"] = g.get("odd_draw")
                    rd["odd_away"] = g.get("odd_away")
                    rd["odd_over_25"] = g.get("odd_over_25")
                    rd["odd_under_25"] = g.get("odd_under_25")
                continue
            # neues Upcoming aus API
            if (g.get("status_bucket") or "") not in ("not_started", "live"):
                continue
            rows.append(
                {
                    "game_id": gid,
                    "date": g.get("date"),
                    "status": g.get("status"),
                    "status_name": g.get("status_name"),
                    "country_name": g.get("country"),
                    "league_name": g.get("league"),
                    "league_id": g.get("league_id"),
                    "home_team_name": g.get("home"),
                    "away_team_name": g.get("away"),
                    "home_rating": None,
                    "away_rating": None,
                    "xg_glicko_home": None,
                    "xg_glicko_away": None,
                    "odd_home": g.get("odd_home"),
                    "odd_draw": g.get("odd_draw"),
                    "odd_away": g.get("odd_away"),
                    "odd_over_25": g.get("odd_over_25"),
                    "odd_under_25": g.get("odd_under_25"),
                    "odd_over_35": None,
                    "odd_under_35": None,
                    "odd_over_45": None,
                    "odd_under_45": None,
                    "odd_open_home": None,
                    "odd_open_draw": None,
                    "odd_open_away": None,
                    "odd_open_over_25": None,
                    "odd_open_under_25": None,
                    "odd_open_over_35": None,
                    "odd_open_under_35": None,
                    "odd_open_over_45": None,
                    "odd_open_under_45": None,
                }
            )
        # Glicko für API-only nachziehen aus DB
        conn = _conn()
        try:
            ids = [int(r["game_id"]) for r in rows if r.get("xg_glicko_home") is None]
            for i in range(0, len(ids), 400):
                chunk = ids[i : i + 400]
                ph = ",".join("?" * len(chunk))
                for gr in conn.execute(
                    f"""
                    SELECT game_id,
                           home_rating, home_rd, home_volatility,
                           away_rating, away_rd, away_volatility,
                           home_xg, away_xg,
                           home_win_probability, away_win_probability, draw_probability
                    FROM game_glicko WHERE game_id IN ({ph})
                    """,
                    chunk,
                ).fetchall():
                    for r in rows:
                        if int(r["game_id"]) == int(gr["game_id"]):
                            r["home_rating"] = gr["home_rating"]
                            r["home_rd"] = gr["home_rd"]
                            r["home_volatility"] = gr["home_volatility"]
                            r["away_rating"] = gr["away_rating"]
                            r["away_rd"] = gr["away_rd"]
                            r["away_volatility"] = gr["away_volatility"]
                            r["xg_glicko_home"] = gr["home_xg"]
                            r["xg_glicko_away"] = gr["away_xg"]
                            r["home_win_probability"] = gr["home_win_probability"]
                            r["away_win_probability"] = gr["away_win_probability"]
                            r["draw_probability"] = gr["draw_probability"]
        finally:
            conn.close()
    except Exception:
        pass

    matches: List[Dict[str, Any]] = []
    for rd in rows:
        xg_ctx = {
            "xg_h": None,  # Match-xG vor Anpfiff unbekannt
            "xg_a": None,
            "xg_glicko_h": rd.get("xg_glicko_home"),
            "xg_glicko_a": rd.get("xg_glicko_away"),
            "xg_form2_h": rd.get("xg_form2_home"),
            "xg_form2_a": rd.get("xg_form2_away"),
            "form2_home_avg_xg": rd.get("form2_home_avg_xg"),
            "form2_home_avg_xga": rd.get("form2_home_avg_xga"),
            "form2_home_avg_gf": rd.get("form2_home_avg_gf"),
            "form2_home_avg_ga": rd.get("form2_home_avg_ga"),
            "form2_away_avg_xg": rd.get("form2_away_avg_xg"),
            "form2_away_avg_xga": rd.get("form2_away_avg_xga"),
            "form2_away_avg_gf": rd.get("form2_away_avg_gf"),
            "form2_away_avg_ga": rd.get("form2_away_avg_ga"),
            "hometeam_home_xg": rd.get("hometeam_home_xg"),
            "hometeam_home_xga": rd.get("hometeam_home_xga"),
            "hometeam_home_gf": rd.get("hometeam_home_gf"),
            "hometeam_home_ga": rd.get("hometeam_home_ga"),
            "hometeam_away_xg": rd.get("hometeam_away_xg"),
            "hometeam_away_xga": rd.get("hometeam_away_xga"),
            "hometeam_away_gf": rd.get("hometeam_away_gf"),
            "hometeam_away_ga": rd.get("hometeam_away_ga"),
            "awayteam_home_xg": rd.get("awayteam_home_xg"),
            "awayteam_home_xga": rd.get("awayteam_home_xga"),
            "awayteam_home_gf": rd.get("awayteam_home_gf"),
            "awayteam_home_ga": rd.get("awayteam_home_ga"),
            "awayteam_away_xg": rd.get("awayteam_away_xg"),
            "awayteam_away_xga": rd.get("awayteam_away_xga"),
            "awayteam_away_gf": rd.get("awayteam_away_gf"),
            "awayteam_away_ga": rd.get("awayteam_away_ga"),
            "hometeam_pred_xg": rd.get("hometeam_pred_xg"),
            "awayteam_pred_xg": rd.get("awayteam_pred_xg"),
            "rating_h": rd.get("home_rating"),
            "rating_a": rd.get("away_rating"),
            "rd_h": rd.get("home_rd"),
            "rd_a": rd.get("away_rd"),
            "vol_h": rd.get("home_volatility"),
            "vol_a": rd.get("away_volatility"),
            "p_home": rd.get("home_win_probability"),
            "p_draw": rd.get("draw_probability"),
            "p_away": rd.get("away_win_probability"),
        }
        for market in markets:
            odds = strat.pick_odds(rd, market, odds_type)
            # Fallback: Closing wenn Opening gewählt aber fehlt
            if (odds is None or odds <= 1.0) and odds_type == "opening":
                odds = strat.pick_odds(rd, market, "closing")
            if odds is None or odds <= 1.0:
                continue
            if not strat.match_prematch_filters(
                filters,
                market=market,
                odds=odds,
                chance=None,
                rating_h=rd.get("home_rating"),
                rating_a=rd.get("away_rating"),
                country=rd.get("country_name"),
                league=rd.get("league_name"),
                games_count=None,
                xg_ctx=xg_ctx,
                allow_missing_stats=True,
            ):
                continue
            o_open = strat.pick_odds(rd, market, "opening")
            o_close = strat.pick_odds(rd, market, "closing")
            xroi_pct = strat.compute_xroi_pct(o_open, o_close)
            if not strat.passes_xroi_range(filters, xroi_pct):
                continue
            matches.append(
                {
                    "game_id": rd.get("game_id"),
                    "date": rd.get("date"),
                    "home": rd.get("home_team_name"),
                    "away": rd.get("away_team_name"),
                    "league": rd.get("league_name"),
                    "country": rd.get("country_name"),
                    "market": market,
                    "odds": odds,
                    "odds_opening": o_open,
                    "odds_closing": o_close,
                    "xroi_pct": xroi_pct,
                    "rating_h": rd.get("home_rating"),
                    "rating_a": rd.get("away_rating"),
                    "rd_h": rd.get("home_rd"),
                    "rd_a": rd.get("away_rd"),
                    "vol_h": rd.get("home_volatility"),
                    "vol_a": rd.get("away_volatility"),
                    "xg_glicko_h": rd.get("xg_glicko_home"),
                    "xg_glicko_a": rd.get("xg_glicko_away"),
                    "xg_form2_h": rd.get("xg_form2_home"),
                    "xg_form2_a": rd.get("xg_form2_away"),
                    "form2_home_avg_xg": rd.get("form2_home_avg_xg"),
                    "form2_home_avg_xga": rd.get("form2_home_avg_xga"),
                    "form2_home_avg_gf": rd.get("form2_home_avg_gf"),
                    "form2_home_avg_ga": rd.get("form2_home_avg_ga"),
                    "form2_away_avg_xg": rd.get("form2_away_avg_xg"),
                    "form2_away_avg_xga": rd.get("form2_away_avg_xga"),
                    "form2_away_avg_gf": rd.get("form2_away_avg_gf"),
                    "form2_away_avg_ga": rd.get("form2_away_avg_ga"),
                    "hometeam_home_xg": rd.get("hometeam_home_xg"),
                    "hometeam_home_xga": rd.get("hometeam_home_xga"),
                    "hometeam_home_gf": rd.get("hometeam_home_gf"),
                    "hometeam_home_ga": rd.get("hometeam_home_ga"),
                    "hometeam_away_xg": rd.get("hometeam_away_xg"),
                    "hometeam_away_xga": rd.get("hometeam_away_xga"),
                    "hometeam_away_gf": rd.get("hometeam_away_gf"),
                    "hometeam_away_ga": rd.get("hometeam_away_ga"),
                    "awayteam_home_xg": rd.get("awayteam_home_xg"),
                    "awayteam_home_xga": rd.get("awayteam_home_xga"),
                    "awayteam_home_gf": rd.get("awayteam_home_gf"),
                    "awayteam_home_ga": rd.get("awayteam_home_ga"),
                    "awayteam_away_xg": rd.get("awayteam_away_xg"),
                    "awayteam_away_xga": rd.get("awayteam_away_xga"),
                    "awayteam_away_gf": rd.get("awayteam_away_gf"),
                    "awayteam_away_ga": rd.get("awayteam_away_ga"),
                    "hometeam_pred_xg": rd.get("hometeam_pred_xg"),
                    "awayteam_pred_xg": rd.get("awayteam_pred_xg"),
                    "p_home": rd.get("home_win_probability"),
                    "p_draw": rd.get("draw_probability"),
                    "p_away": rd.get("away_win_probability"),
                }
            )

    xrois = [m["xroi_pct"] for m in matches if m.get("xroi_pct") is not None]
    xroi_n = len(xrois)
    lim = max(0, min(int(limit), 1000))
    return {
        "ok": True,
        "markets": markets,
        "odds_type": odds_type,
        "scanned": len(rows),
        "n": len(matches),
        "avg_xroi_pct": (sum(xrois) / xroi_n) if xroi_n else None,
        "xroi_n": xroi_n,
        "matches": matches[:lim],
        "truncated": len(matches) > lim,
    }
