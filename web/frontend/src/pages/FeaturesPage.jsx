/**
 * Feature-Roadmap / Parameter-Übersicht — Dokumentation, keine Live-Logik.
 */

const STATUS = {
  done: { label: 'Aktiv', cls: 'feat-badge feat-badge--done' },
  partial: { label: 'Teilweise', cls: 'feat-badge feat-badge--partial' },
  planned: { label: 'Geplant', cls: 'feat-badge feat-badge--planned' },
}

function Badge({ status }) {
  const s = STATUS[status] || STATUS.planned
  return <span className={s.cls}>{s.label}</span>
}

function ParamTable({ rows }) {
  return (
    <div className="table-wrap feat-table">
      <table>
        <thead>
          <tr>
            <th>Parameter</th>
            <th>Bedeutung</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>
                <code>{r.key}</code>
              </td>
              <td>{r.desc}</td>
              <td>
                <Badge status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const MAIN_PARAMS = [
  { key: 'market_home / draw / away / over / under (+3.5/4.5)', desc: 'Markt-Auswahl für Backtest & Upcoming', status: 'done' },
  { key: 'odds_home_* / odds_away_* / odds_over_* / odds_under_*', desc: 'Quoten-Min/Max (Hauptkriterien, optional)', status: 'done' },
  { key: 'odds_type', desc: 'Closing oder Opening als Settlement-Quote', status: 'done' },
  { key: 'gender_filter', desc: 'Männer / Frauen / Beide (über Liga-Name)', status: 'done' },
  { key: 'league_filter / country_filter', desc: 'Textfilter Liga / Land', status: 'done' },
  { key: 'date_from / date_to', desc: 'Zeitraum (Backtest)', status: 'done' },
]

const GLICKO_PARAMS = [
  { key: 'glicko_home_min/max · glicko_away_min/max', desc: 'homeRating / awayRating', status: 'done' },
  { key: 'glicko_rd_* · glicko_vol_*', desc: 'RD und Volatility Home/Away', status: 'done' },
  { key: 'glicko_p_home/draw/away_*', desc: 'Glicko-Wahrscheinlichkeiten P(H/D/A)', status: 'done' },
  { key: 'xg_glicko_home/away_*', desc: 'Glicko-xG dieses Spiels', status: 'done' },
  { key: 'season_games_home/away_*', desc: 'Saison-Spielnummer pro Team', status: 'done' },
]

const FUNC_PARAMS = [
  { key: 'use_xg_comparison + xg_attr1/2 + op + cmp + Wert', desc: 'Vergleich/Differenz (vs − + × ÷ · ≥ ≤ > < = ≠)', status: 'done' },
  { key: 'use_percentile + percentile_value + percentile_metric', desc: 'Top-X% nach Chance / Rating / Diff / xG / Quote / xROI / Profit', status: 'done' },
]

const ANALYSIS_PLANNED = [
  {
    key: 'opening_columns',
    desc: 'Unter Analyse: Opening-Quoten-Spalten Home · Draw · Away · Over 2.5 · Under 2.5',
    status: 'planned',
  },
  {
    key: 'outcome_under_columns',
    desc: 'Unter jeder Spalte: Anteil/Anzahl wie oft Home gewonnen, Unentschieden, Away, Over, Under',
    status: 'planned',
  },
  {
    key: 'roi_profit_opening_per_market',
    desc: 'Pro Markt (H/D/A/O/U): ROI und Profit, wenn mit Opening-Quote gewettet würde',
    status: 'planned',
  },
  {
    key: 'equity_chart_selected_markets',
    desc: 'Grafik: kumulierter Profit über Historie — nur für die gewählten Märkte',
    status: 'partial',
  },
  {
    key: 'equity_open_vs_close',
    desc: 'Equity-Linien Opening vs Closing (aktuell schon im Strategie-Tab)',
    status: 'done',
  },
  {
    key: 'outcome_pct_1x2_ou',
    desc: 'Ergebnis-% Home/Draw/Away/Over/Under über gefilterte Spiele',
    status: 'done',
  },
]

const MORE_IDEAS = [
  { key: 'expected_value', desc: 'EV = Chance × Quote − 1 (pro Wette / Ø)', status: 'planned' },
  { key: 'kelly', desc: 'Kelly-Stake aus Chance und Quote', status: 'planned' },
  { key: 'sharpe_yield', desc: 'Yield, Sharpe, Profit-Faktor', status: 'planned' },
  { key: 'value_vs_glicko_p', desc: 'Value-Bets: Marktquote vs Glicko-P', status: 'planned' },
  { key: 'calibration', desc: 'Kalibrierung Chance vs tatsächliche Hitrate', status: 'planned' },
]

export default function FeaturesPage() {
  return (
    <div className="main features-page">
      <div className="toolbar">
        <div>
          <h1 className="page-title">Features</h1>
          <p className="page-sub">
            Alle Strategie-Parameter und geplante Analyse-Anzeigen — Übersicht, noch nicht alles gebaut
          </p>
        </div>
      </div>

      <section className="stat-section">
        <div className="stat-section-head">
          <h2>Geplante Analyse-Anzeige</h2>
          <Badge status="planned" />
        </div>
        <p className="muted" style={{ marginBottom: '0.85rem' }}>
          Nach „Analysieren“: Opening-Quoten für Home / Draw / Away / Over / Under — darunter Gewinnanteil
          (wie oft Home/Draw/Away/Over/Under), ROI + Profit bei Opening-Wette. Unten Profit-Grafik nur für
          die gewählten Märkte über die Historie.
        </p>
        <div className="feat-mock">
          <div className="feat-mock-row">
            {['Home', 'Draw', 'Away', 'Over 2.5', 'Under 2.5'].map((m) => (
              <div key={m} className="feat-mock-col">
                <div className="feat-mock-head">{m}</div>
                <div className="feat-mock-line">Open-Quote · Ø</div>
                <div className="feat-mock-line">Gewinn % · n</div>
                <div className="feat-mock-line">ROI Open</div>
                <div className="feat-mock-line">Profit Open</div>
              </div>
            ))}
          </div>
          <div className="feat-mock-chart">Profit-Kurve (nur gewählte Märkte) — chronologisch</div>
        </div>
        <ParamTable rows={ANALYSIS_PLANNED} />
      </section>

      <section className="stat-section">
        <h2>Hauptkriterien</h2>
        <ParamTable rows={MAIN_PARAMS} />
      </section>

      <section className="stat-section">
        <h2>Glicko / xG / Saison</h2>
        <ParamTable rows={GLICKO_PARAMS} />
      </section>

      <section className="stat-section">
        <h2>Funktionen (Vergleich · Percentile)</h2>
        <ParamTable rows={FUNC_PARAMS} />
      </section>

      <section className="stat-section">
        <h2>Weitere Ideen</h2>
        <ParamTable rows={MORE_IDEAS} />
      </section>
    </div>
  )
}
