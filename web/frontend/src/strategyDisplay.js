/** Client-Fallbacks für Outcomes / Equity (wenn Backend-Metriken fehlen). */

export function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

/** Dezimalquote: nur Werte > 1 gültig (nie negativ / ≤1). */
export function oddsNum(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 1) return '—'
  return n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function validOdds(v) {
  const n = Number(v)
  return Number.isFinite(n) && n > 1 ? n : null
}

export function pctCell(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  const p = n > 1 ? n : n * 100
  return `${p.toFixed(0)}%`
}

export function outcomesFromResults(results) {
  const by = new Map()
  for (const r of results || []) {
    if (r.game_id == null || by.has(r.game_id)) continue
    const hs = Number(r.home_score)
    const aws = Number(r.away_score)
    if (!Number.isFinite(hs) || !Number.isFinite(aws)) continue
    by.set(r.game_id, { hs, aws })
  }
  let home = 0
  let draw = 0
  let away = 0
  let over25 = 0
  let under25 = 0
  for (const { hs, aws } of by.values()) {
    if (hs > aws) home += 1
    else if (hs < aws) away += 1
    else draw += 1
    if (hs + aws > 2.5) over25 += 1
    else under25 += 1
  }
  const n = by.size
  const pct = (c) => (n ? (c / n) * 100 : 0)
  return {
    games_n: n,
    home_n: home,
    draw_n: draw,
    away_n: away,
    over25_n: over25,
    under25_n: under25,
    home_pct: pct(home),
    draw_pct: pct(draw),
    away_pct: pct(away),
    over25_pct: pct(over25),
    under25_pct: pct(under25),
  }
}

function settle(market, hs, aws, odds) {
  const o = validOdds(odds)
  if (o == null) return null
  if (!Number.isFinite(hs) || !Number.isFinite(aws)) return null
  let won = false
  if (market === 'Home') won = hs > aws
  else if (market === 'Draw') won = hs === aws
  else if (market === 'Away') won = hs < aws
  else if (market === 'Over 2.5') won = hs + aws > 2.5
  else if (market === 'Under 2.5') won = hs + aws < 2.5
  else if (market === 'Over 3.5') won = hs + aws > 3.5
  else if (market === 'Under 3.5') won = hs + aws < 3.5
  else if (market === 'Over 4.5') won = hs + aws > 4.5
  else if (market === 'Under 4.5') won = hs + aws < 4.5
  else return null
  return won ? o - 1 : -1
}

export function equityFromResults(results) {
  const ordered = [...(results || [])].sort((a, b) =>
    String(a.date || '').localeCompare(String(b.date || '')),
  )
  let eqC = 0
  let eqO = 0
  let nC = 0
  let nO = 0
  const series = []
  ordered.forEach((r, i) => {
    const hs = Number(r.home_score)
    const aws = Number(r.away_score)
    const pc = settle(r.market, hs, aws, r.odds_closing ?? r.odds)
    const po = settle(r.market, hs, aws, r.odds_opening)
    if (pc != null) {
      eqC += pc
      nC += 1
    }
    if (po != null) {
      eqO += po
      nO += 1
    }
    series.push({
      i: i + 1,
      date: String(r.date || '').slice(0, 10),
      equity_close: Math.round(eqC * 10000) / 10000,
      equity_open: Math.round(eqO * 10000) / 10000,
    })
  })
  return {
    series,
    n_close: nC,
    n_open: nO,
    total_profit_close: eqC,
    total_profit_open: eqO,
    roi_close_pct: nC ? (eqC / nC) * 100 : 0,
    roi_open_pct: nO ? (eqO / nO) * 100 : 0,
  }
}

export function resolveOutcomes(metrics, results) {
  const oc = metrics?.outcomes
  if (oc && (oc.games_n > 0 || oc.home_n != null)) return oc
  return outcomesFromResults(results)
}

export function resolveEquity(metrics, results) {
  const eq = metrics?.equity
  if (eq?.series?.length) return eq
  return equityFromResults(results)
}

function avg(arr) {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null
}

export function glickoFromResults(results) {
  const by = new Map()
  for (const r of results || []) {
    if (r.game_id == null || by.has(r.game_id)) continue
    by.set(r.game_id, r)
  }
  const rows = [...by.values()]
  const col = (k) =>
    rows.map((r) => Number(r[k])).filter((n) => Number.isFinite(n))
  const diffs = []
  for (const r of rows) {
    const a = Number(r.rating_h)
    const b = Number(r.rating_a)
    if (Number.isFinite(a) && Number.isFinite(b)) diffs.push(a - b)
  }
  const rh = col('rating_h')
  const xgMatchH = []
  const xgMatchA = []
  const goalsH = []
  const goalsA = []
  const goalsSum = []
  for (const r of rows) {
    const mh = Number(r.xg_h ?? r.xg_match_h)
    const ma = Number(r.xg_a ?? r.xg_match_a)
    if (Number.isFinite(mh)) xgMatchH.push(mh)
    if (Number.isFinite(ma)) xgMatchA.push(ma)
    const gh = Number(r.home_score)
    const ga = Number(r.away_score)
    if (Number.isFinite(gh)) goalsH.push(gh)
    if (Number.isFinite(ga)) goalsA.push(ga)
    if (Number.isFinite(gh) && Number.isFinite(ga)) goalsSum.push(gh + ga)
  }
  const avgXgMatchH = avg(xgMatchH)
  const avgXgMatchA = avg(xgMatchA)
  return {
    games_n: rows.length,
    avg_rating_h: avg(rh),
    avg_rating_a: avg(col('rating_a')),
    avg_rating_diff: avg(diffs),
    avg_rd_h: avg(col('rd_h')),
    avg_rd_a: avg(col('rd_a')),
    avg_vol_h: avg(col('vol_h')),
    avg_vol_a: avg(col('vol_a')),
    avg_p_home: avg(col('p_home')),
    avg_p_draw: avg(col('p_draw')),
    avg_p_away: avg(col('p_away')),
    avg_xg_h: avg(col('xg_glicko_h')),
    avg_xg_a: avg(col('xg_glicko_a')),
    avg_xg_match_h: avgXgMatchH,
    avg_xg_match_a: avgXgMatchA,
    avg_xg_match_sum:
      avgXgMatchH != null && avgXgMatchA != null ? avgXgMatchH + avgXgMatchA : null,
    avg_goals_h: avg(goalsH),
    avg_goals_a: avg(goalsA),
    avg_goals_sum: avg(goalsSum),
    n_rating: rh.length,
    n_xg: col('xg_glicko_h').length,
    n_xg_match: xgMatchH.length,
    n_goals: goalsSum.length,
    n_p: col('p_home').length,
  }
}

export function resolveGlicko(metrics, results) {
  const g = metrics?.glicko
  if (g && (g.games_n > 0 || g.avg_rating_h != null)) return g
  return glickoFromResults(results)
}
