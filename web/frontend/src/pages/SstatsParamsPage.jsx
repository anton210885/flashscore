import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

const WHEN_LABEL = {
  pre: 'vor Spiel',
  post: 'nach/im Spiel',
  live: 'live',
  both: 'immer',
}

export default function SstatsParamsPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [group, setGroup] = useState('all')
  const [q, setQ] = useState('')
  const [live, setLive] = useState(true)

  function load(withLive = live) {
    setLoading(true)
    setError('')
    api
      .sstatsCatalog({ live: withLive, save: true })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rows = useMemo(() => {
    let fields = data?.fields || []
    if (group !== 'all') fields = fields.filter((f) => f.group === group)
    const query = q.trim().toLowerCase()
    if (query) {
      fields = fields.filter(
        (f) =>
          String(f.key || '').toLowerCase().includes(query) ||
          String(f.label || '').toLowerCase().includes(query) ||
          String(f.desc || '').toLowerCase().includes(query),
      )
    }
    return fields
  }, [data, group, q])

  if (loading) return <div className="loading">Lade SStats-Parameter…</div>
  if (error) return <div className="error">Fehler: {error}</div>

  const sample = data?.sample || {}

  return (
    <div className="main" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <div className="toolbar" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>SStats Parameter</h1>
          <div className="sub" style={{ marginTop: 4 }}>
            Basis: {data?.base_url} · {data?.field_count} Felder · {data?.generated_at}
          </div>
        </div>
        <div className="toolbar" style={{ marginBottom: 0 }}>
          <label>
            <input
              type="checkbox"
              checked={live}
              onChange={(e) => {
                setLive(e.target.checked)
                load(e.target.checked)
              }}
            />
            Live-Sample
          </label>
          <a className="nav-btn" href="/api/sstats/catalog.csv?live=true">
            CSV Download
          </a>
          <a className="nav-btn" href="/api/sstats/catalog.json?live=true">
            JSON Download
          </a>
          <button type="button" className="nav-btn" onClick={() => load(live)}>
            Neu laden
          </button>
        </div>
      </div>

      {sample.match && (
        <div className="sample-card">
          <strong>Sample:</strong> {sample.match}
          <span className="meta">
            {' '}
            · ID {sample.game_id} · {sample.league} · {(sample.date || '').slice(0, 16)}
          </span>
          {sample.glicko && Object.keys(sample.glicko).length > 0 && (
            <div className="glicko-strip">
              Rating {fmt(sample.glicko.homeRating)} – {fmt(sample.glicko.awayRating)}
              {' · '}
              Modell-xG {fmt(sample.glicko.homeXg)} – {fmt(sample.glicko.awayXg)}
              {' · '}
              P(Win) {pct(sample.glicko.homeWinProbability)} – {pct(sample.glicko.awayWinProbability)}
            </div>
          )}
        </div>
      )}

      <div className="endpoints">
        {(data?.endpoints || []).map((ep) => (
          <div key={ep.path} className="ep-chip">
            <code>{ep.method}</code> {ep.path}
            <span>{ep.desc}</span>
          </div>
        ))}
      </div>

      <div className="toolbar">
        <div className="metric-tabs">
          <button
            type="button"
            className={group === 'all' ? 'active' : ''}
            onClick={() => setGroup('all')}
          >
            Alle
          </button>
          {(data?.groups || []).map((g) => (
            <button
              key={g.id}
              type="button"
              className={group === g.id ? 'active' : ''}
              onClick={() => setGroup(g.id)}
            >
              {g.title} ({g.count})
            </button>
          ))}
        </div>
        <input
          placeholder="Suche Key / Label…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>{rows.length} Zeilen</span>
      </div>

      <div className="table-wrap" style={{ maxHeight: 'calc(100vh - 320px)' }}>
        <table>
          <thead>
            <tr>
              <th>Gruppe</th>
              <th>Key</th>
              <th>Label</th>
              <th>Wann</th>
              <th>Beschreibung</th>
              <th className="num">Sample</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={`${f.group}-${f.key}`}>
                <td>
                  <span className={`badge group-${f.group}`}>{f.group}</span>
                  {f.subgroup ? <span className="sub-tag"> {f.subgroup}</span> : null}
                </td>
                <td>
                  <code>{f.key}</code>
                </td>
                <td>{f.label}</td>
                <td>{WHEN_LABEL[f.when] || f.when}</td>
                <td style={{ whiteSpace: 'normal', maxWidth: 360 }}>{f.desc}</td>
                <td className="num">{fmtSample(f.sample)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data?.saved && (
        <p className="sub" style={{ marginTop: 12 }}>
          Gespeichert: {data.saved.json} · {data.saved.csv}
        </p>
      )}
    </div>
  )
}

function fmt(v) {
  if (v == null || Number.isNaN(Number(v))) return '–'
  return Number(v).toFixed(2)
}

function pct(v) {
  if (v == null) return '–'
  return `${(Number(v) * 100).toFixed(1)}%`
}

function fmtSample(v) {
  if (v == null || v === '') return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3)
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
