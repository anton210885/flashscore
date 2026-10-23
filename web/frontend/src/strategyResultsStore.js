/** Letzte Strategie-Analyse teilen (Strategie → Vergangene Spiele). */

const KEY = 'flashscore_strategy_last'

export function saveStrategyResults({ data, upcoming, filters, rankReport }) {
  // Schlank speichern: volle Results-Tabelle weglassen, Metriken + Equity behalten
  const slimData = data
    ? {
        ...data,
        results: (data.results || []).slice(0, 200),
        metrics: data.metrics || {},
      }
    : null
  const slimRank = rankReport?.ok
    ? {
        ok: true,
        n: rankReport.n,
        baseline: rankReport.baseline,
        min_n: rankReport.min_n,
        ranked: (rankReport.ranked || []).slice(0, 50),
      }
    : rankReport || null
  const payload = {
    data: slimData,
    upcoming: upcoming
      ? { ...upcoming, matches: (upcoming.matches || []).slice(0, 200) }
      : null,
    rankReport: slimRank,
    filters: filters || null,
    savedAt: Date.now(),
  }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(payload))
  } catch {
    // Quota: nur Metriken behalten
    try {
      sessionStorage.setItem(
        KEY,
        JSON.stringify({
          data: slimData
            ? {
                ok: slimData.ok,
                n: slimData.n,
                metrics: slimData.metrics,
                percentile: slimData.percentile,
                results: [],
              }
            : null,
          upcoming: upcoming
            ? { ok: upcoming.ok, n: upcoming.n, matches: [], avg_xroi_pct: upcoming.avg_xroi_pct }
            : null,
          filters: null,
          savedAt: Date.now(),
        }),
      )
    } catch {
      /* ignore */
    }
  }
  window.dispatchEvent(new CustomEvent('strategy-results', { detail: payload }))
  return payload
}

export function loadStrategyResults() {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}
