"""Suche: alle Kombinationen auf dem Lernzeitraum bewerten, die besten auf dem Prüfzeitraum testen.

Warum zwei Zeiträume: Wer tausende Kombinationen auf denselben Daten ausprobiert, findet immer
welche mit tollem ROI — reiner Zufall. Erst der spätere, unberührte Prüfzeitraum zeigt, ob davon
etwas hält. Rangfolge nach der unteren 95 %-Grenze des Lern-ROI (nicht nach ROI oder xROI allein).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .evaluator import combo_to_filters, describe, evaluate_combination, load_rows
from .search_space import METRICS, ODDS_BANDS
from .xg_selector import candidates, score


def run_search(
    df: Optional[pd.DataFrame] = None,
    *,
    markets: Optional[List[str]] = None,
    odds_type: str = "opening",
    split: Optional[str] = None,
    min_bets: int = 100,
    include_glicko: bool = False,
    top_k: int = 20,
    scope_only: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    step = progress or (lambda s: None)
    if df is None:
        step("Daten laden")
        df = load_rows(scope_only=scope_only)
    markets = [m for m in (markets or list(ODDS_BANDS)) if m in ODDS_BANDS]
    if not markets:
        raise ValueError("Mindestens einen Markt wählen.")

    # Nur Spiele mit Quote des gewählten Typs in mind. einem Markt zählen für den Stichtag
    from .evaluator import ODDS_COLS
    col = 1 if odds_type == "opening" else 0
    has_odds = np.zeros(len(df), bool)
    for m in markets:
        has_odds |= pd.to_numeric(df[ODDS_COLS[m][col]], errors="coerce").to_numpy(float) > 1
    dates = df.date[has_odds]
    if len(dates) < 500:
        raise ValueError(f"Zu wenig Spiele mit {odds_type}-Quoten ({len(dates)}).")
    split_ts = pd.Timestamp(split, tz="UTC") if split else dates.iloc[int(len(dates) * 0.7)].normalize()
    train = (df.date < split_ts).to_numpy() & has_odds
    test = (df.date >= split_ts).to_numpy() & has_odds
    if train.sum() < 300 or test.sum() < 100:
        raise ValueError(f"Stichtag ungünstig: Lernzeitraum {int(train.sum())}, Prüfzeitraum {int(test.sum())} Spiele.")

    found: List[tuple] = []
    for market in markets:
        step(f"Suche {market}")
        for band in ODDS_BANDS[market]:
            base = {"market": market, "odds_band": band, "odds_type": odds_type}
            found.extend(candidates(df, base, train, min_bets=min_bets, include_glicko=include_glicko))
    n_tested = len(found)
    if not found:
        raise ValueError(f"Keine Kombination mit mindestens {min_bets} Wetten im Lernzeitraum.")

    step("Beste Kombinationen prüfen")
    found.sort(key=lambda c: score(c[1]), reverse=True)
    top, seen = [], set()
    for combo, tr in found:
        key = describe(combo)
        if key in seen:
            continue
        seen.add(key)
        te = evaluate_combination(combo, df, test)
        top.append({
            "label": key,
            "combo": combo,
            "filters": combo_to_filters(combo),
            "glicko": bool(combo.get("metric") and METRICS[combo["metric"]][4]),
            "train": tr,
            "test": {k: v for k, v in te.items() if k != "combo"},
        })
        if len(top) >= top_k:
            break

    # Vergleich: wie schneiden ALLE Kombinationen bzw. nur die Quotenbänder im Prüfzeitraum ab?
    train_pos = sum(1 for _, s in found if (s.get("roi") or 0) > 0)
    test_rois = [t["test"].get("roi") for t in top if t["test"].get("n")]
    test_xrois = [t["test"].get("xroi") for t in top if t["test"].get("xroi") is not None]
    summary = {
        "n_tested": n_tested,
        "train_positive_pct": round(100 * train_pos / n_tested, 1),
        "top_train_roi_avg": round(float(np.mean([t["train"]["roi"] for t in top])), 2),
        "top_test_roi_avg": round(float(np.mean(test_rois)), 2) if test_rois else None,
        "top_test_positive": sum(1 for r in test_rois if r > 0),
        "top_test_n": len(test_rois),
        "top_test_xroi_avg": round(float(np.mean(test_xrois)), 2) if test_xrois else None,
    }
    return {
        "split": str(split_ts.date()),
        "train_games": int(train.sum()), "test_games": int(test.sum()),
        "train_from": str(df.date[train].min().date()), "test_to": str(df.date[test].max().date()),
        "summary": summary,
        "top": top,
    }


def pretty_print(result: Dict[str, Any]) -> None:
    s = result["summary"]
    print(f"Lernen bis {result['split']} ({result['train_games']} Spiele) · Prüfen danach ({result['test_games']})")
    print(f"{s['n_tested']} Kombinationen getestet, davon {s['train_positive_pct']} % im Lernzeitraum im Plus")
    print(f"{'#':<3} {'Lern-ROI':>9} {'n':>5} {'Prüf-ROI':>9} {'n':>5} {'Prüf-xROI':>9}  Kombination")
    for i, r in enumerate(result["top"], 1):
        tr, te = r["train"], r["test"]
        print(f"{i:<3} {tr['roi']:>8.1f}% {tr['n']:>5} {te.get('roi', 0):>8.1f}% {te.get('n', 0):>5} "
              f"{(te.get('xroi') or 0):>8.2f}%  {r['label']}")
    print(f"Ø Prüf-ROI der Top {s['top_test_n']}: {s['top_test_roi_avg']} % · im Plus: {s['top_test_positive']}")
