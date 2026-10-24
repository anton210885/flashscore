import { metricName } from './metricNames'
/** Texte für Korrelation & Metriken (Strategie-Tab). */

const CORR_METRIC_HELP_RAW = [
  {
    key: 'chance',
    label: 'chance',
    text: 'Gewinnwahrscheinlichkeit des gewählten Markts (0–1) vor dem Spiel, aus historischen Trefferquoten / Modellchance.',
  },
  {
    key: 'odds',
    label: 'odds',
    text: 'Dezimalquote des gewählten Markts (Closing bzw. gewählter Quotentyp). Höhere Quote = höheres Risiko/Auszahlung.',
  },
  {
    key: 'home_quote',
    label: 'home_quote',
    text: 'Home-Quote (1) des Spiels — unabhängig vom gewählten Wettmarkt. Closing oder Opening je nach Quotentyp-Filter.',
  },
  {
    key: 'away_quote',
    label: 'away_quote',
    text: 'Away-Quote (2) des Spiels — unabhängig vom gewählten Wettmarkt.',
  },
  {
    key: 'over_25_quote',
    label: 'over_25_quote',
    text: 'Quote Over 2.5 des Spiels — unabhängig vom gewählten Wettmarkt.',
  },
  {
    key: 'xroi_pct',
    label: 'xroi_pct',
    text: 'xROI % = (Opening − Closing) / Closing × 100. Positiv = bessere Quote bei Eröffnung (Closing-Line-Value).',
  },
  {
    key: 'rating_home',
    label: 'rating_home',
    text: 'Glicko-Rating der Heimmannschaft vor dem Spiel. Höher = stärkere Heimseite laut Glicko.',
  },
  {
    key: 'rating_away',
    label: 'rating_away',
    text: 'Glicko-Rating der Auswärtsmannschaft vor dem Spiel. Höher = stärkere Auswärtsseite laut Glicko.',
  },
  {
    key: 'rating_avg',
    label: 'rating_avg',
    text: 'Durchschnitt aus Home- und Away-Glicko-Rating. Misst das allgemeine Niveau beider Teams.',
  },
  {
    key: 'rating_diff',
    label: 'rating_diff',
    text: 'Glicko-Differenz Home − Away. Positiv = Heimseite laut Rating stärker; negativ = Auswärtsseite stärker.',
  },
  {
    key: 'rating_ratio',
    label: 'rating_ratio',
    text: 'Verhältnis Glicko-Rating Home / Away. > 1 = Heimseite stärker; < 1 = Auswärtsseite stärker.',
  },
  {
    key: 'rating_sum',
    label: 'rating_sum',
    text: 'Summe Glicko-Rating Home + Away. Misst das Gesamtniveau beider Teams (= 2 × rating_avg).',
  },
  {
    key: 'xg_glicko_home',
    label: 'xg_glicko_home',
    text: 'Erwartete Tore (xG) der Heimmannschaft aus dem Glicko-Modell (pre-match) — Vorhersage, nicht die im Match erzielten xG.',
  },
  {
    key: 'xg_glicko_away',
    label: 'xg_glicko_away',
    text: 'Erwartete Tore (xG) der Auswärtsmannschaft aus dem Glicko-Modell (pre-match).',
  },
  {
    key: 'xg_glicko_sum',
    label: 'xg_glicko_sum',
    text: 'Summe xG Glicko Home + Away. Proxy für erwartete Gesamtchancen / Over-Potenzial.',
  },
  {
    key: 'xg_glicko_diff',
    label: 'xg_glicko_diff',
    text: 'Differenz xG Glicko Home − Away. Positiv = Heimseite wird offensiv stärker eingeschätzt.',
  },
  {
    key: 'xg_glicko_ratio',
    label: 'xg_glicko_ratio',
    text: 'Verhältnis xG Glicko Home / Away. > 1 = Heimseite offensiv stärker eingeschätzt; < 1 = Auswärtsseite.',
  },
  {
    key: 'xg_form2_home',
    label: 'xg_form2_home',
    text: 'Form2 pred. xG Home = (Ø Match-xG Home + Ø xGA Away) / 2 aus der laufenden Saison bis vor dem Spiel. Parallel zu Glicko2, selbst berechnet.',
  },
  {
    key: 'xg_form2_away',
    label: 'xg_form2_away',
    text: 'Form2 pred. xG Away = (Ø Match-xG Away + Ø xGA Home) / 2. Nur Meisterschaften, Reset pro Saison.',
  },
  {
    key: 'xg_form2_sum',
    label: 'xg_form2_sum',
    text: 'Summe xG Form2 Home + Away.',
  },
  {
    key: 'xg_form2_diff',
    label: 'xg_form2_diff',
    text: 'Differenz xG Form2 Home − Away. Positiv = Heimseite laut Saisonform offensiv stärker.',
  },
  {
    key: 'xg_form2_ratio',
    label: 'xg_form2_ratio',
    text: 'Verhältnis xG Form2 Home / Away. > 1 = Heimseite stärker laut Form2; < 1 = Auswärtsseite.',
  },
  {
    key: 'form2_avg_xg_home',
    label: 'form2_avg_xg_home',
    text: 'Saison-Durchschnitt der Match-xG der Heimmannschaft vor dem Spiel.',
  },
  {
    key: 'form2_avg_xg_away',
    label: 'form2_avg_xg_away',
    text: 'Saison-Durchschnitt der Match-xG der Auswärtsmannschaft vor dem Spiel.',
  },
  {
    key: 'form2_avg_xga_home',
    label: 'form2_avg_xga_home',
    text: 'Saison-Durchschnitt xGA (zugelassene xG) der Heimmannschaft vor dem Spiel.',
  },
  {
    key: 'form2_avg_xga_away',
    label: 'form2_avg_xga_away',
    text: 'Saison-Durchschnitt xGA (zugelassene xG) der Auswärtsmannschaft vor dem Spiel.',
  },
  {
    key: 'form2_avg_gf_home',
    label: 'form2_avg_gf_home',
    text: 'Saison-Durchschnitt erzielter Tore der Heimmannschaft vor dem Spiel.',
  },
  {
    key: 'form2_avg_gf_away',
    label: 'form2_avg_gf_away',
    text: 'Saison-Durchschnitt erzielter Tore der Auswärtsmannschaft vor dem Spiel.',
  },
  {
    key: 'hometeam_home_xg',
    label: 'hometeam_home_xg',
    text: 'Ø Match-xG des Heimteams nur in Heimspielen (Saison, vor Kickoff).',
  },
  {
    key: 'hometeam_home_xga',
    label: 'hometeam_home_xga',
    text: 'Ø xGA des Heimteams nur in Heimspielen.',
  },
  {
    key: 'hometeam_away_xg',
    label: 'hometeam_away_xg',
    text: 'Ø Match-xG des Heimteams nur in Auswärtsspielen.',
  },
  {
    key: 'awayteam_away_xg',
    label: 'awayteam_away_xg',
    text: 'Ø Match-xG des Gasts nur in Auswärtsspielen.',
  },
  {
    key: 'awayteam_away_xga',
    label: 'awayteam_away_xga',
    text: 'Ø xGA des Gasts nur in Auswärtsspielen.',
  },
  {
    key: 'hometeam_pred_xg',
    label: 'hometeam_pred_xg',
    text: 'Venue-Pred: (hometeam_home_xg + awayteam_away_xga) / 2.',
  },
  {
    key: 'awayteam_pred_xg',
    label: 'awayteam_pred_xg',
    text: 'Venue-Pred: (awayteam_away_xg + hometeam_home_xga) / 2.',
  },
  {
    key: 'power_home',
    label: 'power_home',
    text: 'Ø xG ÷ Ø xGA des Heimteams (alle Saisonspiele). Über 1 = erzeugt mehr Chancen als es zulässt.',
  },
  {
    key: 'power_away',
    label: 'power_away',
    text: 'Ø xG ÷ Ø xGA des Gastteams (alle Saisonspiele). Über 1 = erzeugt mehr Chancen als es zulässt.',
  },
  {
    key: 'power_diff',
    label: 'power_diff',
    text: 'Power Home − Power Away. Positiv = Heimteam laut Chancenverhältnis stärker, negativ = Gast stärker.',
  },
  {
    key: 'tempo_home',
    label: 'tempo_home',
    text: 'Ø xG + Ø xGA des Heimteams: Chancen pro Spiel insgesamt — hoch = offene Spiele.',
  },
  {
    key: 'tempo_away',
    label: 'tempo_away',
    text: 'Ø xG + Ø xGA des Gastteams: Chancen pro Spiel insgesamt — hoch = offene Spiele.',
  },
  {
    key: 'tempo_sum',
    label: 'tempo_sum',
    text: 'Tempo Home + Tempo Away — erwartete Offenheit des Spiels (interessant für Over/Under).',
  },
  {
    key: 'power_home_venue',
    label: 'power_home_venue',
    text: 'Wie Power Home, aber nur Heimspiele des Heimteams.',
  },
  {
    key: 'power_away_venue',
    label: 'power_away_venue',
    text: 'Wie Power Away, aber nur Auswärtsspiele des Gastteams.',
  },
  {
    key: 'power_diff_venue',
    label: 'power_diff_venue',
    text: 'Power Home (Heimspiele) − Power Away (Auswärtsspiele).',
  },
  {
    key: 'tempo_home_venue',
    label: 'tempo_home_venue',
    text: 'Wie Tempo Home, aber nur Heimspiele des Heimteams.',
  },
  {
    key: 'tempo_away_venue',
    label: 'tempo_away_venue',
    text: 'Wie Tempo Away, aber nur Auswärtsspiele des Gastteams.',
  },
]

