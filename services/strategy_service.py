"""Gemeinsame Strategie-Logik: Settlement, Filter-Matching, Kennzahlen."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
import math


MARKET_DEFS = {
    "Home": {"odds_keys": ("odd_home", "odd_open_home"), "chance_key": "chance_home_win", "line": None, "side": "home"},
    "Draw": {"odds_keys": ("odd_draw", "odd_open_draw"), "chance_key": "chance_home_draw", "line": None, "side": "draw"},
    "Away": {"odds_keys": ("odd_away", "odd_open_away"), "chance_key": "chance_home_lose", "line": None, "side": "away"},
    "Over 2.5": {"odds_keys": ("odd_over_25", "odd_open_over_25"), "chance_key": "chance_home_over_25", "line": 2.5, "side": "over"},
    "Under 2.5": {"odds_keys": ("odd_under_25", "odd_open_under_25"), "chance_key": "chance_home_under_25", "line": 2.5, "side": "under"},
    "Over 3.5": {"odds_keys": ("odd_over_35", "odd_open_over_35"), "chance_key": "chance_home_over_35", "line": 3.5, "side": "over"},
    "Under 3.5": {"odds_keys": ("odd_under_35", "odd_open_under_35"), "chance_key": "chance_home_under_35", "line": 3.5, "side": "under"},
    "Over 4.5": {"odds_keys": ("odd_over_45", "odd_open_over_45"), "chance_key": "chance_home_over_45", "line": 4.5, "side": "over"},
    "Under 4.5": {"odds_keys": ("odd_under_45", "odd_open_under_45"), "chance_key": "chance_home_under_45", "line": 4.5, "side": "under"},
}

# Percentile-Metriken ohne Ergebnis-Leak (pre-match) — auch für Upcoming nutzbar
PREMATCH_PERCENTILE_METRICS = (
    "chance",
    "glicko_rating",
    "rating_diff",
    "rating_sum",
    "glicko_diff",
    "glicko_xg",
    "xg_glicko_sum",
    "xg_glicko_diff",
    "xg_glicko_ratio",
    "xg_glicko_home",
    "xg_glicko_away",
    "odds",
    "xroi_pct",
    "xg_form2_home",
    "xg_form2_away",
    "xg_form2_sum",
    "xg_form2_diff",
    "xg_form2_ratio",
    "form2_avg_xg_home",
    "form2_avg_xg_away",
    "form2_avg_xga_home",
    "form2_avg_xga_away",
    "form2_avg_gf_home",
    "form2_avg_gf_away",
    "form2_avg_ga_home",
    "form2_avg_ga_away",
    "hometeam_home_xg",
    "hometeam_home_xga",
    "hometeam_home_gf",
    "hometeam_home_ga",
    "hometeam_away_xg",
    "hometeam_away_xga",
    "hometeam_away_gf",
    "hometeam_away_ga",
    "awayteam_home_xg",
    "awayteam_home_xga",
    "awayteam_home_gf",
    "awayteam_home_ga",
    "awayteam_away_xg",
    "awayteam_away_xga",
    "awayteam_away_gf",
    "awayteam_away_ga",
    "hometeam_pred_xg",
    "awayteam_pred_xg",
    "power_home",
    "power_away",
    "power_diff",
    "tempo_home",
    "tempo_away",
    "tempo_sum",
    "power_home_venue",
    "power_away_venue",
    "power_diff_venue",
    "tempo_home_venue",
    "tempo_away_venue",
)

PERCENTILE_METRIC_LABELS = {
    "chance": "Chance (Modell)",
    "glicko_rating": "Ø Glicko Rating",
    "rating_diff": "Rating Diff (H−A)",
    "glicko_diff": "Rating Diff (H−A)",
    "rating_ratio": "Rating-Verhältnis H/A",
    "rating_sum": "Rating Summe (H+A)",
    "glicko_xg": "xG Summe (Glicko)",
    "xg_glicko_sum": "xG Summe (Glicko)",
    "xg_glicko_diff": "xG Diff Glicko (H−A)",
    "xg_glicko_ratio": "xG-Verhältnis Glicko H/A",
    "xg_glicko_home": "xG Glicko Home",
    "xg_glicko_away": "xG Glicko Away",
    "xg_form2_home": "xG Form2 Home",
    "xg_form2_away": "xG Form2 Away",
    "xg_form2_sum": "xG Summe (Form2)",
    "xg_form2_diff": "xG Diff Form2 (H−A)",
    "xg_form2_ratio": "xG-Verhältnis Form2 H/A",
    "form2_avg_xg_home": "Form2 Ø xG Home (Saison)",
    "form2_avg_xg_away": "Form2 Ø xG Away (Saison)",
    "form2_avg_xga_home": "Form2 Ø xGA Home (Saison)",
    "form2_avg_xga_away": "Form2 Ø xGA Away (Saison)",
    "form2_avg_gf_home": "Form2 Ø Tore Home (Saison)",
    "form2_avg_gf_away": "Form2 Ø Tore Away (Saison)",
    "form2_avg_ga_home": "Form2 Ø Gegentore Home (Saison)",
    "form2_avg_ga_away": "Form2 Ø Gegentore Away (Saison)",
    "hometeam_home_xg": "Heimteam Ø xG (Heimspiele)",
    "hometeam_home_xga": "Heimteam Ø xGA (Heimspiele)",
    "hometeam_home_gf": "Heimteam Ø Tore (Heimspiele)",
    "hometeam_home_ga": "Heimteam Ø Gegentore (Heimspiele)",
    "hometeam_away_xg": "Heimteam Ø xG (Auswärtsspiele)",
    "hometeam_away_xga": "Heimteam Ø xGA (Auswärtsspiele)",
    "hometeam_away_gf": "Heimteam Ø Tore (Auswärtsspiele)",
    "hometeam_away_ga": "Heimteam Ø Gegentore (Auswärtsspiele)",
    "awayteam_home_xg": "Gast Ø xG (Heimspiele)",
    "awayteam_home_xga": "Gast Ø xGA (Heimspiele)",
    "awayteam_home_gf": "Gast Ø Tore (Heimspiele)",
    "awayteam_home_ga": "Gast Ø Gegentore (Heimspiele)",
    "awayteam_away_xg": "Gast Ø xG (Auswärtsspiele)",
    "awayteam_away_xga": "Gast Ø xGA (Auswärtsspiele)",
    "awayteam_away_gf": "Gast Ø Tore (Auswärtsspiele)",
    "awayteam_away_ga": "Gast Ø Gegentore (Auswärtsspiele)",
    "hometeam_pred_xg": "pred. xG Heimteam (Venue)",
    "awayteam_pred_xg": "pred. xG Gast (Venue)",
    "xg_match_home": "xG Match Home (erzielt)",
    "xg_match_away": "xG Match Away (erzielt)",
    "xg_match_sum": "xG Match Summe (erzielt)",
    "xg_match_diff": "xG Match Diff (H−A)",
    "xg_match_ratio": "xG Match-Verhältnis H/A",
    "rating_home": "Rating Home",
    "rating_away": "Rating Away",
    "rating_avg": "Rating Ø",
    "odds": "Quote",
    "home_quote": "Home-Quote",
    "away_quote": "Away-Quote",
    "draw_quote": "Draw-Quote",
    "over_25_quote": "Over 2.5 Quote",
    "under_25_quote": "Under 2.5 Quote",
    "xroi_pct": "xROI % (Open vs Close)",
    "profit": "Profit (Look-ahead!)",
}


def _f(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def normalize_chance(val: Any) -> Optional[float]:
    """Chance als 0–1; akzeptiert auch Prozent (z. B. 55)."""
    c = _f(val)
    if c is None:
        return None
    if c > 1.0:
        c = c / 100.0
    return max(0.0, min(1.0, c))


def valid_odds(val: Any) -> Optional[float]:
    """Dezimalquote: nur > 1.0 (nie negativ / ≤1)."""
    o = _f(val)
    if o is None or o <= 1.0:
        return None
    return o


def settle_unit_profit(odds: Optional[float], won: bool) -> Optional[float]:
    o = valid_odds(odds)
    if o is None:
        return None
    return (o - 1.0) if won else -1.0


def settle_market(market: str, home: Any, away: Any, odds: Optional[float]) -> Optional[float]:
    """1-Einheit Stake Profit für Markt anhand Endergebnis."""
    try:
        h = int(home)
        a = int(away)
    except (TypeError, ValueError):
        return None
    total = h + a
    meta = MARKET_DEFS.get(market)
    if not meta:
        return None
    side = meta["side"]
    line = meta["line"]
    if side == "home":
        won = h > a
    elif side == "away":
        won = a > h
    elif side == "draw":
        won = h == a
    elif side == "over":
        won = total > float(line)
    elif side == "under":
        won = total <= float(line)
    else:
        return None
    return settle_unit_profit(odds, won)


def pick_odds(row: Dict[str, Any], market: str, odds_type: str = "closing") -> Optional[float]:
    """odds_type: 'closing' = Quote vor Anpfiff (value), 'opening' = Eröffnungsquote.

    Bei 'opening' kein Fallback auf Closing — sonst vermischt man CLV/xROI.
    """
    meta = MARKET_DEFS.get(market)
    if not meta:
        return None
    closing_key = meta["odds_keys"][0]
    opening_key = meta["odds_keys"][1] if len(meta["odds_keys"]) > 1 else None
    if odds_type == "opening":
        return valid_odds(row.get(opening_key)) if opening_key else None
    return valid_odds(row.get(closing_key))


def compute_xroi_pct(opening: Any, closing: Any) -> Optional[float]:
    """xROI % = (Opening − Closing) / Closing × 100.

    Positiv = Opening höher als Closing (bessere Quote bei Eröffnung).
    """
    o = valid_odds(opening)
    c = valid_odds(closing)
    if o is None or c is None:
        return None
    return ((o - c) / c) * 100.0


MARKET_FILTER_KEYS = [
    ("market_home", "Home"),
    ("market_draw", "Draw"),
    ("market_away", "Away"),
    ("market_over", "Over 2.5"),
    ("market_under", "Under 2.5"),
    ("market_over_35", "Over 3.5"),
    ("market_under_35", "Under 3.5"),
    ("market_over_45", "Over 4.5"),
    ("market_under_45", "Under 4.5"),
]


def selected_markets_from_filters(filters: Dict[str, Any]) -> List[str]:
    return [name for key, name in MARKET_FILTER_KEYS if filters.get(key)]


def all_market_names() -> List[str]:
    return [name for _, name in MARKET_FILTER_KEYS]


CHANCE_BY_MARKET = {
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


def compute_per_market_stats(
    game_rows: Sequence[Dict[str, Any]],
    filters: Dict[str, Any],
    *,
    selected_markets: Optional[Sequence[str]] = None,
    odds_type: str = "closing",
    only_unselected: bool = True,
    skip_prematch_filters: bool = False,
) -> List[Dict[str, Any]]:
    """Pro Markt: Prozent (Winrate), Profit, ROI, xROI.

    skip_prematch_filters=True: Spiele sind schon die Strategie-Treffer —
    nur Quote + Settlement (+ optional FT/xROI-Filter).
    """
    selected = set(selected_markets or selected_markets_from_filters(filters))
    rows = list(game_rows or [])
    out: List[Dict[str, Any]] = []
    for market in all_market_names():
        if only_unselected and market in selected:
            continue
        profits: List[float] = []
        xrois: List[float] = []
        for rd in rows:
            # Closing bevorzugen; bei fehlendem Closing (häufig Over 4.5) Opening nutzen
            odds = pick_odds(rd, market, odds_type)
            if odds is None:
                other = "opening" if odds_type != "opening" else "closing"
                odds = pick_odds(rd, market, other)
            if odds is None:
                continue
            if not skip_prematch_filters:
                if not passes_other_market_odds(filters, rd, odds_type, fallback_closing=True):
                    continue
                xg_ctx = {
                    "xg_h": rd.get("xg_home"),
                    "xg_a": rd.get("xg_away"),
                    "xg_glicko_h": rd.get("xg_glicko_home"),
                    "xg_glicko_a": rd.get("xg_glicko_away"),
                    "rating_h": rd.get("home_rating") if rd.get("home_rating") is not None else rd.get("rating_h"),
                    "rating_a": rd.get("away_rating") if rd.get("away_rating") is not None else rd.get("rating_a"),
                    "rd_h": rd.get("home_rd") if rd.get("home_rd") is not None else rd.get("rd_h"),
                    "rd_a": rd.get("away_rd") if rd.get("away_rd") is not None else rd.get("rd_a"),
                    "vol_h": rd.get("home_volatility") if rd.get("home_volatility") is not None else rd.get("vol_h"),
                    "vol_a": rd.get("away_volatility") if rd.get("away_volatility") is not None else rd.get("vol_a"),
                    "p_home": rd.get("home_win_probability") if rd.get("home_win_probability") is not None else rd.get("p_home"),
                    "p_draw": rd.get("draw_probability") if rd.get("draw_probability") is not None else rd.get("p_draw"),
                    "p_away": rd.get("away_win_probability") if rd.get("away_win_probability") is not None else rd.get("p_away"),
                }
                chance = rd.get(CHANCE_BY_MARKET.get(market, ""), None)
                if not match_prematch_filters(
                    filters,
                    market=market,
                    odds=odds,
                    chance=chance,
                    rating_h=rd.get("home_rating", rd.get("rating_h")),
                    rating_a=rd.get("away_rating", rd.get("rating_a")),
                    country=rd.get("country_name", rd.get("country")),
                    league=rd.get("league_name", rd.get("league")),
                    games_count=rd.get("games_count_home_win"),
                    xg_ctx=xg_ctx,
                    home_season_n=rd.get("home_season_n"),
                    away_season_n=rd.get("away_season_n"),
                    require_selected_market=False,
                ):
                    continue
            home = rd.get("home_ft_result") if "home_ft_result" in rd else rd.get("home_score")
            away = rd.get("away_ft_result") if "away_ft_result" in rd else rd.get("away_score")
            profit = settle_market(market, home, away, odds)
            if profit is None:
                continue
            o_open = pick_odds(rd, market, "opening")
            o_close = pick_odds(rd, market, "closing")
            xr = compute_xroi_pct(o_open, o_close)
            if not skip_prematch_filters and not passes_xroi_range(filters, xr):
                continue
            profits.append(profit)
            if xr is not None:
                xrois.append(xr)
        n = len(profits)
        total = sum(profits) if profits else 0.0
        wins = sum(1 for p in profits if p > 0)
        xroi_n = len(xrois)
        out.append(
            {
                "market": market,
                "selected": market in selected,
                "n": n,
                "percent": (wins / n * 100.0) if n else 0.0,
                "win_rate": (wins / n * 100.0) if n else 0.0,
                "total_profit": total,
                "roi_pct": (total / n * 100.0) if n else 0.0,
                "avg_xroi_pct": (sum(xrois) / xroi_n) if xroi_n else None,
                "xroi_n": xroi_n,
            }
        )
    return out


def compute_unselected_market_stats(
    game_rows: Sequence[Dict[str, Any]],
    selected_markets: Sequence[str],
    odds_type: str = "closing",
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Kompatibilität: ungewählte Märkte mit optionalen Filtern."""
    return compute_per_market_stats(
        game_rows,
        filters or {},
        selected_markets=selected_markets,
        odds_type=odds_type,
        only_unselected=True,
    )


