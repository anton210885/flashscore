import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'

function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

function signed(v, digits = 2) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${num(n, digits)}`
}

const fmtDate = (d) => String(d || '').slice(0, 16).replace('T', ' ')

const SORTS = {
  date_asc: (a, b) => String(a.date).localeCompare(String(b.date)),
  date_desc: (a, b) => String(b.date).localeCompare(String(a.date)),
  strategy: (a, b) =>
    String(a.strategy_name).localeCompare(String(b.strategy_name)) ||
    String(a.date).localeCompare(String(b.date)),
}

export default function VerificationPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [msg, setMsg] = useState('')
  const [strategy, setStrategy] = useState('')
  const [status, setStatus] = useState('')
  const [sortBy, setSortBy] = useState('date_asc')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    api
      .verification()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const scan = () => {
    setScanning(true)
    setError('')
    setMsg('Prüfe alle Strategien auf bevorstehende Spiele… (kann einige Minuten dauern)')
    api
      .verificationScan()
      .then((r) => {
        setMsg(
          `Fertig: ${r.new} neu, ${r.updated} aktualisiert, ${r.no_longer_matching} passen nicht mehr, ` +
            `${r.settled} abgerechnet${r.errors?.length ? ` · Fehler: ${r.errors.join('; ')}` : ''}`,
        )
        load()
      })
      .catch((e) => {
        setMsg('')
        setError(e.message)
      })
      .finally(() => setScanning(false))
  }

  const summary = data?.summary || []
  const bets = useMemo(() => {
    const rows = (data?.bets || []).filter(
      (b) => (!strategy || b.strategy_id === strategy) && (!status || b.status === status),
    )
    return [...rows].sort(SORTS[sortBy])
  }, [data, strategy, status, sortBy])

  return (
    <div className="main strategy-page verification-page">
      <div className="toolbar">
        <div>
          <h1 className="page-title">Verifikation</h1>
          <p className="page-sub">
            Treffer deiner gespeicherten Strategien werden vor dem Spiel festgehalten (stündlich, automatisch)
            und nach dem Spiel abgerechnet — der echte Test ohne Rückblick.
          </p>
        </div>
        <div className="toolbar-actions">
          <button type="button" className="nav-btn" onClick={load} disabled={loading || scanning}>
            {loading ? 'Lädt…' : 'Aktualisieren'}
          </button>
          <button type="button" className="nav-btn" onClick={scan} disabled={scanning}>
            {scanning ? 'Prüfe…' : 'Jetzt prüfen'}
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {msg ? <p className="muted">{msg}</p> : null}

      <h2 className="page-sub" style={{ marginTop: '0.5rem' }}>Pro Strategie</h2>
      {!summary.length && !loading ? (
        <p className="muted">
          Noch keine Einträge. Die Pipeline prüft stündlich — oder „Jetzt prüfen“ klicken.
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Strategie</th>
                <th className="num">Wetten</th>
                <th className="num">Offen</th>
                <th className="num">Gewonnen</th>
                <th className="num">Verloren</th>
                <th className="num">Trefferquote</th>
                <th className="num">Profit</th>
                <th className="num">ROI %</th>
                <th className="num" title="ROI im Backtest (Vergangenheit) zum Vergleich">Backtest ROI %</th>
                <th className="num" title="Verlorene Wetten in Folge (aktuell)">Serie −</th>
                <th className="num" title="Gewonnene Wetten in Folge (aktuell)">Serie +</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((s) => (
                <tr
                  key={s.strategy_id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setStrategy(strategy === s.strategy_id ? '' : s.strategy_id)}
                  title="Klick → nur diese Strategie anzeigen"
                >
                  <td>{strategy === s.strategy_id ? <strong>{s.strategy}</strong> : s.strategy}</td>
                  <td className="num">{s.bets}</td>
                  <td className="num">{s.open}</td>
                  <td className="num pos">{s.won}</td>
                  <td className="num neg">{s.lost}</td>
                  <td className="num">{s.win_rate == null ? '—' : `${num(s.win_rate, 1)}%`}</td>
                  <td className={`num ${s.profit > 0 ? 'pos' : s.profit < 0 ? 'neg' : ''}`}>{signed(s.profit)}</td>
                  <td className={`num ${s.roi_pct > 0 ? 'pos' : s.roi_pct < 0 ? 'neg' : ''}`}>
                    {s.roi_pct == null ? '—' : signed(s.roi_pct, 1)}
                  </td>
                  <td className="num">
                    {s.backtest_roi == null ? '—' : `${signed(s.backtest_roi, 1)} (n=${s.backtest_n})`}
                  </td>
                  <td className={`num ${s.losing_streak > 0 ? 'neg' : ''}`}>{s.losing_streak}</td>
                  <td className={`num ${s.winning_streak > 0 ? 'pos' : ''}`}>{s.winning_streak}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="toolbar" style={{ marginTop: '1rem' }}>
        <label>
          Strategie{' '}
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="">alle</option>
            {summary.map((s) => (
              <option key={s.strategy_id} value={s.strategy_id}>
                {s.strategy}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status{' '}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">alle</option>
            <option value="offen">offen</option>
            <option value="gewonnen">gewonnen</option>
            <option value="verloren">verloren</option>
          </select>
        </label>
        <label>
          Sortierung{' '}
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="date_asc">Datum ↑ (älteste zuerst)</option>
            <option value="date_desc">Datum ↓ (neueste zuerst)</option>
            <option value="strategy">Strategie, dann Datum</option>
          </select>
        </label>
        <span className="muted">{bets.length} Wetten</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Land</th>
              <th>Liga</th>
              <th>Heim</th>
              <th>Gast</th>
              <th>Markt</th>
              <th className="num" title="Quote, mit der abgerechnet wird (Opening/Closing laut Strategie)">Quote</th>
              <th>Strategie</th>
              <th className="num">Ergebnis</th>
              <th>Status</th>
              <th className="num">Profit</th>
            </tr>
          </thead>
          <tbody>
            {bets.map((b) => (
              <tr key={b.id}>
                <td>{fmtDate(b.date)}</td>
                <td>{b.country || '—'}</td>
                <td>{b.league || '—'}</td>
                <td>{b.home}</td>
                <td>{b.away}</td>
                <td>{b.market}</td>
                <td className="num">{num(b.odds_used)}</td>
                <td>{b.strategy_name}</td>
                <td className="num">
                  {b.home_score == null ? '—' : `${b.home_score}:${b.away_score}`}
                </td>
                <td className={b.status === 'gewonnen' ? 'pos' : b.status === 'verloren' ? 'neg' : 'muted'}>
                  {b.status}
                  {b.status === 'offen' && !b.still_matches ? (
                    <span className="muted" title="Spiel passt nicht mehr zu den Filtern (z. B. Quote verschoben) — bleibt trotzdem drin">
                      {' '}· passt nicht mehr
                    </span>
                  ) : null}
                </td>
                <td className={`num ${b.profit > 0 ? 'pos' : b.profit < 0 ? 'neg' : ''}`}>
                  {b.profit == null ? '—' : signed(b.profit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
