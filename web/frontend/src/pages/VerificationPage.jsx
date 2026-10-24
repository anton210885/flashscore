import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ProfitChart from '../components/ProfitChart'
import SwisslosBadge from '../components/SwisslosBadge'

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

const MARKETS = ['Home', 'Draw', 'Away', 'Over 2.5', 'Under 2.5', 'Over 3.5', 'Under 3.5', 'Over 4.5', 'Under 4.5']

/** Kennzahlen einer Wetten-Liste; Serie = aktuelle Serie nach Datum (Verlust = Profit <= 0). */
function aggregate(rows) {
  const done = rows.filter((b) => b.settled_at != null)
  const won = done.filter((b) => b.won === 1).length
  const profit = done.reduce((sum, b) => sum + (Number(b.profit) || 0), 0)
  let losing = 0
  let winning = 0
  const losingRuns = []
  const winningRuns = []
  for (const b of [...done].sort((a, c) => String(a.date).localeCompare(String(c.date)))) {
    if (b.won === 1) {
      if (losing) losingRuns.push(losing)
      winning += 1
      losing = 0
    } else {
      if (winning) winningRuns.push(winning)
      losing += 1
      winning = 0
    }
  }
  if (losing) losingRuns.push(losing)
  if (winning) winningRuns.push(winning)
  return {
    bets: rows.length,
    open: rows.length - done.length,
    won,
    lost: done.length - won,
    win_rate: done.length ? (won / done.length) * 100 : null,
    profit,
    roi_pct: done.length ? (profit / done.length) * 100 : null,
    losing_streak: losing,
    winning_streak: winning,
    max_losing_streak: Math.max(0, ...losingRuns),
    max_winning_streak: Math.max(0, ...winningRuns),
    median_losing_streak: median(losingRuns),
    median_winning_streak: median(winningRuns),
    n_losing_streaks: losingRuns.length,
    n_winning_streaks: winningRuns.length,
  }
}

function median(values) {
  if (!values.length) return null
  const v = [...values].sort((a, b) => a - b)
  const mid = Math.floor(v.length / 2)
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2
}

/** „2 (5)“ = Median 2 aus 5 Serien */
const medianCell = (m, n) => (m == null ? '—' : `${num(m, 1)} (${n})`)

/** Offene Wette: Live-Stand aus dem Sync (alle 3 Min.) */
function liveText(b) {
  const l = b.live
  if (!l || l.phase === 'scheduled') return 'offen'
  const score = l.home != null ? ` · ${l.home}:${l.away}` : ''
  if (l.phase === 'finished') return `beendet${score} · wird abgerechnet`
  return `live ${l.minute != null ? `${l.minute}'` : l.label || ''}${score}`
}

function liveTone(b) {
  const l = b.live
  if (!l || l.winning == null || l.phase === 'scheduled') return 'muted'
  return l.winning ? 'pos' : 'neg'
}