export const CORR_RULE_HELP = [
  { key: '>= p70', text: 'Nur Wetten im oberen ~30 % der Metric-Werte (ab 70. Perzentil).' },
  { key: '>= p80', text: 'Nur Wetten im oberen ~20 % der Metric-Werte (ab 80. Perzentil).' },
  { key: '>= p90', text: 'Nur Wetten im oberen ~10 % der Metric-Werte (ab 90. Perzentil).' },
  { key: '<= p30', text: 'Nur Wetten im unteren ~30 % der Metric-Werte (bis 30. Perzentil).' },
  { key: '<= p20', text: 'Nur Wetten im unteren ~20 % der Metric-Werte (bis 20. Perzentil).' },
  { key: '<= p10', text: 'Nur Wetten im unteren ~10 % der Metric-Werte (bis 10. Perzentil).' },
]

export const CORR_METRIC_HELP = CORR_METRIC_HELP_RAW.map((m) => ({
  ...m,
  label: m.label === m.key ? `${metricName(m.key)} (${m.key})` : m.label,
}))

export const CORR_METRIC_MAP = Object.fromEntries(CORR_METRIC_HELP.map((m) => [m.key, m.text]))

/** Spalten der Korrelations-Tabelle (Hover + Hilfe-Panel). */
export const CORR_COLUMN_HELP = [
  {
    key: '#',
    label: '#',
    text: 'Rang je nach Sortierung: Δ ROI oder Δ Profit (beste Verbesserung zuerst). Bei Gleichstand das jeweils andere Delta, dann größeres n.',
  },
  {
    key: 'Metric',
    label: 'Metric',
    text: 'Welche Kenngröße getestet wird (z. B. rating_away, odds, xg_glicko_ratio). Pro Zeile wird nur diese eine Metrik zusätzlich eingeschränkt.',
  },
  {
    key: 'Regel',
    label: 'Regel',
    text: 'Perzentil-Regel auf der Baseline: Top ~10/20/30 % (≥ p90/p80/p70) oder Bottom ~10/20/30 % (≤ p10/p20/p30).',
  },
  {
    key: 'Bedingung',
    label: 'Bedingung',
    text: 'Konkrete Schwelle aus den Daten, z. B. rating_away ≥ 1786. Das kannst du als Filter übernehmen.',
  },
  {
    key: 'n',
    label: 'n',
    text: 'Anzahl Wetten/Spiele in dieser Teilmenge (nach der Schwelle). Zu kleines n = unsicher, auch bei hohem ROI.',
  },
  {
    key: 'WR%',
    label: 'WR%',
    text: 'Winrate der Teilmenge in Prozent (Anteil gewonnener Wetten).',
  },
  {
    key: 'Profit',
    label: 'Profit',
    text: 'Summe der Einheiten-Gewinne/Verluste in der Teilmenge (1 Einheit Einsatz pro Wette).',
  },
  {
    key: 'ROI%',
    label: 'ROI%',
    text: 'Return on Investment der Teilmenge: Profit ÷ n × 100.',
  },
  {
    key: 'Δ ROI',
    label: 'Δ ROI',
    text: 'ROI Teilmenge minus ROI Baseline. Positiv = diese Schwelle hätte den ROI historisch verbessert. Sortieroption „Δ ROI“.',
  },
  {
    key: 'Δ Profit',
    label: 'Δ Profit',
    text: 'Profit Teilmenge minus Profit Baseline. Zeigt, ob der absolute Gewinn trotz weniger Wetten steigen würde. Sortieroption „Δ Profit“.',
  },
  {
    key: 'Anteil%',
    label: 'Anteil%',
    text: 'Wie viel Prozent der Baseline-Wetten die Schwelle erfüllen (Coverage). Sehr klein = eng, oft Überanpassung.',
  },
]

