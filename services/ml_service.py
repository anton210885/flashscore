"""Machine Learning: Modelle ehrlich gegen den Markt testen (Tab „Machine Learning“).

Zwei Arten von Läufen:
  • Vorhersage — ein Modell schätzt 1X2 bzw. Über/Unter 2,5 und muss die Pinnacle-Opening schlagen.
  • Strategie-Filter — ein Modell lernt, welche Wetten einer gespeicherten Strategie man besser weglässt.

Immer streng zeitlich: Training vor dem Stichtag, Test danach. Gemessen wird am Log-Loss (Vorhersage)
und am CLV gegen das faire Closing (Wettwert) — ROI allein ist bei wenigen hundert Wetten zu zufällig.
Ergebnisse liegen als JSON in logs/ml_runs/ (nichts in der Datenbank).
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "flashscore.db"
RUNS_DIR = ROOT / "logs" / "ml_runs"
MAX_RUNS = 60

MODELS: Dict[str, Dict[str, Any]] = {
    "market": {"label": "Markt (Opening-Quote)", "modes": ["predict"], "trains": False,
               "help": "Kein Lernen: die faire Opening-Wahrscheinlichkeit. Das ist die Messlatte."},
    "glicko": {"label": "Glicko (sstats)", "modes": ["predict"], "markets": ["1x2"], "trains": False,
               "help": "Die Sieg-Wahrscheinlichkeiten von sstats direkt, ohne Lernen."},
    "poisson": {"label": "Poisson-Tore", "modes": ["predict"], "trains": True,
                "help": "Klassisches Fussball-Modell: schätzt erwartete Tore je Team, daraus 1X2 und Über/Unter."},
    "logreg": {"label": "Logistische Regression", "modes": ["predict", "strategy"], "trains": True,
               "help": "Einfaches lineares Modell — robust, wenig Gefahr von Overfitting."},
    "boosting": {"label": "Gradient Boosting", "modes": ["predict", "strategy"], "trains": True,
                 "help": "Viele kleine Entscheidungsbäume nacheinander — findet auch verschachtelte Muster."},
    "forest": {"label": "Random Forest", "modes": ["predict", "strategy"], "trains": True,
               "help": "Viele unabhängige Entscheidungsbäume, gemittelt — stabil, aber grob."},
}

MARKETS = {
    "1x2": {"label": "1X2 (Heim / Remis / Auswärts)", "outcomes": ["Heim", "Remis", "Auswärts"]},
    "ou25": {"label": "Über / Unter 2,5 Tore", "outcomes": ["Über 2,5", "Unter 2,5"]},
}

FEATURE_GROUPS = {
    "opening": {"label": "Opening-Quote", "help": "Faire Wahrscheinlichkeiten und Marge der Pinnacle-Opening."},
    "xg": {"label": "xG-Durchschnitte (Form2)", "help": "Saison-Schnitt xG / xGA / Tore, Heim- und Auswärts-Schnitt."},
    "glicko": {"label": "Glicko", "help": "Ratings, Unsicherheit, Sieg-Wahrscheinlichkeiten und Glicko-xG von sstats."},
}

_lock = threading.Lock()
_state: Dict[str, Any] = {"running": False, "run_id": None, "started_at": None, "step": None}


# ── Daten ──────────────────────────────────────────────────────────────────

_QUERY = """
SELECT g.id, g.date, g.league_id, g.home_ft_result AS hg, g.away_ft_result AS ag,
  o.oh, o.od, o.oa, o.ch, o.cd, o.ca, t.oo, t.ou, t.co, t.cu,
  gl.home_rating, gl.away_rating, gl.home_rd, gl.away_rd,
  gl.home_xg AS gl_xg_h, gl.away_xg AS gl_xg_a,
  gl.home_win_probability AS gl_ph, gl.draw_probability AS gl_pd, gl.away_win_probability AS gl_pa,
  CASE WHEN gl.created_at IS NULL THEN NULL
       WHEN datetime(gl.created_at) < datetime(g.date) THEN 1 ELSE 0 END AS gl_honest,
  f.home_n, f.away_n, f.home_avg_xg, f.home_avg_xga, f.home_avg_gf, f.home_avg_ga,
  f.away_avg_xg, f.away_avg_xga, f.away_avg_gf, f.away_avg_ga,
  f.hometeam_home_xg, f.hometeam_home_xga, f.awayteam_away_xg, f.awayteam_away_xga,
  f.hometeam_pred_xg, f.awayteam_pred_xg
