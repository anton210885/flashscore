import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts'
import { api } from '../api'

function goalsBandClass(band) {
  if (band === 'u25') return 'band-u25'
  if (band === 'o25') return 'band-o25'
  if (band === 'o35') return 'band-o35'
  if (band === 'o45') return 'band-o45'
  return ''
}

export default function DetailPanel({ selection, metric }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [year, setYear] = useState(null)
  const [tab, setTab] = useState('spiele')

  useEffect(() => {
    if (!selection) {
      setData(null)
      setYear(null)
      setSyncMsg('')
      return
    }
    setYear(null)
    setTab('spiele')
    setSyncMsg('')
  }, [selection?.id, selection?.source_id, selection?.phase])

  async function loadDetail(y) {
    if (!selection) return
    setLoading(true)
    setError('')
    const id = selection.source_id || selection.id
    const phase = selection.phase || 'all'
    try {
      const d = await api.leagueDetail(id, phase, y)
      setData(d)
      if (y == null && d?.games_year != null) setYear(d.games_year)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!selection) {
      setData(null)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const id = selection.source_id || selection.id
        const phase = selection.phase || 'all'
        const d = await api.leagueDetail(id, phase, year)
        if (cancelled) return
        setData(d)
        if (year == null && d?.games_year != null) setYear(d.games_year)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selection, year])

  async function handleSync() {
    if (!selection || syncing) return
    const id = selection.source_id || selection.id
    const y = year ?? data?.games_year
    setSyncing(true)
    setSyncMsg('Lade fehlende Spiele von API…')
    try {
      const r = await api.leagueSync(id, y)
      const loaded = r.loaded ?? 0
      const found = r.total_found ?? 0
      setSyncMsg(
        loaded > 0
          ? `+${loaded} Spiele nachgeladen (${found} fertig in API)`
          : `Aktuell — keine neuen Spiele (${found} in API, bereits in DB)`,
      )
      await loadDetail(y)
    } catch (e) {
      setSyncMsg(`Fehler: ${e.message}`)
    } finally {
      setSyncing(false)
    }
  }

  if (!selection) {
    return (
      <aside className="detail">
        <p className="empty">Liga auswählen → alle Spiele (wie in Python)</p>
      </aside>
    )
  }

  const key = metric === '35' ? 'over35' : metric === '45' ? 'over45' : 'over25'
  const label = metric === '35' ? '3.5' : metric === '45' ? '4.5' : '2.5'
  const yearOptions =
    data?.available_years?.length > 0
      ? data.available_years
      : (data?.years || []).map((y) => Number(y)).filter((y) => Number.isFinite(y))

  return (
    <aside className="detail detail-wide">
      <h2>{selection.name?.trim()}</h2>
      <div className="sub">
        {selection.country} · ID {selection.source_id || selection.id}
        {selection.phase && selection.phase !== 'all' ? ` · ${selection.phase}` : ''}
      </div>

      <div className="detail-tabs">
        <button type="button" className={tab === 'spiele' ? 'active' : ''} onClick={() => setTab('spiele')}>
          Spiele {data?.games_n != null ? `(${data.games_n})` : ''}
        </button>
        <button type="button" className={tab === 'heute' ? 'active' : ''} onClick={() => setTab('heute')}>
          Heute ({data?.today_games?.length || 0})
        </button>
        <button type="button" className={tab === 'chart' ? 'active' : ''} onClick={() => setTab('chart')}>
          Chart
        </button>
      </div>

      {loading && <p className="loading">Lade Spiele…</p>}
      {error && <p className="error">{error}</p>}

      {data && tab === 'spiele' && (
        <>
          <div className="toolbar" style={{ marginBottom: '0.6rem' }}>
            <label>
              Saison{' '}
              <select
                value={year ?? data.games_year ?? ''}
                onChange={(e) => setYear(Number(e.target.value))}
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="nav-btn" disabled={syncing} onClick={handleSync}>
              {syncing ? 'Lädt…' : 'Spiele nachladen'}
            </button>
            <span className="sub" style={{ margin: 0 }}>
              beendet · neueste zuerst
            </span>
          </div>
          {syncMsg && <p className="sub sync-msg">{syncMsg}</p>}
          <div className="band-legend">
            <span className="band-u25">≤2.5</span>
            <span className="band-o25">Over 2.5</span>
            <span className="band-o35">Over 3.5</span>
            <span className="band-o45">Over 4.5</span>
          </div>
          {data.games?.length ? (
            <div className="league-games-wrap">
              <table className="league-games-table">
                <thead>
                  <tr>
                    <th>Datum</th>
                    <th>Heim</th>
                    <th>Gast</th>
                    <th>Erg.</th>
                    <th>S2.5</th>
                    <th>S3.5</th>
                    <th>S4.5</th>
                    <th>Runde</th>
                  </tr>
                </thead>
                <tbody>
                  {data.games.map((g) => (
                    <tr key={g.id} className={goalsBandClass(g.goals_band)}>
                      <td className="mono">{(g.date || '').slice(0, 10)}</td>
                      <td>{g.home}</td>
                      <td>{g.away}</td>
                      <td className="mono num">
                        {g.home_score ?? '–'}:{g.away_score ?? '–'}
                      </td>
                      <td className="num">{g.streak25 ?? 0}</td>
                      <td className="num">{g.streak35 ?? 0}</td>
                      <td className="num">{g.streak45 ?? 0}</td>
                      <td className="muted">{g.round || '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="sub">
              Keine beendeten Spiele für Saison {year ?? data.games_year}.{' '}
              <button type="button" className="linkish" onClick={handleSync}>
                Nachladen
              </button>
            </p>
          )}
        </>
      )}

      {data && tab === 'heute' && (
        <>
          {data.today_games?.length ? (
            <ul className="today-list">
              {data.today_games.map((g) => (
                <li key={g.id}>
                  <div>
                    {g.home} – {g.away}
                  </div>
                  <div className="meta">
                    {(g.date || '').slice(0, 16)} · {g.round || '–'} · {g.status}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sub">Keine offenen Spiele heute</p>
          )}
        </>
      )}

      {data && tab === 'chart' && (
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.series}>
              <CartesianGrid stroke="#2a3544" strokeDasharray="3 3" />
              <XAxis dataKey="year" stroke="#8b9bb0" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="#8b9bb0" fontSize={12} unit="%" />
              <Tooltip
                contentStyle={{
                  background: '#161d27',
                  border: '1px solid #2a3544',
                  borderRadius: 8,
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey={key}
                name={`Over ${label} %`}
                stroke="#3d9cfd"
                strokeWidth={2}
                dot={{ r: 4 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </aside>
  )
}