def odds_range_for_market(filters: Dict[str, Any], market: str) -> Tuple[Optional[float], Optional[float]]:
    key_map = {
        "Home": ("odds_home_min", "odds_home_max"),
        "Draw": ("odds_draw_min", "odds_draw_max"),
        "Away": ("odds_away_min", "odds_away_max"),
        "Over 2.5": ("odds_over_min", "odds_over_max"),
        "Under 2.5": ("odds_under_min", "odds_under_max"),
        "Over 3.5": ("odds_over35_min", "odds_over35_max"),
        "Under 3.5": ("odds_under35_min", "odds_under35_max"),
        "Over 4.5": ("odds_over45_min", "odds_over45_max"),
        "Under 4.5": ("odds_under45_min", "odds_under45_max"),
    }
    keys = key_map.get(market)
    if not keys:
        return None, None
    return _f(filters.get(keys[0])), _f(filters.get(keys[1]))


def passes_other_market_odds(
    filters: Dict[str, Any],
    row: Dict[str, Any],
    odds_type: str = "closing",
    *,
    fallback_closing: bool = False,
) -> bool:
    """Quotenbereiche nicht gewählter Märkte als Spiel-Filter.

    Beispiel: Away wetten, aber nur Spiele mit Over-2.5-Quote 1–1.7. Der Bereich eines
    gewählten Markts gilt weiter nur für dessen eigene Wette (match_prematch_filters).
    """
    selected = set(selected_markets_from_filters(filters))
    for market in all_market_names():
        if market in selected:
            continue
        omin, omax = odds_range_for_market(filters, market)
        if omin is None and omax is None:
            continue
        odds = pick_odds(row, market, odds_type)
        if odds is None and fallback_closing and odds_type == "opening":
            odds = pick_odds(row, market, "closing")
        if not in_range(odds, omin, omax):
            return False
    return True


def in_range(val: Optional[float], vmin: Optional[float], vmax: Optional[float]) -> bool:
    if val is None:
        # Wenn Filter gesetzt sind, fehlender Wert = raus
        return vmin is None and vmax is None
    if vmin is not None and val < vmin:
        return False
    if vmax is not None and val > vmax:
        return False
    return True


# Liga-Namen-Hinweise für Frauenfußball (SStats hat kein separates gender-Feld)
_WOMEN_LEAGUE_MARKERS = (
    "women",
    "woman",
    "womens",
    "women's",
    "female",
    "ladies",
    "frau",
    "frauen",
    "femenil",
    "femenina",
    "féminine",
    "feminine",
    "w-league",
    "w league",
    "nwsl",
    "a-league women",
    "liga f",
    "damallsvenskan",
    "frauen-bundesliga",
    "women bundesliga",
    "fa wsl",
    "wsl",
    "uwcl",
    "women's champions",
)


def detect_league_gender(league: Any) -> str:
    """'women' oder 'men' anhand Liga-Name (Heuristik)."""
    s = str(league or "").strip().lower()
    if not s:
        return "men"
    if any(m in s for m in _WOMEN_LEAGUE_MARKERS):
        return "women"
    # z.B. "J2 League Women", "Serie A Women"
    if s.endswith(" w") or " (w)" in s or s.endswith(" (w)"):
        return "women"
    return "men"


def passes_gender(filters: Dict[str, Any], league: Any) -> bool:
    """gender_filter: all|men|women (leer = all)."""
    raw = (filters.get("gender_filter") or filters.get("gender") or "all").strip().lower()
    if raw in ("", "all", "beide", "any"):
        return True
    g = detect_league_gender(league)
    if raw in ("men", "mann", "manner", "männer", "male", "m"):
        return g == "men"
    if raw in ("women", "frau", "frauen", "female", "w"):
        return g == "women"
    return True


def passes_country_league(filters: Dict[str, Any], country: Any, league: Any) -> bool:
    cf = (filters.get("country_filter") or "").strip().lower()
    lf = (filters.get("league_filter") or "").strip().lower()
    if cf and cf not in str(country or "").lower():
        return False
    if lf and lf not in str(league or "").lower():
        return False
    if not passes_gender(filters, league):
        return False
    return True


def _passes_minmax(
    filters: Dict[str, Any],
    val: Any,
    min_key: str,
    max_key: str,
    *,
    as_chance: bool = False,
) -> bool:
    """Generischer Min/Max-Filter; as_chance=True → Prozent oder 0–1."""
    has = filters.get(min_key) not in (None, "") or filters.get(max_key) not in (None, "")
    if as_chance:
        v = normalize_chance(val)
        vmin = normalize_chance(filters.get(min_key))
        vmax = normalize_chance(filters.get(max_key))
    else:
        v = _f(val)
        vmin = _f(filters.get(min_key))
        vmax = _f(filters.get(max_key))
    if has and v is None:
        return False
    return in_range(v, vmin, vmax)


def passes_glicko(filters: Dict[str, Any], rating_h: Any, rating_a: Any) -> bool:
    """homeRating / awayRating (Glicko-2)."""
    return (
        _passes_minmax(filters, rating_h, "glicko_home_min", "glicko_home_max")
        and _passes_minmax(filters, rating_a, "glicko_away_min", "glicko_away_max")
    )


def passes_glicko_rd(filters: Dict[str, Any], rd_h: Any, rd_a: Any) -> bool:
    """homeRd / awayRd."""
    return (
        _passes_minmax(filters, rd_h, "glicko_rd_home_min", "glicko_rd_home_max")
        and _passes_minmax(filters, rd_a, "glicko_rd_away_min", "glicko_rd_away_max")
    )


def passes_glicko_volatility(filters: Dict[str, Any], vol_h: Any, vol_a: Any) -> bool:
    """homeVolatility / awayVolatility."""
    return (
        _passes_minmax(filters, vol_h, "glicko_vol_home_min", "glicko_vol_home_max")
        and _passes_minmax(filters, vol_a, "glicko_vol_away_min", "glicko_vol_away_max")
    )


def passes_glicko_probs(
    filters: Dict[str, Any], p_home: Any, p_draw: Any, p_away: Any
) -> bool:
    """homeWinProbability / drawProbability / awayWinProbability (0–1 oder %)."""
    return (
        _passes_minmax(filters, p_home, "glicko_p_home_min", "glicko_p_home_max", as_chance=True)
        and _passes_minmax(filters, p_draw, "glicko_p_draw_min", "glicko_p_draw_max", as_chance=True)
        and _passes_minmax(filters, p_away, "glicko_p_away_min", "glicko_p_away_max", as_chance=True)
    )


def passes_glicko_xg(filters: Dict[str, Any], xg_h: Any, xg_a: Any) -> bool:
    """Glicko-xG Home/Away Min–Max (pre-match Modellwert dieses Spiels)."""
    return (
        _passes_minmax(filters, xg_h, "xg_glicko_home_min", "xg_glicko_home_max")
        and _passes_minmax(filters, xg_a, "xg_glicko_away_min", "xg_glicko_away_max")
    )


def passes_form2_xg(filters: Dict[str, Any], xg_h: Any, xg_a: Any) -> bool:
    """Form2 pred. xG Home/Away Min–Max (saisonale Avgs, pre-match)."""
    return (
        _passes_minmax(filters, xg_h, "xg_form2_home_min", "xg_form2_home_max")
        and _passes_minmax(filters, xg_a, "xg_form2_away_min", "xg_form2_away_max")
    )


def passes_season_game_no(
    filters: Dict[str, Any],
    home_n: Any,
    away_n: Any,
    *,
    allow_missing: bool = False,
) -> bool:
    """Filter nach Saison-Spielnummer (1 = erstes Liga-Spiel der Season pro Team)."""
    keys = (
        "season_games_home_min", "season_games_home_max",
        "season_games_away_min", "season_games_away_max",
    )
    if not any(filters.get(k) for k in keys):
        return True
    hn, an = _f(home_n), _f(away_n)
    if hn is None or an is None:
        return bool(allow_missing)
    return (
        in_range(hn, _f(filters.get("season_games_home_min")), _f(filters.get("season_games_home_max")))
        and in_range(an, _f(filters.get("season_games_away_min")), _f(filters.get("season_games_away_max")))
    )


def passes_chance(filters: Dict[str, Any], chance: Any, *, allow_missing: bool = False) -> bool:
    c = normalize_chance(chance)
    cmin = normalize_chance(filters.get("chance_min"))
    cmax = normalize_chance(filters.get("chance_max"))
    # Wenn Chance-Filter gesetzt und Wert fehlt → raus (außer Live allow_missing)
    if (filters.get("chance_min") or filters.get("chance_max")) and c is None:
        return bool(allow_missing)
    return in_range(c, cmin, cmax)


def passes_min_games(filters: Dict[str, Any], games_count: Any, *, allow_missing: bool = False) -> bool:
    need = _f(filters.get("min_games_count"))
    if need is None or need <= 0:
        return True
    gc = _f(games_count)
    if gc is None:
        # Live/Upcoming: games_count oft unbekannt → optional durchlassen
        return bool(allow_missing)
    return gc >= need


def passes_xroi_range(filters: Dict[str, Any], xroi_pct: Any) -> bool:
    """xROI % = (Open−Close)/Close×100 — Min/Max wie Quote."""
    xmin = _f(filters.get("xroi_min"))
    xmax = _f(filters.get("xroi_max"))
    if xmin is None and xmax is None:
        return True
    xr = _f(xroi_pct)
    if xr is None:
        return False
    return in_range(xr, xmin, xmax)


