import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

const num = (v, d = 1) =>
  v == null || Number.isNaN(v) ? '—' : Number(v).toLocaleString('de-CH', { minimumFractionDigits: d, maximumFractionDigits: d })
const signed = (v, d = 1) => (v == null ? '—' : `${v > 0 ? '+' : ''}${num(v, d)} %`)
const cls = (v) => (v == null ? '' : v > 0 ? 'diff-pos' : v < 0 ? 'diff-neg' : '')
const when = (s) => (s ? s.replace('T', ' ').slice(0, 16) : '')
const span = (s) => (s?.roi_lo != null ? `${signed(s.roi_lo)} … ${signed(s.roi_hi)}` : '')

/** Automatische Strategie-Suche: lernen bis Stichtag, prüfen danach — und Treffer als Strategie speichern */
export default function StrategyBuilderBlock() {
  const [catalog, setCatalog] = useState(null)
  const [data, setData] = useState({ runs: [], running: {} })
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [cfg, setCfg] = useState({
    markets: ['Home', 'Away', 'Draw', 'Over 2.5', 'Under 2.5'],
    odds_type: 'opening',
    autoSplit: true,
    split: '2026-09-01',
    min_bets: 100,
    include_glicko: false,
    scope_only: false,
  })

  const load = useCallback(() => {
    api
      .builderRuns()
      .then((d) => {
        setData(d)
        setError('')
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    api.builderCatalog().then(setCatalog).catch((e) => setError(e.message))
    load()
  }, [load])

  const running = !!data.running?.running
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [running, load])

  const [waitFor, setWaitFor] = useState(null)
  useEffect(() => {
    if (waitFor && !running && data.runs.some((r) => r.id === waitFor)) {
      setSelected(waitFor)
      setWaitFor(null)
    }
  }, [waitFor, running, data.runs])

  useEffect(() => {
    if (!selected) {
      setDetail(null)
      return
    }
    api.builderRun(selected).then(setDetail).catch((e) => setError(e.message))
  }, [selected])

  const set = (k, v) => setCfg((x) => ({ ...x, [k]: v }))
  const toggleMarket = (m) =>
    setCfg((x) => ({ ...x, markets: x.markets.includes(m) ? x.markets.filter((y) => y !== m) : [...x.markets, m] }))

  const start = () => {
    setMsg('')
    api
      .builderStart({
        markets: cfg.markets,
        odds_type: cfg.odds_type,
        split: cfg.autoSplit ? null : cfg.split,
        min_bets: Number(cfg.min_bets) || 100,
        include_glicko: cfg.include_glicko,
        scope_only: cfg.scope_only,
      })
      .then((r) => {
        if (!r.started) setError(r.error || 'Konnte nicht starten')
        else {
          setError('')
          setWaitFor(r.run_id)
        }
        load()
      })
      .catch((e) => setError(e.message))
  }

  const remove = (id, e) => {
    e.stopPropagation()
    api.builderDelete(id).then(() => {
      if (selected === id) setSelected(null)
      load()
    })
  }

  const save = (i, row) => {
    const name = window.prompt('Name der neuen Strategie:', `builder_${row.combo.market}_${row.combo.odds_band.join('-')}`)
    if (name == null) return
    api
      .builderSave(detail.id, i, name)
      .then((r) => setMsg(`Gespeichert als Strategie „${r.name}“ — die Verifikation zeichnet ab jetzt ihre Wetten auf.`))
      .catch((e) => setError(e.message))
  }

  const res = detail?.result
  const s = res?.summary

  return (
    <>
      <div className="ml-grid">
        <section className="strat-card">
          <h3>Neue Suche</h3>
          <p className="muted ml-help">
            Probiert für jeden Markt jedes Quotenband und jede Vor-Spiel-Bedingung (Metrik ≥/≤ Schwelle) aus — aber nur
            auf dem Lernzeitraum. Die besten werden danach auf dem Prüfzeitraum getestet.
          </p>
          <div className="strat-field">
            Märkte
            <div className="ml-checks ml-checks-row">
              {(catalog?.markets || []).map((m) => (
                <label key={m}>
                  <input type="checkbox" checked={cfg.markets.includes(m)} onChange={() => toggleMarket(m)} />
                  {m}
                </label>
              ))}
            </div>
          </div>
          <label className="strat-field">
            Quote
            <select value={cfg.odds_type} onChange={(e) => set('odds_type', e.target.value)}>
              <option value="opening">Opening (früh wetten)</option>
              <option value="closing">Closing (kurz vor Anpfiff)</option>
            </select>
          </label>
          <label className="strat-field">
            Mindestens Wetten im Lernzeitraum
            <input
              type="number"
              min={30}
              step={10}
              value={cfg.min_bets}
              onChange={(e) => set('min_bets', e.target.value)}
            />
          </label>
          <div className="ml-checks">
            <label>
              <input type="checkbox" checked={cfg.autoSplit} onChange={(e) => set('autoSplit', e.target.checked)} />
              Stichtag automatisch (ältere 70 % lernen, neuere 30 % prüfen)
            </label>
            {!cfg.autoSplit ? (
              <input type="date" value={cfg.split} onChange={(e) => set('split', e.target.value)} />
            ) : null}
            <label title="Glicko-Werte der Vergangenheit wurden oft erst nach Anpfiff geholt">
              <input
                type="checkbox"
                checked={cfg.include_glicko}
                onChange={(e) => set('include_glicko', e.target.checked)}
              />
              Glicko-Metriken einbeziehen (Achtung: Look-ahead in alten Daten)
            </label>
            <label>
              <input type="checkbox" checked={cfg.scope_only} onChange={(e) => set('scope_only', e.target.checked)} />
              Nur beobachtete Ligen
            </label>
          </div>
          <button type="button" className="nav-btn ml-start" onClick={start} disabled={running || !cfg.markets.length}>
            {running ? `Sucht… ${data.running?.step || ''}` : 'Suche starten'}
          </button>
        </section>

        <section className="strat-card ml-explain">
          <h3>Warum Lern- und Prüfzeitraum?</h3>
          <ul>
            <li>
              Wer tausende Kombinationen auf denselben Daten ausprobiert, findet <b>immer</b> welche mit tollem ROI —
              durch Zufall. Das sagt nichts über die Zukunft.
            </li>
            <li>
              Deshalb zählt die Spalte <b>Prüfzeitraum</b>: Spiele, die bei der Suche nicht verwendet wurden. Bricht der ROI
              dort ein, war es Zufall.
            </li>
            <li>
              Sortiert wird nach der <b>unteren Grenze</b> des Lern-ROI — das bevorzugt Kombinationen mit vielen Wetten statt
              Glückstreffer mit wenigen.
            </li>
            <li>
              <b>xROI</b> = Opening gegen Closing (wie auf der Strategie-Seite). Positiv heisst: der Markt ist danach in deine
              Richtung gegangen — ein guter früher Hinweis.
            </li>
            <li>
              <b>Speichern</b> legt die Kombination als Strategie an. Ab dann zeichnet die Verifikation ihre echten Wetten auf —
              der ehrlichste Test.
            </li>
          </ul>
        </section>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {msg ? <div className="ml-ok">{msg}</div> : null}

      <section className="stat-section">
        <h2>Bisherige Suchen</h2>
        {data.runs.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Zeit</th>
                  <th>Märkte</th>
                  <th>Quote</th>
                  <th>Stichtag</th>
                  <th className="num">Kombinationen</th>
                  <th className="num">Top: Lern-ROI Ø</th>
                  <th className="num">Top: Prüf-ROI Ø</th>
                  <th className="num">im Plus (Prüfung)</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr
                    key={r.id}
                    className={`dq-row ${selected === r.id ? 'ml-sel' : ''}`}
                    onClick={() => setSelected(selected === r.id ? null : r.id)}
                  >
                    <td className="muted">{when(r.created_at)}</td>
                    <td>{(r.config?.markets || []).join(', ')}</td>
                    <td>{r.config?.odds_type}</td>
                    <td>{r.split || (r.status === 'error' ? <span className="diff-neg">{r.error}</span> : '—')}</td>
                    <td className="num">{r.summary?.n_tested ?? '—'}</td>
                    <td className={`num ${cls(r.summary?.top_train_roi_avg)}`}>{signed(r.summary?.top_train_roi_avg)}</td>
                    <td className={`num ${cls(r.summary?.top_test_roi_avg)}`}>{signed(r.summary?.top_test_roi_avg)}</td>
                    <td className="num">
                      {r.summary ? `${r.summary.top_test_positive} / ${r.summary.top_test_n}` : '—'}
                    </td>
                    <td>
                      <button type="button" className="ml-del" title="Suche löschen" onClick={(e) => remove(r.id, e)}>
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Noch keine Suche. Starte oben die erste.</p>
        )}
      </section>

      {res ? (
        <section className="strat-card ml-detail">
          <div className="toolbar">
            <div>
              <h2>Ergebnis der Suche</h2>
              <p className="page-sub">
                {when(detail.created_at)} · {detail.seconds}s · Lernen {res.train_from} – {res.split} ({res.train_games}{' '}
                Spiele) · Prüfen ab {res.split} bis {res.test_to} ({res.test_games} Spiele)
              </p>
            </div>
            <button type="button" className="nav-btn nav-btn--muted" onClick={() => setSelected(null)}>
              Schliessen
            </button>
          </div>
          <div className="ml-verdict">
            {s.n_tested.toLocaleString('de-CH')} Kombinationen getestet — {num(s.train_positive_pct)} % davon waren im
            Lernzeitraum im Plus. Die besten {s.top_test_n} hatten dort Ø {signed(s.top_train_roi_avg)}, im Prüfzeitraum Ø{' '}
            <b className={cls(s.top_test_roi_avg)}>{signed(s.top_test_roi_avg)}</b> ({s.top_test_positive} von {s.top_test_n}{' '}
            im Plus
            {s.top_test_xroi_avg != null ? `, xROI Ø ${signed(s.top_test_xroi_avg, 2)}` : ''}).{' '}
            {s.top_test_roi_avg != null && s.top_test_roi_avg < s.top_train_roi_avg / 2
              ? 'Der Vorsprung aus dem Lernzeitraum hält nicht — das meiste war Zufall.'
              : 'Ein Teil des Vorsprungs hält — Kandidaten in der Verifikation weiter beobachten.'}
          </div>
          <div className="table-wrap">
            <table className="data-table ml-small">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Kombination</th>
                  <th className="num">Lern: Wetten</th>
                  <th className="num">Lern: ROI</th>
                  <th className="num">Lern: Spanne</th>
                  <th className="num">Prüf: Wetten</th>
                  <th className="num">Prüf: ROI</th>
                  <th className="num">Prüf: Treffer</th>
                  <th className="num">Prüf: xROI</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {res.top.map((r, i) => (
                  <tr key={r.label}>
                    <td className="muted">{i + 1}</td>
                    <td>
                      {r.label}
                      {r.glicko ? <span className="dq-chip dq-warn ml-tag">Glicko</span> : null}
                    </td>
                    <td className="num">{r.train.n}</td>
                    <td className={`num ${cls(r.train.roi)}`}>{signed(r.train.roi)}</td>
                    <td className="num muted">{span(r.train)}</td>
                    <td className="num">{r.test.n ?? 0}</td>
                    <td className={`num ${cls(r.test.roi)}`}>{signed(r.test.roi)}</td>
                    <td className="num">{r.test.hit != null ? `${num(r.test.hit, 0)} %` : '—'}</td>
                    <td className={`num ${cls(r.test.xroi)}`}>{signed(r.test.xroi, 2)}</td>
                    <td>
                      <button type="button" className="nav-btn nav-btn--muted ml-save" onClick={() => save(i, r)}>
                        Als Strategie speichern
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted ml-legend">
            Spanne = 95 %-Bereich des ROI. Im Prüfzeitraum sind es meist nur wenige Wetten pro Kombination — einzelne
            Werte schwanken stark, aussagekräftig ist der Durchschnitt über alle.
          </p>
        </section>
      ) : detail?.error ? (
        <div className="error-banner">{detail.error}</div>
      ) : null}
    </>
  )
}
