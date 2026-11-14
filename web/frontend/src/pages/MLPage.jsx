import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import StrategyBuilderBlock from '../components/StrategyBuilderBlock'

const num = (v, d = 2) =>
  v == null || Number.isNaN(v) ? '—' : Number(v).toLocaleString('de-CH', { minimumFractionDigits: d, maximumFractionDigits: d })
const signed = (v, d = 2, unit = ' %') => (v == null ? '—' : `${v > 0 ? '+' : ''}${num(v, d)}${unit}`)
const ci = (c) => (c ? `${signed(c[0], 1, '')} … ${signed(c[1], 1, '')}` : '')
const cls = (v) => (v == null ? '' : v > 0 ? 'diff-pos' : v < 0 ? 'diff-neg' : '')
const when = (s) => (s ? s.replace('T', ' ').slice(0, 16) : '')

const MODE_LABEL = { predict: 'Vorhersage', strategy: 'Strategie-Filter' }

function Verdict({ run }) {
  if (run.status === 'error') return <span className="dq-chip dq-error">Fehler</span>
  if (run.status === 'running') return <span className="dq-chip dq-info">läuft</span>
  if (run.config?.mode === 'strategy') {
    if (run.filter_helps == null) return <span className="dq-chip dq-info">zu wenig Daten</span>
    return run.filter_helps ? (
      <span className="dq-chip dq-ok">Filter hilft</span>
    ) : (
      <span className="dq-chip dq-warn">hilft nicht</span>
    )
  }
  if (run.config?.model === 'market') return <span className="dq-chip dq-info">Messlatte</span>
  return run.beats_opening ? (
    <span className="dq-chip dq-ok">schlägt Opening</span>
  ) : (
    <span className="dq-chip dq-warn">nicht besser</span>
  )
}

function Importance({ items }) {
  if (!items?.length) return null
  const max = Math.max(...items.map((i) => Math.abs(i.importance)), 1e-9)
  return (
    <div className="ml-imp">
      {items.map((i) => (
        <div key={i.feature} className="ml-imp-row">
          <span className="ml-imp-name">{i.feature}</span>
          <span className="ml-imp-bar">
            <span
              style={{ width: `${Math.max(0, (100 * i.importance) / max)}%` }}
              className={i.importance > 0 ? '' : 'ml-imp-zero'}
            />
          </span>
          <span className="num muted">{num(i.importance, 4)}</span>
        </div>
      ))}
    </div>
  )
}

