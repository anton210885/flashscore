"""Search space definition for automatic strategy discovery.

User can fix some constraints (e.g. home_odds range).
The searcher explores the rest.
"""

from typing import Dict, List, Tuple, Any

# Pre-match xG-related parameters that can be auto-selected
XG_PARAMS = [
    "xg_glicko_diff",
    "xg_glicko_sum",
    "xg_glicko_ratio",
    "xg_form2_sum",
    "xg_form2_diff",
    "power_diff",
    "power_home",
    "power_away",
    "tempo_sum",
    "xg_form2_home",
    "xg_form2_away",
]

SEARCH_SPACE: Dict[str, Any] = {
    "home_odds": [(1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 2.5)],
    "away_odds": [(1.0, 1.3), (1.3, 1.6), (1.6, 2.0)],
    "over25_odds": [(1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 2.5)],
    "under25_odds": [(1.0, 1.3), (1.3, 1.6), (1.6, 2.0)],
    "use_opening_odds": [True, False],
    "min_games": [6, 10, 15],
    "xg_param": XG_PARAMS,
    "xg_percentile": [60, 70, 80, 90],  # threshold as percentile of the feature
}


def sample_combination(user_constraints: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a random valid combination, respecting user fixed constraints."""
    import random
    combo = {}
    constraints = user_constraints or {}

    for key, options in SEARCH_SPACE.items():
        if key in constraints:
            combo[key] = constraints[key]
        else:
            combo[key] = random.choice(options)
    return combo