const tone = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')

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
  const [status, setStatus] = useState('offen')
  const [market, setMarket] = useState('')
  const [onlySwisslos, setOnlySwisslos] = useState(() => {
    try {
      return localStorage.getItem('verification.onlySwisslos') === '1'
    } catch {
      return false
    }
  })
  const [auto, setAuto] = useState(true)
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

  // Live-Stände: der Sync aktualisiert alle 3 Min. — jede Minute neu laden reicht
  useEffect(() => {
    if (!auto) return undefined
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [auto, load])

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

  useEffect(() => {
    try {
      localStorage.setItem('verification.onlySwisslos', onlySwisslos ? '1' : '0')
    } catch {
      /* Speicher nicht verfügbar */
    }
  }, [onlySwisslos])

  // Markt- und Swisslos-Filter gelten für alles; Strategie/Status nur für die Wetten-Liste
  const marketBets = useMemo(
    () =>
      (data?.bets || []).filter(
        (b) => (!market || b.market === market) && (!onlySwisslos || b.swisslos),
      ),
    [data, market, onlySwisslos],
  )
  const summary = useMemo(() => {
    const backtest = Object.fromEntries((data?.summary || []).map((s) => [s.strategy_id, s]))
    const groups = {}
    for (const b of marketBets) (groups[b.strategy_id] ||= []).push(b)
    // Gespeicherte Strategien ohne Treffer trotzdem zeigen (0 Wetten)
    for (const s of data?.summary || []) if (!s.bets) groups[s.strategy_id] ||= []
    return Object.entries(groups)
      .map(([id, rows]) => ({
        strategy_id: id,
        strategy: rows.length ? rows[rows.length - 1].strategy_name : backtest[id]?.strategy,
        backtest_roi: backtest[id]?.backtest_roi,
        backtest_n: backtest[id]?.backtest_n,
        backtest: backtest[id]?.backtest || null,
        ...aggregate(rows),
      }))
      .sort((a, b) => String(a.strategy).localeCompare(String(b.strategy)))
  }, [data, marketBets])
  const total = useMemo(() => aggregate(marketBets), [marketBets])
  // Vergleich auf denselben Wetten: abgerechnet und mit Swisslos-Quote
  const slCompare = useMemo(() => {
    const rows = marketBets.filter((b) => b.profit_swisslos != null)
    const sum = (key) => rows.reduce((acc, b) => acc + (Number(b[key]) || 0), 0)
    const sl = sum('profit_swisslos')
    const pin = sum('profit')
    return { n: rows.length, sl, pin, slRoi: rows.length ? (sl / rows.length) * 100 : null }
  }, [marketBets])
  const bets = useMemo(() => {
    const rows = marketBets.filter(
      (b) => (!strategy || b.strategy_id === strategy) && (!status || b.status === status),
    )
    return [...rows].sort(SORTS[sortBy])
  }, [marketBets, strategy, status, sortBy])
  const selection = useMemo(() => aggregate(bets), [bets])

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
          <label className="chk">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            Live jede Minute
          </label>
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

      <div className="toolbar" style={{ marginTop: '0.5rem' }}>
        <label>
          Markt{' '}
          <select value={market} onChange={(e) => setMarket(e.target.value)}>
            <option value="">alle Märkte</option>
            {MARKETS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="chk" title="Nur Spiele aus Ligen, die Swisslos Sporttip anbietet">
          <input type="checkbox" checked={onlySwisslos} onChange={(e) => setOnlySwisslos(e.target.checked)} />
          nur Swisslos
        </label>
        <span>
          Gesamt: <strong>{total.bets}</strong> Wetten · {total.open} offen ·{' '}
          <span className="pos">{total.won} gewonnen</span> · <span className="neg">{total.lost} verloren</span>
          {' · '}Profit <strong className={tone(total.profit)}>{signed(total.profit)}</strong>
          {' · '}ROI{' '}
          <strong className={tone(total.roi_pct)}>
            {total.roi_pct == null ? '—' : `${signed(total.roi_pct, 1)}%`}
          </strong>
        </span>
        {slCompare.n ? (
          <span title="Nur abgerechnete Wetten, für die eine Swisslos-Quote vor Anpfiff gespeichert ist">
            Mit Swisslos-Quoten ({slCompare.n} W.): Profit{' '}
            <strong className={tone(slCompare.sl)}>{signed(slCompare.sl)}</strong>
            {' · '}ROI <strong className={tone(slCompare.slRoi)}>{signed(slCompare.slRoi, 1)}%</strong>
            {' · '}Pinnacle auf denselben: <strong className={tone(slCompare.pin)}>{signed(slCompare.pin)}</strong>
          </span>
        ) : null}
      </div>

      <h2 className="page-sub" style={{ marginTop: '0.5rem' }}>Profit-Verlauf</h2>
      <ProfitChart bets={marketBets} strategies={data?.summary || []} />

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
                <th rowSpan={2}>Strategie</th>
                <th colSpan={7} className="num" style={{ textAlign: 'center' }} title="Vergangenheit (Backtest der aktuellen Filter)">
                  Backtest
                </th>
                <th colSpan={11} className="num" style={{ textAlign: 'center' }} title="Echte Vorwärts-Wetten ab Start der Verifikation">
                  Verifikation
                </th>
              </tr>
              <tr>
                <th className="num">Wetten</th>
                <th className="num">Profit</th>
                <th className="num">ROI %</th>
                <th className="num" title="Längste Niederlagenserie">Max −</th>
                <th className="num" title="Längste Siegesserie">Max +</th>
                <th className="num" title="Typische Niederlagenserie: Median (Anzahl Serien)">Median −</th>
                <th className="num" title="Typische Siegesserie: Median (Anzahl Serien)">Median +</th>
                <th className="num">Wetten</th>
                <th className="num">Offen</th>
                <th className="num">Gew.</th>
                <th className="num">Verl.</th>
                <th className="num">Treffer</th>
                <th className="num">Profit</th>
                <th className="num">ROI %</th>
                <th className="num" title="Längste Niederlagenserie">Max −</th>
                <th className="num" title="Längste Siegesserie">Max +</th>
                <th className="num" title="Typische Niederlagenserie: Median (Anzahl Serien)">Median −</th>
                <th className="num" title="Aktuelle Serie: − verloren / + gewonnen in Folge">Aktuell</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((s) => {
                const bt = s.backtest || {}
                return (
                  <tr
                    key={s.strategy_id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setStrategy(strategy === s.strategy_id ? '' : s.strategy_id)}
                    title="Klick → nur diese Strategie anzeigen"
                  >
                    <td>{strategy === s.strategy_id ? <strong>{s.strategy}</strong> : s.strategy}</td>
                    <td className="num">{num(bt.n_bets ?? s.backtest_n, 0)}</td>
                    <td className={`num ${tone(bt.profit)}`}>{signed(bt.profit)}</td>
                    <td className={`num ${tone(bt.roi_pct ?? s.backtest_roi)}`}>{signed(bt.roi_pct ?? s.backtest_roi, 1)}</td>
                    <td className="num neg">{num(bt.max_losing_streak, 0)}</td>
                    <td className="num pos">{num(bt.max_winning_streak, 0)}</td>
                    <td className="num">{medianCell(bt.median_losing_streak, bt.n_losing_streaks)}</td>
                    <td className="num">{medianCell(bt.median_winning_streak, bt.n_winning_streaks)}</td>
                    <td className="num">{s.bets}</td>
                    <td className="num">{s.open}</td>
                    <td className="num pos">{s.won}</td>
                    <td className="num neg">{s.lost}</td>
                    <td className="num">{s.win_rate == null ? '—' : `${num(s.win_rate, 1)}%`}</td>
                    <td className={`num ${tone(s.profit)}`}>{signed(s.profit)}</td>
                    <td className={`num ${tone(s.roi_pct)}`}>{s.roi_pct == null ? '—' : signed(s.roi_pct, 1)}</td>
                    <td className="num neg">{s.max_losing_streak}</td>
                    <td className="num pos">{s.max_winning_streak}</td>
                    <td className="num">{medianCell(s.median_losing_streak, s.n_losing_streaks)}</td>
                    <td className={`num ${s.losing_streak > 0 ? 'neg' : s.winning_streak > 0 ? 'pos' : ''}`}>
                      {s.losing_streak > 0 ? `−${s.losing_streak}` : s.winning_streak > 0 ? `+${s.winning_streak}` : '0'}
                    </td>
                  </tr>
                )
              })}
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
        <span>
          Auswahl: <strong>{selection.bets}</strong> Wetten · {selection.won}/{selection.won + selection.lost} gewonnen
          {' · '}Profit <strong className={tone(selection.profit)}>{signed(selection.profit)}</strong>
          {' · '}ROI{' '}
          <strong className={tone(selection.roi_pct)}>
            {selection.roi_pct == null ? '—' : `${signed(selection.roi_pct, 1)}%`}
          </strong>
        </span>
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
              <th className="num" title="Letzte Swisslos-Quote vor Anpfiff (stündlich abgeholt)">Swisslos</th>
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
                <td>
                  {b.league || '—'}
                  {b.swisslos ? <SwisslosBadge /> : null}
                </td>
                <td>{b.home}</td>
                <td>{b.away}</td>
                <td>{b.market}</td>
                <td className="num">{num(b.odds_used)}</td>
                <td
                  className={`num ${b.odds_swisslos && b.odds_used && b.odds_swisslos < b.odds_used ? 'muted' : ''}`}
                  title={b.odds_swisslos && b.odds_used ? `${signed((b.odds_swisslos / b.odds_used - 1) * 100, 1)}% gegenüber Pinnacle` : undefined}
                >
                  {num(b.odds_swisslos)}
                </td>
                <td>{b.strategy_name}</td>
                <td className="num">
                  {b.home_score == null ? '—' : `${b.home_score}:${b.away_score}`}
                </td>
                <td className={b.status === 'gewonnen' ? 'pos' : b.status === 'verloren' ? 'neg' : liveTone(b)}>
                  {b.status === 'offen' ? liveText(b) : b.status}
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