COMPARISON_ATTRS = (
    "rating_home",
    "rating_away",
    "xg_home_glicko",
    "xg_away_glicko",
    "rd_home",
    "rd_away",
    "vol_home",
    "vol_away",
    "p_home",
    "p_draw",
    "p_away",
    "xg_form2_home",
    "xg_form2_away",
    "form2_avg_xg_home",
    "form2_avg_xg_away",
    "form2_avg_xga_home",
    "form2_avg_xga_away",
    "form2_avg_gf_home",
    "form2_avg_gf_away",
    "form2_avg_ga_home",
    "form2_avg_ga_away",
    "hometeam_home_xg",
    "hometeam_home_xga",
    "hometeam_home_gf",
    "hometeam_home_ga",
    "hometeam_away_xg",
    "hometeam_away_xga",
    "hometeam_away_gf",
    "hometeam_away_ga",
    "awayteam_home_xg",
    "awayteam_home_xga",
    "awayteam_home_gf",
    "awayteam_home_ga",
    "awayteam_away_xg",
    "awayteam_away_xga",
    "awayteam_away_gf",
    "awayteam_away_ga",
    "hometeam_pred_xg",
    "awayteam_pred_xg",
)


def _comparison_attr_value(key: Any, ctx: Dict[str, Any]) -> Optional[float]:
    """Attribut-Wert aus Kontext (Glicko / Form2 / Venue) — ohne Match-xG."""
    k = str(key or "").strip()
    mapping = {
        "xg_home_glicko": ctx.get("xg_glicko_h"),
        "xg_away_glicko": ctx.get("xg_glicko_a"),
        "rating_home": ctx.get("rating_h"),
        "rating_away": ctx.get("rating_a"),
        "rd_home": ctx.get("rd_h"),
        "rd_away": ctx.get("rd_a"),
        "vol_home": ctx.get("vol_h"),
        "vol_away": ctx.get("vol_a"),
        "p_home": ctx.get("p_home"),
        "p_draw": ctx.get("p_draw"),
        "p_away": ctx.get("p_away"),
        "xg_form2_home": ctx.get("xg_form2_h"),
        "xg_form2_away": ctx.get("xg_form2_a"),
        "form2_avg_xg_home": ctx.get("form2_home_avg_xg"),
        "form2_avg_xg_away": ctx.get("form2_away_avg_xg"),
        "form2_avg_xga_home": ctx.get("form2_home_avg_xga"),
        "form2_avg_xga_away": ctx.get("form2_away_avg_xga"),
        "form2_avg_gf_home": ctx.get("form2_home_avg_gf"),
        "form2_avg_gf_away": ctx.get("form2_away_avg_gf"),
        "form2_avg_ga_home": ctx.get("form2_home_avg_ga"),
        "form2_avg_ga_away": ctx.get("form2_away_avg_ga"),
        "hometeam_home_xg": ctx.get("hometeam_home_xg"),
        "hometeam_home_xga": ctx.get("hometeam_home_xga"),
        "hometeam_home_gf": ctx.get("hometeam_home_gf"),
        "hometeam_home_ga": ctx.get("hometeam_home_ga"),
        "hometeam_away_xg": ctx.get("hometeam_away_xg"),
        "hometeam_away_xga": ctx.get("hometeam_away_xga"),
        "hometeam_away_gf": ctx.get("hometeam_away_gf"),
        "hometeam_away_ga": ctx.get("hometeam_away_ga"),
        "awayteam_home_xg": ctx.get("awayteam_home_xg"),
        "awayteam_home_xga": ctx.get("awayteam_home_xga"),
        "awayteam_home_gf": ctx.get("awayteam_home_gf"),
        "awayteam_home_ga": ctx.get("awayteam_home_ga"),
        "awayteam_away_xg": ctx.get("awayteam_away_xg"),
        "awayteam_away_xga": ctx.get("awayteam_away_xga"),
        "awayteam_away_gf": ctx.get("awayteam_away_gf"),
        "awayteam_away_ga": ctx.get("awayteam_away_ga"),
        "hometeam_pred_xg": ctx.get("hometeam_pred_xg"),
        "awayteam_pred_xg": ctx.get("awayteam_pred_xg"),
    }
    if k in POWER_TEMPO_METRICS:
        return power_tempo_value(ctx, k)
    if k in mapping:
        return _f(mapping[k])
    # Fallback: Key direkt im Kontext (Row-Keys)
    return _f(ctx.get(k))


def _apply_cmp(left: float, cmp_op: str, right: float) -> bool:
    op = (cmp_op or ">=").strip()
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op in ("==", "="):
        return abs(left - right) < 1e-9
    if op in ("!=", "<>", "!"):
        return abs(left - right) >= 1e-9
    return False


def _eval_one_comparison(
    *,
    attr1: Any,
    attr2: Any,
    operation: Any,
    cmp_op: Any,
    raw_val: Any,
    ctx: Dict[str, Any],
) -> bool:
    """Eine Vergleichsbedingung: Attr1 [+−*/|vs] Attr2 [><=≠] Wert."""
    a1 = _comparison_attr_value(attr1, ctx)
    a2 = _comparison_attr_value(attr2, ctx)
    if a1 is None or a2 is None:
        return False
    op = str(operation or "+").strip().lower()
    cmp = cmp_op or ">="
    try:
        if op in ("vs", "none", "", "cmp"):
            return _apply_cmp(a1, cmp, a2)
        if op == "+":
            calc = a1 + a2
        elif op == "-":
            calc = a1 - a2
        elif op == "*":
            calc = a1 * a2
        elif op == "/":
            if a2 == 0:
                return False
            calc = a1 / a2
        else:
            return False
        if raw_val in (None, ""):
            target = 0.0
        else:
            target = float(raw_val)
        return _apply_cmp(calc, cmp, target)
    except Exception:
        return False


