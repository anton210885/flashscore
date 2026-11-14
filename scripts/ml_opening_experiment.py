"""ML-Experiment: Kann ein Modell die Pinnacle-OPENING-Quote schlagen?

Frage: Sagt ein Modell aus Merkmalen vor Anpfiff (Opening-Quote, Glicko, xG Saison, Power/Tempo)
den Ausgang (1/X/2) besser voraus als die Opening-Quote selbst — und hätten seine Tipps einen
positiven CLV (Closing Line Value) gehabt, also früh zu einem besseren Preis als das Closing?

Ehrlich gemessen:
  * strikt zeitlich: lernen auf älteren Spielen, testen auf späteren (nie gemischt)
  * Closing-Quote ist NUR Messlatte, nie Merkmal
  * Ergebnis nach Liga-Stufe (Opening-Marge als Mass für „weiche“ Märkte)

  python -u scripts/ml_opening_experiment.py
  python -u scripts/ml_opening_experiment.py --split 2026-09-01
Bericht: logs/ml_opening_experiment.txt (+ .json)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss

ROOT = Path(__file__).resolve().parent.parent
OUT_TXT = ROOT / "logs" / "ml_opening_experiment.txt"
OUT_JSON = ROOT / "logs" / "ml_opening_experiment.json"
OUTCOMES = ("H", "D", "A")

QUERY = """
SELECT g.id, g.date, g.league_id, g.home_ft_result AS hg, g.away_ft_result AS ag,
       o.oh, o.od, o.oa, o.ch, o.cd, o.ca,
       gl.home_rating, gl.away_rating, gl.home_rd, gl.away_rd, gl.home_xg AS gl_xg_h, gl.away_xg AS gl_xg_a,
       gl.home_win_probability AS gl_ph, gl.draw_probability AS gl_pd, gl.away_win_probability AS gl_pa,
       f.home_n, f.away_n, f.home_avg_xg, f.home_avg_xga, f.home_avg_gf, f.home_avg_ga,
       f.away_avg_xg, f.away_avg_xga, f.away_avg_gf, f.away_avg_ga,
       f.hometeam_home_n, f.hometeam_home_xg, f.hometeam_home_xga,
       f.awayteam_away_n, f.awayteam_away_xg, f.awayteam_away_xga,
       f.hometeam_pred_xg, f.awayteam_pred_xg
