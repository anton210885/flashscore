"""Main search loop: random / grid search over strategy combinations."""

from typing import Dict, Any, List
import random
from .search_space import sample_combination
from .xg_selector import select_best_xg
from .evaluator import evaluate_combination


def run_search(
    historical_rows: List[Dict[str, Any]],
    user_constraints: Dict[str, Any] | None = None,
    n_trials: int = 100,
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """
    Explore strategy space.
    For each sampled odds combination, automatically pick the best xG parameter.
    """
    results = []
    user_constraints = user_constraints or {}

    for i in range(n_trials):
        base = sample_combination(user_constraints)
        # Force xg selection
        param, pct, _ = select_best_xg(base, historical_rows)
        full_combo = {**base, "xg_param": param, "xg_percentile": pct}

        metrics = evaluate_combination(full_combo, historical_rows)
        if metrics.get("valid"):
            results.append(metrics)

    # Sort by xROI descending
    results.sort(key=lambda r: r.get("xroi", 0), reverse=True)
    return results[:top_k]


def pretty_print(results: List[Dict[str, Any]]) -> None:
    print(f"{'Rank':<5} {'xROI':>7} {'ROI':>7} {'Bets':>5}  xG param / percentile")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        c = r.get("combo", {})
        print(
            f"{i:<5} {r.get('xroi', 0):>7.3f} {r.get('roi', 0):>7.3f} "
            f"{r.get('n_bets', 0):>5}  {c.get('xg_param')} @ {c.get('xg_percentile')}%"
        )
