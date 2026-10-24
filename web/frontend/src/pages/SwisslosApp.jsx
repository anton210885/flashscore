import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import {
  advice,
  fmtKickoff,
  notStarted,
  num,
  pinnacleOdds,
  readSetting,
  signed,
  stats,
  writeSetting,
} from '../betAdvice'

/** Schlanke Handy-App nur für Swisslos: Tipps vor Anpfiff, gesetzte Wetten, Bilanz.
 * Gesetzt wird in der offiziellen Swisslos-App; hier nur markieren. Läuft unter /sl. */

const tone = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')

function liveText(b) {
  const l = b.live
  if (!l || l.phase === 'scheduled') return fmtKickoff(b.date).slice(11)
  const score = l.home != null ? ` ${l.home}:${l.away}` : ''
  if (l.phase === 'finished') return `Ende${score}`
  return `live ${l.minute != null ? `${l.minute}'` : ''}${score}`
}

function StreakChip({ s }) {
  if (!s) return null
  if (s.losing > 0) return <span className="sl-chip neg">−{s.losing}</span>
  if (s.winning > 0) return <span className="sl-chip pos">+{s.winning}</span>
  return null
}

function PlaceForm({ bet, defaultStake, onSaved, onCancel }) {
  const [odds, setOdds] = useState(String(bet.placed?.odds ?? bet.odds_swisslos ?? ''))
  const [stake, setStake] = useState(String(bet.placed?.stake ?? defaultStake))
  const [err, setErr] = useState('')
  const save = () => {
    api
      .verificationPlaced({
        bet_id: bet.id,
        odds: Number(odds.replace(',', '.')),
        stake: Number(stake.replace(',', '.')),
      })
      .then(onSaved)
      .catch((e) => setErr(e.message))
  }
  return (
    <div className="sl-place">
      <label>
        Quote
        <input inputMode="decimal" value={odds} onChange={(e) => setOdds(e.target.value)} />
      </label>
      <label>
        Einsatz CHF
        <input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} />
      </label>
      <button type="button" className="sl-btn sl-btn--primary" onClick={save}>
        Speichern
      </button>
      <button type="button" className="sl-btn" onClick={onCancel}>
        Abbrechen
      </button>
      {err ? <div className="neg">{err}</div> : null}
    </div>
  )
}

