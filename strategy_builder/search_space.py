"""Suchraum für den automatischen Strategie-Builder.

Eine Kombination = EIN Wettmarkt + Quotenband dieses Markts + optional EINE Vor-Spiel-Bedingung
(Metrik >= bzw. <= Schwelle). Die Metriken sind so gewählt, dass sie sich 1:1 als Vergleichsfilter
der Strategie-Seite speichern lassen (Attribut1 [+ − /] Attribut2  ≥/≤  Wert).
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

MARKETS = ["Home", "Draw", "Away", "Over 2.5", "Under 2.5"]

# Quotenbänder je Markt (Wette nur, wenn die Quote des Markts im Band liegt)
ODDS_BANDS: Dict[str, List[Tuple[float, float]]] = {
    "Home": [(1.01, 1.3), (1.3, 1.5), (1.5, 1.7), (1.7, 2.0), (2.0, 2.5), (2.5, 3.2), (3.2, 4.5), (4.5, 8.0)],
    "Away": [(1.01, 1.3), (1.3, 1.5), (1.5, 1.7), (1.7, 2.0), (2.0, 2.5), (2.5, 3.2), (3.2, 4.5), (4.5, 8.0)],
    "Draw": [(2.0, 3.0), (3.0, 3.4), (3.4, 3.8), (3.8, 4.5), (4.5, 6.0)],
    "Over 2.5": [(1.2, 1.5), (1.5, 1.7), (1.7, 1.9), (1.9, 2.1), (2.1, 2.4), (2.4, 3.0)],
    "Under 2.5": [(1.2, 1.5), (1.5, 1.7), (1.7, 1.9), (1.9, 2.1), (2.1, 2.4), (2.4, 3.0)],
}

# Metrik → (Attribut1, Operation, Attribut2, Label, Glicko?)
# Attributnamen wie in strategy_service._comparison_attr_value → speicherbar als Strategie
METRICS: Dict[str, Tuple[str, str, str, str, bool]] = {
    "power_diff": ("power_home", "-", "power_away", "Power Diff (H−A)", False),
    "power_diff_venue": ("power_home_venue", "-", "power_away_venue", "Power Diff Heim/Ausw.-Ort", False),
    "tempo_sum": ("tempo_home", "+", "tempo_away", "Tempo Summe", False),
    "xg_form2_diff": ("xg_form2_home", "-", "xg_form2_away", "xG Form2 Diff (H−A)", False),
    "xg_form2_sum": ("xg_form2_home", "+", "xg_form2_away", "xG Form2 Summe", False),
    "form2_xg_diff": ("form2_avg_xg_home", "-", "form2_avg_xg_away", "Ø xG Diff (Saison)", False),
    "form2_xga_diff": ("form2_avg_xga_home", "-", "form2_avg_xga_away", "Ø xGA Diff (Saison)", False),
    "pred_xg_diff": ("hometeam_pred_xg", "-", "awayteam_pred_xg", "pred. xG Diff", False),
    "pred_xg_sum": ("hometeam_pred_xg", "+", "awayteam_pred_xg", "pred. xG Summe", False),
    "rating_diff": ("rating_home", "-", "rating_away", "Glicko Rating Diff (H−A)", True),
    "xg_glicko_diff": ("xg_home_glicko", "-", "xg_away_glicko", "xG Glicko Diff (H−A)", True),
    "xg_glicko_sum": ("xg_home_glicko", "+", "xg_away_glicko", "xG Glicko Summe", True),
}

# Schwellen = Quantile der Metrik im Lernzeitraum (nie aus dem Prüfzeitraum)
QUANTILES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
DIRECTIONS = [">=", "<="]

SEARCH_SPACE: Dict[str, Any] = {
    "market": MARKETS,
    "odds_bands": ODDS_BANDS,
    "metric": list(METRICS),
    "quantile": QUANTILES,
    "direction": DIRECTIONS,
    "odds_type": ["opening", "closing"],
}


def metric_names(include_glicko: bool) -> List[str]:
    return [k for k, v in METRICS.items() if include_glicko or not v[4]]


def sample_combination(user_constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Zufällige gültige Kombination; vom Nutzer fixierte Teile bleiben."""
    c = dict(user_constraints or {})
    market = c.get("market") or random.choice(MARKETS)
    combo = {
        "market": market,
        "odds_band": c.get("odds_band") or random.choice(ODDS_BANDS[market]),
        "odds_type": c.get("odds_type") or random.choice(SEARCH_SPACE["odds_type"]),
    }
    if c.get("metric", True) is not None:
        combo["metric"] = c.get("metric") or random.choice(list(METRICS))
        combo["quantile"] = c.get("quantile") or random.choice(QUANTILES)
        combo["direction"] = c.get("direction") or random.choice(DIRECTIONS)
    return combo
