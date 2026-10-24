import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import SwisslosBadge from '../components/SwisslosBadge'
import { strategyTooltipFromSummary } from '../strategyTooltip'

/** Wett-Assistent: Strategie-Treffer vor Anpfiff mit Swisslos-Quote, Empfehlung und Link.
 * Gesetzt wird selbst in der offiziellen Swisslos-App/-Seite; hier nur markieren. */

function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

function readSetting(key, fallback) {
  try {
    const v = localStorage.getItem(`assistant.${key}`)
    return v == null ? fallback : JSON.parse(v)
  } catch {
    return fallback
  }
}

function writeSetting(key, value) {
  try {
    localStorage.setItem(`assistant.${key}`, JSON.stringify(value))
  } catch {
    // privater Modus o. ä. — Einstellung gilt dann nur bis zum Neuladen
  }
}

const fmtKickoff = (d) => String(d || '').slice(0, 16).replace('T', ' ')
const pinnacleOdds = (b) => b.odds_closing || b.odds_used

/** Empfehlung: setzen, wenn Swisslos-Liga, Quote vorhanden und nicht zu weit unter Pinnacle. */
function advice(b, maxShortfall) {
  if (!b.swisslos) return { key: 'no_sl', text: 'Liga nicht bei Swisslos', tone: 'muted' }
  if (!b.odds_swisslos) return { key: 'no_odds', text: 'Swisslos-Quote fehlt noch', tone: 'muted' }
  const pin = pinnacleOdds(b)
  const diff = pin ? (b.odds_swisslos / pin - 1) * 100 : null
  if (diff != null && diff < -maxShortfall) {
    return { key: 'low', text: `Quote zu tief (${num(diff, 1)} %)`, tone: 'neg', diff }
  }
  return { key: 'bet', text: 'setzen', tone: 'pos', diff }
}

function notify(title, body) {
  try {
    if ('Notification' in window && Notification.permission === 'granted') new Notification(title, { body })
  } catch {
    // Benachrichtigungen nicht verfügbar
  }
}

