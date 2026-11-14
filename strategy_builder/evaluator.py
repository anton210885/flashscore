"""Evaluate a single strategy combination using real strategy_service logic."""

from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

# Make sure we can import from the parent project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import strategy_service as ss


def combo_to_filters(combo: Dict[str, Any]) -> Dict[str, Any]:
    """Convert our internal combo dict into the filter format expected by strategy_service."""
    filters: Dict[str, Any] = {}

    # Odds ranges
    if "home_odds" in combo and combo["home_odds"]:
        lo, hi = combo["home_odds"]
        filters["odds_home_min"] = lo
        filters["odds_home_max"] = hi
        filters["market_home"] = True

    if "over25_odds" in combo and combo["over25_odds"]:
        lo, hi = combo["over25_odds"]
        filters["odds_over_min"] = lo
        filters["odds_over_max"] = hi
        filters["market_over"] = True

    if "away_odds" in combo and combo["away_odds"]:
        lo, hi = combo["away_odds"]
        filters["odds_away_min"] = lo
        filters["odds_away_max"] = hi
        filters["market_away"] = True

    # Opening vs closing
    if combo.get("use_opening_odds"):
        filters["odds_type"] = "opening"
    else:
        filters["odds_type"] = "closing"

    # Min games
    if "min_games" in combo:
        filters["min_games"] = combo["min_games"]

    return filters


def evaluate_combination(
    combo: Dict[str, Any],
    historical_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply filters from combo and compute real metrics via strategy_service.
    """
    if not historical_rows:
        return {"valid": False, "n_bets": 0, "reason": "no data"}

    filters = combo_to_filters(combo)
    odds_type = filters.get("odds_type", "closing")

    # First pass: basic odds + min_games filtering using existing helpers
    candidate_rows = []
    for row in historical_rows:
        # Check main market odds range
        market = "Home" if filters.get("market_home") else "Over 2.5"
        odds = ss.pick_odds(row, market, odds_type)
        if odds is None:
            continue

        omin, omax = ss.odds_range_for_market(filters, market)
        if not ss.in_range(odds, omin, omax):
            continue

        # Other market odds constraints
        if not ss.passes_other_market_odds(filters, row, odds_type, fallback_closing=True):
            continue

        candidate_rows.append(row)

    # Apply xG percentile filter if requested
    xg_param = combo.get("xg_param")
    xg_pct = combo.get("xg_percentile")
    if xg_param and xg_pct and candidate_rows:
        candidate_rows = ss.apply_percentile_filter(candidate_rows, float(xg_pct), xg_param)

    n = len(candidate_rows)
    min_games = combo.get("min_games", 6)
    if n < min_games:
        return {
            "valid": False,
            "n_bets": n,
            "reason": f"too few bets ({n} < {min_games})",
            "combo": combo,
        }

    # Compute real stats
    # We treat the selected market as the one we bet on
    selected_markets = ss.selected_markets_from_filters(filters)
    stats_list = ss.compute_per_market_stats(
        candidate_rows,
        filters,
        selected_markets=selected_markets,
        odds_type=odds_type,
        only_unselected=False,
        skip_prematch_filters=True,  # we already filtered
    )

    # Aggregate across markets (simple average for now)
    if not stats_list:
        return {"valid": False, "n_bets": n, "reason": "no stats", "combo": combo}

    # Take the primary market stats
    primary = stats_list[0]
    return {
        "valid": True,
        "n_bets": n,
        "roi": primary.get("roi"),
        "xroi": primary.get("xroi"),
        "winrate": primary.get("percent"),
        "profit": primary.get("profit"),
        "combo": combo,
        "primary_market": primary.get("market"),
    }
