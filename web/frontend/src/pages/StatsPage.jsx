import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import DataQualityBlock from '../components/DataQualityBlock'

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('de-DE')
}

function Bar({ pct, tone = 'accent' }) {
  const p = Math.max(0, Math.min(100, Number(pct) || 0))
  return (
    <div className="stat-bar">
      <div className={`stat-bar-fill tone-${tone}`} style={{ width: `${p}%` }} />
      <span className="stat-bar-label">{p.toFixed(1)}%</span>
    </div>
  )
}

function Card({ title, value, sub, pct, tone }) {
  return (
    <div className="stat-card">
      <div className="stat-card-title">{title}</div>
      <div className="stat-card-value">{value}</div>
      {sub ? <div className="stat-card-sub">{sub}</div> : null}
      {pct != null ? <Bar pct={pct} tone={tone} /> : null}
    </div>
  )
}

function BackfillBlock({ title, bf }) {
  if (!bf) {
    return (
      <section className="stat-section">
        <h2>{title}</h2>
        <p className="muted">Kein Log</p>
      </section>
    )
  }
  return (
    <section className="stat-section">
      <div className="stat-section-head">
        <h2>{title}</h2>
        <span className={`pill ${bf.running_hint ? 'pill-live' : 'pill-muted'}`}>
          {bf.running_hint ? 'läuft' : 'idle / fertig'}
        </span>
      </div>
      {bf.done != null ? (
        <>
          <Bar pct={bf.pct} tone={bf.running_hint ? 'green' : 'accent'} />
          <div className="stat-meta">
            <span>
              {fmt(bf.done)} / {fmt(bf.total)}
            </span>
            <span>loaded {fmt(bf.loaded)}</span>
            <span>no_data {fmt(bf.no_data)}</span>
            <span>errors {fmt(bf.errors)}</span>
            {bf.db_glicko != null ? <span>db_glicko {fmt(bf.db_glicko)}</span> : null}
            {bf.eta_min != null ? <span>ETA ~{bf.eta_min} min</span> : null}
          </div>
        </>
      ) : (
        <p className="muted">Noch kein Fortschritt im Log.</p>
      )}
      <div className="stat-meta muted">
        <span>{bf.log}</span>
        {bf.started ? <span>Start {bf.started}</span> : null}
        {bf.log_mtime ? <span>Log {bf.log_mtime}</span> : null}
      </div>
    </section>
  )
}

const XG_PHASES = { xg: 'xG laden', form2: 'Form2 neu berechnen', glicko: 'Glicko laden' }

function XgBackfillBlock({ bf }) {
  if (!bf) return null
  const run = bf.run
  const running = !!run?.running_hint
  return (
    <section className="stat-section">
      <div className="stat-section-head">
        <h2>xG-Nachladen · beendete Spiele</h2>
        <span className={`pill ${running ? 'pill-live' : 'pill-muted'}`}>
          {running ? `läuft · ${XG_PHASES[run.phase] || run.phase}` : 'idle / fertig'}
        </span>
      </div>
      <Bar pct={bf.pct} tone="green" />
      <div className="stat-meta">
        <span>
          mit xG {fmt(bf.with_xg)} / {fmt(bf.finished)}
        </span>
        <span>ohne xG {fmt(bf.missing)}</span>
        <span>davon noch offen {fmt(bf.missing_open)}</span>
        <span>davon ohne Daten bei API {fmt(bf.missing_tried)}</span>
      </div>
      {run ? (
        <>
          <Bar pct={run.pct} tone={running ? 'green' : 'accent'} />
          <div className="stat-meta">
            <span>
              {XG_PHASES[run.phase] || run.phase || '—'}: {fmt(run.done)} / {fmt(run.total)}
            </span>
            <span>neu {fmt(run.new)}</span>
            <span>Fehler {fmt(run.errors)}</span>
          </div>
          <div className="stat-meta muted">
            {run.started_at ? <span>Start {run.started_at}</span> : null}
            {run.finished_at ? <span>Ende {run.finished_at}</span> : null}
            {run.updated_at ? <span>Update {run.updated_at}</span> : null}
          </div>
        </>
      ) : (
        <p className="muted">Noch kein Lauf · start_backfill_xg.bat</p>
      )}
    </section>
  )
}

