import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'

function todayOffset(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  // lokale Kalenderdaten (nicht UTC — sonst „verschwindet“ heute nachts)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function fmtNum(v, digits = 2) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function fmtOdd(v) {
  if (v == null || v === '') return '—'
  return Number(v).toFixed(2)
}

function statusClass(bucket) {
  if (bucket === 'live') return 'st-live'
  if (bucket === 'finished') return 'st-fin'
  if (bucket === 'not_started') return 'st-ns'
  return 'st-other'
}

function OddCell({ value, win }) {
  const missing = value == null || value === ''
  return (
    <td className={`num odd-cell ${win ? 'odd-win' : ''} ${missing ? 'odd-missing' : ''}`}>
      {fmtOdd(value)}
    </td>
  )
}

export default function GamesPage() {
  const [status, setStatus] = useState('not_started')
  const [dateFrom, setDateFrom] = useState(todayOffset(0))
  const [dateTo, setDateTo] = useState(todayOffset(1))
  const [q, setQ] = useState('')
  const [pinnacle, setPinnacle] = useState(false)
  const [onlyWithOdds, setOnlyWithOdds] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    api
      .games({
        status,
        dateFrom,
        dateTo,
        q,
        limit: 250,
        pinnacle,
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [status, dateFrom, dateTo, q, pinnacle])

  useEffect(() => {
    load()
  }, [load])

  const games = useMemo(() => {
    let rows = data?.games || []
    if (onlyWithOdds) {
      rows = rows.filter(
        (g) =>
          g.has_odds ||
          g.odd_home != null ||
          g.odd_draw != null ||
          g.odd_away != null ||
          g.odd_over_25 != null ||
          g.odd_under_25 != null,
      )
    }
    return rows
  }, [data, onlyWithOdds])

  const counts = data?.counts || {}

  return (
    <div className="main" style={{ maxWidth: 1600, margin: '0 auto' }}>
      <div className="toolbar" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem' }}>Spiele</h1>
          <div className="sub" style={{ marginTop: 4 }}>
            Bei Finished: treffende Quote <span className="odd-win-legend">grün</span> markiert
            {' · '}
            Pinnacle ID {data?.pinnacle_bookmaker_id ?? 4}
          </div>
        </div>
        <div className="toolbar" style={{ marginBottom: 0, flexWrap: 'wrap' }}>
          <label>
            von
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </label>
          <label>
            bis
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </label>
          <input
            placeholder="Team / Liga…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ minWidth: 160 }}
          />
          <label>
            <input
              type="checkbox"
              checked={onlyWithOdds}
              onChange={(e) => setOnlyWithOdds(e.target.checked)}
            />
            nur mit Quoten
          </label>
          <label>
            <input
              type="checkbox"
              checked={pinnacle}
              onChange={(e) => setPinnacle(e.target.checked)}
            />
            Pinnacle live
          </label>
          <button type="button" className="nav-btn" onClick={load} disabled={loading}>
            {loading ? 'Lädt…' : 'Aktualisieren'}
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="metric-tabs">
          {[
            ['not_started', 'Nicht gestartet', counts.not_started],
            ['live', 'Live', counts.live],
            ['finished', 'Finished', counts.finished],
            ['all', 'Alle', counts.all],
          ].map(([key, label, n]) => (
            <button
              key={key}
              type="button"
              className={status === key ? 'active' : ''}
              onClick={() => {
                setStatus(key)
                // Finished: oft Quoten in DB → Filter sinnvoll; offene Spiele: API-Quoten nicht immer da
                if (key === 'finished') setOnlyWithOdds(true)
                else setOnlyWithOdds(false)
              }}
            >
              {label}
              {n != null ? ` (${n})` : ''}
            </button>
          ))}
        </div>
        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
          {data ? `${games.length} angezeigt` : ''}
          {data?.with_odds != null ? ` · ${data.with_odds}/${data.total} mit Quoten` : ''}
          {onlyWithOdds ? ' · Filter: nur mit Quoten' : ''}
          {' · '}
          Quelle: Today-API / DB{pinnacle ? ' / Pinnacle' : ''}
        </span>
      </div>

      {error && <div className="error">Fehler: {error}</div>}
      {loading && !data && <div className="loading">Lade Spiele…</div>}

      <div className="table-wrap" style={{ maxHeight: 'calc(100vh - 220px)' }}>
        <table>
          <thead>
            <tr>
              <th>Kickoff</th>
              <th>Status</th>
              <th>Liga</th>
              <th>Home</th>
              <th>Away</th>
              <th className="num">Stand</th>
              <th className="num">Rating H</th>
              <th className="num">Rating A</th>
              <th className="num">RD H</th>
              <th className="num">RD A</th>
              <th className="num">Vol H</th>
              <th className="num">Vol A</th>
              <th className="num">xG-G H</th>
              <th className="num">xG-G A</th>
              <th className="num">P(H)</th>
              <th className="num">P(D)</th>
              <th className="num">P(A)</th>
              <th className="num">1</th>
              <th className="num">X</th>
              <th className="num">2</th>
              <th className="num">O2.5</th>
              <th className="num">U2.5</th>
              <th>Bookie</th>
            </tr>
          </thead>
          <tbody>
            {games.map((g) => {
              const finished = g.status_bucket === 'finished'
              const w1 = finished ? g.winner_1x2 : null
              const wou = finished ? g.winner_ou25 : null
              return (
                <tr
                  key={`${g.source}-${g.id}`}
                  className={`${g.status_bucket === 'live' ? 'today' : ''} ${g.has_odds ? 'has-odds' : ''}`}
                >
                  <td style={{ fontFamily: 'var(--mono)', fontSize: '0.78rem' }}>
                    {(g.date || '').replace('T', ' ').slice(0, 16)}
                  </td>
                  <td>
                    <span className={`badge ${statusClass(g.status_bucket)}`}>
                      {g.status_name || g.status_bucket}
                    </span>
                    {g.has_odds && (
                      <span className="badge odds-yes" title="Quoten vorhanden">
                        Q
                      </span>
                    )}
                  </td>
                  <td>
                    <div>{g.league || '—'}</div>
                    <div className="sub" style={{ fontSize: '0.72rem' }}>
                      {g.country || ''}
                    </div>
                  </td>
                  <td>{g.home}</td>
                  <td>{g.away}</td>
                  <td className="num">{g.score || '—'}</td>
                  <td className="num">{fmtNum(g.rating_h, 0)}</td>
                  <td className="num">{fmtNum(g.rating_a, 0)}</td>
                  <td className="num">{fmtNum(g.rd_h, 1)}</td>
                  <td className="num">{fmtNum(g.rd_a, 1)}</td>
                  <td className="num">{fmtNum(g.vol_h, 3)}</td>
                  <td className="num">{fmtNum(g.vol_a, 3)}</td>
                  <td className="num">{fmtNum(g.xg_glicko_h)}</td>
                  <td className="num">{fmtNum(g.xg_glicko_a)}</td>
                  <td className="num">
                    {g.p_home == null ? '—' : `${(Number(g.p_home) * 100).toFixed(0)}%`}
                  </td>
                  <td className="num">
                    {g.p_draw == null ? '—' : `${(Number(g.p_draw) * 100).toFixed(0)}%`}
                  </td>
                  <td className="num">
                    {g.p_away == null ? '—' : `${(Number(g.p_away) * 100).toFixed(0)}%`}
                  </td>
                  <OddCell value={g.odd_home} win={w1 === 'home'} />
                  <OddCell value={g.odd_draw} win={w1 === 'draw'} />
                  <OddCell value={g.odd_away} win={w1 === 'away'} />
                  <OddCell value={g.odd_over_25} win={wou === 'over'} />
                  <OddCell value={g.odd_under_25} win={wou === 'under'} />
                  <td style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    {g.bookmaker || (g.odds_source === 'db' ? 'DB' : '—')}
                  </td>
                </tr>
              )
            })}
            {!loading && games.length === 0 && (
              <tr>
                <td colSpan={22} style={{ textAlign: 'center', color: 'var(--muted)', padding: '2rem' }}>
                  Keine Spiele für Filter / Zeitraum
                  {onlyWithOdds ? ' (oder keine Quoten in DB)' : ''}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