export const CORR_COLUMN_MAP = Object.fromEntries(CORR_COLUMN_HELP.map((c) => [c.label, c.text]))

function _fmtNum(v, digits = 2) {
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v ?? '—')
  if (Math.abs(n) >= 100) return String(Math.round(n))
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(digits).replace(/\.?0+$/, '')
}

function _parseCondition(condition) {
  // Backend zeigt Formeln wie „Rating Home − Away ≤ -50“ (≥/≤), ältere Stände „rating_diff <= -50“
  const m = String(condition || '').match(/(≥|≤|[<>]=?)\s*([-+]?\d*\.?\d+)/)
  if (!m) return { op: null, thr: null }
  const op = { '≥': '>=', '≤': '<=' }[m[1]] || m[1]
  return { op, thr: Number(m[2]) }
}

function _rulePlain(rule) {
  const r = String(rule || '')
  if (r.includes('p90') && r.includes('>=')) return 'nur die obersten ~10 % der Werte'
  if (r.includes('p80') && r.includes('>=')) return 'nur die obersten ~20 % der Werte'
  if (r.includes('p70') && r.includes('>=')) return 'nur die obersten ~30 % der Werte'
  if (r.includes('p10') && r.includes('<=')) return 'nur die untersten ~10 % der Werte'
  if (r.includes('p20') && r.includes('<=')) return 'nur die untersten ~20 % der Werte'
  if (r.includes('p30') && r.includes('<=')) return 'nur die untersten ~30 % der Werte'
  return CORR_RULE_HELP.find((h) => r.includes(h.key.replace(/\s/g, '')) || r.startsWith(h.key))?.text
    || `Regel „${rule}“`
}

