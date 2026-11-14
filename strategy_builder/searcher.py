"""Suche über drei Zeitabschnitte: Lernen → Auswahl → Prüfung.

  • Lernzeitraum: alle Kombinationen bewerten (Schwellen kommen nur von hier).
  • Auswahlzeitraum: nur Kombinationen, die auch hier im Plus sind, gelten als „stabil“.
    Rangfolge nach der unteren 95 %-Grenze des ROI über Lernen+Auswahl zusammen.
  • Prüfzeitraum: wird bei der Auswahl NIE angeschaut — erst danach zeigt er, was hält.

Würde man nach dem Prüfzeitraum auswählen, wäre er nur ein weiterer Lernzeitraum und die
Ergebnisse wieder zu optimistisch.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .evaluator import ODDS_COLS, combo_to_filters, describe, evaluate_combination, load_rows
from .search_space import METRICS, ODDS_BANDS
from .xg_selector import candidates, score, thresholds


def _avg(vals: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in vals if v is not None]
    return round(float(np.mean(vals)), 2) if vals else None


def run_search(
    df: Optional[pd.DataFrame] = None,
    *,
    markets: Optional[List[str]] = None,
    odds_type: str = "opening",
    split: Optional[str] = None,
    min_bets: int = 50,
    min_valid_bets: int = 20,
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

    col = 1 if odds_type == "opening" else 0
    has_odds = np.zeros(len(df), bool)
    for m in markets:
        has_odds |= pd.to_numeric(df[ODDS_COLS[m][col]], errors="coerce").to_numpy(float) > 1
    dates = df.date[has_odds].reset_index(drop=True)
    if len(dates) < 1000:
        raise ValueError(f"Zu wenig Spiele mit {odds_type}-Quoten ({len(dates)}).")
    # Stichtag = Beginn der Prüfung; Auswahl = letztes Viertel davor. Automatisch: 60 / 20 / 20
    test_ts = pd.Timestamp(split, tz="UTC") if split else dates.iloc[int(len(dates) * 0.8)].normalize()
    before = dates[dates < test_ts]
    if len(before) < 800:
        raise ValueError(f"Stichtag zu früh: nur {len(before)} Spiele davor.")
    valid_ts = before.iloc[int(len(before) * 0.75)].normalize()
    d = df.date
    train = (d < valid_ts).to_numpy() & has_odds
    valid = ((d >= valid_ts) & (d < test_ts)).to_numpy() & has_odds
    test = (d >= test_ts).to_numpy() & has_odds
    if test.sum() < 100:
        raise ValueError(f"Prüfzeitraum zu klein ({int(test.sum())} Spiele) — Stichtag früher wählen.")

    step("Schwellen festlegen")
    thr = thresholds(df, train, include_glicko)
    found: List[Dict[str, Any]] = []
    for market in markets:
        step(f"Suche {market}")
        for band in ODDS_BANDS[market]:
            base = {"market": market, "odds_band": band, "odds_type": odds_type}
            found.extend(candidates(df, base, train, valid, thr, min_bets=min_bets, include_glicko=include_glicko))
    if not found:
        raise ValueError(f"Keine Kombination mit mindestens {min_bets} Wetten im Lernzeitraum.")

    def stable(c: Dict[str, Any]) -> bool:
        tr, va = c["train"], c["valid"]
        return tr["roi"] > 0 and va.get("n", 0) >= min_valid_bets and (va.get("roi") or -1) > 0

    n_stable = sum(1 for c in found if stable(c))
    # Stabile zuerst (nach unterer Grenze Lernen+Auswahl), danach der Rest zum Vergleich
    found.sort(key=lambda c: (stable(c), score(c["pooled"])), reverse=True)

    step("Prüfzeitraum auswerten")
    top, seen = [], set()
    for c in found:
        label = describe(c["combo"])
        if label in seen:
            continue
        seen.add(label)
        te = evaluate_combination(c["combo"], df, test)
        top.append({
            "label": label,
            "combo": c["combo"],
            "filters": combo_to_filters(c["combo"]),
            "glicko": bool(c["combo"].get("metric") and METRICS[c["combo"]["metric"]][4]),
            "stable": stable(c),
            "train": c["train"],
            "valid": c["valid"],
            "test": {k: v for k, v in te.items() if k != "combo"},
        })
        if len(top) >= top_k:
            break

    tested = [t for t in top if t["test"].get("n")]
    summary = {
        "n_tested": len(found),
        "n_stable": n_stable,
        "train_positive_pct": round(100 * sum(1 for c in found if c["train"]["roi"] > 0) / len(found), 1),
        "top_train_roi_avg": _avg([t["train"]["roi"] for t in top]),
        "top_valid_roi_avg": _avg([t["valid"].get("roi") for t in top]),
        "top_test_roi_avg": _avg([t["test"].get("roi") for t in tested]),
        "top_test_positive": sum(1 for t in tested if t["test"]["roi"] > 0),
        "top_test_n": len(tested),
        "top_test_bets": int(sum(t["test"]["n"] for t in tested)),
        # nach Wetten gewichtet: Kombinationen mit 10 Wetten verzerren den Schnitt sonst stark
        "top_test_roi_weighted": (round(100 * sum(t["test"]["profit"] for t in tested)
                                        / sum(t["test"]["n"] for t in tested), 2) if tested else None),
        "top_test_xroi_avg": _avg([t["test"].get("xroi") for t in tested]),
    }
    return {
        "split": str(test_ts.date()),
        "valid_from": str(valid_ts.date()),
        "train_games": int(train.sum()), "valid_games": int(valid.sum()), "test_games": int(test.sum()),
        "train_from": str(d[train].min().date()), "test_to": str(d[test].max().date()),
        "summary": summary,
        "top": top,
    }


def pretty_print(result: Dict[str, Any]) -> None:
    s = result["summary"]
    print(f"Lernen bis {result['valid_from']} ({result['train_games']}) · Auswahl bis {result['split']} "
          f"({result['valid_games']}) · Prüfung danach ({result['test_games']})")
    print(f"{s['n_tested']} Kombinationen, davon stabil (Lernen und Auswahl im Plus): {s['n_stable']}")
    print(f"{'#':<3} {'Lern':>7} {'n':>5} {'Ausw.':>7} {'n':>4} {'Prüf':>7} {'n':>4} {'xROI':>6}  Kombination")
    for i, r in enumerate(result["top"], 1):
        tr, va, te = r["train"], r["valid"], r["test"]
        print(f"{i:<3} {tr['roi']:>6.1f}% {tr['n']:>5} {va.get('roi', 0):>6.1f}% {va.get('n', 0):>4} "
              f"{te.get('roi', 0):>6.1f}% {te.get('n', 0):>4} {(te.get('xroi') or 0):>5.2f}%  "
              f"{'' if r['stable'] else '(nicht stabil) '}{r['label']}")
    print(f"Top {s['top_test_n']} im Prüfzeitraum: Ø ROI {s['top_test_roi_avg']} % · im Plus: {s['top_test_positive']} "
          f"· {s['top_test_bets']} Wetten · gewichtet {s['top_test_roi_weighted']} %")
