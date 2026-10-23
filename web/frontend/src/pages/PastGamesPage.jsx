import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts'
import { loadStrategyResults } from '../strategyResultsStore'

function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

function pctCell(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  const p = n > 1 ? n : n * 100
  return `${p.toFixed(0)}%`
}

export default function PastGamesPage() {
  const [bundle, setBundle] = useState(() => loadStrategyResults())

  useEffect(() => {
    const onUpdate = (e) => setBundle(e.detail || loadStrategyResults())
    window.addEventListener('strategy-results', onUpdate)
    setBundle(loadStrategyResults())
    return () => window.removeEventListener('strategy-results', onUpdate)
  }, [])

  const data = bundle?.data
  const m = data?.metrics || {}
  const oc = m.outcomes || {}
  const equity = m.equity || {}
  const equitySeries = equity.series || []
  const pctInfo = data?.percentile || m.percentile || {}

  return (
    <div className="main strategy-page">
      <div className="toolbar" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Vergangene Spiele</h1>
          <p className="page-sub">
            Backtest der letzten Analyse aus Strategie · ROI · Equity · Spielausgänge
          </p>
        </div>
        <Link to="/strategy" className="nav-btn">
          ← Strategie
        </Link>
      </div>

      {!data?.ok ? (
        <section className="stat-section">
          <p className="muted">
            Noch keine Analyse. Unter <Link to="/strategy">Strategie</Link> Filter setzen und
            „Analysieren“ — Ergebnisse erscheinen hier.
          </p>
        </section>
      ) : (
        <section className="stat-section">
          {pctInfo.enabled ? (
            <p className="muted" style={{ marginBottom: '0.65rem' }}>
              Percentile Top {pctInfo.percentile}% · {pctInfo.metric}
              {pctInfo.threshold != null ? ` · Schwelle ≥ ${num(pctInfo.threshold, 3)}` : ''}
              {' · '}
              {pctInfo.n_before} → {pctInfo.n_after} Wetten
              {pctInfo.look_ahead ? ' · ⚠ Look-ahead' : ''}
            </p>
          ) : null}

          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Wetten N</div>
              <div className="stat-card-value">{num(m.n, 0)}</div>
              {pctInfo.enabled && pctInfo.n_before != null ? (
                <div className="stat-card-sub">von {pctInfo.n_before}</div>
              ) : null}
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Winrate</div>
              <div className="stat-card-value">{num(m.win_rate)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Profit</div>
              <div className="stat-card-value">{num(m.total_profit)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">ROI</div>
              <div className="stat-card-value">{num(m.roi_pct)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Ø xROI</div>
              <div className="stat-card-value">
                {m.avg_xroi_pct != null ? `${num(m.avg_xroi_pct, 1)}%` : '—'}
              </div>
              <div className="stat-card-sub">n={m.xroi_n ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Ø Quote</div>
              <div className="stat-card-value">{num(m.avg_odds)}</div>
            </div>
          </div>

          <h3 className="strat-outcome-title">
            Spielausgänge · n={num(oc.games_n, 0)} Spiele
          </h3>
          <div className="stat-grid strat-outcome-grid">
            <div className="stat-card">
              <div className="stat-card-title">Home</div>
              <div className="stat-card-value">{num(oc.home_pct, 1)}%</div>
              <div className="stat-card-sub">{oc.home_n ?? 0} Spiele</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Unentschieden</div>
              <div className="stat-card-value">{num(oc.draw_pct, 1)}%</div>
              <div className="stat-card-sub">{oc.draw_n ?? 0} Spiele</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Auswärts</div>
              <div className="stat-card-value">{num(oc.away_pct, 1)}%</div>
              <div className="stat-card-sub">{oc.away_n ?? 0} Spiele</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Over 2.5</div>
              <div className="stat-card-value">{num(oc.over25_pct, 1)}%</div>
              <div className="stat-card-sub">{oc.over25_n ?? 0} Spiele</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Under 2.5</div>
              <div className="stat-card-value">{num(oc.under25_pct, 1)}%</div>
              <div className="stat-card-sub">{oc.under25_n ?? 0} Spiele</div>
            </div>
          </div>

          {equitySeries.length > 0 ? (
            <div className="strat-equity">
              <div className="stat-section-head">
                <h3 className="strat-outcome-title" style={{ margin: 0 }}>
                  Profit über Zeit (kumuliert)
                </h3>
                <span className="pill pill-muted">
                  Close {num(equity.total_profit_close)} u · ROI {num(equity.roi_close_pct, 1)}%
                </span>
                <span className="pill pill-muted">
                  Open {num(equity.total_profit_open)} u · ROI {num(equity.roi_open_pct, 1)}%
                </span>
              </div>
              <div className="strat-equity-chart">
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={equitySeries} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                    <XAxis dataKey="date" stroke="var(--muted)" fontSize={11} minTickGap={40} />
                    <YAxis
                      stroke="var(--muted)"
                      fontSize={11}
                      tickFormatter={(v) => Number(v).toFixed(0)}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-elevated)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                      }}
                      formatter={(v, name) => [num(v, 2), name]}
                      labelFormatter={(l, payload) => {
                        const i = payload?.[0]?.payload?.i
                        return i != null ? `#${i} · ${l}` : String(l)
                      }}
                    />
                    <Legend />
                    <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
                    <Line
                      type="monotone"
                      dataKey="equity_close"
                      name="Closing"
                      stroke="#3d9cfd"
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity_open"
                      name="Opening"
                      stroke="#e8a838"
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}

          {data.truncated ? (
            <p className="muted">Tabelle auf {data.results.length} Zeilen begrenzt (gesamt {data.n}).</p>
          ) : null}

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Home</th>
                  <th>Away</th>
                  <th className="num">S#H</th>
                  <th className="num">S#A</th>
                  <th className="num">Rating H</th>
                  <th className="num">Rating A</th>
                  <th className="num">RD H</th>
                  <th className="num">RD A</th>
                  <th className="num">xG H</th>
                  <th className="num">xG A</th>
                  <th className="num">P(H)</th>
                  <th className="num">P(D)</th>
                  <th className="num">P(A)</th>
                  <th>Markt</th>
                  <th className="num">Open</th>
                  <th className="num">Close</th>
                  <th className="num">xROI %</th>
                  <th className="num">Quote</th>
                  <th className="num">Profit</th>
                  <th className="num">Erg.</th>
                </tr>
              </thead>
              <tbody>
                {(data.results || []).map((r, i) => (
                  <tr key={`${r.game_id}-${r.market}-${i}`}>
                    <td>{String(r.date || '').slice(0, 10)}</td>
                    <td>{r.home}</td>
                    <td>{r.away}</td>
                    <td className="num">{r.home_season_n ?? '—'}</td>
                    <td className="num">{r.away_season_n ?? '—'}</td>
                    <td className="num">{num(r.rating_h, 0)}</td>
                    <td className="num">{num(r.rating_a, 0)}</td>
                    <td className="num">{num(r.rd_h, 1)}</td>
                    <td className="num">{num(r.rd_a, 1)}</td>
                    <td className="num">{num(r.xg_glicko_h)}</td>
                    <td className="num">{num(r.xg_glicko_a)}</td>
                    <td className="num">{pctCell(r.p_home)}</td>
                    <td className="num">{pctCell(r.p_draw)}</td>
                    <td className="num">{pctCell(r.p_away)}</td>
                    <td>{r.market}</td>
                    <td className="num">{num(r.odds_opening)}</td>
                    <td className="num">{num(r.odds_closing)}</td>
                    <td className={`num ${r.xroi_pct >= 0 ? 'pos' : 'neg'}`}>
                      {r.xroi_pct == null ? '—' : `${num(r.xroi_pct, 1)}%`}
                    </td>
                    <td className="num">{num(r.odds)}</td>
                    <td className={`num ${r.profit >= 0 ? 'pos' : 'neg'}`}>{num(r.profit)}</td>
                    <td className="num">
                      {r.home_score}–{r.away_score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