function PipelineBlock({ pipe }) {
  if (!pipe) {
    return (
      <section className="stat-section">
        <h2>Live-Pipeline</h2>
        <p className="muted">Nicht gestartet · start_live_pipeline.ps1</p>
      </section>
    )
  }
  const q = pipe.queue || {}
  const jobs = pipe.jobs || {}
  const jobLine = (name) => {
    const j = jobs[name]
    if (!j?.last_run) return `${name}: —`
    const s = j.stats || {}
    if (name === 'sync') {
      return `sync: +${s.upcoming_upsert || 0} upcoming · ${s.finished_promoted || 0} promoted`
    }
    if (name === 'odds') {
      return `odds: close+${s.closing_loaded || 0} open+${s.opening_loaded || 0}`
    }
    return `enrich: xg_ok ${s.loaded || 0} · noch ohne xG ${s.no_data || 0}`
  }
  return (
    <section className="stat-section">
      <div className="stat-section-head">
        <h2>Live-Pipeline</h2>
        <span className={`pill ${pipe.running_hint ? 'pill-live' : 'pill-muted'}`}>
          {pipe.running_hint ? 'läuft' : 'gestoppt'}
        </span>
      </div>
      <div className="stat-meta">
        <span>Queue xG fehlt (5d): {fmt(q.missing_xg_recent)}</span>
        <span>Upcoming: {fmt(q.upcoming_open)}</span>
        <span>ohne Closing: {fmt(q.upcoming_no_closing)}</span>
        <span>ohne Opening: {fmt(q.upcoming_no_opening)}</span>
      </div>
      <div className="stat-meta">
        <span>{jobLine('sync')}</span>
        <span>{jobLine('odds')}</span>
        <span>{jobLine('enrich')}</span>
      </div>
      <div className="stat-meta muted">
        {pipe.started_at ? <span>Start {pipe.started_at}</span> : null}
        {pipe.updated_at ? <span>Update {pipe.updated_at}</span> : null}
        {pipe.intervals ? (
          <span>
            Intervalle {pipe.intervals.sync_s}/{pipe.intervals.odds_s}/{pipe.intervals.enrich_s}s
          </span>
        ) : null}
      </div>
    </section>
  )
}