def eval_xg_comparison(filters: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """Vergleichsbedingungen (AND) — gilt für Backtest und Upcoming.

    Primär: use_xg_comparison + xg_attr1/2 + op + cmp + Wert.
    Extra: xg_comparisons = [{attr1, operation, attr2, comparison_operator, comparison_value}, ...]
    """
    if not filters.get("use_xg_comparison"):
        return True
    if not _eval_one_comparison(
        attr1=filters.get("xg_attr1"),
        attr2=filters.get("xg_attr2"),
        operation=filters.get("xg_operation"),
        cmp_op=filters.get("xg_comparison_operator"),
        raw_val=filters.get("xg_comparison_value"),
        ctx=ctx,
    ):
        return False
    extras = filters.get("xg_comparisons") or []
    if not isinstance(extras, (list, tuple)):
        return True
    for item in extras:
        if not isinstance(item, dict):
            continue
        if not _eval_one_comparison(
            attr1=item.get("attr1") or item.get("xg_attr1"),
            attr2=item.get("attr2") or item.get("xg_attr2"),
            operation=item.get("operation") or item.get("xg_operation"),
            cmp_op=item.get("comparison_operator")
            or item.get("xg_comparison_operator"),
            raw_val=item.get("comparison_value")
            if "comparison_value" in item
            else item.get("xg_comparison_value"),
            ctx=ctx,
        ):
            return False
    return True


def match_prematch_filters(
    filters: Dict[str, Any],
    *,
    market: str,
    odds: Optional[float],
    chance: Any,
    rating_h: Any,
    rating_a: Any,
    country: Any = None,
    league: Any = None,
    games_count: Any = None,
    xg_ctx: Optional[Dict[str, Any]] = None,
    home_season_n: Any = None,
    away_season_n: Any = None,
    allow_missing_stats: bool = False,
    require_selected_market: bool = True,
) -> bool:
    """Gemeinsame Pre-Match-Filter für Backtest und Live.

    allow_missing_stats: bei Live/Upcoming fehlende Chance/Min-Spiele nicht hart blockieren.
    require_selected_market: False = Markt-Checkbox ignorieren (Vergleich anderer Märkte).
    """
    if require_selected_market:
        markets = selected_markets_from_filters(filters)
        if markets and market not in markets:
            return False
    if not passes_country_league(filters, country, league):
        return False
    ctx = xg_ctx or {}
    rh = rating_h if rating_h is not None else ctx.get("rating_h")
    ra = rating_a if rating_a is not None else ctx.get("rating_a")
    if not passes_glicko(filters, rh, ra):
        return False
    if not passes_glicko_rd(filters, ctx.get("rd_h"), ctx.get("rd_a")):
        return False
    if not passes_glicko_volatility(filters, ctx.get("vol_h"), ctx.get("vol_a")):
        return False
    if not passes_glicko_probs(
        filters, ctx.get("p_home"), ctx.get("p_draw"), ctx.get("p_away")
    ):
        return False
    if not passes_glicko_xg(filters, ctx.get("xg_glicko_h"), ctx.get("xg_glicko_a")):
        return False
    if not passes_form2_xg(filters, ctx.get("xg_form2_h"), ctx.get("xg_form2_a")):
        return False
    if not passes_season_game_no(
        filters, home_season_n, away_season_n, allow_missing=allow_missing_stats
    ):
        return False
    if not passes_chance(filters, chance, allow_missing=allow_missing_stats):
        return False
    if not passes_min_games(filters, games_count, allow_missing=allow_missing_stats):
        return False
    omin, omax = odds_range_for_market(filters, market)
    if not in_range(_f(odds), omin, omax):
        return False
    if not eval_xg_comparison(filters, ctx):
        return False
    return True


def _percentile_metric_value(row: Dict[str, Any], metric: str) -> Optional[float]:
    """Wert für Percentile-Filter (inkl. Alias-Metriken)."""
    if metric == "profit":
        return _f(row.get("profit"))
    if metric == "glicko_rating":
        rh, ra = _f(row.get("rating_h")), _f(row.get("rating_a"))
        if rh is None and ra is None:
            return None
        return ((rh or 0.0) + (ra or 0.0)) / (2.0 if rh is not None and ra is not None else 1.0)
    if metric == "glicko_xg":
        return _metric_value(row, "xg_glicko_sum")
    if metric == "xroi_pct":
        xr = _f(row.get("xroi_pct"))
        if xr is not None:
            return xr
        return compute_xroi_pct(row.get("odds_opening"), row.get("odds_closing"))
    return _metric_value(row, metric)


def percentile_threshold(
    results: List[Dict[str, Any]],
    percentile: float,
    metric: str,
) -> Optional[float]:
    """Schwelle für Top-X% (absteigend sortiert)."""
    if not results or percentile <= 0:
        return None
    valid = [
        v
        for v in (_percentile_metric_value(r, metric) for r in results)
        if v is not None
    ]
    if not valid:
        return None
    sorted_vals = sorted(valid, reverse=True)
    cut_index = max(0, int(math.ceil(len(sorted_vals) * (percentile / 100.0))) - 1)
    cut_index = min(cut_index, len(sorted_vals) - 1)
    return sorted_vals[cut_index]


def apply_percentile_filter(
    results: List[Dict[str, Any]],
    percentile: float,
    metric: str,
) -> List[Dict[str, Any]]:
    """Top-X% Filter. 'profit' ist post-hoc (Look-ahead) – bewusst erlaubt, aber markiert."""
    if not results:
        return results
    threshold = percentile_threshold(results, percentile, metric)
    if threshold is None:
        return results
    out = []
    for r in results:
        v = _percentile_metric_value(r, metric)
        if v is not None and v >= threshold:
            out.append(r)
    return out


def filter_by_metric_threshold(
    rows: List[Dict[str, Any]],
    metric: str,
    threshold: float,
) -> List[Dict[str, Any]]:
    """Zeilen mit Metrik >= threshold behalten."""
    out = []
    for r in rows:
        v = _percentile_metric_value(r, metric)
        if v is not None and v >= threshold:
            out.append(r)
    return out


def _sort_key_date(row: Dict[str, Any]) -> str:
    d = row.get("date") or row.get("match_date") or ""
    return str(d)


def compute_streaks(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gewinn-/Verlustserien chronologisch (nach date). Verlust = profit <= 0.

    Median = typische Serienlänge; n_* = Anzahl abgeschlossener + laufender Serien,
    damit man sieht, wie belastbar der Median ist.
    """
    import statistics

    ordered = sorted(results or [], key=_sort_key_date)
    losing: List[int] = []
    winning: List[int] = []
    cur_lose = cur_win = 0
    for r in ordered:
        p = _f(r.get("profit"))
        if p is None:
            continue
        if p > 0:
            if cur_lose:
                losing.append(cur_lose)
            cur_win += 1
            cur_lose = 0
        else:
            if cur_win:
                winning.append(cur_win)
            cur_lose += 1
            cur_win = 0
    all_losing = losing + ([cur_lose] if cur_lose else [])
    all_winning = winning + ([cur_win] if cur_win else [])
    return {
        "max_losing_streak": max(all_losing, default=0),
        "max_winning_streak": max(all_winning, default=0),
        "current_losing_streak": cur_lose,
        "current_winning_streak": cur_win,
        "median_losing_streak": statistics.median(all_losing) if all_losing else None,
        "median_winning_streak": statistics.median(all_winning) if all_winning else None,
        "n_losing_streaks": len(all_losing),
        "n_winning_streaks": len(all_winning),
    }


def compute_outcome_distribution(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ergebnis-Verteilung der einzigartigen Spiele (nicht Wetten).

    Home / Draw / Away und Over/Under 2.5 als n und %.
    """
    by_game: Dict[Any, Tuple[Optional[float], Optional[float]]] = {}
    for r in results:
        gid = r.get("game_id")
        if gid is None:
            continue
        if gid in by_game:
            continue
        hs, aws = _f(r.get("home_score")), _f(r.get("away_score"))
        if hs is None or aws is None:
            continue
        by_game[gid] = (hs, aws)

    n_games = len(by_game)
    home = draw = away = over25 = under25 = 0
    for hs, aws in by_game.values():
        if hs > aws:
            home += 1
        elif hs < aws:
            away += 1
        else:
            draw += 1
        goals = hs + aws
        if goals > 2.5:
            over25 += 1
        else:
            under25 += 1

    def _pct(c: int) -> float:
        return (c / n_games * 100.0) if n_games else 0.0

    return {
        "games_n": n_games,
        "home_n": home,
        "draw_n": draw,
        "away_n": away,
        "over25_n": over25,
        "under25_n": under25,
        "home_pct": _pct(home),
        "draw_pct": _pct(draw),
        "away_pct": _pct(away),
        "over25_pct": _pct(over25),
        "under25_pct": _pct(under25),
    }


def compute_equity_curves(
    results: List[Dict[str, Any]], *, max_points: int = 600
) -> Dict[str, Any]:
    """Kumulierter Profit über Zeit: Closing- vs Opening-Quoten (1u/Wette)."""
    ordered = sorted(results, key=_sort_key_date)
    eq_close = 0.0
    eq_open = 0.0
    n_close = n_open = 0
    full: List[Dict[str, Any]] = []
    for i, r in enumerate(ordered):
        market = r.get("market") or ""
        hs, aws = r.get("home_score"), r.get("away_score")
        o_close = _f(r.get("odds_closing"))
        o_open = _f(r.get("odds_opening"))
        # Fallback: wenn Closing fehlt, gewählte Quote nutzen
        if o_close is None:
            o_close = _f(r.get("odds"))
        pc = settle_market(market, hs, aws, o_close) if o_close else None
        po = settle_market(market, hs, aws, o_open) if o_open else None
        if pc is not None:
            eq_close += pc
            n_close += 1
        if po is not None:
            eq_open += po
            n_open += 1
        date_s = str(r.get("date") or "")[:10]
        full.append(
            {
                "i": i + 1,
                "date": date_s,
                "equity_close": round(eq_close, 4),
                "equity_open": round(eq_open, 4),
            }
        )

    # Downsample für Chart (Anfang, Ende, gleichmäßige Schritte)
    if len(full) <= max_points:
        series = full
    else:
        step = max(1, (len(full) - 1) // (max_points - 1))
        idxs = list(range(0, len(full), step))
        if idxs[-1] != len(full) - 1:
            idxs.append(len(full) - 1)
        series = [full[j] for j in idxs]

    stake_c = float(n_close) if n_close else 0.0
    stake_o = float(n_open) if n_open else 0.0
    return {
        "series": series,
        "n_close": n_close,
        "n_open": n_open,
        "total_profit_close": eq_close,
        "total_profit_open": eq_open,
        "roi_close_pct": (eq_close / stake_c * 100.0) if stake_c else 0.0,
        "roi_open_pct": (eq_open / stake_o * 100.0) if stake_o else 0.0,
    }


def _avg_of(vals: List[float]) -> Optional[float]:
    return (sum(vals) / len(vals)) if vals else None


def compute_glicko_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ø Glicko-Parameter über einzigartige Spiele (nicht doppelte Märkte)."""
    by_game: Dict[Any, Dict[str, Any]] = {}
    for r in results:
        gid = r.get("game_id")
        if gid is None or gid in by_game:
            continue
        by_game[gid] = r

    rows = list(by_game.values())

    def col(key: str) -> List[float]:
        out: List[float] = []
        for r in rows:
            v = _f(r.get(key))
            if v is not None:
                # Wahrscheinlichkeiten oft 0–1; Anzeige später als %
                out.append(v)
        return out

    rh, ra = col("rating_h"), col("rating_a")
    diffs = []
    for r in rows:
        a, b = _f(r.get("rating_h")), _f(r.get("rating_a"))
        if a is not None and b is not None:
            diffs.append(a - b)

    # Match-xG (erzielt) — Aliase xg_h / xg_match_h
    xg_match_h: List[float] = []
    xg_match_a: List[float] = []
    goals_h: List[float] = []
    goals_a: List[float] = []
    goals_sum: List[float] = []
    for r in rows:
        mh = _f(r.get("xg_h") if r.get("xg_h") is not None else r.get("xg_match_h"))
        ma = _f(r.get("xg_a") if r.get("xg_a") is not None else r.get("xg_match_a"))
        if mh is not None:
            xg_match_h.append(mh)
        if ma is not None:
            xg_match_a.append(ma)
        gh = _f(r.get("home_score"))
        ga = _f(r.get("away_score"))
        if gh is not None:
            goals_h.append(gh)
        if ga is not None:
            goals_a.append(ga)
        if gh is not None and ga is not None:
            goals_sum.append(gh + ga)

    avg_xg_match_h = _avg_of(xg_match_h)
    avg_xg_match_a = _avg_of(xg_match_a)
    avg_goals_h = _avg_of(goals_h)
    avg_goals_a = _avg_of(goals_a)

    return {
        "games_n": len(rows),
        "avg_rating_h": _avg_of(rh),
        "avg_rating_a": _avg_of(ra),
        "avg_rating_diff": _avg_of(diffs),
        "avg_rd_h": _avg_of(col("rd_h")),
        "avg_rd_a": _avg_of(col("rd_a")),
        "avg_vol_h": _avg_of(col("vol_h")),
        "avg_vol_a": _avg_of(col("vol_a")),
        "avg_p_home": _avg_of(col("p_home")),
        "avg_p_draw": _avg_of(col("p_draw")),
        "avg_p_away": _avg_of(col("p_away")),
        "avg_xg_h": _avg_of(col("xg_glicko_h")),
        "avg_xg_a": _avg_of(col("xg_glicko_a")),
        "avg_xg_match_h": avg_xg_match_h,
        "avg_xg_match_a": avg_xg_match_a,
        "avg_xg_match_sum": (
            (avg_xg_match_h + avg_xg_match_a)
            if avg_xg_match_h is not None and avg_xg_match_a is not None
            else None
        ),
        "avg_goals_h": avg_goals_h,
        "avg_goals_a": avg_goals_a,
        "avg_goals_sum": _avg_of(goals_sum),
        "n_rating": len(rh),
        "n_xg": len(col("xg_glicko_h")),
        "n_xg_match": len(xg_match_h),
        "n_goals": len(goals_sum),
        "n_p": len(col("p_home")),
    }


def compute_strategy_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    profits = [_f(r.get("profit")) for r in results]
    profits = [p for p in profits if p is not None]
    odds_list = [o for o in (valid_odds(r.get("odds")) for r in results) if o is not None]
    n = len(profits)
    wins = [p for p in profits if p > 0]
    total = sum(profits) if profits else 0.0
    stake = float(n)  # 1u pro Wette
    roi = (total / stake * 100.0) if stake else 0.0
    # Max drawdown on cumulative equity (chronologisch)
    ordered = sorted(results, key=_sort_key_date)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in ordered:
        p = _f(r.get("profit"))
        if p is None:
            continue
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    # xROI: Opening vs Closing (unabhängig vom gewählten odds_type)
    xroi_vals = []
    for r in results:
        xr = _f(r.get("xroi_pct"))
        if xr is None:
            xr = compute_xroi_pct(r.get("odds_opening"), r.get("odds_closing"))
        if xr is not None:
            xroi_vals.append(xr)
    # Ø nur über Spiele mit Open+Close; fehlende Daten zählen nicht → xroi_n kann 0 sein
    xroi_n = len(xroi_vals)
    avg_xroi = (sum(xroi_vals) / xroi_n) if xroi_n else None
    streaks = compute_streaks(results)
    outcomes = compute_outcome_distribution(results)
    equity_curves = compute_equity_curves(results)
    glicko = compute_glicko_metrics(results)
    return {
        "n": n,
        "wins": len(wins),
        "win_rate": (len(wins) / n * 100.0) if n else 0.0,
        "total_profit": total,
        "avg_profit": (total / n) if n else 0.0,
        "roi_pct": roi,
        "avg_odds": (sum(odds_list) / len(odds_list)) if odds_list else 0.0,
        "max_drawdown": max_dd,
        "avg_xroi_pct": avg_xroi,
        "xroi_n": xroi_n,
        "avg_clv": (avg_xroi / 100.0) if avg_xroi is not None else None,
        "clv_n": xroi_n,
        "outcomes": outcomes,
        "equity": equity_curves,
        "glicko": glicko,
        **streaks,
    }


def results_to_csv_rows(results: List[Dict[str, Any]]) -> List[List[Any]]:
    headers = [
        "game_id", "date", "home", "away", "season_n_h", "season_n_a",
        "market", "odds", "odds_opening", "odds_closing",
        "chance", "profit", "rating_h", "rating_a", "xg_glicko_h", "xg_glicko_a",
        "home_score", "away_score", "result",
    ]
    rows = [headers]
    for r in results:
        rows.append([
            r.get("game_id"),
            r.get("match_date") or r.get("date"),
            r.get("home"),
            r.get("away"),
            r.get("home_season_n"),
            r.get("away_season_n"),
            r.get("market"),
            r.get("odds"),
            r.get("odds_opening"),
            r.get("odds_closing"),
            r.get("chance"),
            r.get("profit"),
            r.get("rating_h"),
            r.get("rating_a"),
            r.get("xg_glicko_h"),
            r.get("xg_glicko_a"),
            r.get("home_score"),
            r.get("away_score"),
            r.get("result"),
        ])
    return rows


# Power = Ø xG ÷ Ø xGA (Chancen erzeugt im Verhältnis zu zugelassenen; > 1 = mehr erzeugt als zugelassen)
# Tempo = Ø xG + Ø xGA (Chancen pro Spiel insgesamt — wie offen die Spiele des Teams sind)
# Saison = alle Spiele; Venue = Heimteam nur Heimspiele, Gast nur Auswärtsspiele.
# Felder heißen in Ergebnis-Zeilen, bevorstehenden Spielen und Vergleichs-Kontext gleich.
_POWER_TEMPO_PARTS = {
    "power_home": ("form2_home_avg_xg", "form2_home_avg_xga", "/"),
    "power_away": ("form2_away_avg_xg", "form2_away_avg_xga", "/"),
    "tempo_home": ("form2_home_avg_xg", "form2_home_avg_xga", "+"),
    "tempo_away": ("form2_away_avg_xg", "form2_away_avg_xga", "+"),
    "power_home_venue": ("hometeam_home_xg", "hometeam_home_xga", "/"),
    "power_away_venue": ("awayteam_away_xg", "awayteam_away_xga", "/"),
    "tempo_home_venue": ("hometeam_home_xg", "hometeam_home_xga", "+"),
    "tempo_away_venue": ("awayteam_away_xg", "awayteam_away_xga", "+"),
}
_POWER_TEMPO_COMBINED = {
    "power_diff": ("power_home", "power_away", "-"),
    "power_diff_venue": ("power_home_venue", "power_away_venue", "-"),
    "tempo_sum": ("tempo_home", "tempo_away", "+"),
}
POWER_TEMPO_METRICS = (*_POWER_TEMPO_PARTS, *_POWER_TEMPO_COMBINED)


def power_tempo_value(d: Dict[str, Any], metric: str) -> Optional[float]:
    if metric in _POWER_TEMPO_COMBINED:
        a_key, b_key, op = _POWER_TEMPO_COMBINED[metric]
        a, b = power_tempo_value(d, a_key), power_tempo_value(d, b_key)
    else:
        a_key, b_key, op = _POWER_TEMPO_PARTS[metric]
        a, b = _f(d.get(a_key)), _f(d.get(b_key))
    if a is None or b is None:
        return None
    if op == "/":
        return a / b if b > 0 else None
    return a + b if op == "+" else a - b


def _metric_value(row: Dict[str, Any], metric: str) -> Optional[float]:
    if metric in POWER_TEMPO_METRICS:
        return power_tempo_value(row, metric)
    if metric == "chance":
        return normalize_chance(row.get("chance"))
    if metric == "odds":
        return _f(row.get("odds"))
    if metric == "rating_home":
        return _f(row.get("rating_h"))
    if metric == "rating_away":
        return _f(row.get("rating_a"))
    if metric == "rating_avg":
        rh, ra = _f(row.get("rating_h")), _f(row.get("rating_a"))
        if rh is None and ra is None:
            return None
        return ((rh or 0.0) + (ra or 0.0)) / (2.0 if rh is not None and ra is not None else 1.0)
    if metric == "rating_sum":
        rh, ra = _f(row.get("rating_h")), _f(row.get("rating_a"))
        if rh is None or ra is None:
            return None
        return rh + ra
    if metric == "rating_diff" or metric == "glicko_diff":
        rh, ra = _f(row.get("rating_h")), _f(row.get("rating_a"))
        if rh is None or ra is None:
            return None
        return rh - ra
    if metric == "xg_glicko_home":
        return _f(row.get("xg_glicko_h"))
    if metric == "xg_glicko_away":
        return _f(row.get("xg_glicko_a"))
    if metric == "xg_glicko_sum":
        xh = _f(row.get("xg_glicko_h"))
        xa = _f(row.get("xg_glicko_a"))
        if xh is None and xa is None:
            return None
        return (xh or 0.0) + (xa or 0.0)
    if metric == "xg_glicko_diff":
        xh = _f(row.get("xg_glicko_h"))
        xa = _f(row.get("xg_glicko_a"))
        if xh is None or xa is None:
            return None
        return xh - xa
    if metric == "rating_ratio":
        rh, ra = _f(row.get("rating_h")), _f(row.get("rating_a"))
        if rh is None or ra is None or ra == 0:
            return None
        return rh / ra
    if metric == "xg_glicko_ratio":
        xh = _f(row.get("xg_glicko_h"))
        xa = _f(row.get("xg_glicko_a"))
        if xh is None or xa is None or xa == 0:
            return None
        return xh / xa
    # Form2 (saisonale Avgs → pred. xG)
    if metric == "xg_form2_home":
        return _f(row.get("xg_form2_h") or row.get("xg_form2_home"))
    if metric == "xg_form2_away":
        return _f(row.get("xg_form2_a") or row.get("xg_form2_away"))
    if metric == "xg_form2_sum":
        xh = _f(row.get("xg_form2_h") or row.get("xg_form2_home"))
        xa = _f(row.get("xg_form2_a") or row.get("xg_form2_away"))
        if xh is None and xa is None:
            return None
        return (xh or 0.0) + (xa or 0.0)
    if metric == "xg_form2_diff":
        xh = _f(row.get("xg_form2_h") or row.get("xg_form2_home"))
        xa = _f(row.get("xg_form2_a") or row.get("xg_form2_away"))
        if xh is None or xa is None:
            return None
        return xh - xa
    if metric == "xg_form2_ratio":
        xh = _f(row.get("xg_form2_h") or row.get("xg_form2_home"))
        xa = _f(row.get("xg_form2_a") or row.get("xg_form2_away"))
        if xh is None or xa is None or xa == 0:
            return None
        return xh / xa
    if metric == "form2_avg_xg_home":
        return _f(row.get("form2_home_avg_xg"))
    if metric == "form2_avg_xg_away":
        return _f(row.get("form2_away_avg_xg"))
    if metric == "form2_avg_xga_home":
        return _f(row.get("form2_home_avg_xga"))
    if metric == "form2_avg_xga_away":
        return _f(row.get("form2_away_avg_xga"))
    if metric == "form2_avg_gf_home":
        return _f(row.get("form2_home_avg_gf"))
    if metric == "form2_avg_gf_away":
        return _f(row.get("form2_away_avg_gf"))
    if metric == "form2_avg_ga_home":
        return _f(row.get("form2_home_avg_ga"))
    if metric == "form2_avg_ga_away":
        return _f(row.get("form2_away_avg_ga"))
    # Venue-Split (Namen B)
    if metric in (
        "hometeam_home_xg", "hometeam_home_xga", "hometeam_home_gf", "hometeam_home_ga",
        "hometeam_away_xg", "hometeam_away_xga", "hometeam_away_gf", "hometeam_away_ga",
        "awayteam_home_xg", "awayteam_home_xga", "awayteam_home_gf", "awayteam_home_ga",
        "awayteam_away_xg", "awayteam_away_xga", "awayteam_away_gf", "awayteam_away_ga",
        "hometeam_pred_xg", "awayteam_pred_xg",
    ):
        return _f(row.get(metric))
    # Tatsächliche Match-xG (nach dem Spiel / calculated)
    if metric == "xg_match_home":
        return _f(row.get("xg_h") or row.get("xg_match_h"))
    if metric == "xg_match_away":
        return _f(row.get("xg_a") or row.get("xg_match_a"))
    if metric == "xg_match_sum":
        xh = _f(row.get("xg_h") or row.get("xg_match_h"))
        xa = _f(row.get("xg_a") or row.get("xg_match_a"))
        if xh is None and xa is None:
            return None
        return (xh or 0.0) + (xa or 0.0)
    if metric == "xg_match_diff":
        xh = _f(row.get("xg_h") or row.get("xg_match_h"))
        xa = _f(row.get("xg_a") or row.get("xg_match_a"))
        if xh is None or xa is None:
            return None
        return xh - xa
    if metric == "xg_match_ratio":
        xh = _f(row.get("xg_h") or row.get("xg_match_h"))
        xa = _f(row.get("xg_a") or row.get("xg_match_a"))
        if xh is None or xa is None or xa == 0:
            return None
        return xh / xa
    # Quoten-Felder (unabhängig vom gewählten Markt)
    quote_keys = {
        "home_quote": ("home_quote", "odd_home"),
        "draw_quote": ("draw_quote", "odd_draw"),
        "away_quote": ("away_quote", "odd_away"),
        "over_25_quote": ("over_25_quote", "odd_over_25"),
        "under_25_quote": ("under_25_quote", "odd_under_25"),
        "quote_home": ("home_quote", "odd_home"),
        "quote_away": ("away_quote", "odd_away"),
        "quote_draw": ("draw_quote", "odd_draw"),
    }
    if metric in quote_keys:
        for key in quote_keys[metric]:
            v = _f(row.get(key))
            if v is not None:
                return v
        return None
    return None


RANKABLE_METRICS = (
    "chance",
    "odds",
    "xroi_pct",
    "rating_home",
    "rating_away",
    "rating_avg",
    "rating_diff",
    "rating_ratio",
    "rating_sum",
    "xg_glicko_home",
    "xg_glicko_away",
    "xg_glicko_sum",
    "xg_glicko_diff",
    "xg_glicko_ratio",
    "xg_form2_home",
    "xg_form2_away",
    "xg_form2_sum",
    "xg_form2_diff",
    "xg_form2_ratio",
    "form2_avg_xg_home",
    "form2_avg_xg_away",
    "form2_avg_xga_home",
    "form2_avg_xga_away",
    "form2_avg_gf_home",
    "form2_avg_gf_away",
    "form2_avg_ga_home",
    "form2_avg_ga_away",
    "hometeam_home_xg",
    "hometeam_home_xga",
    "hometeam_home_gf",
    "hometeam_home_ga",
    "hometeam_away_xg",
    "hometeam_away_xga",
    "hometeam_away_gf",
    "hometeam_away_ga",
    "awayteam_home_xg",
    "awayteam_home_xga",
    "awayteam_home_gf",
    "awayteam_home_ga",
    "awayteam_away_xg",
    "awayteam_away_xga",
    "awayteam_away_gf",
    "awayteam_away_ga",
    "hometeam_pred_xg",
    "awayteam_pred_xg",
    "power_home",
    "power_away",
    "power_diff",
    "tempo_home",
    "tempo_away",
    "tempo_sum",
    "power_home_venue",
    "power_away_venue",
    "power_diff_venue",
    "tempo_home_venue",
    "tempo_away_venue",
)

METRIC_DESCRIPTIONS = {
    "chance": (
        "Gewinnwahrscheinlichkeit des gewählten Markts (0–1) vor dem Spiel, "
        "aus historischen Trefferquoten / Modellchance."
    ),
    "odds": (
        "Dezimalquote des gewählten Markts (Closing bzw. gewählter Quotentyp). "
        "Höhere Quote = höheres Risiko/Auszahlung."
    ),
    "xroi_pct": (
        "xROI % = (Opening − Closing) / Closing × 100. "
        "Positiv = bessere Quote bei Eröffnung (Closing-Line-Value)."
    ),
    "rating_home": (
        "Glicko-Rating der Heimmannschaft vor dem Spiel. "
        "Höher = stärkere Heimseite laut Glicko."
    ),
    "rating_away": (
        "Glicko-Rating der Auswärtsmannschaft vor dem Spiel. "
        "Höher = stärkere Auswärtsseite laut Glicko."
    ),
    "rating_avg": (
        "Durchschnitt aus Home- und Away-Glicko-Rating. "
        "Misst das allgemeine Niveau beider Teams."
    ),
    "rating_diff": (
        "Glicko-Differenz Home − Away. "
        "Positiv = Heimseite laut Rating stärker; negativ = Auswärtsseite stärker."
    ),
    "rating_ratio": (
        "Verhältnis Glicko-Rating Home / Away. "
        "> 1 = Heimseite stärker laut Rating; < 1 = Auswärtsseite stärker."
    ),
    "rating_sum": (
        "Summe Glicko-Rating Home + Away. "
        "Misst das Gesamtniveau beider Teams (= 2 × rating_avg)."
    ),
    "glicko_diff": (
        "Alias für rating_diff: Glicko Home − Away. "
        "Positiv = Heimseite stärker; negativ = Auswärtsseite stärker."
    ),
    "xg_glicko_home": (
        "Erwartete Tore (xG) der Heimmannschaft aus dem Glicko-Modell (pre-match), "
        "nicht die tatsächlichen Nachspiel-xG."
    ),
    "xg_glicko_away": (
        "Erwartete Tore (xG) der Auswärtsmannschaft aus dem Glicko-Modell (pre-match)."
    ),
    "xg_glicko_sum": (
        "Summe xG Glicko Home + Away. "
        "Proxy für erwartete Gesamtchancen / Over-Potenzial."
    ),
    "xg_glicko_diff": (
        "Differenz xG Glicko Home − Away. "
        "Positiv = Heimseite wird offensiv stärker eingeschätzt."
    ),
    "xg_glicko_ratio": (
        "Verhältnis xG Glicko Home / Away. "
        "> 1 = Heimseite offensiv stärker eingeschätzt; < 1 = Auswärtsseite."
    ),
    "xg_form2_home": (
        "Erwartete Tore (xG) Home aus Form2: (Ø xG Home + Ø xGA Away) / 2 "
        "aus der laufenden Saison bis vor diesem Spiel."
    ),
    "xg_form2_away": (
        "Erwartete Tore (xG) Away aus Form2: (Ø xG Away + Ø xGA Home) / 2 "
        "aus der laufenden Saison bis vor diesem Spiel."
    ),
    "xg_form2_sum": "Summe xG Form2 Home + Away (saisonale Form-Vorhersage).",
    "xg_form2_diff": (
        "Differenz xG Form2 Home − Away. "
        "Positiv = Heimseite laut Saisonform offensiv stärker."
    ),
    "xg_form2_ratio": (
        "Verhältnis xG Form2 Home / Away. "
        "> 1 = Heimseite stärker laut Form2; < 1 = Auswärtsseite."
    ),
    "form2_avg_xg_home": "Saison-Durchschnitt Match-xG der Heimmannschaft vor dem Spiel.",
    "form2_avg_xg_away": "Saison-Durchschnitt Match-xG der Auswärtsmannschaft vor dem Spiel.",
    "form2_avg_xga_home": "Saison-Durchschnitt xGA (zugelassene xG) der Heimmannschaft vor dem Spiel.",
    "form2_avg_xga_away": "Saison-Durchschnitt xGA (zugelassene xG) der Auswärtsmannschaft vor dem Spiel.",
    "form2_avg_gf_home": "Saison-Durchschnitt erzielter Tore der Heimmannschaft vor dem Spiel.",
    "form2_avg_gf_away": "Saison-Durchschnitt erzielter Tore der Auswärtsmannschaft vor dem Spiel.",
    "form2_avg_ga_home": "Saison-Durchschnitt Gegentore der Heimmannschaft vor dem Spiel.",
    "form2_avg_ga_away": "Saison-Durchschnitt Gegentore der Auswärtsmannschaft vor dem Spiel.",
    "hometeam_home_xg": "Ø Match-xG des Heimteams nur in Heimspielen (Saison, vor Kickoff).",
    "hometeam_home_xga": "Ø xGA des Heimteams nur in Heimspielen.",
    "hometeam_home_gf": "Ø Tore des Heimteams nur in Heimspielen.",
    "hometeam_home_ga": "Ø Gegentore des Heimteams nur in Heimspielen.",
    "hometeam_away_xg": "Ø Match-xG des Heimteams nur in Auswärtsspielen.",
    "hometeam_away_xga": "Ø xGA des Heimteams nur in Auswärtsspielen.",
    "hometeam_away_gf": "Ø Tore des Heimteams nur in Auswärtsspielen.",
    "hometeam_away_ga": "Ø Gegentore des Heimteams nur in Auswärtsspielen.",
    "awayteam_home_xg": "Ø Match-xG des Gasts nur in dessen Heimspielen.",
    "awayteam_home_xga": "Ø xGA des Gasts nur in dessen Heimspielen.",
    "awayteam_home_gf": "Ø Tore des Gasts nur in dessen Heimspielen.",
    "awayteam_home_ga": "Ø Gegentore des Gasts nur in dessen Heimspielen.",
    "awayteam_away_xg": "Ø Match-xG des Gasts nur in Auswärtsspielen.",
    "awayteam_away_xga": "Ø xGA des Gasts nur in Auswärtsspielen.",
    "awayteam_away_gf": "Ø Tore des Gasts nur in Auswärtsspielen.",
    "awayteam_away_ga": "Ø Gegentore des Gasts nur in Auswärtsspielen.",
    "hometeam_pred_xg": "Venue-Pred xG Heim: (hometeam_home_xg + awayteam_away_xga) / 2.",
    "awayteam_pred_xg": "Venue-Pred xG Gast: (awayteam_away_xg + hometeam_home_xga) / 2.",
    "xg_match_home": (
        "Tatsächliche xG der Heimmannschaft in diesem Spiel (calculated/expectedGoals). "
        "Look-ahead — erst nach dem Spiel bekannt."
    ),
    "xg_match_away": (
        "Tatsächliche xG der Auswärtsmannschaft in diesem Spiel. Look-ahead."
    ),
    "xg_match_sum": "Summe der tatsächlichen Match-xG Home + Away. Look-ahead.",
    "xg_match_diff": "Differenz Match-xG Home − Away. Look-ahead.",
    "xg_match_ratio": "Verhältnis Match-xG Home / Away. Look-ahead.",
    "away_quote": "Closing-/gewählte Away-Quote (2) des Spiels.",
    "home_quote": "Closing-/gewählte Home-Quote (1) des Spiels.",
    "draw_quote": "Closing-/gewählte Draw-Quote (X) des Spiels.",
    "over_25_quote": "Quote Over 2.5 des Spiels.",
    "under_25_quote": "Quote Under 2.5 des Spiels.",
    "power_home": "Ø xG ÷ Ø xGA des Heimteams (alle Saisonspiele). Über 1 = erzeugt mehr Chancen als es zulässt.",
    "power_away": "Ø xG ÷ Ø xGA des Gastteams (alle Saisonspiele). Über 1 = erzeugt mehr Chancen als es zulässt.",
    "power_diff": "Power Home − Power Away. Positiv = Heimteam laut Chancenverhältnis stärker, negativ = Gast stärker.",
    "tempo_home": "Ø xG + Ø xGA des Heimteams: Chancen pro Spiel insgesamt — hoch = offene Spiele.",
    "tempo_away": "Ø xG + Ø xGA des Gastteams: Chancen pro Spiel insgesamt — hoch = offene Spiele.",
    "tempo_sum": "Tempo Home + Tempo Away — erwartete Offenheit des Spiels (interessant für Over/Under).",
    "power_home_venue": "Wie Power Home, aber nur Heimspiele des Heimteams.",
    "power_away_venue": "Wie Power Away, aber nur Auswärtsspiele des Gastteams.",
    "power_diff_venue": "Power Home (Heimspiele) − Power Away (Auswärtsspiele).",
    "tempo_home_venue": "Wie Tempo Home, aber nur Heimspiele des Heimteams.",
    "tempo_away_venue": "Wie Tempo Away, aber nur Auswärtsspiele des Gastteams.",
}

RULE_DESCRIPTIONS = {
    ">= p70 (Top ~30%)": "Nur Wetten im oberen ~30% der Metric-Werte (ab 70. Perzentil).",
    ">= p80 (Top ~20%)": "Nur Wetten im oberen ~20% der Metric-Werte (ab 80. Perzentil).",
    ">= p90 (Top ~10%)": "Nur Wetten im oberen ~10% der Metric-Werte (ab 90. Perzentil).",
    "<= p30 (Bottom ~30%)": "Nur Wetten im unteren ~30% der Metric-Werte (bis 30. Perzentil).",
    "<= p20 (Bottom ~20%)": "Nur Wetten im unteren ~20% der Metric-Werte (bis 20. Perzentil).",
    "<= p10 (Bottom ~10%)": "Nur Wetten im unteren ~10% der Metric-Werte (bis 10. Perzentil).",
}


def metric_description(metric: str) -> str:
    return METRIC_DESCRIPTIONS.get(metric, f"Metric „{metric}“.")


def rule_description(rule: str) -> str:
    return RULE_DESCRIPTIONS.get(rule, f"Regel „{rule}“.")


# Anzeige-Namen der Metriken (gleiches Schema wie web/frontend/src/metricNames.js).
# Interne Schlüssel bleiben, damit gespeicherte Strategien weiter funktionieren.
# Home/Away = Heimteam bzw. Gast; Klammer = Datenbasis; „xG Saison“ = früher „Form2“.
METRIC_DISPLAY_NAMES = {
    "rating_home": "Rating Home",
    "rating_away": "Rating Away",
    "rating_avg": "Rating Ø (Home + Away) ÷ 2",
    "rating_sum": "Rating Home + Away",
    "rating_diff": "Rating Home − Away",
    "glicko_diff": "Rating Home − Away",
    "rating_ratio": "Rating Home ÷ Away",
    "glicko_rating": "Rating Ø (Home + Away) ÷ 2",
    "xg_glicko_home": "xG Glicko Home",
    "xg_glicko_away": "xG Glicko Away",
    "xg_home_glicko": "xG Glicko Home",
    "xg_away_glicko": "xG Glicko Away",
    "xg_glicko_sum": "xG Glicko Home + Away",
    "glicko_xg": "xG Glicko Home + Away",
    "xg_glicko_diff": "xG Glicko Home − Away",
    "xg_glicko_ratio": "xG Glicko Home ÷ Away",
    "xg_form2_home": "xG Saison Home",
    "xg_form2_away": "xG Saison Away",
    "xg_form2_sum": "xG Saison Home + Away",
    "xg_form2_diff": "xG Saison Home − Away",
    "xg_form2_ratio": "xG Saison Home ÷ Away",
    "hometeam_pred_xg": "xG Venue Home",
    "awayteam_pred_xg": "xG Venue Away",
    "form2_avg_xg_home": "Ø xG Home (Saison)",
    "form2_avg_xg_away": "Ø xG Away (Saison)",
    "form2_avg_xga_home": "Ø xGA Home (Saison)",
    "form2_avg_xga_away": "Ø xGA Away (Saison)",
    "form2_avg_gf_home": "Ø Tore Home (Saison)",
    "form2_avg_gf_away": "Ø Tore Away (Saison)",
    "form2_avg_ga_home": "Ø Gegentore Home (Saison)",
    "form2_avg_ga_away": "Ø Gegentore Away (Saison)",
    "hometeam_home_xg": "Ø xG Home (Heimspiele)",
    "hometeam_home_xga": "Ø xGA Home (Heimspiele)",
    "hometeam_home_gf": "Ø Tore Home (Heimspiele)",
    "hometeam_home_ga": "Ø Gegentore Home (Heimspiele)",
    "hometeam_away_xg": "Ø xG Home (Auswärtsspiele)",
    "hometeam_away_xga": "Ø xGA Home (Auswärtsspiele)",
    "hometeam_away_gf": "Ø Tore Home (Auswärtsspiele)",
    "hometeam_away_ga": "Ø Gegentore Home (Auswärtsspiele)",
    "awayteam_home_xg": "Ø xG Away (Heimspiele)",
    "awayteam_home_xga": "Ø xGA Away (Heimspiele)",
    "awayteam_home_gf": "Ø Tore Away (Heimspiele)",
    "awayteam_home_ga": "Ø Gegentore Away (Heimspiele)",
    "awayteam_away_xg": "Ø xG Away (Auswärtsspiele)",
    "awayteam_away_xga": "Ø xGA Away (Auswärtsspiele)",
    "awayteam_away_gf": "Ø Tore Away (Auswärtsspiele)",
    "awayteam_away_ga": "Ø Gegentore Away (Auswärtsspiele)",
    "xg_match_home": "xG Match Home",
    "xg_match_away": "xG Match Away",
    "xg_match_sum": "xG Match Home + Away",
    "xg_match_diff": "xG Match Home − Away",
    "xg_match_ratio": "xG Match Home ÷ Away",
    "rd_home": "Rating-Unsicherheit (RD) Home",
    "rd_away": "Rating-Unsicherheit (RD) Away",
    "vol_home": "Rating-Volatilität Home",
    "vol_away": "Rating-Volatilität Away",
    "power_home": "Power Home (Saison) xG ÷ xGA",
    "power_away": "Power Away (Saison) xG ÷ xGA",
    "power_diff": "Power Home − Away (Saison)",
    "tempo_home": "Tempo Home (Saison) xG + xGA",
    "tempo_away": "Tempo Away (Saison) xG + xGA",
    "tempo_sum": "Tempo Home + Away (Saison)",
    "power_home_venue": "Power Home (Heimspiele) xG ÷ xGA",
    "power_away_venue": "Power Away (Auswärtsspiele) xG ÷ xGA",
    "power_diff_venue": "Power Home − Away (Venue)",
    "tempo_home_venue": "Tempo Home (Heimspiele) xG + xGA",
    "tempo_away_venue": "Tempo Away (Auswärtsspiele) xG + xGA",
}
PERCENTILE_METRIC_LABELS.update(METRIC_DISPLAY_NAMES)


def metric_expr(metric: str) -> str:
    """Anzeige-Name/Formel, z. B. rating_diff → „Rating Home − Away“; sonst der Metrik-Name."""
    return PERCENTILE_METRIC_LABELS.get(metric, metric)


def _percentile_cut(sorted_vals: List[float], pct: float) -> Optional[float]:
    """pct in 0..100; higher pct = higher threshold on ascending sorted list."""
    if not sorted_vals:
        return None
    if pct <= 0:
        return sorted_vals[0]
    if pct >= 100:
        return sorted_vals[-1]
    idx = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, idx))]


def rank_metrics_influence(
    results: List[Dict[str, Any]],
    *,
    min_n: int = 40,
    metrics: Optional[Sequence[str]] = None,
    sort_by: str = "roi",
) -> Dict[str, Any]:
    """Testet Metric-Schwellen und rankt nach ROI- oder Profit-Verbesserung vs. Baseline.

    Pro Metric: Top/Bottom-Quantile (>=p70/p80/p90, <=p30/p20/p10).
    sort_by: 'roi' → Δ ROI, dann Δ Profit; 'profit' → Δ Profit, dann Δ ROI.
    Match-xG (Look-ahead) wird bewusst ausgeschlossen.
    """
    baseline = compute_strategy_metrics(results)
    base_roi = baseline.get("roi_pct") or 0.0
    base_profit = baseline.get("total_profit") or 0.0
    base_n = baseline.get("n") or 0

    raw = list(metrics) if metrics else list(RANKABLE_METRICS)
    # Nie Match-xG / Look-ahead-Ergebnis-Metriken in Korrelation
    metric_list = [
        m
        for m in raw
        if m
        and not str(m).startswith("xg_match")
        and str(m) not in ("profit", "xg_home_match", "xg_away_match")
    ]
    # Regeln: (label, cmp, percentile) — percentile auf aufsteigend sortierten Werten
    rules = [
        (">= p70 (Top ~30%)", "gte", 70),
        (">= p80 (Top ~20%)", "gte", 80),
        (">= p90 (Top ~10%)", "gte", 90),
        ("<= p30 (Bottom ~30%)", "lte", 30),
        ("<= p20 (Bottom ~20%)", "lte", 20),
        ("<= p10 (Bottom ~10%)", "lte", 10),
    ]

    ranked: List[Dict[str, Any]] = []
    # Gleiche Spielauswahl nur einmal: bei Gleichständen fallen p70/p80 auf denselben Wert,
    # und rating_sum wählt immer dieselben Spiele wie rating_avg
    seen_subsets: set = set()
    for metric in metric_list:
        pairs = []
        for r in results:
            v = _metric_value(r, metric)
            if v is not None:
                pairs.append((v, r))
        if len(pairs) < max(min_n, 20):
            continue
        vals = sorted(v for v, _ in pairs)
        for rule_label, cmp_op, pct in rules:
            thr = _percentile_cut(vals, float(pct))
            if thr is None:
                continue
            if cmp_op == "gte":
                subset = [r for v, r in pairs if v >= thr]
                cond = f"{metric_expr(metric)} ≥ {thr:.4g}"
            else:
                subset = [r for v, r in pairs if v <= thr]
                cond = f"{metric_expr(metric)} ≤ {thr:.4g}"
            if len(subset) < min_n:
                continue
            subset_key = frozenset(id(r) for r in subset)
            if subset_key in seen_subsets:
                continue
            seen_subsets.add(subset_key)
            m = compute_strategy_metrics(subset)
            roi = m.get("roi_pct") or 0.0
            profit = m.get("total_profit") or 0.0
            ranked.append({
                "metric": metric,
                "metric_label": metric_expr(metric),
                "rule": rule_label,
                "condition": cond,
                "threshold": thr,
                "n": m.get("n") or 0,
                "wins": m.get("wins") or 0,
                "win_rate": m.get("win_rate") or 0.0,
                "total_profit": profit,
                "roi_pct": roi,
                "roi_delta": roi - base_roi,
                "profit_delta": profit - base_profit,
                "max_losing_streak": m.get("max_losing_streak") or 0,
                "avg_odds": m.get("avg_odds") or 0.0,
                "coverage_pct": ((m.get("n") or 0) / base_n * 100.0) if base_n else 0.0,
            })

    sb = (sort_by or "roi").strip().lower()
    if sb in ("profit", "profit_delta", "delta_profit"):
        ranked.sort(key=lambda x: (x["profit_delta"], x["roi_delta"], x["n"]), reverse=True)
        sort_mode = "profit"
    else:
        ranked.sort(key=lambda x: (x["roi_delta"], x["profit_delta"], x["n"]), reverse=True)
        sort_mode = "roi"
    return {
        "baseline": baseline,
        "ranked": ranked,
        "min_n": min_n,
        "sort_by": sort_mode,
    }


BUCKET_METRICS = (
    "away_quote",
    "home_quote",
    "draw_quote",
    "odds",
    "chance",
    "rating_diff",
    "rating_ratio",
    "rating_sum",
    "glicko_diff",
    "rating_avg",
    "xg_glicko_sum",
    "xg_glicko_diff",
    "xg_glicko_ratio",
    "xg_glicko_home",
    "xg_glicko_away",
    "xg_form2_sum",
    "xg_form2_diff",
    "xg_form2_ratio",
    "xg_form2_home",
    "xg_form2_away",
    "form2_avg_xg_home",
    "form2_avg_xg_away",
    "form2_avg_xga_home",
    "form2_avg_xga_away",
    "form2_avg_gf_home",
    "form2_avg_gf_away",
    "hometeam_home_xg",
    "hometeam_home_xga",
    "hometeam_away_xg",
    "awayteam_away_xg",
    "awayteam_away_xga",
    "hometeam_pred_xg",
    "awayteam_pred_xg",
    "over_25_quote",
    "under_25_quote",
    "power_home",
    "power_away",
    "power_diff",
    "tempo_home",
    "tempo_away",
    "tempo_sum",
    "power_home_venue",
    "power_away_venue",
    "power_diff_venue",
    "tempo_home_venue",
    "tempo_away_venue",
)


def _avg_xg_glicko(subset: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Mittelwerte xG Glicko Home/Away (und Sum/Diff) — nur Vorhersage, kein Match-xG."""
    xh_vals: List[float] = []
    xa_vals: List[float] = []
    for r in subset:
        xh = _f(r.get("xg_glicko_h"))
        xa = _f(r.get("xg_glicko_a"))
        if xh is not None:
            xh_vals.append(xh)
        if xa is not None:
            xa_vals.append(xa)
    avg_h = (sum(xh_vals) / len(xh_vals)) if xh_vals else None
    avg_a = (sum(xa_vals) / len(xa_vals)) if xa_vals else None
    avg_sum = None
    avg_diff = None
    if avg_h is not None and avg_a is not None:
        avg_sum = avg_h + avg_a
        avg_diff = avg_h - avg_a
    elif avg_h is not None:
        avg_sum = avg_h
    elif avg_a is not None:
        avg_sum = avg_a
    return {
        "avg_xg_glicko_h": avg_h,
        "avg_xg_glicko_a": avg_a,
        "avg_xg_glicko_sum": avg_sum,
        "avg_xg_glicko_diff": avg_diff,
    }


def _nice_step(span: float, target_bins: int = 16) -> float:
    """Rundet Schrittweite auf lesbare Werte (0.05, 0.1, 1, 10, …)."""
    if span <= 0 or target_bins <= 0:
        return 1.0
    raw = span / float(target_bins)
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = mult * mag
        if step >= raw * 0.85:
            return step
    return 10.0 * mag


def auto_bucket_metric(
    results: List[Dict[str, Any]],
    metric: str,
    *,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    step: Optional[float] = None,
    target_bins: int = 16,
) -> Dict[str, Any]:
    """Bucket-Analyse mit Auto-Range (Min/Max/Step aus den Daten), inkl. bestem ROI-Bin."""
    vals = []
    for r in results or []:
        v = _metric_value(r, metric)
        if v is not None:
            vals.append(v)
    if len(vals) < 5:
        return {
            "ok": False,
            "error": "Zu wenig Werte für diese Metrik (min. 5).",
            "metric": metric,
            "bins": [],
            "n_values": len(vals),
        }
    lo = float(vmin) if vmin is not None else min(vals)
    hi = float(vmax) if vmax is not None else max(vals)
    if hi < lo:
        lo, hi = hi, lo
    if abs(hi - lo) < 1e-12:
        hi = lo + 1.0
    st = float(step) if step is not None and step > 0 else _nice_step(hi - lo, target_bins)
    report = bucket_metric_range(results, metric, lo, hi, st)
    bins = report.get("bins") or []
    nonempty = [b for b in bins if (b.get("n") or 0) > 0]
    best = None
    if nonempty:
        best = max(
            nonempty,
            key=lambda b: (b.get("roi_pct") or -1e18, b.get("total_profit") or -1e18, b.get("n") or 0),
        )
    return {
        "ok": True,
        **report,
        "n_values": len(vals),
        "best_bin": best,
        "metric_label": PERCENTILE_METRIC_LABELS.get(metric) or METRIC_DESCRIPTIONS.get(metric, metric),
    }


def bucket_metric_range(
    results: List[Dict[str, Any]],
    metric: str,
    vmin: float,
    vmax: float,
    step: float = 0.1,
) -> Dict[str, Any]:
    """Zerlegt [vmin, vmax] in Bins der Breite step und berechnet Profit/ROI je Bin.

    Beispiel: away_quote 3.0–3.5, step 0.1 → 3.0–3.1, 3.1–3.2, …, 3.4–3.5
    Letztes Bin inkl. vmax.
    """
    if step <= 0:
        raise ValueError("step muss > 0 sein")
    if vmax < vmin:
        vmin, vmax = vmax, vmin

    # Float-sichere Bin-Grenzen
    edges = []
    cur = float(vmin)
    # Schutz vor Endlosschleife
    max_bins = 500
    while cur < vmax - 1e-12 and len(edges) < max_bins:
        nxt = round(cur + step, 10)
        if nxt > vmax:
            nxt = float(vmax)
        edges.append((cur, nxt))
        cur = nxt
    if not edges:
        edges = [(float(vmin), float(vmax))]

    bins_out: List[Dict[str, Any]] = []
    for lo, hi in edges:
        subset = []
        for r in results:
            v = _metric_value(r, metric)
            if v is None:
                continue
            # [lo, hi) außer letztes Bin [lo, hi]
            is_last = abs(hi - vmax) < 1e-9
            if is_last:
                if lo - 1e-12 <= v <= hi + 1e-12:
                    subset.append(r)
            else:
                if lo - 1e-12 <= v < hi - 1e-12:
                    subset.append(r)
        m = compute_strategy_metrics(subset)
        xg = _avg_xg_glicko(subset)
        bins_out.append({
            "metric": metric,
            "bin_from": lo,
            "bin_to": hi,
            "label": f"{lo:.2f}–{hi:.2f}",
            "n": m.get("n") or 0,
            "wins": m.get("wins") or 0,
            "win_rate": m.get("win_rate") or 0.0,
            "total_profit": m.get("total_profit") or 0.0,
            "roi_pct": m.get("roi_pct") or 0.0,
            "avg_odds": m.get("avg_odds") or 0.0,
            "max_losing_streak": m.get("max_losing_streak") or 0,
            **xg,
        })

    in_range = []
    for r in results:
        v = _metric_value(r, metric)
        if v is not None and vmin - 1e-12 <= v <= vmax + 1e-12:
            in_range.append(r)
    overall = compute_strategy_metrics(in_range)
    overall_xg = _avg_xg_glicko(in_range)
    return {
        "metric": metric,
        "vmin": vmin,
        "vmax": vmax,
        "step": step,
        "bins": bins_out,
        "overall": overall,
        "overall_xg": overall_xg,
        "n_total": len(results),
        "n_in_range": overall.get("n") or 0,
    }


# Vordefinierte Parameter für 1-/2-Parameter-Profit-Optimierung
OPTIMIZE_METRICS = (
    "odds",
    "home_quote",
    "away_quote",
    "over_25_quote",
    "rating_away",
    "rating_home",
    "rating_diff",
    "rating_ratio",
    "rating_sum",
    "rating_avg",
    "xg_glicko_ratio",
    "xg_glicko_diff",
    "xg_glicko_sum",
    "xg_form2_ratio",
    "xg_form2_diff",
    "xg_form2_sum",
    "chance",
    "xroi_pct",
    "power_home",
    "power_away",
    "power_diff",
    "tempo_home",
    "tempo_away",
    "tempo_sum",
)

# Metric → (filter_min_key, filter_max_key)
_OPTIMIZE_FILTER_KEYS = {
    "home_quote": ("odds_home_min", "odds_home_max"),
    "away_quote": ("odds_away_min", "odds_away_max"),
    "over_25_quote": ("odds_over_min", "odds_over_max"),
    "under_25_quote": ("odds_under_min", "odds_under_max"),
    "rating_away": ("glicko_away_min", "glicko_away_max"),
    "rating_home": ("glicko_home_min", "glicko_home_max"),
    "xg_glicko_home": ("xg_glicko_home_min", "xg_glicko_home_max"),
    "xg_glicko_away": ("xg_glicko_away_min", "xg_glicko_away_max"),
    "xg_form2_home": ("xg_form2_home_min", "xg_form2_home_max"),
    "xg_form2_away": ("xg_form2_away_min", "xg_form2_away_max"),
    "xroi_pct": ("xroi_min", "xroi_max"),
}

_ODDS_FILTER_BY_MARKET = {
    "Home": ("odds_home_min", "odds_home_max"),
    "Draw": ("odds_draw_min", "odds_draw_max"),
    "Away": ("odds_away_min", "odds_away_max"),
    "Over 2.5": ("odds_over_min", "odds_over_max"),
    "Under 2.5": ("odds_under_min", "odds_under_max"),
    "Over 3.5": ("odds_over35_min", "odds_over35_max"),
    "Under 3.5": ("odds_under35_min", "odds_under35_max"),
}


def _fmt_thr(v: float) -> str:
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}"
    return f"{v:.4g}"


def _candidate_constraints_for_metric(
    results: List[Dict[str, Any]],
    metric: str,
    *,
    min_n: int,
) -> List[Dict[str, Any]]:
    """Erzeugt gte/lte/between-Kandidaten aus Perzentilen (Quote: extra Band-Fenster)."""
    vals = []
    for r in results:
        v = _metric_value(r, metric)
        if v is not None:
            vals.append(float(v))
    if len(vals) < max(min_n, 12):
        return []
    vals.sort()
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(op: str, lo: Optional[float], hi: Optional[float], label: str) -> None:
        key = (op, round(lo or 0, 6), round(hi or 0, 6))
        if key in seen:
            return
        seen.add(key)
        expr = metric_expr(metric)
        if op == "gte":
            cond = f"{expr} ≥ {_fmt_thr(lo)}"
        elif op == "lte":
            cond = f"{expr} ≤ {_fmt_thr(hi)}"
        else:
            cond = f"{_fmt_thr(lo)} ≤ {expr} ≤ {_fmt_thr(hi)}"
        out.append({
            "metric": metric,
            "op": op,
            "lo": lo,
            "hi": hi,
            "label": label,
            "condition": cond,
        })

    # Einseitige Perzentil-Schwellen
    for pct, tag in ((70, "Top~30%"), (80, "Top~20%"), (90, "Top~10%")):
        thr = _percentile_cut(vals, float(pct))
        if thr is not None:
            add("gte", thr, None, f">= p{pct} ({tag})")
    for pct, tag in ((30, "Bottom~30%"), (20, "Bottom~20%"), (10, "Bottom~10%")):
        thr = _percentile_cut(vals, float(pct))
        if thr is not None:
            add("lte", None, thr, f"<= p{pct} ({tag})")

    # Quote-/Werte-Bänder: [p_a, p_b] — besonders für optimale Quote
    band_pcts = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
    cuts: List[Tuple[int, float]] = []
    for p in band_pcts:
        if p <= 0:
            cuts.append((0, vals[0]))
        elif p >= 100:
            cuts.append((100, vals[-1]))
        else:
            thr = _percentile_cut(vals, float(p))
            if thr is not None:
                cuts.append((p, thr))
    # Fenster über 2–4 Perzentil-Schritte (~20–40 % der Verteilung)
    for width in (2, 3, 4):
        for i in range(len(cuts) - width):
            p_lo, lo = cuts[i]
            p_hi, hi = cuts[i + width]
            if hi < lo:
                continue
            # zu enge Bänder überspringen
            if hi - lo < 1e-9 and metric != "odds":
                continue
            add("between", lo, hi, f"Band p{p_lo}–p{p_hi}")

    return out


def _row_passes_constraint(row: Dict[str, Any], c: Dict[str, Any]) -> bool:
    v = _metric_value(row, c["metric"])
    if v is None:
        return False
    op = c["op"]
    if op == "gte":
        return v >= float(c["lo"])
    if op == "lte":
        return v <= float(c["hi"])
    if op == "between":
        return float(c["lo"]) <= v <= float(c["hi"])
    return False


def _filter_keys_for_metric(metric: str, markets: Sequence[str]) -> Optional[Tuple[str, str]]:
    if metric == "odds":
        if not markets:
            return None
        # Primärer Markt; bei mehreren denselben Typ bevorzugen
        for m in markets:
            keys = _ODDS_FILTER_BY_MARKET.get(m)
            if keys:
                return keys
        return None
    return _OPTIMIZE_FILTER_KEYS.get(metric)


def constraint_to_filter_patch(
    constraint: Dict[str, Any],
    markets: Sequence[str],
) -> Dict[str, Any]:
    """Wandelt eine Constraint in UI-Filterfelder um (soweit möglich)."""
    metric = constraint["metric"]
    keys = _filter_keys_for_metric(metric, markets)
    patch: Dict[str, Any] = {}
    if not keys:
        # rating_diff / ratio etc. haben keinen Direktfilter — nur Hinweis
        return patch
    min_k, max_k = keys
    op = constraint["op"]
    if op == "gte" and constraint.get("lo") is not None:
        patch[min_k] = _fmt_thr(float(constraint["lo"]))
    elif op == "lte" and constraint.get("hi") is not None:
        patch[max_k] = _fmt_thr(float(constraint["hi"]))
    elif op == "between":
        if constraint.get("lo") is not None:
            patch[min_k] = _fmt_thr(float(constraint["lo"]))
        if constraint.get("hi") is not None:
            patch[max_k] = _fmt_thr(float(constraint["hi"]))
    return patch


def optimize_two_params(
    results: List[Dict[str, Any]],
    *,
    markets: Optional[Sequence[str]] = None,
    min_n: int = 25,
    max_params: int = 2,
    metrics: Optional[Sequence[str]] = None,
    top_k: int = 15,
) -> Dict[str, Any]:
    """Sucht 1–2 vordefinierte Parameter-Schwellen mit maximalem Profit.

    Primär Sortierung: total_profit, dann ROI, dann n.
    „odds“ = Quote des gewählten Markts (optimales Quotenband möglich).
    """
    baseline = compute_strategy_metrics(results)
    base_profit = float(baseline.get("total_profit") or 0.0)
    base_roi = float(baseline.get("roi_pct") or 0.0)
    base_n = int(baseline.get("n") or 0)
    market_list = list(markets or [])
    metric_list = [m for m in (metrics or OPTIMIZE_METRICS) if m]
    max_params = max(1, min(int(max_params or 2), 2))
    min_n = max(5, int(min_n or 25))

    # Kandidaten je Metrik vorbereiten
    by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for metric in metric_list:
        cands = _candidate_constraints_for_metric(results, metric, min_n=min_n)
        if cands:
            by_metric[metric] = cands
    usable = list(by_metric.keys())

    evaluated: List[Dict[str, Any]] = []

    def eval_combo(constraints: List[Dict[str, Any]]) -> None:
        subset = [r for r in results if all(_row_passes_constraint(r, c) for c in constraints)]
        if len(subset) < min_n:
            return
        m = compute_strategy_metrics(subset)
        profit = float(m.get("total_profit") or 0.0)
        roi = float(m.get("roi_pct") or 0.0)
        n = int(m.get("n") or 0)
        patch: Dict[str, Any] = {}
        for c in constraints:
            patch.update(constraint_to_filter_patch(c, market_list))
        odds_band = None
        for c in constraints:
            if c["metric"] in ("odds", "home_quote", "away_quote", "over_25_quote", "under_25_quote"):
                if c["op"] == "between":
                    odds_band = {"metric": c["metric"], "min": c["lo"], "max": c["hi"]}
                elif c["op"] == "gte":
                    odds_band = {"metric": c["metric"], "min": c["lo"], "max": None}
                elif c["op"] == "lte":
                    odds_band = {"metric": c["metric"], "min": None, "max": c["hi"]}
                break
        evaluated.append({
            "params": [
                {
                    "metric": c["metric"],
                    "metric_label": PERCENTILE_METRIC_LABELS.get(c["metric"])
                    or METRIC_DESCRIPTIONS.get(c["metric"], c["metric"]),
                    "rule": c["label"],
                    "condition": c["condition"],
                    "op": c["op"],
                    "lo": c.get("lo"),
                    "hi": c.get("hi"),
                }
                for c in constraints
            ],
            "n_params": len(constraints),
            "conditions": [c["condition"] for c in constraints],
            "odds_band": odds_band,
            "suggested_filters": patch,
            "n": n,
            "wins": m.get("wins") or 0,
            "win_rate": m.get("win_rate") or 0.0,
            "total_profit": profit,
            "roi_pct": roi,
            "profit_delta": profit - base_profit,
            "roi_delta": roi - base_roi,
            "avg_odds": m.get("avg_odds") or 0.0,
            "coverage_pct": (n / base_n * 100.0) if base_n else 0.0,
        })

    # 1 Parameter
    for metric in usable:
        for c in by_metric[metric]:
            eval_combo([c])

    # 2 Parameter (verschiedene Metriken)
    if max_params >= 2:
        for i, m1 in enumerate(usable):
            for m2 in usable[i + 1 :]:
                for c1 in by_metric[m1]:
                    for c2 in by_metric[m2]:
                        eval_combo([c1, c2])

    evaluated.sort(
        key=lambda x: (x["total_profit"], x["roi_pct"], x["n"]),
        reverse=True,
    )
    top = evaluated[: max(1, int(top_k or 15))]
    best = top[0] if top else None

    # Beste reine Quote-Empfehlung (nur odds / market quotes)
    best_odds = None
    for row in evaluated:
        if row["n_params"] == 1 and row["params"][0]["metric"] in (
            "odds",
            "home_quote",
            "away_quote",
            "over_25_quote",
        ):
            best_odds = row
            break

    return {
        "ok": True,
        "baseline": baseline,
        "min_n": min_n,
        "max_params": max_params,
        "metrics_used": usable,
        "n_evaluated": len(evaluated),
        "best": best,
        "best_odds_only": best_odds,
        "top": top,
    }


def games_missing_opening_odds(conn, limit: int = 500) -> List[int]:
    """Game-IDs mit Closing-Quote aber ohne Opening (1X2 Home als Proxy)."""
    rows = conn.execute(
        """
        SELECT DISTINCT o.game_id
        FROM game_odds o
        WHERE o.market_id = 1 AND o.name = 'Home'
          AND o.value IS NOT NULL
          AND (o.opening_value IS NULL OR o.opening_value <= 0)
        ORDER BY o.game_id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    out = []
    for r in rows:
        out.append(int(r[0] if not hasattr(r, "keys") else r["game_id"]))
    return out


def _extract_bookmaker_markets(data, bookmaker_id: int):
    """Pick markets list from /Odds response for bookmaker (fallback: first)."""
    if isinstance(data, list) and data:
        chosen = None
        for b in data:
            if isinstance(b, dict) and b.get("bookmakerId") == bookmaker_id:
                chosen = b
                break
        if chosen is None:
            chosen = data[0] if isinstance(data[0], dict) else None
        if chosen:
            return chosen.get("odds") or []
    return None


def backfill_opening_odds(
    client,
    db_manager,
    game_ids: Sequence[int],
    *,
    bookmaker_id: int = 4,
    delay: float = 0.35,
    progress_cb=None,
) -> Dict[str, int]:
    """Lädt Opening-Odds (API opening=true) und speichert in opening_value.

    Default Bookmaker: Pinnacle (4). Fallback: erster Bookie der Antwort.
    """
    import time

    loaded = 0
    empty = 0
    errors = 0
    total = len(list(game_ids))
    for idx, gid in enumerate(game_ids, start=1):
        try:
            raw = client.get_game_odds(int(gid), bookmaker_id=bookmaker_id, opening=True)
            data = raw.get("data", raw) if isinstance(raw, dict) else raw
            markets = _extract_bookmaker_markets(data, bookmaker_id)
            if markets:
                n = db_manager.upsert_odds_markets(int(gid), markets, as_opening=True)
                if n > 0:
                    loaded += 1
                else:
                    empty += 1
            else:
                empty += 1
        except Exception:
            errors += 1
        if progress_cb and (idx % 10 == 0 or idx == total):
            progress_cb(idx, total, loaded, empty, errors)
        if delay > 0:
            time.sleep(delay)
    return {"loaded": loaded, "empty": empty, "errors": errors, "total": total}


def backfill_closing_odds(
    client,
    db_manager,
    game_ids: Sequence[int],
    *,
    bookmaker_id: int = 4,
    delay: float = 0.35,
    progress_cb=None,
) -> Dict[str, int]:
    """Lädt Closing-Odds (API opening=false) und speichert in value.

    Default Bookmaker: Pinnacle (4). Fallback: erster Bookie der Antwort.
    """
    import time

    loaded = 0
    empty = 0
    errors = 0
    ids = list(game_ids)
    total = len(ids)
    for idx, gid in enumerate(ids, start=1):
        try:
            raw = client.get_game_odds(int(gid), bookmaker_id=bookmaker_id, opening=False)
            data = raw.get("data", raw) if isinstance(raw, dict) else raw
            markets = _extract_bookmaker_markets(data, bookmaker_id)
            if markets:
                n = db_manager.upsert_odds_markets(int(gid), markets, as_opening=False)
                if n > 0:
                    loaded += 1
                else:
                    empty += 1
            else:
                empty += 1
        except Exception:
            errors += 1
        if progress_cb and (idx % 10 == 0 or idx == total):
            progress_cb(idx, total, loaded, empty, errors)
        if delay > 0:
            time.sleep(delay)
    return {"loaded": loaded, "empty": empty, "errors": errors, "total": total}
