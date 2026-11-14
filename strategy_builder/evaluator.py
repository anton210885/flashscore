"""Daten laden und Kombinationen bewerten — vektorisiert, gleiche Regeln wie die Strategie-Seite.

Quoten, Abrechnung (1 Einheit), xROI und Power/Tempo entsprechen services/strategy_service.py,
damit eine gefundene Kombination als Strategie gespeichert dasselbe Ergebnis liefert.
"""
from __future__ import annotations

import math
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategy_builder.search_space import METRICS  # noqa: E402

DB_PATH = ROOT / "data" / "flashscore.db"

# Markt → (Closing-Spalte, Opening-Spalte) wie strategy_service.MARKET_DEFS
ODDS_COLS = {
    "Home": ("odd_home", "odd_open_home"),
    "Draw": ("odd_draw", "odd_open_draw"),
    "Away": ("odd_away", "odd_open_away"),
    "Over 2.5": ("odd_over_25", "odd_open_over_25"),
    "Under 2.5": ("odd_under_25", "odd_open_under_25"),
}
MARKET_FILTER_KEY = {"Home": "home", "Draw": "draw", "Away": "away", "Over 2.5": "over", "Under 2.5": "under"}

_QUERY = """
SELECT g.game_id, g.date, g.league_id, g.country_name, g.league_name,
       g.home_ft_result AS hg, g.away_ft_result AS ag,
       g.home_rating, g.away_rating, g.xg_glicko_home, g.xg_glicko_away,
       o.odd_home, o.odd_draw, o.odd_away, o.odd_over_25, o.odd_under_25,
       o.odd_open_home, o.odd_open_draw, o.odd_open_away, o.odd_open_over_25, o.odd_open_under_25,
       f2.home_xg AS f2_home_xg, f2.away_xg AS f2_away_xg,
       f2.home_avg_xg, f2.home_avg_xga, f2.away_avg_xg, f2.away_avg_xga,
       f2.hometeam_home_xg, f2.hometeam_home_xga, f2.awayteam_away_xg, f2.awayteam_away_xga,
       f2.hometeam_pred_xg, f2.awayteam_pred_xg
FROM game_details_view g
LEFT JOIN game_odds_pivoted o ON o.game_id = g.game_id
LEFT JOIN game_form2 f2 ON f2.game_id = g.game_id
WHERE g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
"""


def _div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a.where(b > 0) / b.where(b > 0)