FROM games g
LEFT JOIN (SELECT game_id,
   MAX(CASE WHEN name='Home' THEN opening_value END) oh, MAX(CASE WHEN name='Draw' THEN opening_value END) od,
   MAX(CASE WHEN name='Away' THEN opening_value END) oa, MAX(CASE WHEN name='Home' THEN value END) ch,
   MAX(CASE WHEN name='Draw' THEN value END) cd, MAX(CASE WHEN name='Away' THEN value END) ca
   FROM game_odds WHERE market_id = 1 GROUP BY game_id) o ON o.game_id = g.id
LEFT JOIN (SELECT game_id,
   MAX(CASE WHEN name='Over 2.5' THEN opening_value END) oo, MAX(CASE WHEN name='Under 2.5' THEN opening_value END) ou,
   MAX(CASE WHEN name='Over 2.5' THEN value END) co, MAX(CASE WHEN name='Under 2.5' THEN value END) cu
   FROM game_odds WHERE market_id = 5 GROUP BY game_id) t ON t.game_id = g.id
LEFT JOIN game_glicko gl ON gl.game_id = g.id
LEFT JOIN game_form2 f ON f.game_id = g.id
WHERE g.status IN (7, 8, 9, 10) AND g.home_ft_result IS NOT NULL AND g.away_ft_result IS NOT NULL
"""

_ODDS = {"1x2": (["oh", "od", "oa"], ["ch", "cd", "ca"]), "ou25": (["oo", "ou"], ["co", "cu"])}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _fair(df: pd.DataFrame, cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    inv = 1.0 / df[cols].to_numpy(dtype=float)
    s = inv.sum(axis=1, keepdims=True)
    return inv / s, s[:, 0] - 1.0


def _load_predict(market: str, scope_only: bool) -> pd.DataFrame:
    conn = _connect()
    try:
        df = pd.read_sql_query(_QUERY, conn)
    finally:
        conn.close()
    oc, cc = _ODDS[market]
    df = df.dropna(subset=oc + cc)
    df = df[(df[oc + cc] > 1.01).all(axis=1) & (df[oc + cc] < 50).all(axis=1)].copy()
    if scope_only:
        from services.league_scope import active_league_ids
        ids = active_league_ids()
        if ids:
            df = df[df.league_id.isin(list(ids))]
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    for c in ("gl_ph", "gl_pd", "gl_pa"):
        df[c] = np.where(df[c] > 1, df[c] / 100.0, df[c])
    if market == "1x2":
        df["y"] = np.select([df.hg > df.ag, df.hg == df.ag], [0, 1], 2)
    else:
        df["y"] = np.where(df.hg + df.ag > 2.5, 0, 1)
    return df.sort_values("date").reset_index(drop=True)


def _features(df: pd.DataFrame, groups: List[str], market: str) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    oc, _ = _ODDS[market]
    po, margin = _fair(df, oc)
    names = MARKETS[market]["outcomes"]
    if "opening" in groups:
        for i, n in enumerate(names):
            X[f"Opening p({n})"] = po[:, i]
        X["Opening-Marge"] = margin
    if "xg" in groups:
        X["Spiele min."] = np.minimum(df.home_n, df.away_n)
        X["Heim xG"], X["Heim xGA"] = df.home_avg_xg, df.home_avg_xga
        X["Ausw. xG"], X["Ausw. xGA"] = df.away_avg_xg, df.away_avg_xga
        X["xG-Differenz"] = (df.home_avg_xg - df.home_avg_xga) - (df.away_avg_xg - df.away_avg_xga)
        X["xG-Diff. Heim/Ausw.-Ort"] = (df.hometeam_home_xg - df.hometeam_home_xga) - (df.awayteam_away_xg - df.awayteam_away_xga)
        X["Pred-xG Summe"] = df.hometeam_pred_xg + df.awayteam_pred_xg
        X["Pred-xG Differenz"] = df.hometeam_pred_xg - df.awayteam_pred_xg
        X["Heim Tore−xG"] = df.home_avg_gf - df.home_avg_xg
        X["Ausw. Tore−xG"] = df.away_avg_gf - df.away_avg_xg
    if "glicko" in groups:
        X["Glicko-Differenz"] = df.home_rating - df.away_rating
        X["Glicko RD Summe"] = df.home_rd + df.away_rd
        X["Glicko-xG Summe"] = df.gl_xg_h + df.gl_xg_a
        X["Glicko-xG Differenz"] = df.gl_xg_h - df.gl_xg_a
        X["Glicko p(Heim)"], X["Glicko p(Remis)"], X["Glicko p(Ausw.)"] = df.gl_ph, df.gl_pd, df.gl_pa
        if market == "1x2":
            X["Glicko−Opening Heim"] = df.gl_ph - po[:, 0]
            X["Glicko−Opening Ausw."] = df.gl_pa - po[:, 2]
    return X


# ── Modelle ────────────────────────────────────────────────────────────────

def _classifier(model: str):
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if model == "logreg":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=0.3, max_iter=3000))
    if model == "boosting":
        return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.04, max_leaf_nodes=15,
                                              min_samples_leaf=80, l2_regularization=1.0, random_state=1)
    if model == "forest":
        return make_pipeline(SimpleImputer(strategy="median"),
                             RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=50,
                                                    n_jobs=1, random_state=1))
    raise ValueError(f"Unbekanntes Modell: {model}")


class _PoissonGoals:
    """Zwei Poisson-Regressionen (Heim-/Auswärtstore) → Wahrscheinlichkeiten über ein Tore-Raster."""

    def __init__(self, market: str):
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import PoissonRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self.market = market
        mk = lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                   PoissonRegressor(alpha=0.05, max_iter=1000))
        self.h, self.a = mk(), mk()

    def fit(self, X, hg, ag):
        self.h.fit(X, np.clip(hg, 0, 10))
        self.a.fit(X, np.clip(ag, 0, 10))
        return self

    def predict_proba(self, X) -> np.ndarray:
        from scipy.stats import poisson

        lh, la = self.h.predict(X), self.a.predict(X)
        k = np.arange(11)
        ph = poisson.pmf(k[None, :], lh[:, None])
        pa = poisson.pmf(k[None, :], la[:, None])
        grid = ph[:, :, None] * pa[:, None, :]  # [n, heim, ausw]
        hh, aa = np.meshgrid(k, k, indexing="ij")
        if self.market == "1x2":
            P = np.stack([(grid * (hh > aa)).sum((1, 2)), (grid * (hh == aa)).sum((1, 2)),
                          (grid * (hh < aa)).sum((1, 2))], axis=1)
        else:
            over = (grid * ((hh + aa) > 2.5)).sum((1, 2))
            P = np.stack([over, 1 - over], axis=1)
        return P / P.sum(axis=1, keepdims=True)


def _log_loss(y: np.ndarray, P: np.ndarray) -> float:
    p = np.clip(P[np.arange(len(y)), y], 1e-12, 1)
    return float(-np.mean(np.log(p)))


def _brier(y: np.ndarray, P: np.ndarray) -> float:
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1
    return float(np.mean(((P - Y) ** 2).sum(axis=1)))


def _roi_block(profit: np.ndarray) -> Dict[str, Any]:
    n = len(profit)
    if not n:
        return {"n": 0}
    m = float(profit.mean())
    se = float(profit.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    return {"n": int(n), "roi_pct": round(m * 100, 2), "profit": round(float(profit.sum()), 2),
            "roi_ci95": [round((m - 1.96 * se) * 100, 1), round((m + 1.96 * se) * 100, 1)] if n > 1 else None}


def _verdict(clv_mean: Optional[float], ci: Optional[List[float]], n: int) -> str:
    if not n or clv_mean is None:
        return "keine Wetten"
    if n < 100:
        return "zu wenig Wetten"
    if clv_mean > 0.5 and ci and ci[0] > -20:
        return "vielversprechend — weiter beobachten"
    if clv_mean > 0:
        return "knapp positiv — noch kein Beleg"
    return "kein Vorteil"


def _permutation(predict: Callable[[pd.DataFrame], np.ndarray], X: pd.DataFrame, y: np.ndarray,
                 base: float, repeats: int = 2) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(1)
    if len(X) > 4000:
        idx = rng.choice(len(X), 4000, replace=False)
        X, y = X.iloc[idx].reset_index(drop=True), y[idx]
        base = _log_loss(y, predict(X))
    out = []
    for col in X.columns:
        deltas = []
        for _ in range(repeats):
            Xp = X.copy()
            Xp[col] = rng.permutation(Xp[col].to_numpy())
            deltas.append(_log_loss(y, predict(Xp)) - base)
        out.append({"feature": col, "importance": round(float(np.mean(deltas)), 5)})
    return sorted(out, key=lambda r: -r["importance"])


def _calibration(y: np.ndarray, P: np.ndarray, bins: int = 10) -> List[Dict[str, Any]]:
    p, hit = P[:, 0], (y == 0).astype(float)
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    out = []
    for i in range(bins):
        m = (p >= edges[i]) & (p <= edges[i + 1] if i == bins - 1 else p < edges[i + 1])
        if m.sum() >= 20:
            out.append({"predicted": round(float(p[m].mean()), 3), "actual": round(float(hit[m].mean()), 3),
                        "n": int(m.sum())})
    return out


# ── Lauf: Vorhersage ──────────────────────────────────────────────────────

def _run_predict(cfg: Dict[str, Any], step: Callable[[str], None]) -> Dict[str, Any]:
    market, model = cfg["market"], cfg["model"]
    groups = [g for g in cfg.get("features") or [] if g in FEATURE_GROUPS]
    if MODELS[model]["trains"] and not groups:
        raise ValueError("Mindestens eine Merkmal-Gruppe wählen.")
    if model == "glicko" and market != "1x2":
        raise ValueError("Glicko (sstats) gibt es nur für 1X2.")
    step("Daten laden")
    df = _load_predict(market, cfg.get("scope_only", True))
    notes = []
    if model == "glicko" or "glicko" in groups:
        df = df.dropna(subset=["gl_ph", "gl_pa"])
        if cfg.get("honest_glicko"):
            df = df[df.gl_honest == 1]
            notes.append("Nur Spiele, deren Glicko vor Anpfiff geholt wurde.")
        else:
            notes.append("Achtung: enthält Glicko, das erst nach Anpfiff geholt wurde — kennt teils den Closing-Markt.")
    if "xg" in groups or model == "poisson":
        df = df[(df.home_n >= 3) & (df.away_n >= 3) & df.home_avg_xg.notna() & df.away_avg_xg.notna()]
        notes.append("Nur Spiele, bei denen beide Teams mindestens 3 frühere Spiele mit xG haben.")
    df = df.reset_index(drop=True)
    split = pd.Timestamp(cfg["split"], tz="UTC")
    tr, te = (df.date < split).to_numpy(), (df.date >= split).to_numpy()
    if te.sum() < 200 or (MODELS[model]["trains"] and tr.sum() < 500):
        hint = "Stichtag oder Merkmale ändern."
        if cfg.get("honest_glicko") and len(df):
            hint = (f"Ehrliches Glicko (vor Anpfiff geholt) gibt es erst für {len(df)} Spiele ab "
                    f"{df.date.min().date()} — mit der Zeit kommen täglich neue dazu. Bis dahin ohne Glicko testen.")
        raise ValueError(f"Zu wenig Spiele (Training {int(tr.sum())}, Test {int(te.sum())}). {hint}")

    oc, cc = _ODDS[market]
    po, margin = _fair(df, oc)
    pc, _ = _fair(df, cc)
    y = df.y.to_numpy()
    X = _features(df, groups, market) if groups else pd.DataFrame(index=df.index)
    importance: List[Dict[str, Any]] = []

    step("Modell trainieren")
    if model == "market":
        P = po[te]
    elif model == "glicko":
        g = df[["gl_ph", "gl_pd", "gl_pa"]].to_numpy(dtype=float)
        g = np.clip(g, 1e-4, None)
        P = (g / g.sum(axis=1, keepdims=True))[te]
    elif model == "poisson":
        m = _PoissonGoals(market).fit(X[tr], df.hg.to_numpy()[tr], df.ag.to_numpy()[tr])
        P = m.predict_proba(X[te])
        step("Merkmale bewerten")
        importance = _permutation(m.predict_proba, X[te].reset_index(drop=True), y[te], _log_loss(y[te], P))
    else:
        m = _classifier(model).fit(X[tr], y[tr])
        P = m.predict_proba(X[te])
        step("Merkmale bewerten")
        importance = _permutation(m.predict_proba, X[te].reset_index(drop=True), y[te], _log_loss(y[te], P))

    yt = y[te]
    step("Wetten auswerten")
    odds_open = df[oc].to_numpy(dtype=float)[te]
    pct = pc[te]
    ev = P * odds_open - 1
    best = ev.argmax(axis=1)
    best_ev = ev[np.arange(len(best)), best]
    names = MARKETS[market]["outcomes"]
    bets = []
    for t in (0.0, 0.02, 0.05, 0.10):
        idx = np.where(best_ev > t)[0]
        k = best[idx]
        o = odds_open[idx, k]
        clv = o * pct[idx, k] - 1
        profit = np.where(yt[idx] == k, o - 1, -1.0)
        clv_ci = None
        if len(idx) > 1:
            se = clv.std(ddof=1) / math.sqrt(len(idx))
            clv_ci = [round((clv.mean() - 1.96 * se) * 100, 2), round((clv.mean() + 1.96 * se) * 100, 2)]
        row = {"threshold_pct": int(t * 100), **_roi_block(profit)}
        if len(idx):
            row.update({
                "avg_odds": round(float(o.mean()), 2),
                "clv_pct": round(float(clv.mean() * 100), 2), "clv_ci95": clv_ci,
                "clv_positive_pct": round(float((clv > 0).mean() * 100), 1),
                "by_outcome": {names[i]: int((k == i).sum()) for i in range(len(names))},
            })
        row["verdict"] = _verdict(row.get("clv_pct"), row.get("roi_ci95"), len(idx))
        bets.append(row)

    ll_model, ll_open, ll_close = _log_loss(yt, P), _log_loss(yt, po[te]), _log_loss(yt, pc[te])
    return {
        "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "train_from": str(df.date[tr].min().date()) if tr.any() else None,
        "test_to": str(df.date[te].max().date()),
        "notes": notes,
        "scores": {
            "model": {"log_loss": round(ll_model, 4), "brier": round(_brier(yt, P), 4)},
            "opening": {"log_loss": round(ll_open, 4), "brier": round(_brier(yt, po[te]), 4)},
            "closing": {"log_loss": round(ll_close, 4), "brier": round(_brier(yt, pc[te]), 4)},
        },
        "beats_opening": bool(ll_model < ll_open - 0.0005),
        "gap_to_opening": round(ll_open - ll_model, 4),
        "bets": bets,
        "importance": importance[:15],
        "calibration": {"outcome": names[0], "bins": _calibration(yt, P)},
    }


# ── Lauf: Strategie-Filter ────────────────────────────────────────────────

# Was das Modell bei einer Strategie-Wette sehen darf (Closing und xROI wären Blick in die Zukunft,
# wenn zur Opening gewettet wird; die Spalten odd_* sind immer Closing)
_STRAT_FEATURES = {
    "odds": "Quote", "home_quote": "Quote Heim", "draw_quote": "Quote Remis", "away_quote": "Quote Ausw.",
    "over_25_quote": "Quote Über 2,5", "under_25_quote": "Quote Unter 2,5",
    "rating_h": "Glicko Heim", "rating_a": "Glicko Ausw.", "rd_h": "RD Heim", "rd_a": "RD Ausw.",
    "p_home": "Glicko p(Heim)", "p_draw": "Glicko p(Remis)", "p_away": "Glicko p(Ausw.)",
    "xg_glicko_h": "Glicko-xG Heim", "xg_glicko_a": "Glicko-xG Ausw.",
    "xg_form2_h": "Form2-xG Heim", "xg_form2_a": "Form2-xG Ausw.",
    "form2_home_n": "Spiele Heim", "form2_away_n": "Spiele Ausw.",
    "form2_home_avg_xg": "Heim xG", "form2_home_avg_xga": "Heim xGA",
    "form2_away_avg_xg": "Ausw. xG", "form2_away_avg_xga": "Ausw. xGA",
    "form2_home_avg_gf": "Heim Tore", "form2_away_avg_gf": "Ausw. Tore",
}


def _run_strategy(cfg: Dict[str, Any], step: Callable[[str], None]) -> Dict[str, Any]:
    from services import strategy_presets_service as presets_svc
    from services import web_strategy_service as strategy_svc

    model = cfg["model"]
    if "strategy" not in MODELS[model]["modes"]:
        raise ValueError("Dieses Modell gibt es nur für Vorhersagen.")
    preset = next((p for p in presets_svc.load_presets() if p.get("id") == cfg.get("preset_id")), None)
    if not preset:
        raise ValueError("Strategie nicht gefunden.")
    step("Strategie-Wetten laden")
    rows: List[Dict[str, Any]] = []
    res = strategy_svc.analyze(preset.get("filters") or {}, limit_results=1, skip_upcoming=True,
                               collect_results_out=rows)
    if not res.get("ok", True) and not rows:
        raise ValueError(res.get("error") or "Strategie liefert keine Wetten.")
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Strategie liefert keine Wetten.")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date", "odds", "profit"]).sort_values("date").reset_index(drop=True)
    for c in _STRAT_FEATURES:
        if c not in df:
            df[c] = np.nan
    X = df[list(_STRAT_FEATURES)].apply(pd.to_numeric, errors="coerce").rename(columns=_STRAT_FEATURES)
    for mk in sorted(df.market.dropna().unique()):
        if df.market.nunique() > 1:
            X[f"Markt {mk}"] = (df.market == mk).astype(float)
    X = X.loc[:, X.notna().mean() > 0.3]
    y = (df.profit.astype(float) > 0).astype(int).to_numpy()
    if cfg.get("split") == "auto":
        # ältere 60 % lernen, neuere 40 % testen — Stichtag auf einen Tageswechsel legen
        split = df.date.iloc[int(len(df) * 0.6)].normalize()
    else:
        split = pd.Timestamp(cfg["split"], tz="UTC")
    tr, te = (df.date < split).to_numpy(), (df.date >= split).to_numpy()
    if tr.sum() < 100 or te.sum() < 40:
        raise ValueError(f"Zu wenig Wetten (insgesamt {len(df)}: Training {int(tr.sum())}, Test {int(te.sum())}). "
                         "Ein Filter-Modell braucht mindestens 100 Wetten vor und 40 nach dem Stichtag.")
    if len(set(y[tr])) < 2:
        raise ValueError("Im Training gibt es nur Treffer oder nur Nieten — nichts zu lernen.")

    step("Modell trainieren")
    m = _classifier(model).fit(X[tr], y[tr])
    p = m.predict_proba(X[te])[:, 1]
    odds = df.odds.astype(float).to_numpy()[te]
    profit = df.profit.astype(float).to_numpy()[te]
    o_open = pd.to_numeric(df.odds_opening, errors="coerce").to_numpy()[te]
    o_close = pd.to_numeric(df.odds_closing, errors="coerce").to_numpy()[te]
    ev = p * odds - 1

    def block(mask: np.ndarray, label: str) -> Dict[str, Any]:
        out = {"label": label, **_roi_block(profit[mask])}
        if mask.any():
            out["hit_pct"] = round(float((profit[mask] > 0).mean() * 100), 1)
            out["avg_odds"] = round(float(odds[mask].mean()), 2)
            ok = mask & np.isfinite(o_open) & np.isfinite(o_close) & (o_close > 1)
            if ok.any():
                # Opening gegen Closing (inkl. Marge) — Näherung, ohne Gegenquoten
                out["clv_pct"] = round(float((o_open[ok] / o_close[ok] - 1).mean() * 100), 2)
        return out

    step("Auswerten")
    half = np.quantile(ev, 0.5)
    selections = [
        block(np.ones(len(p), bool), "Alle Wetten der Strategie"),
        block(ev > 0, "Modell: Erwartungswert > 0 %"),
        block(ev > 0.05, "Modell: Erwartungswert > 5 %"),
        block(ev >= half, "Modell: bessere Hälfte"),
        block(ev < half, "Modell: schlechtere Hälfte (zur Kontrolle)"),
    ]
    implied = np.clip(1 / odds, 1e-4, 1 - 1e-4)
    P2 = np.stack([1 - p, p], axis=1)
    Pi = np.stack([1 - implied, implied], axis=1)
    importance = _permutation(m.predict_proba, X[te].reset_index(drop=True), y[te], _log_loss(y[te], P2))
    base, best = selections[0], selections[3]
    better = bool(best.get("n") and base.get("n") and best["roi_pct"] > base["roi_pct"]
                  and selections[4].get("roi_pct", 0) < base["roi_pct"])
    return {
        "preset": {"id": preset.get("id"), "name": preset.get("name")},
        "odds_type": (preset.get("filters") or {}).get("odds_type") or "closing",
        "n_train": int(tr.sum()), "n_test": int(te.sum()), "split_used": str(split.date()),
        "train_from": str(df.date[tr].min().date()), "test_to": str(df.date[te].max().date()),
        "train_roi_pct": round(float(df.profit.astype(float)[tr].mean() * 100), 2),
        "scores": {"model": {"log_loss": round(_log_loss(y[te], P2), 4)},
                   "quote": {"log_loss": round(_log_loss(y[te], Pi), 4)}},
        "selections": selections,
        "filter_helps": better if te.sum() >= 200 else None,  # darunter: kein Urteil
        "importance": importance[:15],
        "notes": ["CLV hier: Opening- gegen Closing-Quote derselben Wette (Marge nicht herausgerechnet) — Näherung."]
                 + (["Wenige Wetten: Unterschiede zwischen den Gruppen sind meist Zufall."] if te.sum() < 200 else []),
    }


# ── Steuerung ─────────────────────────────────────────────────────────────

def catalog() -> Dict[str, Any]:
    from services import strategy_presets_service as presets_svc

    return {
        "models": [{"id": k, **v} for k, v in MODELS.items()],
        "markets": [{"id": k, "label": v["label"]} for k, v in MARKETS.items()],
        "feature_groups": [{"id": k, **v} for k, v in FEATURE_GROUPS.items()],
        "presets": [{"id": p.get("id"), "name": p.get("name")} for p in presets_svc.load_presets()],
        "default_split": "2026-09-01",
    }


def _save(run: Dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_DIR / f"{run['id']}.json.tmp"
    tmp.write_text(json.dumps(run, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(RUNS_DIR / f"{run['id']}.json")
    old = sorted(RUNS_DIR.glob("*.json"))[:-MAX_RUNS]
    for f in old:
        f.unlink(missing_ok=True)


def _summary(run: Dict[str, Any]) -> Dict[str, Any]:
    cfg, res = run.get("config") or {}, run.get("result") or {}
    s = {"id": run["id"], "created_at": run.get("created_at"), "status": run.get("status"),
         "error": run.get("error"), "seconds": run.get("seconds"), "config": cfg,
         "n_test": res.get("n_test")}
    if cfg.get("mode") == "strategy":
        sel = res.get("selections") or []
        s["strategy"] = (res.get("preset") or {}).get("name")
        s["base_roi"] = sel[0].get("roi_pct") if sel else None
        s["filtered_roi"] = sel[3].get("roi_pct") if len(sel) > 3 else None
        s["filter_helps"] = res.get("filter_helps")
    else:
        sc = res.get("scores") or {}
        s["log_loss"] = (sc.get("model") or {}).get("log_loss")
        s["log_loss_opening"] = (sc.get("opening") or {}).get("log_loss")
        s["beats_opening"] = res.get("beats_opening")
        b = next((x for x in res.get("bets") or [] if x.get("threshold_pct") == 2), None)
        if b:
            s["bets_n"], s["clv_pct"], s["roi_pct"] = b.get("n"), b.get("clv_pct"), b.get("roi_pct")
    return s


def _validate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    mode = cfg.get("mode") if cfg.get("mode") in ("predict", "strategy") else "predict"
    model = cfg.get("model")
    if model not in MODELS or mode not in MODELS[model]["modes"]:
        raise ValueError("Modell passt nicht zur Art des Tests.")
    if mode == "strategy" and cfg.get("split") in (None, "", "auto"):
        split = "auto"
    else:
        try:
            split = str(pd.Timestamp(cfg.get("split") or "2026-09-01").date())
        except Exception:
            raise ValueError("Stichtag ungültig.")
    out = {"mode": mode, "model": model, "split": split}
    if mode == "predict":
        out.update({
            "market": cfg.get("market") if cfg.get("market") in MARKETS else "1x2",
            "features": [g for g in cfg.get("features") or [] if g in FEATURE_GROUPS],
            "honest_glicko": bool(cfg.get("honest_glicko")),
            "scope_only": cfg.get("scope_only", True) is not False,
        })
    else:
        out["preset_id"] = cfg.get("preset_id")
    return out


def _worker(run: Dict[str, Any]) -> None:
    t0 = time.time()

    def step(s: str) -> None:
        _state["step"] = s

    try:
        fn = _run_strategy if run["config"]["mode"] == "strategy" else _run_predict
        run["result"] = fn(run["config"], step)
        run["status"] = "done"
    except ValueError as e:
        run["status"], run["error"] = "error", str(e)
    except Exception as e:  # pragma: no cover - Fehler im Lauf sichtbar machen
        traceback.print_exc()
        run["status"], run["error"] = "error", f"{type(e).__name__}: {e}"
    run["seconds"] = round(time.time() - t0, 1)
    _save(run)
    with _lock:
        _state.update(running=False, run_id=None, started_at=None, step=None)


def start(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _validate(cfg)
    with _lock:
        if _state["running"]:
            return {"started": False, "error": "Es läuft schon ein Test.", "run_id": _state["run_id"]}
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        _state.update(running=True, run_id=run_id, started_at=datetime.now().isoformat(timespec="seconds"),
                      step="Start")
    run = {"id": run_id, "created_at": datetime.now().isoformat(timespec="seconds"), "status": "running",
           "config": cfg}
    threading.Thread(target=_worker, args=(run,), daemon=True, name="ml-run").start()
    return {"started": True, "run_id": run_id}


def runs() -> Dict[str, Any]:
    items = []
    if RUNS_DIR.exists():
        for f in sorted(RUNS_DIR.glob("*.json"), reverse=True):
            try:
                items.append(_summary(json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                continue
    return {"running": dict(_state), "runs": items}


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    if not run_id.replace("-", "").isdigit():
        return None
    f = RUNS_DIR / f"{run_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def delete_run(run_id: str) -> bool:
    if not run_id.replace("-", "").isdigit():
        return False
    f = RUNS_DIR / f"{run_id}.json"
    if f.exists():
        f.unlink()
        return True
    return False


if __name__ == "__main__":
    import sys

    cfg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"mode": "predict", "model": "logreg",
                                                              "market": "1x2", "features": ["opening", "xg"]}
    cfg = _validate(cfg)
    res = (_run_strategy if cfg["mode"] == "strategy" else _run_predict)(cfg, lambda s: print("·", s))
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:4000])
