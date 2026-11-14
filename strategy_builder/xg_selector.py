"""Automatic selection of the best pre-match xG parameter for a given odds setup."""

from typing import Dict, Any, List, Tuple
from .search_space import XG_PARAMS
from .evaluator import evaluate_combination


def select_best_xg(
    base_combo: Dict[str, Any],
    historical_rows: List[Dict[str, Any]],
    percentiles: List[int] | None = None,
) -> Tuple[str, int, Dict[str, Any]]:
    """
    Try several xG parameters and percentiles.
    Return (best_param, best_percentile, best_metrics).
    """
    percentiles = percentiles or [70, 80, 90]
    best_score = float("-inf")
    best = None

    for param in XG_PARAMS:
        for pct in percentiles:
            combo = {**base_combo, "xg_param": param, "xg_percentile": pct}
            result = evaluate_combination(combo, historical_rows)
            if not result.get("valid"):
                continue
            # Prefer higher xROI, then higher number of bets
            score = result.get("xroi", 0) + 0.001 * result.get("n_bets", 0)
            if score > best_score:
                best_score = score
                best = (param, pct, result)

    if best is None:
        # fallback
        return XG_PARAMS[0], 70, {"valid": False, "n_bets": 0}

    return best