export default function AssistantPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [onlySwisslos, setOnlySwisslos] = useState(() => readSetting('onlySwisslos', true))
  const [onlyBet, setOnlyBet] = useState(() => readSetting('onlyBet', false))
  const [maxShortfall, setMaxShortfall] = useState(() => readSetting('maxShortfall', 5))
  const [defaultStake, setDefaultStake] = useState(() => readSetting('defaultStake', 10))
  const [notifyOn, setNotifyOn] = useState(() => readSetting('notify', false))
  const [editing, setEditing] = useState(null) // { id, odds, stake }
  const seen = useRef(new Set(readSetting('seen', [])))

  useEffect(() => writeSetting('onlySwisslos', onlySwisslos), [onlySwisslos])
  useEffect(() => writeSetting('onlyBet', onlyBet), [onlyBet])
  useEffect(() => writeSetting('maxShortfall', maxShortfall), [maxShortfall])
  useEffect(() => writeSetting('defaultStake', defaultStake), [defaultStake])
  useEffect(() => writeSetting('notify', notifyOn), [notifyOn])

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
    // Quoten (Swisslos stündlich, Pinnacle vor Anpfiff alle 15 Min.) — jede Minute neu laden reicht
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [load])

  // Offene Wetten vor Anpfiff + bereits gesetzte, noch nicht abgerechnete
  const rows = useMemo(() => {
    const open = (data?.bets || []).filter(
      (b) => b.settled_at == null && (b.placed || !b.live || b.live.phase === 'scheduled'),
    )
    return open
      .map((b) => ({ ...b, advice: advice(b, Number(maxShortfall) || 0) }))
      .filter((b) => (!onlySwisslos || b.swisslos) && (!onlyBet || b.advice.key === 'bet' || b.placed))
      .sort((a, b) => String(a.date).localeCompare(String(b.date)))
  }, [data, onlySwisslos, onlyBet, maxShortfall])

  // Neue „setzen“-Treffer melden (nur solange die Seite in einem Browser-Tab offen ist)
  useEffect(() => {
    if (!notifyOn) return
    const fresh = rows.filter((b) => b.advice.key === 'bet' && !b.placed && !seen.current.has(b.id))
    for (const b of fresh.slice(0, 5)) {
      notify(`Wett-Assistent: ${b.home} – ${b.away}`, `${b.market} @ ${num(b.odds_swisslos)} · ${b.strategy_name} · ${fmtKickoff(b.date)}`)
    }
    if (fresh.length > 5) notify('Wett-Assistent', `${fresh.length - 5} weitere neue Treffer`)
    for (const b of fresh) seen.current.add(b.id)
    if (fresh.length) writeSetting('seen', [...seen.current].slice(-500))
  }, [rows, notifyOn])

  const toggleNotify = async (on) => {
    if (on && 'Notification' in window && Notification.permission !== 'granted') {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') {
        setError('Benachrichtigungen wurden im Browser nicht erlaubt.')
        return
      }
    }
    // Beim Einschalten nicht alle vorhandenen Treffer auf einmal melden
    if (on) for (const b of rows) seen.current.add(b.id)
    setNotifyOn(on)
  }

  const savePlaced = () => {
    const { id, odds, stake } = editing
    api
      .verificationPlaced({ bet_id: id, odds: Number(String(odds).replace(',', '.')), stake: Number(String(stake).replace(',', '.')) })
      .then(() => {
        setEditing(null)
        load()
      })
      .catch((e) => setError(e.message))
  }

  const unplace = (id) => api.verificationUnplaced(id).then(load).catch((e) => setError(e.message))

  const summaryById = useMemo(() => Object.fromEntries((data?.summary || []).map((s) => [s.strategy_id, s])), [data])
  const toBet = rows.filter((b) => b.advice.key === 'bet' && !b.placed).length
  const placedOpen = rows.filter((b) => b.placed)
  const stakeOpen = placedOpen.reduce((s, b) => s + (Number(b.placed.stake) || 0), 0)

  return (
    <div className="main strategy-page assistant-page">
      <div className="toolbar">
        <div>
          <h1 className="page-title">Wett-Assistent</h1>
          <p className="page-sub">
            Treffer deiner Strategien vor Anpfiff. Gesetzt wird selbst bei Swisslos — danach hier „Gesetzt“ eintragen,
            dann zeigt die Verifikation deinen echten Gewinn.
          </p>
        </div>
        <div className="toolbar-actions">
          <button type="button" className="nav-btn" onClick={load} disabled={loading}>
            {loading ? 'Lädt…' : 'Aktualisieren'}
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="toolbar">
        <label className="chk">
          <input type="checkbox" checked={onlySwisslos} onChange={(e) => setOnlySwisslos(e.target.checked)} />
          nur Swisslos-Ligen
        </label>
        <label className="chk">
          <input type="checkbox" checked={onlyBet} onChange={(e) => setOnlyBet(e.target.checked)} />
          nur „setzen“
        </label>
        <label title="Wie weit die Swisslos-Quote höchstens unter Pinnacle liegen darf">
          Swisslos max.{' '}
          <input
            type="number"
            min="0"
            step="0.5"
            value={maxShortfall}
            onChange={(e) => setMaxShortfall(e.target.value)}
            style={{ width: '4rem' }}
          />{' '}
          % unter Pinnacle
        </label>
        <label>
          Standard-Einsatz{' '}
          <input
            type="number"
            min="0"
            step="1"
            value={defaultStake}
            onChange={(e) => setDefaultStake(e.target.value)}
            style={{ width: '4.5rem' }}
          />{' '}
          CHF
        </label>
        <label className="chk" title="Browser-Meldung bei neuen „setzen“-Treffern, solange diese Seite in einem Tab offen ist">
          <input type="checkbox" checked={notifyOn} onChange={(e) => toggleNotify(e.target.checked)} />
          Benachrichtigen
        </label>
        <span>
          <strong className="pos">{toBet}</strong> zu setzen · <strong>{placedOpen.length}</strong> gesetzt offen (
          {num(stakeOpen)} CHF)
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Anstoß</th>
              <th>Liga</th>
              <th>Heim</th>
              <th>Gast</th>
              <th>Markt</th>
              <th>Strategie</th>
              <th className="num" title="Pinnacle: Closing (vor Anpfiff aufgefrischt) bzw. Quote laut Strategie">Pinnacle</th>
              <th className="num" title="Letzte Swisslos-Quote (stündlich abgeholt)">Swisslos</th>
              <th>Empfehlung</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id}>
                <td>{fmtKickoff(b.date)}</td>
                <td>
                  {b.swisslos ? <SwisslosBadge /> : null} {b.league || '—'}
                </td>
                <td>{b.home}</td>
                <td>{b.away}</td>
                <td>{b.market}</td>
                <td className="has-tooltip" title={strategyTooltipFromSummary(b.strategy_name, summaryById[b.strategy_id])}>
                  {b.strategy_name}
                </td>
                <td className="num">{num(pinnacleOdds(b))}</td>
                <td className="num">
                  <strong>{num(b.odds_swisslos)}</strong>
                  {b.advice.diff != null ? <span className="muted"> ({num(b.advice.diff, 1)} %)</span> : null}
                </td>
                <td className={b.placed ? 'pos' : b.advice.tone}>
                  {b.placed ? `✓ gesetzt ${num(b.placed.odds)} × ${num(b.placed.stake)} CHF` : b.advice.text}
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {b.sporttip_url ? (
                    <a className="nav-btn" href={b.sporttip_url} target="_blank" rel="noopener noreferrer" title="Länderseite bei Swisslos Sporttip öffnen">
                      Swisslos ↗
                    </a>
                  ) : null}{' '}
                  {editing?.id === b.id ? (
                    <span>
                      <input
                        value={editing.odds}
                        onChange={(e) => setEditing({ ...editing, odds: e.target.value })}
                        style={{ width: '3.8rem' }}
                        title="Quote, zu der du gesetzt hast"
                      />{' '}
                      ×{' '}
                      <input
                        value={editing.stake}
                        onChange={(e) => setEditing({ ...editing, stake: e.target.value })}
                        style={{ width: '3.8rem' }}
                        title="Einsatz in CHF"
                      />{' '}
                      <button type="button" className="nav-btn" onClick={savePlaced}>
                        Speichern
                      </button>{' '}
                      <button type="button" className="nav-btn nav-btn--muted" onClick={() => setEditing(null)}>
                        ×
                      </button>
                    </span>
                  ) : b.placed ? (
                    <>
                      <button
                        type="button"
                        className="nav-btn nav-btn--muted"
                        onClick={() => setEditing({ id: b.id, odds: b.placed.odds, stake: b.placed.stake })}
                      >
                        Ändern
                      </button>{' '}
                      <button type="button" className="nav-btn nav-btn--muted" onClick={() => unplace(b.id)}>
                        Rückgängig
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="nav-btn"
                      onClick={() => setEditing({ id: b.id, odds: b.odds_swisslos || pinnacleOdds(b) || '', stake: defaultStake })}
                    >
                      Gesetzt
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && !loading ? (
              <tr>
                <td colSpan={10} className="muted">
                  Keine offenen Treffer vor Anpfiff. Neue Treffer kommen mit der stündlichen Prüfung der Strategien.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