function PredictDetail({ res, cfg, catalog }) {
  const s = res.scores || {}
  const outcomes = Object.keys(res.bets?.find((b) => b.by_outcome)?.by_outcome || {})
  const modelLabel = catalog?.models?.find((m) => m.id === cfg.model)?.label || cfg.model
  return (
    <>
      <h3>Vorhersage-Güte auf den Testspielen</h3>
      <p className="muted">
        Log-Loss: wie gut die Wahrscheinlichkeiten zum Ergebnis passen — kleiner ist besser. Das Closing ist die
        Obergrenze (so viel weiss der Markt kurz vor Anpfiff), die Opening die Messlatte, die man schlagen muss.
      </p>
      <table className="data-table ml-small">
        <thead>
          <tr>
            <th />
            <th className="num">Log-Loss</th>
            <th className="num">Brier</th>
          </tr>
        </thead>
        <tbody>
          <tr className="ml-hl">
            <td>{modelLabel}</td>
            <td className="num">{num(s.model?.log_loss, 4)}</td>
            <td className="num">{num(s.model?.brier, 4)}</td>
          </tr>
          <tr>
            <td>Opening-Quote (Messlatte)</td>
            <td className="num">{num(s.opening?.log_loss, 4)}</td>
            <td className="num">{num(s.opening?.brier, 4)}</td>
          </tr>
          <tr>
            <td className="muted">Closing-Quote (Obergrenze)</td>
            <td className="num muted">{num(s.closing?.log_loss, 4)}</td>
            <td className="num muted">{num(s.closing?.brier, 4)}</td>
          </tr>
        </tbody>
      </table>

      <h3>Wenn man die Tipps des Modells zur Opening-Quote gespielt hätte</h3>
      <p className="muted">
        Tipp = Ausgang mit dem höchsten Erwartungswert laut Modell, sobald er über der Schwelle liegt. CLV = Wert der
        Quote gemessen am fairen Closing — der verlässlichste Hinweis auf echten Vorteil. ROI schwankt stark (Spanne =
        95 %-Bereich).
      </p>
      <div className="table-wrap">
        <table className="data-table ml-small">
          <thead>
            <tr>
              <th>Schwelle</th>
              <th className="num">Wetten</th>
              <th className="num">Ø Quote</th>
              <th className="num">CLV Ø</th>
              <th className="num">CLV &gt; 0</th>
              <th className="num">ROI</th>
              <th className="num">ROI-Spanne</th>
              {outcomes.map((o) => (
                <th key={o} className="num">
                  {o}
                </th>
              ))}
              <th>Urteil</th>
            </tr>
          </thead>
          <tbody>
            {(res.bets || []).map((b) => (
              <tr key={b.threshold_pct}>
                <td>EV &gt; {b.threshold_pct} %</td>
                <td className="num">{b.n}</td>
                <td className="num">{num(b.avg_odds)}</td>
                <td className={`num ${cls(b.clv_pct)}`}>{signed(b.clv_pct)}</td>
                <td className="num">{b.clv_positive_pct != null ? `${num(b.clv_positive_pct, 0)} %` : '—'}</td>
                <td className={`num ${cls(b.roi_pct)}`}>{signed(b.roi_pct, 1)}</td>
                <td className="num muted">{ci(b.roi_ci95)}</td>
                {outcomes.map((o) => (
                  <td key={o} className="num muted">
                    {b.by_outcome?.[o] ?? 0}
                  </td>
                ))}
                <td className="muted">{b.verdict}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {res.calibration?.bins?.length ? (
        <>
          <h3>Kalibrierung: „{res.calibration.outcome}“ vorhergesagt vs. eingetreten</h3>
          <div className="ml-calib">
            {res.calibration.bins.map((b, i) => (
              <div key={i} className="ml-calib-col" title={`n=${b.n}`}>
                <div className="ml-calib-bars">
                  <span className="ml-calib-p" style={{ height: `${b.predicted * 100}%` }} />
                  <span className="ml-calib-a" style={{ height: `${b.actual * 100}%` }} />
                </div>
                <span className="muted">{num(b.predicted * 100, 0)}%</span>
              </div>
            ))}
          </div>
          <p className="muted ml-legend">
            <span className="ml-calib-p ml-dot" /> vorhergesagt <span className="ml-calib-a ml-dot" /> tatsächlich —
            gleich hoch = gut kalibriert
          </p>
        </>
      ) : null}
    </>
  )
}

function StrategyDetail({ res }) {
  return (
    <>
      <h3>
        Strategie „{res.preset?.name}“ · Testwetten ab {res.split_used} ({res.n_test} Wetten, gelernt aus{' '}
        {res.n_train})
      </h3>
      <p className="muted">
        Das Modell bewertet jede Testwette. Hilft der Filter, ist die bessere Hälfte deutlich besser als alle Wetten
        und die schlechtere Hälfte deutlich schlechter. ROI im Training: {signed(res.train_roi_pct, 1)}.
      </p>
      <div className="table-wrap">
        <table className="data-table ml-small">
          <thead>
            <tr>
              <th>Auswahl</th>
              <th className="num">Wetten</th>
              <th className="num">Treffer</th>
              <th className="num">Ø Quote</th>
              <th className="num">CLV (Näherung)</th>
              <th className="num">ROI</th>
              <th className="num">ROI-Spanne</th>
              <th className="num">Gewinn (Einheiten)</th>
            </tr>
          </thead>
          <tbody>
            {(res.selections || []).map((s, i) => (
              <tr key={s.label} className={i === 0 ? 'ml-hl' : ''}>
                <td>{s.label}</td>
                <td className="num">{s.n}</td>
                <td className="num">{s.hit_pct != null ? `${num(s.hit_pct, 0)} %` : '—'}</td>
                <td className="num">{num(s.avg_odds)}</td>
                <td className={`num ${cls(s.clv_pct)}`}>{signed(s.clv_pct)}</td>
                <td className={`num ${cls(s.roi_pct)}`}>{signed(s.roi_pct, 1)}</td>
                <td className="num muted">{ci(s.roi_ci95)}</td>
                <td className={`num ${cls(s.profit)}`}>{num(s.profit, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default function MLPage() {
  const [tab, setTab] = useState('models')
  const [catalog, setCatalog] = useState(null)
  const [data, setData] = useState({ runs: [], running: {} })
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [cfg, setCfg] = useState({
    mode: 'predict',
    model: 'logreg',
    market: '1x2',
    features: ['opening', 'xg'],
    honest_glicko: true,
    scope_only: true,
    split: '2026-09-01',
    preset_id: '',
    autoSplit: true,
  })

  const load = useCallback(() => {
    api
      .mlRuns()
      .then((d) => {
        setData(d)
        setError('')
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    api
      .mlCatalog()
      .then((c) => {
        setCatalog(c)
        setCfg((x) => ({ ...x, split: c.default_split, preset_id: c.presets?.[0]?.id || '' }))
      })
      .catch((e) => setError(e.message))
    load()
  }, [load])

  const running = !!data.running?.running
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [running, load])

  // Nach einem fertigen Lauf: diesen gleich öffnen
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
    api
      .mlRun(selected)
      .then(setDetail)
      .catch((e) => setError(e.message))
  }, [selected])

  const models = useMemo(
    () =>
      (catalog?.models || []).filter(
        (m) => m.modes.includes(cfg.mode) && (!m.markets || cfg.mode !== 'predict' || m.markets.includes(cfg.market)),
      ),
    [catalog, cfg.mode, cfg.market],
  )
  const model = models.find((m) => m.id === cfg.model)
  useEffect(() => {
    if (catalog && !model && models.length) setCfg((x) => ({ ...x, model: models[0].id }))
  }, [catalog, model, models])

  const set = (k, v) => setCfg((x) => ({ ...x, [k]: v }))
  const toggleFeature = (id) =>
    setCfg((x) => ({
      ...x,
      features: x.features.includes(id) ? x.features.filter((f) => f !== id) : [...x.features, id],
    }))

  const usesGlicko = cfg.mode === 'predict' && (cfg.model === 'glicko' || cfg.features.includes('glicko'))
  const needsFeatures = cfg.mode === 'predict' && model?.trains

  const start = () => {
    const body =
      cfg.mode === 'predict'
        ? {
            mode: 'predict',
            model: cfg.model,
            market: cfg.market,
            features: needsFeatures ? cfg.features : [],
            honest_glicko: cfg.honest_glicko,
            scope_only: cfg.scope_only,
            split: cfg.split,
          }
        : { mode: 'strategy', model: cfg.model, preset_id: cfg.preset_id, split: cfg.autoSplit ? 'auto' : cfg.split }
    api
      .mlStart(body)
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
    api.mlDelete(id).then(() => {
      if (selected === id) setSelected(null)
      load()
    })
  }

  const marketLabel = (id) => catalog?.markets?.find((m) => m.id === id)?.label?.split(' (')[0] || id
  const modelLabel = (id) => catalog?.models?.find((m) => m.id === id)?.label || id
  const featLabel = (ids) =>
    (ids || []).map((f) => catalog?.feature_groups?.find((g) => g.id === f)?.label?.split(' (')[0] || f).join(' + ')

  return (
    <div className="ml-page">
      <div className="toolbar">
        <div>
          <h2>Machine Learning</h2>
          <p className="page-sub">
            Modelle ehrlich testen: lernen nur aus Spielen vor dem Stichtag, geprüft auf den Spielen danach.
          </p>
        </div>
      </div>

      <div className="ml-seg ml-tabs">
        <button type="button" className={`nav-btn ${tab === 'models' ? '' : 'nav-btn--muted'}`} onClick={() => setTab('models')}>
          Modelle
        </button>
        <button type="button" className={`nav-btn ${tab === 'builder' ? '' : 'nav-btn--muted'}`} onClick={() => setTab('builder')}>
          Strategie-Builder
        </button>
      </div>

      {tab === 'builder' ? <StrategyBuilderBlock /> : null}
      {tab === 'models' ? (
      <>
      {error ? <div className="error-banner">{error}</div> : null}

      <div className="ml-grid">
        <section className="strat-card">
          <h3>Neuer Test</h3>
          <div className="ml-seg">
            {Object.entries(MODE_LABEL).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`nav-btn ${cfg.mode === id ? '' : 'nav-btn--muted'}`}
                onClick={() => set('mode', id)}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="muted ml-help">
            {cfg.mode === 'predict'
              ? 'Das Modell schätzt die Wahrscheinlichkeiten eines Marktes und muss die Pinnacle-Opening schlagen.'
              : 'Das Modell lernt aus den bisherigen Wetten einer Strategie, welche man besser weglässt.'}
          </p>

          <label className="strat-field">
            Modell
            <select value={cfg.model} onChange={(e) => set('model', e.target.value)}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          {model ? <p className="muted ml-help">{model.help}</p> : null}

          {cfg.mode === 'predict' ? (
            <>
              <label className="strat-field">
                Markt
                <select value={cfg.market} onChange={(e) => set('market', e.target.value)}>
                  {(catalog?.markets || []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </label>
              {needsFeatures ? (
                <div className="strat-field">
                  Merkmale
                  <div className="ml-checks">
                    {(catalog?.feature_groups || []).map((g) => (
                      <label key={g.id} title={g.help}>
                        <input
                          type="checkbox"
                          checked={cfg.features.includes(g.id)}
                          onChange={() => toggleFeature(g.id)}
                        />
                        {g.label}
                      </label>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className="ml-checks">
                {usesGlicko ? (
                  <label title="Glicko, das nach Anpfiff geholt wurde, kennt teils schon den Closing-Markt">
                    <input
                      type="checkbox"
                      checked={cfg.honest_glicko}
                      onChange={(e) => set('honest_glicko', e.target.checked)}
                    />
                    Nur Glicko von vor Anpfiff (ehrlich)
                  </label>
                ) : null}
                <label>
                  <input type="checkbox" checked={cfg.scope_only} onChange={(e) => set('scope_only', e.target.checked)} />
                  Nur beobachtete Ligen
                </label>
              </div>
              <label className="strat-field">
                Stichtag (Test ab)
                <input type="date" value={cfg.split} onChange={(e) => set('split', e.target.value)} />
              </label>
            </>
          ) : (
            <>
              <label className="strat-field">
                Strategie
                <select value={cfg.preset_id} onChange={(e) => set('preset_id', e.target.value)}>
                  {(catalog?.presets || []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="ml-checks">
                <label>
                  <input type="checkbox" checked={cfg.autoSplit} onChange={(e) => set('autoSplit', e.target.checked)} />
                  Stichtag automatisch (ältere 60 % lernen, neuere 40 % testen)
                </label>
              </div>
              {!cfg.autoSplit ? (
                <label className="strat-field">
                  Stichtag (Test ab)
                  <input type="date" value={cfg.split} onChange={(e) => set('split', e.target.value)} />
                </label>
              ) : null}
            </>
          )}

          <button type="button" className="nav-btn ml-start" onClick={start} disabled={running || !catalog}>
            {running ? `Läuft… ${data.running?.step || ''}` : 'Test starten'}
          </button>
        </section>

        <section className="strat-card ml-explain">
          <h3>So liest du die Ergebnisse</h3>
          <ul>
            <li>
              <b>Opening schlagen</b> ist die Hürde: Pinnacle preist öffentliche Daten (xG, Glicko) schon ein. Ein
              Modell, das schlechter ist als die Opening, findet nichts Neues.
            </li>
            <li>
              <b>CLV</b> (Quote gegen faires Closing) zählt mehr als ROI. Ein positiver CLV über viele Wetten ist der
              verlässlichste frühe Hinweis auf echten Vorteil.
            </li>
            <li>
              <b>ROI-Spanne</b>: Liegt 0 darin, ist der ROI von Zufall nicht zu unterscheiden — bei wenigen hundert
              Wetten fast immer.
            </li>
            <li>
              <b>Merkmal-Wichtigkeit</b>: wie viel schlechter das Modell wird, wenn man ein Merkmal durchmischt.
            </li>
            <li>
              <b>Glicko</b>: nur „vor Anpfiff“ ist ehrlich. Seit 8.11. wird Glicko eingefroren — die Datenmenge wächst
              täglich.
            </li>
          </ul>
        </section>
      </div>

      <section className="stat-section">
        <h2>Bisherige Tests</h2>
        {data.runs.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Zeit</th>
                  <th>Art</th>
                  <th>Modell</th>
                  <th>Markt / Strategie</th>
                  <th className="num">Testspiele</th>
                  <th className="num">Log-Loss Modell / Opening</th>
                  <th className="num">CLV</th>
                  <th className="num">ROI</th>
                  <th>Urteil</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.runs.map((r) => {
                  const c = r.config || {}
                  const strat = c.mode === 'strategy'
                  return (
                    <tr
                      key={r.id}
                      className={`dq-row ${selected === r.id ? 'ml-sel' : ''}`}
                      onClick={() => setSelected(selected === r.id ? null : r.id)}
                    >
                      <td className="muted">{when(r.created_at)}</td>
                      <td>{MODE_LABEL[c.mode]}</td>
                      <td>{modelLabel(c.model)}</td>
                      <td>
                        {strat ? r.strategy || '—' : marketLabel(c.market)}
                        {!strat && c.features?.length ? <span className="muted"> · {featLabel(c.features)}</span> : null}
                        {!strat && (c.model === 'glicko' || c.features?.includes('glicko')) ? (
                          <span className="muted"> · {c.honest_glicko ? 'ehrlich' : 'mit Look-ahead'}</span>
                        ) : null}
                      </td>
                      <td className="num">{r.n_test ?? '—'}</td>
                      <td className="num">
                        {strat ? '—' : `${num(r.log_loss, 4)} / ${num(r.log_loss_opening, 4)}`}
                      </td>
                      <td className={`num ${cls(r.clv_pct)}`}>{strat ? '—' : signed(r.clv_pct)}</td>
                      <td className={`num ${cls(strat ? r.filtered_roi : r.roi_pct)}`}>
                        {strat ? `${signed(r.base_roi, 1)} → ${signed(r.filtered_roi, 1)}` : signed(r.roi_pct, 1)}
                      </td>
                      <td>
                        <Verdict run={r} />
                      </td>
                      <td>
                        <button type="button" className="ml-del" title="Test löschen" onClick={(e) => remove(r.id, e)}>
                          ×
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Noch keine Tests. Starte oben den ersten — z. B. „Markt (Opening-Quote)“ als Messlatte.</p>
        )}
        <p className="muted ml-legend">CLV und ROI in der Liste: Vorhersage bei Schwelle EV &gt; 2 %; Strategie: alle → bessere Hälfte.</p>
      </section>

      {detail ? (
        <section className="strat-card ml-detail">
          <div className="toolbar">
            <div>
              <h2>
                {modelLabel(detail.config?.mode === 'strategy' ? detail.config.model : detail.config?.model)} ·{' '}
                {MODE_LABEL[detail.config?.mode]}
              </h2>
              <p className="page-sub">
                {when(detail.created_at)} · {detail.seconds}s
                {detail.result
                  ? ` · Training ${detail.result.n_train} (ab ${detail.result.train_from || '—'}) · Test ${detail.result.n_test} (bis ${detail.result.test_to})`
                  : ''}
              </p>
            </div>
            <button type="button" className="nav-btn nav-btn--muted" onClick={() => setSelected(null)}>
              Schliessen
            </button>
          </div>
          {detail.error ? <div className="error-banner">{detail.error}</div> : null}
          {detail.result?.notes?.length ? (
            <ul className="ml-notes">
              {detail.result.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}
          {detail.result ? (
            detail.config?.mode === 'strategy' ? (
              <StrategyDetail res={detail.result} />
            ) : (
              <PredictDetail res={detail.result} cfg={detail.config} catalog={catalog} />
            )
          ) : null}
          {detail.result?.importance?.length ? (
            <>
              <h3>Merkmal-Wichtigkeit</h3>
              <Importance items={detail.result.importance} />
            </>
          ) : null}
        </section>
      ) : null}
      </>
      ) : null}
    </div>
  )
}