/** Alltags-Erklärung einer Korrelations-Zeile (Metric + Schwelle). */
export function explainCorrRow(row) {
  if (!row) return null
  const metric = String(row.metric || '')
  const { op, thr } = _parseCondition(row.condition)
  const thrS = thr == null ? null : _fmtNum(thr, metric.includes('ratio') || metric.startsWith('xg') ? 4 : 2)
  const metricDef = CORR_METRIC_MAP[metric] || `Metrik „${metric}“.`
  const rulePlain = _rulePlain(row.rule)

  let plain = null
  let filterHint = null

  if (metric === 'xg_glicko_ratio' && op && thrS != null) {
    if (op.startsWith('<')) {
      const pct = thr > 0 && thr < 2 ? Math.round(thr * 100) : null
      plain =
        `xG Home ÷ xG Away ${op} ${thrS}` +
        (pct != null
          ? ` — die Heimseite hat laut Modell höchstens ~${pct} % der erwarteten Tore der Auswärtsseite.`
          : '.') +
        ' Kurz: Away wird offensiv klar stärker eingeschätzt.'
      filterHint =
        'Filter: Away-xG hoch / Home-xG niedrig, oder Attribut-Filter „xG Home / xG Away“ mit Max = Schwelle.'
    } else {
      plain = `xG Home ÷ xG Away ${op} ${thrS} — Heimseite wird offensiv relativ stärker eingeschätzt.`
      filterHint = 'Filter: Home-xG hoch / Away-xG niedrig, oder Attribut-Filter mit Min = Schwelle.'
    }
  } else if (metric === 'rating_ratio' && op && thrS != null) {
    if (op.startsWith('<')) {
      plain =
        `Home-Rating ÷ Away-Rating ${op} ${thrS} — Away ist laut Glicko relativ klar stärker (Verhältnis unter 1).`
      filterHint =
        'Filter: awayRating-Min hoch und/oder homeRating-Max niedriger; Attribut „homeRating / awayRating“ Max = Schwelle.'
    } else {
      plain = `Home-Rating ÷ Away-Rating ${op} ${thrS} — Heimseite laut Rating relativ stärker.`
      filterHint = 'Filter: homeRating-Min / awayRating-Max, oder Attribut-Verhältnis Min = Schwelle.'
    }
  } else if (metric === 'rating_diff' && op && thrS != null) {
    if (op.startsWith('<')) {
      plain =
        `Home-Rating − Away-Rating ${op} ${thrS} — Away um mindestens ${Math.abs(thr).toFixed(0)} Ratingpunkte stärker.`
      filterHint = 'Filter: Attribut „homeRating − awayRating“ mit Max = Schwelle (oder awayRating hoch).'
    } else {
      plain =
        `Home-Rating − Away-Rating ${op} ${thrS} — Heimseite laut Rating (relativ) stärker bzw. weniger unterlegen.`
      filterHint = 'Filter: Attribut „homeRating − awayRating“ mit Min = Schwelle.'
    }
  } else if (metric === 'xg_glicko_diff' && op && thrS != null) {
    if (op.startsWith('<')) {
      plain = `xG Home − xG Away ${op} ${thrS} — Away wird offensiv deutlich stärker erwartet.`
      filterHint = 'Filter: Away-xG Min hoch / Home-xG Max niedrig, oder Diff-Attribut Max = Schwelle.'
    } else {
      plain = `xG Home − xG Away ${op} ${thrS} — Heimseite wird offensiv stärker erwartet.`
      filterHint = 'Filter: Home-xG Min / Away-xG Max, oder Diff-Attribut Min = Schwelle.'
    }
  } else if (metric === 'rating_away' && op && thrS != null) {
    plain = op.startsWith('>')
      ? `Away-Glicko ${op} ${thrS} — nur Spiele mit starker Auswärtsmannschaft.`
      : `Away-Glicko ${op} ${thrS} — Away eher schwächer geratet.`
    filterHint = op.startsWith('>')
      ? `Filter setzen: awayRating Min = ${thrS}`
      : `Filter setzen: awayRating Max = ${thrS}`
  } else if (metric === 'rating_home' && op && thrS != null) {
    plain = op.startsWith('>')
      ? `Home-Glicko ${op} ${thrS} — starke Heimmannschaft.`
      : `Home-Glicko ${op} ${thrS} — eher schwache Heimmannschaft.`
    filterHint = op.startsWith('>')
      ? `Filter setzen: homeRating Min = ${thrS}`
      : `Filter setzen: homeRating Max = ${thrS}`
  } else if (metric === 'rating_avg' && op && thrS != null) {
    plain = op.startsWith('>')
      ? `Ø-Rating beider Teams ${op} ${thrS} — höheres Gesamt-Niveau der Partie.`
      : `Ø-Rating beider Teams ${op} ${thrS} — eher niedrigeres Niveau.`
    filterHint = 'Kein Direktfilter — über homeRating + awayRating gemeinsam eingrenzen.'
  } else if (metric === 'odds' && op && thrS != null) {
    plain = op.startsWith('>')
      ? `Quote des gewählten Markts ${op} ${thrS} — etwas längere Kurse (mehr Auszahlung, mehr Risiko).`
      : `Quote des gewählten Markts ${op} ${thrS} — kürzere Kurse (Favoriten).`
    filterHint = op.startsWith('>')
      ? `Filter: Markt-Quote Min ≈ ${thrS}`
      : `Filter: Markt-Quote Max ≈ ${thrS}`
  } else if (metric === 'home_quote' && op && thrS != null) {
    plain = `Home-Quote (1) ${op} ${thrS} — unabhängig vom gewählten Wettmarkt.`
    filterHint = op.startsWith('>')
      ? `Filter: Home-Quote Min ≈ ${thrS}`
      : `Filter: Home-Quote Max ≈ ${thrS}`
  } else if (metric === 'away_quote' && op && thrS != null) {
    plain = `Away-Quote (2) ${op} ${thrS} — unabhängig vom gewählten Wettmarkt.`
    filterHint = op.startsWith('>')
      ? `Filter: Away-Quote Min ≈ ${thrS}`
      : `Filter: Away-Quote Max ≈ ${thrS}`
  } else if (metric === 'over_25_quote' && op && thrS != null) {
    plain = `Over-2.5-Quote ${op} ${thrS} — unabhängig vom gewählten Wettmarkt.`
    filterHint = op.startsWith('>')
      ? `Filter: Over-2.5-Quote Min ≈ ${thrS}`
      : `Filter: Over-2.5-Quote Max ≈ ${thrS}`
  } else if (metric === 'xg_glicko_home' && op && thrS != null) {
    plain = `Erwartete Tore Home (Glicko) ${op} ${thrS}.`
    filterHint = op.startsWith('>')
      ? `Filter: Home xG Min = ${thrS}`
      : `Filter: Home xG Max = ${thrS}`
  } else if (metric === 'xg_glicko_away' && op && thrS != null) {
    plain = `Erwartete Tore Away (Glicko) ${op} ${thrS}.`
    filterHint = op.startsWith('>')
      ? `Filter: Away xG Min = ${thrS}`
      : `Filter: Away xG Max = ${thrS}`
  } else if (metric === 'xg_glicko_sum' && op && thrS != null) {
    plain = `xG Home + Away ${op} ${thrS} — Proxy für erwartete Gesamtchancen.`
    filterHint = 'Kein Direktfilter für Summe — Home/Away-xG getrennt setzen.'
  } else if (metric === 'xroi_pct' && op && thrS != null) {
    plain = `xROI % ${op} ${thrS} — Closing-Line-Value der Quote.`
    filterHint = op.startsWith('>')
      ? `Filter: xROI Min = ${thrS}`
      : `Filter: xROI Max = ${thrS}`
  } else if (metric === 'chance' && op && thrS != null) {
    plain = `Modell-Chance des Markts ${op} ${thrS}.`
    filterHint = 'Über Chance-/Wahrscheinlichkeitsfilter eingrenzen, falls vorhanden.'
  } else if (op && thrS != null) {
    plain = `${metric} ${op} ${thrS}.`
  }

  const delta = Number(row.roi_delta)
  const edgeNote = Number.isFinite(delta)
    ? delta >= 0
      ? `Historisch hätte diese Schwelle den ROI um ${delta.toFixed(1)} Punkte gegenüber der Baseline verbessert (Look-ahead, kein Zukunfts-Garantie).`
      : `Historisch hätte diese Schwelle den ROI um ${Math.abs(delta).toFixed(1)} Punkte gegenüber der Baseline verschlechtert.`
    : null

  return {
    metric,
    rule: row.rule,
    condition: row.condition,
    metricDef,
    rulePlain,
    plain,
    filterHint,
    edgeNote,
    n: row.n,
    win_rate: row.win_rate,
    roi_pct: row.roi_pct,
    roi_delta: row.roi_delta,
  }
}

