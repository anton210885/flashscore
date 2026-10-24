/** Alle Parameter eines Spiels aus der Strategie-Analyse (Klick auf „Vergangene Spiele“). */

function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

const diff = (a, b) => (a == null || b == null ? null : Number(a) - Number(b))
const sum = (a, b) => (a == null || b == null ? null : Number(a) + Number(b))
const ratio = (a, b) => (a == null || b == null || Number(b) === 0 ? null : Number(a) / Number(b))
const pct = (v) => (v == null ? '—' : `${num(Number(v) > 1 ? v : Number(v) * 100, 1)} %`)

/** Zeilen [Bezeichnung, Home, Away, Home − Away] */
function PairTable({ title, rows, colA = 'Home', colB = 'Away', showDiff = true }) {
  return (
    <div className="match-params-block">
      <h4>{title}</h4>
      <table>
        <thead>
          <tr>
            <th></th>
            <th className="num">{colA}</th>
            <th className="num">{colB}</th>
            {showDiff ? <th className="num">{colA} − {colB}</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, a, b, digits = 2]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className="num">{num(a, digits)}</td>
              <td className="num">{num(b, digits)}</td>
              {showDiff ? <td className="num">{num(diff(a, b), digits)}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function venueRows(r, team) {
  const v = (side, k) => r[`${team}_${side}_${k}`]
  return [
    ['Spiele', v('home', 'n'), v('away', 'n'), 0],
    ['Ø xG', v('home', 'xg'), v('away', 'xg')],
    ['Ø xGA', v('home', 'xga'), v('away', 'xga')],
    ['Ø Tore', v('home', 'gf'), v('away', 'gf')],
    ['Ø Gegentore', v('home', 'ga'), v('away', 'ga')],
    ['Power xG ÷ xGA', ratio(v('home', 'xg'), v('home', 'xga')), ratio(v('away', 'xg'), v('away', 'xga'))],
    ['Tempo xG + xGA', sum(v('home', 'xg'), v('home', 'xga')), sum(v('away', 'xg'), v('away', 'xga'))],
  ]
}

export default function MatchParamsPanel({ row: r, onClose }) {
  if (!r) return null
  return (
    <section className="strat-preset-upcoming match-params">
      <div className="strat-preset-upcoming-head">
        <strong>
          {String(r.date || '').slice(0, 16).replace('T', ' ')} · {r.home} – {r.away} ·{' '}
          {r.home_score}:{r.away_score}
        </strong>
        <button type="button" className="strat-corr-explain-close" onClick={onClose} aria-label="Schließen">
          ×
        </button>
      </div>
      <p className="muted" style={{ margin: '0 0 0.5rem' }}>
        {r.country || '—'} · {r.league || '—'} · Markt <strong>{r.market}</strong> · Quote {num(r.odds)} (Open{' '}
        {num(r.odds_opening)}, Close {num(r.odds_closing)}, xROI {num(r.xroi_pct, 1)} %) · Profit{' '}
        <strong className={r.profit > 0 ? 'pos' : 'neg'}>{num(r.profit)}</strong> · Chance {pct(r.chance)}
      </p>
      <div className="match-params-grid">
        <PairTable
          title="Glicko-Rating"
          rows={[
            ['Rating', r.rating_h, r.rating_a, 0],
            ['Rating-Unsicherheit (RD)', r.rd_h, r.rd_a, 1],
            ['Volatilität', r.vol_h, r.vol_a, 4],
            ['Siegwahrscheinlichkeit', r.p_home, r.p_away, 3],
          ]}
        />
        <div className="match-params-block">
          <h4>Verhältnisse</h4>
          <table>
            <tbody>
              <tr><td>Rating Home ÷ Away</td><td className="num">{num(ratio(r.rating_h, r.rating_a), 4)}</td></tr>
              <tr><td>xG Glicko Home ÷ Away</td><td className="num">{num(ratio(r.xg_glicko_h, r.xg_glicko_a), 4)}</td></tr>
              <tr><td>xG Saison Home ÷ Away</td><td className="num">{num(ratio(r.xg_form2_h, r.xg_form2_a), 4)}</td></tr>
              <tr><td>Unentschieden-Wahrscheinlichkeit</td><td className="num">{num(r.p_draw, 3)}</td></tr>
            </tbody>
          </table>
        </div>
        <PairTable
          title="xG-Vorhersagen (vor dem Spiel)"
          rows={[
            ['xG Glicko', r.xg_glicko_h, r.xg_glicko_a],
            ['xG Saison', r.xg_form2_h, r.xg_form2_a],
            ['xG Venue', r.hometeam_pred_xg, r.awayteam_pred_xg],
          ]}
        />
        <PairTable
          title="Saison-Durchschnitte (alle Spiele)"
          rows={[
            ['Saisonspiele', r.home_season_n ?? r.form2_home_n, r.away_season_n ?? r.form2_away_n, 0],
            ['Ø xG', r.form2_home_avg_xg, r.form2_away_avg_xg],
            ['Ø xGA', r.form2_home_avg_xga, r.form2_away_avg_xga],
            ['Ø Tore', r.form2_home_avg_gf, r.form2_away_avg_gf],
            ['Ø Gegentore', r.form2_home_avg_ga, r.form2_away_avg_ga],
            ['Power xG ÷ xGA', ratio(r.form2_home_avg_xg, r.form2_home_avg_xga), ratio(r.form2_away_avg_xg, r.form2_away_avg_xga), 3],
            ['Tempo xG + xGA', sum(r.form2_home_avg_xg, r.form2_home_avg_xga), sum(r.form2_away_avg_xg, r.form2_away_avg_xga)],
          ]}
        />
        <PairTable
          title={`${r.home} nach Spielort`}
          colA="Heimspiele"
          colB="Auswärtsspiele"
          showDiff={false}
          rows={venueRows(r, 'hometeam')}
        />
        <PairTable
          title={`${r.away} nach Spielort`}
          colA="Heimspiele"
          colB="Auswärtsspiele"
          showDiff={false}
          rows={venueRows(r, 'awayteam')}
        />
        <PairTable
          title="xG im Spiel (nach dem Spiel)"
          rows={[['xG Match', r.xg_h ?? r.xg_match_h, r.xg_a ?? r.xg_match_a]]}
        />
        <div className="match-params-block">
          <h4>Quoten {r.odds_opening != null ? '(laut Strategie)' : ''}</h4>
          <table>
            <tbody>
              <tr><td>Home</td><td className="num">{num(r.home_quote)}</td></tr>
              <tr><td>Draw</td><td className="num">{num(r.draw_quote)}</td></tr>
              <tr><td>Away</td><td className="num">{num(r.away_quote)}</td></tr>
              <tr><td>Over 2.5</td><td className="num">{num(r.over_25_quote)}</td></tr>
              <tr><td>Under 2.5</td><td className="num">{num(r.under_25_quote)}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