function TipCard({ b, streak, defaultStake, editing, setEditing, reload }) {
  const a = b.advice
  return (
    <div className={`sl-card ${a.key === 'bet' ? 'sl-card--bet' : ''}`}>
      <div className="sl-card-top">
        <span className="sl-time">{liveText(b)}</span>
        <span className="sl-league">{b.league || '—'}</span>
      </div>
      <div className="sl-teams">
        {b.home} <span className="muted">–</span> {b.away}
      </div>
      <div className="sl-row">
        <span className="sl-market">{b.market}</span>
        <span className="sl-odds">
          {num(b.odds_swisslos)}
          <small className="muted"> Pinnacle {num(pinnacleOdds(b))}</small>
        </span>
      </div>
      <div className="sl-row">
        <span className="muted">
          {b.strategy_name} <StreakChip s={streak} />
        </span>
        <span className={b.placed ? 'pos' : a.tone}>
          {b.placed ? `✓ ${num(b.placed.odds)} × ${num(b.placed.stake)} CHF` : a.text}
        </span>
      </div>
      {editing === b.id ? (
        <PlaceForm
          bet={b}
          defaultStake={defaultStake}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
          onCancel={() => setEditing(null)}
        />
      ) : (
        <div className="sl-actions">
          {b.sporttip_url ? (
            <a className="sl-btn" href={b.sporttip_url} target="_blank" rel="noopener noreferrer">
              Swisslos ↗
            </a>
          ) : null}
          <button type="button" className="sl-btn sl-btn--primary" onClick={() => setEditing(b.id)}>
            {b.placed ? 'Ändern' : 'Gesetzt'}
          </button>
          {b.placed ? (
            <button
              type="button"
              className="sl-btn"
              onClick={() => api.verificationUnplaced(b.id).then(reload)}
            >
              Rückgängig
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}

function Summary({ title, s, unit = '' }) {
  return (
    <div className="sl-summary">
      <div className="sl-summary-title">{title}</div>
      <div className="sl-summary-grid">
        <div>
          <b>{s.n}</b>
          <span>Wetten</span>
        </div>
        <div>
          <b className="pos">{s.won}</b>
          <span>gewonnen</span>
        </div>
        <div>
          <b className="neg">{s.lost}</b>
          <span>verloren</span>
        </div>
        <div>
          <b className={tone(s.profit)}>
            {signed(s.profit)}
            {unit}
          </b>
          <span>Profit</span>
        </div>
        <div>
          <b className={tone(s.roi)}>{s.roi == null ? '—' : `${signed(s.roi, 1)}%`}</b>
          <span>ROI</span>
        </div>
        <div>
          <b>
            −{s.maxLose} / +{s.maxWin}
          </b>
          <span>max. Serie</span>
        </div>
      </div>
    </div>
  )
}

export default function SwisslosApp() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState(() => readSetting('slTab', 'tips'))
  const [onlyBet, setOnlyBet] = useState(() => readSetting('slOnlyBet', true))
  const [editing, setEditing] = useState(null)
  const maxShortfall = Number(readSetting('maxShortfall', 5)) || 0
  const defaultStake = readSetting('defaultStake', 10)

  useEffect(() => writeSetting('slTab', tab), [tab])
  useEffect(() => writeSetting('slOnlyBet', onlyBet), [onlyBet])

  const load = useCallback(() => {
    setLoading(true)
    api
      .verification()
      .then((d) => {
        setData(d)
        setError('')
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    // Beim Zurückkehren in die App sofort aktualisieren
    const onVisible = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [load])

  const slBets = useMemo(() => (data?.bets || []).filter((b) => b.swisslos), [data])

  // Aktuelle Serie pro Strategie mit Swisslos-Quoten
  const streakByStrategy = useMemo(() => {
    const groups = {}
    for (const b of slBets) if (b.profit_swisslos != null) (groups[b.strategy_id] ||= []).push(b)
    return Object.fromEntries(
      Object.entries(groups).map(([id, rows]) => {
        const s = stats(rows, 'profit_swisslos')
        return [id, { losing: s.losing, winning: s.winning }]
      }),
    )
  }, [slBets])

  const tips = useMemo(
    () =>
      slBets
        .filter((b) => notStarted(b) || (b.placed && b.settled_at == null))
        .map((b) => ({ ...b, advice: advice(b, maxShortfall) }))
        .filter((b) => !onlyBet || b.advice.key === 'bet' || b.placed)
        .sort((a, c) => String(a.date).localeCompare(String(c.date))),
    [slBets, onlyBet, maxShortfall],
  )

  const placed = useMemo(
    () => (data?.bets || []).filter((b) => b.placed).sort((a, c) => String(c.date).localeCompare(String(a.date))),
    [data],
  )
  const realStats = useMemo(() => {
    const done = placed.filter((b) => b.profit_real != null)
    const stake = done.reduce((s, b) => s + (Number(b.placed.stake) || 0), 0)
    return { ...stats(placed, 'profit_real'), stake, roi: stake ? (stats(placed, 'profit_real').profit / stake) * 100 : null }
  }, [placed])

  const slStats = useMemo(() => stats(slBets.filter((b) => b.odds_swisslos != null), 'profit_swisslos'), [slBets])
  const perStrategy = useMemo(() => {
    const groups = {}
    for (const b of slBets) if (b.odds_swisslos != null) (groups[b.strategy_id] ||= []).push(b)
    return Object.values(groups)
      .map((rows) => ({ name: rows[0].strategy_name, ...stats(rows, 'profit_swisslos') }))
      .sort((a, c) => c.profit - a.profit)
  }, [slBets])

  const toBet = tips.filter((b) => b.advice.key === 'bet' && !b.placed).length

  return (
    <div className="sl-app">
      <header className="sl-header">
        <div className="sl-title">
          SL Tipps
          {loading ? <span className="muted"> · lädt…</span> : null}
        </div>
        <button type="button" className="sl-btn" onClick={load}>
          ↻
        </button>
      </header>

      {error ? <div className="error-banner">PC nicht erreichbar: {error}</div> : null}

      <main className="sl-main">
        {tab === 'tips' ? (
          <>
            <div className="sl-toolbar">
              <span>
                <b className="pos">{toBet}</b> zu setzen
              </span>
              <label className="chk">
                <input type="checkbox" checked={onlyBet} onChange={(e) => setOnlyBet(e.target.checked)} />
                nur „setzen“
              </label>
            </div>
            {tips.map((b) => (
              <TipCard
                key={b.id}
                b={b}
                streak={streakByStrategy[b.strategy_id]}
                defaultStake={defaultStake}
                editing={editing}
                setEditing={setEditing}
                reload={load}
              />
            ))}
            {!tips.length && data ? <p className="muted sl-empty">Gerade keine Tipps vor Anpfiff.</p> : null}
          </>
        ) : null}

        {tab === 'placed' ? (
          <>
            <Summary title="Echt gesetzt" s={realStats} unit=" CHF" />
            <p className="muted" style={{ margin: '0 0 0.6rem' }}>
              Einsatz {num(realStats.stake)} CHF · ROI auf Einsatz
            </p>
            {placed.map((b) => (
              <div key={b.id} className="sl-card">
                <div className="sl-card-top">
                  <span className="sl-time">{fmtKickoff(b.date)}</span>
                  <span className={b.status === 'gewonnen' ? 'pos' : b.status === 'verloren' ? 'neg' : 'muted'}>
                    {b.status === 'offen' ? liveText(b) : b.status}
                  </span>
                </div>
                <div className="sl-teams">
                  {b.home} <span className="muted">–</span> {b.away}
                </div>
                <div className="sl-row">
                  <span className="muted">
                    {b.market} · {b.strategy_name}
                  </span>
                  <span>
                    {num(b.placed.odds)} × {num(b.placed.stake)} CHF
                    {b.profit_real != null ? (
                      <b className={tone(b.profit_real)}> {signed(b.profit_real)}</b>
                    ) : null}
                  </span>
                </div>
              </div>
            ))}
            {!placed.length ? (
              <p className="muted sl-empty">Noch nichts als gesetzt markiert. Bei „Tipps“ auf „Gesetzt“ tippen.</p>
            ) : null}
          </>
        ) : null}

        {tab === 'stats' ? (
          <>
            <Summary title="Alle Strategien mit Swisslos-Quoten" s={slStats} />
            {perStrategy.map((s) => (
              <div key={s.name} className="sl-card">
                <div className="sl-row">
                  <b>{s.name}</b>
                  <b className={tone(s.profit)}>{signed(s.profit)}</b>
                </div>
                <div className="sl-row muted">
                  <span>
                    {s.n} Wetten · {s.won}/{s.settled} gewonnen · ROI {s.roi == null ? '—' : `${signed(s.roi, 1)}%`}
                  </span>
                  <span>
                    {s.losing > 0 ? `aktuell −${s.losing}` : s.winning > 0 ? `aktuell +${s.winning}` : ''} · max −{s.maxLose}/+
                    {s.maxWin}
                  </span>
                </div>
              </div>
            ))}
            <p className="muted sl-empty">
              Gerechnet mit der letzten Swisslos-Quote vor Anpfiff, Einsatz 1 pro Wette. Mehr Details am PC unter
              Verifikation.
            </p>
          </>
        ) : null}
      </main>

      <nav className="sl-tabbar">
        <button type="button" className={tab === 'tips' ? 'active' : ''} onClick={() => setTab('tips')}>
          <span className="sl-tab-icon">★</span>
          Tipps{toBet ? <span className="sl-badge">{toBet}</span> : null}
        </button>
        <button type="button" className={tab === 'placed' ? 'active' : ''} onClick={() => setTab('placed')}>
          <span className="sl-tab-icon">✓</span>
          Gesetzt
        </button>
        <button type="button" className={tab === 'stats' ? 'active' : ''} onClick={() => setTab('stats')}>
          <span className="sl-tab-icon">∑</span>
          Bilanz
        </button>
      </nav>
    </div>
  )
}