FROM games g
JOIN (
    SELECT game_id,
           MAX(CASE WHEN name='Home' THEN opening_value END) AS oh,
           MAX(CASE WHEN name='Draw' THEN opening_value END) AS od,
           MAX(CASE WHEN name='Away' THEN opening_value END) AS oa,
           MAX(CASE WHEN name='Home' THEN value END) AS ch,
           MAX(CASE WHEN name='Draw' THEN value END) AS cd,
           MAX(CASE WHEN name='Away' THEN value END) AS ca
    FROM game_odds WHERE market_id = 1 GROUP BY game_id
) o ON o.game_id = g.id
LEFT JOIN game_glicko gl ON gl.game_id = g.id
LEFT JOIN game_form2 f ON f.game_id = g.id
WHERE g.status IN (7, 8, 9, 10) AND g.home_ft_result IS NOT NULL
"""


def load(db: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    df = pd.read_sql_query(QUERY, conn)
    conn.close()
    odds = ["oh", "od", "oa", "ch", "cd", "ca"]
    df = df.dropna(subset=odds)
    df = df[(df[odds] > 1.01).all(axis=1) & (df[odds] < 100).all(axis=1)].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["y"] = np.select([df.hg > df.ag, df.hg == df.ag], [0, 1], 2)
    for p in ("o", "c"):
        inv = 1 / df[[f"{p}h", f"{p}d", f"{p}a"]]
        s = inv.sum(axis=1)
        df[f"{p}_margin"] = s - 1
        for k, col in zip(OUTCOMES, ("h", "d", "a")):
            df[f"{p}_p{k}"] = inv[f"{p}{col}"] / s  # faire Wahrscheinlichkeit (Marge proportional entfernt)
    # Glicko-Wahrscheinlichkeiten teils in %, teils 0..1
    for c in ("gl_ph", "gl_pd", "gl_pa"):
        df[c] = np.where(df[c] > 1, df[c] / 100.0, df[c])
    return df.sort_values("date").reset_index(drop=True)


def glicko_timing(df: pd.DataFrame, db: str) -> list:
    """Wie nah ist Glicko am Closing — je nachdem, wann Glicko zuletzt geholt wurde?

    Liegt Glicko „nach Anpfiff geholt“ deutlich näher am Closing als am Opening, enthält es
    Marktinformation von kurz vor Anpfiff → Backtests mit Glicko sind zu optimistisch.
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    upd = pd.read_sql_query("SELECT game_id AS id, updated_at FROM game_glicko", conn).set_index("id").updated_at
    conn.close()
    t = pd.to_datetime(df.id.map(upd).str[:19], errors="coerce")
    t = t.dt.tz_localize("Europe/Zurich", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    hours = (df.date - t).dt.total_seconds() / 3600
    out = []
    for lo, hi, lab in ((-1e9, 0, "nach Anpfiff"), (0, 2, "0–2 h vorher"), (2, 1e9, ">2 h vorher")):
        d = df[(hours > lo) & (hours <= hi)].dropna(subset=["gl_ph"])
        if len(d) < 100:
            continue
        out.append({
            "geholt": lab, "n": int(len(d)),
            "korr_glicko_minus_opening_mit_bewegung": round(float(np.corrcoef(d.gl_ph - d.o_pH, d.c_pH - d.o_pH)[0, 1]), 3),
            "abstand_zu_closing": round(float((d.gl_ph - d.c_pH).abs().mean()), 4),
            "abstand_zu_opening": round(float((d.gl_ph - d.o_pH).abs().mean()), 4),
        })
    return out


def features(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for k in OUTCOMES:
        X[f"open_p{k}"] = df[f"o_p{k}"]
    X["open_margin"] = df["o_margin"]
    X["glicko_diff"] = df.home_rating - df.away_rating
    X["glicko_rd_sum"] = df.home_rd + df.away_rd
    X["glicko_xg_diff"] = df.gl_xg_h - df.gl_xg_a
    X["glicko_xg_sum"] = df.gl_xg_h + df.gl_xg_a
    for k, c in zip(OUTCOMES, ("gl_ph", "gl_pd", "gl_pa")):
        X[f"glicko_p{k}"] = df[c]
        X[f"glicko_vs_open_{k}"] = df[c] - df[f"o_p{k}"]  # wo Glicko anders denkt als der Markt
    X["form_n_min"] = np.minimum(df.home_n, df.away_n)
    X["xg_saison_diff"] = (df.home_avg_xg - df.home_avg_xga) - (df.away_avg_xg - df.away_avg_xga)
    X["xg_venue_diff"] = (df.hometeam_home_xg - df.hometeam_home_xga) - (df.awayteam_away_xg - df.awayteam_away_xga)
    X["pred_xg_diff"] = df.hometeam_pred_xg - df.awayteam_pred_xg
    X["pred_xg_sum"] = df.hometeam_pred_xg + df.awayteam_pred_xg
    X["goals_vs_xg_home"] = (df.home_avg_gf - df.home_avg_xg)  # Effizienz / Glück
    X["goals_vs_xg_away"] = (df.away_avg_gf - df.away_avg_xg)
    return X


def tier(margin: pd.Series) -> pd.Series:
    return pd.cut(margin, [-1, 0.045, 0.08, 1], labels=["Top (<4,5 %)", "Mittel (4,5–8 %)", "Weich (>8 %)"])


def betting(df: pd.DataFrame, P: np.ndarray, thresholds=(0.0, 0.03, 0.05, 0.10)) -> list:
    """Tipps, wo Modell-EV zur Opening-Quote > Schwelle; gemessen an Closing (CLV) und Ergebnis."""
    rows = []
    odds_open = df[["oh", "od", "oa"]].to_numpy()
    p_close = df[["c_pH", "c_pD", "c_pA"]].to_numpy()
    y = df["y"].to_numpy()
    ev = P * odds_open - 1
    best = ev.argmax(axis=1)
    best_ev = ev[np.arange(len(df)), best]
    for t in thresholds:
        m = best_ev > t
        if not m.any():
            rows.append({"threshold": t, "n": 0})
            continue
        idx = np.where(m)[0]
        k = best[idx]
        o = odds_open[idx, k]
        clv = o * p_close[idx, k] - 1  # erwarteter Wert gemessen an der fairen Closing-Wahrscheinlichkeit
        won = (y[idx] == k)
        profit = np.where(won, o - 1, -1.0)
        se = profit.std(ddof=1) / np.sqrt(len(profit)) if len(profit) > 1 else np.nan
        rows.append({
            "threshold": t, "n": int(len(idx)),
            "share_H_D_A": [int((k == i).sum()) for i in range(3)],
            "avg_odds": round(float(o.mean()), 2),
            "clv_mean_pct": round(float(clv.mean() * 100), 2),
            "clv_positive_pct": round(float((clv > 0).mean() * 100), 1),
            "roi_pct": round(float(profit.mean() * 100), 2),
            "roi_ci95_pct": [round(float((profit.mean() - 1.96 * se) * 100), 1),
                             round(float((profit.mean() + 1.96 * se) * 100), 1)],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="ML gegen Pinnacle-Opening")
    ap.add_argument("--db", default=str(ROOT / "data" / "flashscore.db"))
    ap.add_argument("--split", default="2026-09-01", help="Testdaten ab diesem Datum")
    args = ap.parse_args()

    df = load(args.db)
    split = pd.Timestamp(args.split, tz="UTC")
    tr, te = df[df.date < split], df[df.date >= split]
    X = features(df)
    Xtr, Xte = X.loc[tr.index], X.loc[te.index]

    model = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=80,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.15, random_state=42,
    )
    model.fit(Xtr, tr.y)
    P = model.predict_proba(Xte)

    P_open = te[["o_pH", "o_pD", "o_pA"]].to_numpy()
    P_close = te[["c_pH", "c_pD", "c_pA"]].to_numpy()
    P_gl = te[["gl_ph", "gl_pd", "gl_pa"]].to_numpy()
    gl_ok = ~np.isnan(P_gl).any(axis=1)
    P_gl_n = np.where(gl_ok[:, None], P_gl / np.nansum(P_gl, axis=1, keepdims=True), P_open)

    def ll(p, mask=None):
        m = np.ones(len(te), bool) if mask is None else mask
        return round(float(log_loss(te.y[m], np.clip(p[m], 1e-6, 1), labels=[0, 1, 2])), 4) if m.sum() > 50 else None

    tiers = tier(te.o_margin)
    by_tier = []
    for t in tiers.cat.categories:
        m = (tiers == t).to_numpy()
        by_tier.append({
            "tier": str(t), "n": int(m.sum()),
            "logloss_modell": ll(P, m), "logloss_opening": ll(P_open, m), "logloss_closing": ll(P_close, m),
            "bets": betting(te[m], P[m], thresholds=(0.03, 0.05)),
        })

    imp = None
    try:
        from sklearn.inspection import permutation_importance
        sample = Xte.sample(min(3000, len(Xte)), random_state=1)
        r = permutation_importance(model, sample, te.y.loc[sample.index], scoring="neg_log_loss",
                                   n_repeats=3, random_state=1)
        imp = sorted(zip(Xte.columns, r.importances_mean), key=lambda x: -x[1])[:10]
    except Exception:
        pass

    res = {
        "erstellt": datetime.now().isoformat(timespec="seconds"),
        "split": args.split, "train_n": int(len(tr)), "test_n": int(len(te)),
        "train_von_bis": [str(tr.date.min())[:10], str(tr.date.max())[:10]],
        "test_von_bis": [str(te.date.min())[:10], str(te.date.max())[:10]],
        "logloss": {"modell": ll(P), "opening": ll(P_open), "closing": ll(P_close),
                    "glicko_allein": ll(P_gl_n, gl_ok)},
        "bets_alle": betting(te, P),
        "nach_liga_stufe": by_tier,
        "wichtigste_merkmale": [[k, round(float(v), 5)] for k, v in imp] if imp else None,
        "glicko_zeitpunkt": glicko_timing(df, args.db),
    }

    lines = [
        "ML-Experiment: Modell gegen Pinnacle-Opening",
        f"Training {res['train_von_bis'][0]} … {res['train_von_bis'][1]} (n={res['train_n']}) · "
        f"Test {res['test_von_bis'][0]} … {res['test_von_bis'][1]} (n={res['test_n']})",
        "",
        "Log-Loss (kleiner = besser) auf den Testspielen:",
        f"  Modell   {res['logloss']['modell']}",
        f"  Opening  {res['logloss']['opening']}",
        f"  Closing  {res['logloss']['closing']}   (Obergrenze: das weiss der Markt kurz vor Anpfiff)",
        f"  Glicko   {res['logloss']['glicko_allein']}   (nur Spiele mit Glicko)",
        "",
        "Tipps: Modell-EV zur Opening-Quote > Schwelle  (CLV = Wert gemessen am fairen Closing)",
    ]
    for b in res["bets_alle"]:
        if b["n"]:
            lines.append(f"  EV>{b['threshold']:.0%}: n={b['n']} Ø-Quote {b['avg_odds']} · CLV Ø {b['clv_mean_pct']}% "
                         f"({b['clv_positive_pct']}% positiv) · ROI {b['roi_pct']}% (95%: {b['roi_ci95_pct'][0]} … {b['roi_ci95_pct'][1]}) "
                         f"· H/D/A {b['share_H_D_A']}")
        else:
            lines.append(f"  EV>{b['threshold']:.0%}: keine Tipps")
    lines += ["", "Nach Liga-Stufe (Opening-Marge):"]
    for t in by_tier:
        lines.append(f"  {t['tier']}: n={t['n']} · Log-Loss Modell {t['logloss_modell']} / Opening {t['logloss_opening']} / Closing {t['logloss_closing']}")
        for b in t["bets"]:
            if b["n"]:
                lines.append(f"      EV>{b['threshold']:.0%}: n={b['n']} CLV Ø {b['clv_mean_pct']}% · ROI {b['roi_pct']}% "
                             f"(95%: {b['roi_ci95_pct'][0]} … {b['roi_ci95_pct'][1]})")
    if res["wichtigste_merkmale"]:
        lines += ["", "Wichtigste Merkmale (Verschlechterung Log-Loss beim Durchmischen):"]
        lines += [f"  {k}: {v}" for k, v in res["wichtigste_merkmale"]]
    lines += ["", "Glicko-Zeitpunkt (Marktinformation im Glicko?):"]
    for g in res["glicko_zeitpunkt"]:
        lines.append(f"  geholt {g['geholt']}: n={g['n']} · Korrelation mit Quotenbewegung "
                     f"{g['korr_glicko_minus_opening_mit_bewegung']} · Ø Abstand zu Closing "
                     f"{g['abstand_zu_closing']} / zu Opening {g['abstand_zu_opening']}")
    text = "\n".join(lines)

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(text + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
