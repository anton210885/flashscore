"""Für ein festes Markt-/Quotenband die beste Vor-Spiel-Bedingung finden — nur auf dem Lernzeitraum."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .evaluator import market_arrays, stats
from .search_space import DIRECTIONS, QUANTILES, metric_names


def score(s: Dict[str, Any]) -> float:
    """Untere 95 %-Grenze des ROI: bestraft kleine Stichproben (Zufallstreffer)."""
    return s["roi_lo"] if s.get("roi_lo") is not None else float("-inf")


def candidates(
    df: pd.DataFrame,
    base: Dict[str, Any],
    train: np.ndarray,
    *,
    min_bets: int,
    include_glicko: bool,
    quantiles: Optional[List[float]] = None,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Alle Bedingungen (Metrik × Schwelle × Richtung) für base auswerten → [(combo, train_stats)].

    Schwellen sind Quantile der Metrik innerhalb des Quotenbands im Lernzeitraum.
    """
    odds, profit, xroi = market_arrays(df, base["market"], base["odds_type"])
    lo, hi = base["odds_band"]
    band = ~np.isnan(odds) & (odds >= lo) & (odds <= hi)
    bt = band & train
    out = []
    if bt.sum() >= min_bets:
        out.append(({**base, "metric": None}, stats(profit[bt], xroi[bt], odds[bt])))
    for metric in metric_names(include_glicko):
        v = df[f"m_{metric}"].to_numpy(float)
        ok = bt & ~np.isnan(v)
        if ok.sum() < min_bets:
            continue
        thresholds = np.unique(np.round(np.quantile(v[ok], quantiles or QUANTILES), 4))
        for thr in thresholds:
            for d in DIRECTIONS:
                m = ok & ((v >= thr) if d == ">=" else (v <= thr))
                if m.sum() < min_bets:
                    continue
                combo = {**base, "metric": metric, "threshold": float(thr), "direction": d}
                out.append((combo, stats(profit[m], xroi[m], odds[m])))
    return out


def select_best_xg(df, base, train, *, min_bets=100, include_glicko=False):
    """(beste Kombination, ihre Lern-Kennzahlen) oder (None, None)."""
    cands = candidates(df, base, train, min_bets=min_bets, include_glicko=include_glicko)
    if not cands:
        return None, None
    return max(cands, key=lambda c: score(c[1]))
