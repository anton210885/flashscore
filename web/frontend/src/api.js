const BASE = ''

async function get(path, { signal } = {}) {
  const res = await fetch(`${BASE}${path}`, signal ? { signal } : undefined)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText || 'Request failed')
  }
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = err.detail
    const detailStr = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      : detail
    throw new Error(detailStr || res.statusText || `HTTP ${res.status}`)
  }
  return res.json()
}

async function del(path) {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText || `HTTP ${res.status}`)
  }
  return res.json()
}

async function getBlob(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText || `HTTP ${res.status}`)
  }
  return res.blob()
}

export const api = {
  health: () => get('/api/health'),
  stats: (top = 12) => get(`/api/stats?top=${top}`),
  strategyAnalyze: (filters, limit = 200) =>
    post(`/api/strategy/analyze?limit=${limit}`, filters),
  strategyUpcoming: (filters, limit = 200) =>
    post(`/api/strategy/upcoming?limit=${limit}`, filters),
  strategyMetricRank: (filters, minN = 40, sortBy = 'roi') =>
    post(`/api/strategy/metric-rank?min_n=${minN}&sort_by=${encodeURIComponent(sortBy)}`, filters),
  strategyMetricBuckets: (filters, { metric = 'rating_diff', vmin, vmax, step, bins = 16 } = {}) => {
    const params = new URLSearchParams()
    params.set('metric', metric)
    params.set('bins', String(bins))
    if (vmin != null && vmin !== '') params.set('vmin', String(vmin))
    if (vmax != null && vmax !== '') params.set('vmax', String(vmax))
    if (step != null && step !== '') params.set('step', String(step))
    return post(`/api/strategy/metric-buckets?${params.toString()}`, filters)
  },
  strategyOptimizeParams: (filters, { minN = 25, maxParams = 2, topK = 15 } = {}) => {
    const params = new URLSearchParams()
    params.set('min_n', String(minN))
    params.set('max_params', String(maxParams))
    params.set('top_k', String(topK))
    return post(`/api/strategy/optimize-params?${params.toString()}`, filters)
  },
  leagues: (limit, signal) => get(`/api/leagues${limit ? `?limit=${limit}` : ''}`, { signal }),
  leaguesGroup: (group = 'meisterschaften', limit, signal) => {
    const params = new URLSearchParams()
    params.set('group', group)
    if (limit) params.set('limit', String(limit))
    return get(`/api/leagues?${params.toString()}`, { signal })
  },
  european: () => get('/api/european'),
  leagueDetail: (id, phase = 'all', year) => {
    const params = new URLSearchParams()
    params.set('phase', phase)
    if (year != null && year !== '') params.set('year', String(year))
    return get(`/api/leagues/${id}?${params.toString()}`)
  },
  leagueSync: (id, year) => {
    const params = new URLSearchParams()
    if (year != null && year !== '') params.set('year', String(year))
    const q = params.toString()
    return post(`/api/leagues/${id}/sync${q ? `?${q}` : ''}`, {})
  },
  sstatsCatalog: ({ live = true, save = false, gameId } = {}) => {
    const params = new URLSearchParams()
    params.set('live', String(!!live))
    params.set('save', String(!!save))
    if (gameId) params.set('game_id', String(gameId))
    return get(`/api/sstats/catalog?${params.toString()}`)
  },
  games: ({
    status = 'all',
    dateFrom,
    dateTo,
    q = '',
    limit = 100,
    offset = 0,
    pinnacle = false,
  } = {}) => {
    const params = new URLSearchParams()
    params.set('status', status)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    params.set('pinnacle', String(!!pinnacle))
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (q) params.set('q', q)
    return get(`/api/games?${params.toString()}`)
  },
  strategyPresets: () => get('/api/strategy/presets'),
  strategyPresetsSave: (presets) => post('/api/strategy/presets', { presets }),
  strategyPresetsUpcoming: (presets) => post('/api/strategy/presets/upcoming', { presets }),
  settingsAi: () => get('/api/settings/ai'),
  settingsAiSave: (body) => post('/api/settings/ai', body),
  settingsAiClear: () => del('/api/settings/ai/key'),
  settingsAiEnvExport: () => getBlob('/api/settings/ai/env-export'),
}