def load_rows(db: Optional[str] = None, scope_only: bool = False) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{db or DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        df = pd.read_sql_query(_QUERY, conn)
    finally:
        conn.close()
    if scope_only:
        from services.league_scope import active_league_ids
        ids = active_league_ids()
        if ids:
            df = df[df.league_id.isin(list(ids))]
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    # Attribute wie strategy_service._comparison_attr_value / power_tempo_value
    attrs = pd.DataFrame(index=df.index)
    attrs["power_home"] = _div(df.home_avg_xg, df.home_avg_xga)
    attrs["power_away"] = _div(df.away_avg_xg, df.away_avg_xga)
    attrs["tempo_home"] = df.home_avg_xg + df.home_avg_xga
    attrs["tempo_away"] = df.away_avg_xg + df.away_avg_xga
    attrs["power_home_venue"] = _div(df.hometeam_home_xg, df.hometeam_home_xga)
    attrs["power_away_venue"] = _div(df.awayteam_away_xg, df.awayteam_away_xga)
    attrs["xg_form2_home"], attrs["xg_form2_away"] = df.f2_home_xg, df.f2_away_xg
    attrs["form2_avg_xg_home"], attrs["form2_avg_xg_away"] = df.home_avg_xg, df.away_avg_xg
    attrs["form2_avg_xga_home"], attrs["form2_avg_xga_away"] = df.home_avg_xga, df.away_avg_xga
    attrs["hometeam_pred_xg"], attrs["awayteam_pred_xg"] = df.hometeam_pred_xg, df.awayteam_pred_xg
    attrs["rating_home"], attrs["rating_away"] = df.home_rating, df.away_rating
    attrs["xg_home_glicko"], attrs["xg_away_glicko"] = df.xg_glicko_home, df.xg_glicko_away
    for name, (a1, op, a2, *_rest) in METRICS.items():
        x, y = attrs[a1].astype(float), attrs[a2].astype(float)
        df[f"m_{name}"] = x - y if op == "-" else x + y if op == "+" else _div(x, y)
    return df


def market_arrays(df: pd.DataFrame, market: str, odds_type: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(Quote der Wette, Profit je 1 Einheit, xROI %) — NaN, wo keine gültige Quote."""
    close_col, open_col = ODDS_COLS[market]
    odds = pd.to_numeric(df[open_col if odds_type == "opening" else close_col], errors="coerce").to_numpy(float)
    odds = np.where(odds > 1.0, odds, np.nan)
    hg, ag = df.hg.to_numpy(float), df.ag.to_numpy(float)
    won = {"Home": hg > ag, "Away": ag > hg, "Draw": hg == ag,
           "Over 2.5": hg + ag > 2.5, "Under 2.5": hg + ag <= 2.5}[market]
    profit = np.where(np.isnan(odds), np.nan, np.where(won, odds - 1.0, -1.0))
    o = pd.to_numeric(df[open_col], errors="coerce").to_numpy(float)
    c = pd.to_numeric(df[close_col], errors="coerce").to_numpy(float)
    xroi = np.where((o > 1) & (c > 1), (o - c) / c * 100.0, np.nan)
    return odds, profit, xroi


def stats(profit: np.ndarray, xroi: np.ndarray, odds: np.ndarray) -> Dict[str, Any]:
    n = int(len(profit))
    if not n:
        return {"n": 0}
    m = float(profit.mean())
    se = float(profit.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    xr = xroi[~np.isnan(xroi)]
    return {
        "n": n,
        "roi": round(m * 100, 2),
        "roi_lo": round((m - 1.96 * se) * 100, 2) if n > 1 else None,
        "roi_hi": round((m + 1.96 * se) * 100, 2) if n > 1 else None,
        "profit": round(float(profit.sum()), 2),
        "hit": round(float((profit > 0).mean() * 100), 1),
        "avg_odds": round(float(odds.mean()), 2),
        "xroi": round(float(xr.mean()), 2) if len(xr) else None,
        "xroi_n": int(len(xr)),
    }


def combo_mask(df: pd.DataFrame, combo: Dict[str, Any], odds: np.ndarray) -> np.ndarray:
    lo, hi = combo["odds_band"]
    mask = ~np.isnan(odds) & (odds >= lo) & (odds <= hi)
    if combo.get("metric"):
        mask &= condition(df[f"m_{combo['metric']}"].to_numpy(float), combo["direction"], float(combo["threshold"]))
    return mask


def condition(v: np.ndarray, direction: str, thr: float) -> np.ndarray:
    """Bedingung auswerten; NaN zählt nie als erfüllt."""
    with np.errstate(invalid="ignore"):
        if direction == ">=":
            return v >= thr
        if direction == "<=":
            return v <= thr
        if direction == "abs<=":
            return np.abs(v) <= thr
    raise ValueError(f"Unbekannte Richtung: {direction}")


def evaluate_combination(combo: Dict[str, Any], df: pd.DataFrame, period: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """Kennzahlen einer Kombination (optional nur auf einem Zeitraum-Maske)."""
    odds, profit, xroi = market_arrays(df, combo["market"], combo.get("odds_type", "opening"))
    mask = combo_mask(df, combo, odds)
    if period is not None:
        mask &= period
    return {**stats(profit[mask], xroi[mask], odds[mask]), "combo": combo}


def combo_to_filters(combo: Dict[str, Any]) -> Dict[str, Any]:
    """Kombination → Filter der Strategie-Seite (Preset)."""
    key = MARKET_FILTER_KEY[combo["market"]]
    lo, hi = combo["odds_band"]
    f: Dict[str, Any] = {
        f"market_{key}": True,
        "odds_type": combo.get("odds_type", "opening"),
        f"odds_{key}_min": str(lo),
        f"odds_{key}_max": str(hi),
    }
    if combo.get("metric"):
        a1, op, a2 = METRICS[combo["metric"]][:3]
        thr = round(float(combo["threshold"]), 4)
        d = combo["direction"]
        f.update({
            "use_xg_comparison": True,
            "xg_attr1": a1, "xg_operation": op, "xg_attr2": a2,
            "xg_comparison_operator": ">=" if d == "abs<=" else d,
            "xg_comparison_value": str(-thr if d == "abs<=" else thr),
            # |Diff| ≤ x  =  Diff ≥ −x  UND  Diff ≤ x
            "xg_comparisons": ([{"attr1": a1, "operation": op, "attr2": a2,
                                 "comparison_operator": "<=", "comparison_value": str(thr)}]
                               if d == "abs<=" else []),
        })
    return f


def describe(combo: Dict[str, Any]) -> str:
    lo, hi = combo["odds_band"]
    s = f"{combo['market']} {lo:g}–{hi:g} ({combo.get('odds_type', 'opening')})"
    if combo.get("metric"):
        label, thr = METRICS[combo["metric"]][3], round(float(combo["threshold"]), 3)
        s += (f" · |{label}| ≤ {thr:g}" if combo["direction"] == "abs<="
              else f" · {label} {'≥' if combo['direction'] == '>=' else '≤'} {thr:g}")
    return s
