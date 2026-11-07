import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

const LEVELS = {
  ok: { label: 'OK', cls: 'dq-ok' },
  info: { label: 'Hinweis', cls: 'dq-info' },
  warn: { label: 'Warnung', cls: 'dq-warn' },
  error: { label: 'Fehler', cls: 'dq-error' },
}

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('de-CH'))
const pct = (c, t) => (t ? `${((100 * c) / t).toLocaleString('de-CH', { maximumFractionDigits: 2 })} %` : '')

/** Datenqualität: automatische Prüfungen (täglich, oder per Knopf) mit Beispielen je Befund */
export default function DataQualityBlock() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState({})

  const load = useCallback(() => {
    api
      .dataQuality()
      .then((d) => {
        setData(d)
        setError('')
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Während eine Prüfung läuft: alle 4 s nachsehen
  useEffect(() => {
    if (!data?.running) return undefined
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [data?.running, load])

  const run = () => {
    api
      .dataQualityRun()
      .then(() => setData((d) => ({ ...(d || {}), running: true })))
      .catch((e) => setError(e.message))
  }

  const s = data?.summary || {}
  const checks = data?.checks || []

  return (
    <section className="stat-section dq">
      <div className="toolbar">
        <div>
          <h2>Datenqualität</h2>
          <p className="page-sub">
            {data?.checked_at ? `Geprüft ${data.checked_at.replace('T', ' ')} · ${data.seconds}s` : 'Noch nicht geprüft'}
            {data?.running ? ' · Prüfung läuft…' : ''}
          </p>
        </div>
        <div className="toolbar-actions">
          {['error', 'warn', 'info', 'ok'].map((l) =>
            s[l] ? (
              <span key={l} className={`dq-chip ${LEVELS[l].cls}`}>
                {s[l]} {LEVELS[l].label}
              </span>
            ) : null,
          )}
          <button type="button" className="nav-btn" onClick={run} disabled={data?.running}>
            {data?.running ? 'Prüft…' : 'Jetzt prüfen'}
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      {checks.length ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Bereich</th>
                <th>Prüfung</th>
                <th className="num">Befunde</th>
                <th className="num">geprüft</th>
                <th className="num">Anteil</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => {
                const isOpen = !!open[c.key]
                const lv = LEVELS[c.level] || LEVELS.info
                return [
                  <tr
                    key={c.key}
                    className="dq-row"
                    onClick={() => setOpen((o) => ({ ...o, [c.key]: !o[c.key] }))}
                    title="Klick → Erklärung und Beispiele"
                  >
                    <td>
                      <span className={`dq-chip ${lv.cls}`}>{lv.label}</span>
                    </td>
                    <td className="muted">{c.group}</td>
                    <td>
                      {isOpen ? '▾ ' : '▸ '}
                      {c.title}
                    </td>
                    <td className="num">{fmt(c.count)}</td>
                    <td className="num muted">{fmt(c.total)}</td>
                    <td className="num">{pct(c.count, c.total)}</td>
                  </tr>,
                  isOpen ? (
                    <tr key={`${c.key}-d`} className="dq-detail">
                      <td colSpan={6}>
                        <p>{c.detail}</p>
                        {c.examples?.length ? (
                          <table className="data-table dq-examples">
                            <tbody>
                              {c.examples.map((e, i) => (
                                <tr key={`${e.game_id ?? 'x'}-${i}`}>
                                  <td className="muted">{String(e.date || '').slice(0, 16).replace('T', ' ')}</td>
                                  <td>{e.league}</td>
                                  <td>{e.match}</td>
                                  <td className="muted">{e.info}</td>
                                  <td className="num muted">{e.game_id ?? ''}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : null}
                      </td>
                    </tr>
                  ) : null,
                ]
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
