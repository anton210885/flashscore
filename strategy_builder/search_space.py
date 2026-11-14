"""Suchraum für den automatischen Strategie-Builder.

Eine Kombination = EIN Wettmarkt + Quotenband dieses Markts + optional EINE Vor-Spiel-Bedingung.
Bewusst klein gehalten, damit weniger Zufallstreffer entstehen:
  • Pro Markt nur Metriken, die fachlich passen: 1X2 → Differenzen, Über/Unter → Summen/Tempo.
  • Pro Markt nur die logische Richtung (Heim: Diff ≥ x, Auswärts: Diff ≤ −x, Remis: |Diff| ≤ x,
    Über: Summe ≥ x, Unter: Summe ≤ x).
  • Grobe Schwellen: Quantile des Lernzeitraums, auf eine runde Schrittweite gerundet.
Die Metriken lassen sich 1:1 als Vergleichsfilter der Strategie-Seite speichern.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

MARKETS = ["Home", "Draw", "Away", "Over 2.5", "Under 2.5"]

_BANDS_1X2 = [
    (1.01, 1.3), (1.3, 1.5), (1.5, 1.7), (1.7, 2.0), (2.01, 2.3), (2.31, 2.6), (2.61, 2.9),
    (2.91, 3.2), (3.21, 3.5), (3.51, 4.0), (4.01, 4.5), (4.51, 5.0), (5.01, 5.5), (5.51, 6.0),
    (6.01, 7.0), (7.01, 8.0), (8.01, 10.0),
]
_BANDS_GOALS = [(1.01, 1.2), (1.21, 1.5), (1.5, 1.8), (1.8, 2.1), (2.1, 2.4)]

ODDS_BANDS: Dict[str, List[Tuple[float, float]]] = {
    "Home": _BANDS_1X2,
    "Away": _BANDS_1X2,
    "Draw": [(2.0, 3.0), (3.0, 3.4), (3.4, 3.8), (3.8, 4.5), (4.5, 6.0)],
    "Over 2.5": _BANDS_GOALS,
    "Under 2.5": _BANDS_GOALS,
}

# Metrik → (Attribut1, Operation, Attribut2, Label, Glicko?, Art, Schrittweite)
# Attributnamen wie in strategy_service._comparison_attr_value → speicherbar als Strategie
METRICS: Dict[str, Tuple[str, str, str, str, bool, str, float]] = {
    # Differenzen (für Heim / Remis / Auswärts)
    "power_diff_venue": ("power_home_venue", "-", "power_away_venue", "Power Diff (Heim/Ausw.-Ort)", False, "diff", 0.2),
    "pred_xg_diff": ("hometeam_pred_xg", "-", "awayteam_pred_xg", "pred. xG Diff", False, "diff", 0.1),
    "xg_form2_diff": ("xg_form2_home", "-", "xg_form2_away", "xG Form2 Diff (H−A)", False, "diff", 0.1),
    "form2_xg_diff": ("form2_avg_xg_home", "-", "form2_avg_xg_away", "Ø xG Diff (Saison)", False, "diff", 0.1),
    "rating_diff": ("rating_home", "-", "rating_away", "Glicko Rating Diff (H−A)", True, "diff", 25.0),
    "xg_glicko_diff": ("xg_home_glicko", "-", "xg_away_glicko", "xG Glicko Diff (H−A)", True, "diff", 0.1),
    # Summen / Tempo (für Über / Unter)
    "tempo_sum": ("tempo_home", "+", "tempo_away", "Tempo Summe", False, "sum", 0.25),
    "xg_form2_sum": ("xg_form2_home", "+", "xg_form2_away", "xG Form2 Summe", False, "sum", 0.1),
    "pred_xg_sum": ("hometeam_pred_xg", "+", "awayteam_pred_xg", "pred. xG Summe", False, "sum", 0.1),
    "form2_xg_sum": ("form2_avg_xg_home", "+", "form2_avg_xg_away", "Ø xG Summe (Saison)", False, "sum", 0.1),
    "power_sum": ("power_home", "+", "power_away", "Power Summe", False, "sum", 0.2),
}

# Markt → (Metrik-Art, Richtung, Quantile für die Schwelle)
#   ">="     : Metrik ≥ Schwelle (obere Quantile)
#   "<="     : Metrik ≤ Schwelle (untere Quantile)
#   "abs<="  : |Metrik| ≤ Schwelle (Quantile von |Metrik|) — ausgeglichene Spiele
MARKET_RULES: Dict[str, Tuple[str, str, List[float]]] = {
    "Home": ("diff", ">=", [0.6, 0.7, 0.8, 0.9]),
    "Away": ("diff", "<=", [0.4, 0.3, 0.2, 0.1]),
    "Draw": ("diff", "abs<=", [0.2, 0.3, 0.4, 0.5]),
    "Over 2.5": ("sum", ">=", [0.6, 0.7, 0.8, 0.9]),
    "Under 2.5": ("sum", "<=", [0.4, 0.3, 0.2, 0.1]),
}

SEARCH_SPACE: Dict[str, Any] = {
    "market": MARKETS,
    "odds_bands": ODDS_BANDS,
    "metrics": list(METRICS),
    "market_rules": MARKET_RULES,
    "odds_type": ["opening", "closing"],
}


def metrics_for_market(market: str, include_glicko: bool) -> List[str]:
    kind = MARKET_RULES[market][0]
    return [k for k, v in METRICS.items() if v[5] == kind and (include_glicko or not v[4])]


def round_step(value: float, step: float) -> float:
    return round(round(value / step) * step, 4)


def sample_combination(user_constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Zufällige gültige Kombination (ohne Schwelle); vom Nutzer fixierte Teile bleiben."""
    c = dict(user_constraints or {})
    market = c.get("market") or random.choice(MARKETS)
    combo = {
        "market": market,
        "odds_band": c.get("odds_band") or random.choice(ODDS_BANDS[market]),
        "odds_type": c.get("odds_type") or random.choice(SEARCH_SPACE["odds_type"]),
    }
    metrics = metrics_for_market(market, include_glicko=False)
    combo["metric"] = c.get("metric") or random.choice(metrics)
    combo["direction"] = MARKET_RULES[market][1]
    return combo