/** Kennzahlen im Tab Analyse / Ergebnis-Leiste */
export const ANALYSE_METRIC_HELP = [
  {
    key: 'roi',
    label: 'ROI',
    text: 'Return on Investment der Strategie: Gesamtprofit ÷ Anzahl Wetten × 100 (1 Einheit Einsatz pro Wette).',
  },
  {
    key: 'xroi',
    label: 'xROI',
    text: 'Ø Closing-Line-Value: (Opening − Closing) / Closing × 100, gemittelt über Wetten mit Open+Close.',
  },
  {
    key: 'winrate',
    label: 'Winrate',
    text: 'Anteil gewonnener Wetten in Prozent (Profit > 0).',
  },
  {
    key: 'profit',
    label: 'Profit',
    text: 'Summe der Einheiten-Gewinne/Verluste aller Treffer (gewonnen: Quote−1, verloren: −1).',
  },
  {
    key: 'avg_xg_match',
    label: 'Ø xG Match H / A',
    text: 'Durchschnitt der tatsächlichen Match-xG (Home/Away) über die Strategie-Spiele — Look-ahead.',
  },
  {
    key: 'avg_goals',
    label: 'Ø Goals H / A',
    text: 'Durchschnittliche Tore Home/Away laut Endstand über die Strategie-Spiele (1× pro Match).',
  },
  {
    key: 'roi_close',
    label: 'ROI Closing',
    text: 'ROI, wenn jede Wette zum Closing-Kurs abgerechnet wird.',
  },
  {
    key: 'roi_open',
    label: 'ROI Opening',
    text: 'ROI, wenn jede Wette zum Opening-Kurs abgerechnet wird (nur wo Opening vorhanden).',
  },
]