export default function StatsPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [auto, setAuto] = useState(true)

  const inFlight = useRef(false)

  const load = useCallback(() => {
    // Auto-Refresh nicht stapeln, solange die vorige Anfrage noch läuft
    if (inFlight.current) return
    inFlight.current = true
    setLoading(true)
    setError('')
    api
      .stats()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => {
        inFlight.current = false
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!auto) return undefined
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [auto, load])

  const c = data?.coverage

  return (
    <div className="main stats-page">
      <div className="toolbar">
        <div>
          <h1 className="page-title">DB Statistik</h1>
          <p className="page-sub">
            Abdeckung nach Liga & Season · Backfill parallel möglich
            {data?.generated_at ? ` · ${data.generated_at}` : ''}
            {data?.db_size_mb != null ? ` · ${data.db_size_mb} MB` : ''}
          </p>
        </div>
        <div className="toolbar-actions">
          <label className="chk">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            Auto 15s
          </label>
          <button type="button" className="nav-btn" onClick={load} disabled={loading}>
            {loading ? 'Lädt…' : 'Aktualisieren'}
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      {c ? (
        <div className="stat-grid">
          <Card title="Spiele" value={fmt(c.games)} sub="gesamt in DB" />
          <Card
            title="Glicko"
            value={fmt(c.glicko)}
            sub={`${fmt(c.missing_glicko)} fehlen`}
            pct={c.glicko_pct}
            tone="accent"
          />
          <Card title="Glicko xG" value={fmt(c.xg)} sub="home+away xG" pct={c.xg_pct} tone="green" />
          <Card title="Closing Odds" value={fmt(c.odds_games)} sub="Spiele mit Quote" pct={c.odds_pct} tone="yellow" />
          <Card
            title="Opening Odds"
            value={fmt(c.opening_games)}
            sub="Spiele mit Opening"
            pct={c.opening_pct}
            tone="yellow"
          />
          <Card
            title="Profits"
            value={fmt(c.profits_games)}
            sub="Spiele mit Profits"
            pct={c.profits_pct}
            tone="accent"
          />
        </div>
      ) : null}

      <DataQualityBlock />

      <PipelineBlock pipe={data?.live_pipeline} />

      <XgBackfillBlock bf={data?.backfill_xg} />

      <div className="stat-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
        <BackfillBlock title="Glicko-Backfill" bf={data?.backfill} />
        <BackfillBlock title="Opening-Odds-Backfill" bf={data?.backfill_opening} />
        <BackfillBlock title="Closing-Odds-Backfill" bf={data?.backfill_closing} />
      </div>

      {data?.by_season?.length ? (
        <section className="stat-section">
          <h2>Abdeckung nach Season / Jahr</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Season</th>
                  <th className="num">Spiele</th>
                  <th>Glicko %</th>
                  <th>xG %</th>
                  <th>Closing %</th>
                  <th>Opening %</th>
                </tr>
              </thead>
              <tbody>
                {data.by_season.map((r) => (
                  <tr key={r.label}>
                    <td>
                      <strong>{r.label}</strong>
                      <span className="muted"> · {fmt(r.with_glicko)}/{fmt(r.games)} Glicko</span>
                    </td>
                    <td className="num">{fmt(r.games)}</td>
                    <td>
                      <Bar pct={r.glicko_pct} tone="accent" />
                    </td>
                    <td>
                      <Bar pct={r.xg_pct} tone="green" />
                    </td>
                    <td>
                      <Bar pct={r.closing_pct} tone="yellow" />
                    </td>
                    <td>
                      <Bar pct={r.opening_pct} tone="yellow" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {data?.by_league_season?.length ? (
        <section className="stat-section">
          <h2>Liga × Season (meiste fehlende Glicko)</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Liga</th>
                  <th className="num">Season</th>
                  <th className="num">Spiele</th>
                  <th className="num">fehlen</th>
                  <th>Glicko</th>
                  <th>Opening</th>
                </tr>
              </thead>
              <tbody>
                {data.by_league_season.map((r) => (
                  <tr key={`${r.league_id}-${r.season_year}`}>
                    <td>
                      {r.league}
                      <span className="muted id-tag"> #{r.league_id}</span>
                    </td>
                    <td className="num">{r.season_year ?? '—'}</td>
                    <td className="num">{fmt(r.games)}</td>
                    <td className="num">{fmt(r.missing_glicko)}</td>
                    <td>
                      <Bar pct={r.coverage_pct} tone="accent" />
                    </td>
                    <td>
                      <Bar pct={r.opening_pct} tone="yellow" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {data?.top_missing_glicko?.length ? (
        <section className="stat-section">
          <h2>Top Ligen (gesamt, alle Seasons)</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Liga</th>
                  <th className="num">Spiele</th>
                  <th className="num">mit Glicko</th>
                  <th className="num">fehlen</th>
                  <th>Glicko</th>
                  <th>Opening</th>
                </tr>
              </thead>
              <tbody>
                {data.top_missing_glicko.map((r) => (
                  <tr key={r.league_id ?? r.league}>
                    <td>
                      {r.league}
                      <span className="muted id-tag"> #{r.league_id}</span>
                    </td>
                    <td className="num">{fmt(r.games)}</td>
                    <td className="num">{fmt(r.with_glicko)}</td>
                    <td className="num">{fmt(r.missing_glicko)}</td>
                    <td>
                      <Bar pct={r.coverage_pct} tone="accent" />
                    </td>
                    <td>
                      <Bar pct={r.opening_pct} tone="yellow" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
