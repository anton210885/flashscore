"""Bedingungen für ein Markt-/Quotenband erzeugen und auf Lern- und Auswahlzeitraum bewerten."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .evaluator import condition, market_arrays, stats
from .search_space import MARKET_RULES, METRICS, metrics_for_market, round_step


def thresholds(df: pd.DataFrame, train: np.ndarray, include_glicko: bool) -> Dict[Tuple[str, str], List[float]]:
    """Grobe Schwellen je (Markt, Metrik): Quantile des ganzen Lernzeitraums, gerundet.

    Bewusst nicht pro Quotenband — so gibt es wenige, runde, gut lesbare Werte (z. B. Power Diff ≥ 1.0).
    """
    out: Dict[Tuple[str, str], List[float]] = {}
    for market, (_kind, direction, qs) in MARKET_RULES.items():
        for metric in metrics_for_market(market, include_glicko):
            v = df[f"m_{metric}"].to_numpy(float)[train]
            v = v[~np.isnan(v)]
            if len(v) < 100:
                continue
            if direction == "abs<=":
                v = np.abs(v)
            step = METRICS[metric][6]
            vals = sorted({round_step(float(np.quantile(v, q)), step) for q in qs})
            if direction == "abs<=":
                vals = [x for x in vals if x > 0]
            out[(market, metric)] = vals
    return out


def score(s: Dict[str, Any]) -> float:
    """Untere 95 %-Grenze des ROI: bestraft kleine Stichproben (Zufallstreffer)."""
    return s["roi_lo"] if s.get("roi_lo") is not None else float("-inf")


def candidates(
    df: pd.DataFrame,
    base: Dict[str, Any],
    train: np.ndarray,
    valid: np.ndarray,
    thr: Dict[Tuple[str, str], List[float]],
    *,
    min_bets: int,
    include_glicko: bool,
) -> List[Dict[str, Any]]:
    """Alle Bedingungen für base → [{combo, train, valid, pooled}] (nur mit genug Lern-Wetten)."""
    market = base["market"]
    odds, profit, xroi = market_arrays(df, market, base["odds_type"])
    lo, hi = base["odds_band"]
    band = ~np.isnan(odds) & (odds >= lo) & (odds <= hi)
    direction = MARKET_RULES[market][1]

    def rate(combo: Dict[str, Any], mask: np.ndarray) -> Optional[Dict[str, Any]]:
        mt, mv = mask & train, mask & valid
        if mt.sum() < min_bets:
            return None
        both = mt | mv
        return {
            "combo": combo,
            "train": stats(profit[mt], xroi[mt], odds[mt]),
            "valid": stats(profit[mv], xroi[mv], odds[mv]),
            "pooled": stats(profit[both], xroi[both], odds[both]),
        }

    out = []
    r = rate({**base, "metric": None}, band)
    if r:
        out.append(r)
    for metric in metrics_for_market(market, include_glicko):
        v = df[f"m_{metric}"].to_numpy(float)
        for t in thr.get((market, metric), []):
            r = rate({**base, "metric": metric, "direction": direction, "threshold": float(t)},
                     band & condition(v, direction, float(t)))
            if r:
                out.append(r)
    return out


def select_best_xg(df, base, train, valid, *, min_bets=50, include_glicko=False):
    """Beste Bedingung für base (nach Lern+Auswahl zusammen) oder None."""
    thr = thresholds(df, train, include_glicko)
    cands = candidates(df, base, train, valid, thr, min_bets=min_bets, include_glicko=include_glicko)
    return max(cands, key=lambda c: score(c["pooled"])) if cands else None