export const ANALYSE_HELP_TITLE = Object.fromEntries(ANALYSE_METRIC_HELP.map((m) => [m.key, m.text]))

/** Kennzahlen im Tab Metriken (Glicko-Aggregate) */
export const METRIKEN_HELP = [
  {
    key: 'avg_rating_h',
    label: 'Ø Rating H',
    text: 'Durchschnittliches Glicko-Rating der Heimmannschaften in den gefilterten Spielen (pre-match).',
  },
  {
    key: 'avg_rating_a',
    label: 'Ø Rating A',
    text: 'Durchschnittliches Glicko-Rating der Auswärtsmannschaften.',
  },
  {
    key: 'avg_rating_diff',
    label: 'Ø Rating Diff',
    text: 'Mittelwert von (Home-Rating − Away-Rating). Positiv = im Schnitt Heimseite stärker.',
  },
  {
    key: 'avg_rd',
    label: 'Ø RD H / A',
    text: 'Rating Deviation: Unsicherheit des Glicko-Ratings. Höher = weniger Spiele / unsichereres Rating.',
  },
  {
    key: 'avg_vol',
    label: 'Ø Vol H / A',
    text: 'Glicko-Volatility: wie stark das Rating typischerweise schwankt.',
  },
  {
    key: 'avg_xg',
    label: 'Ø xG H / A',
    text: 'Mittlere Glicko-xG Home / Away (Vorhersage pre-match). Match-xG (erzielt) steht separat in den Spieltabellen.',
  },
  {
    key: 'avg_p_home',
    label: 'Ø P(Home)',
    text: 'Mittlere vom Modell geschätzte Heim-Sieg-Wahrscheinlichkeit.',
  },
  {
    key: 'avg_p_draw',
    label: 'Ø P(Draw)',
    text: 'Mittlere vom Modell geschätzte Unentschieden-Wahrscheinlichkeit.',
  },
  {
    key: 'avg_p_away',
    label: 'Ø P(Away)',
    text: 'Mittlere vom Modell geschätzte Auswärts-Sieg-Wahrscheinlichkeit.',
  },
]

export const METRIKEN_HELP_TITLE = Object.fromEntries(METRIKEN_HELP.map((m) => [m.key, m.text]))
