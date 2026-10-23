import {
  ANALYSE_METRIC_HELP,
  CORR_COLUMN_HELP,
  CORR_METRIC_HELP,
  CORR_RULE_HELP,
  METRIKEN_HELP,
  explainCorrRow,
} from '../strategyHelp'

function num(v, d = 1) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return d === 0 ? String(Math.round(n)) : n.toFixed(d)
}

/** Erklärung einer ausgewählten Korrelations-Zeile (Alltagssprache + Filter-Hinweis). */
export function CorrRowExplainPanel({ row, onClose }) {
  const ex = explainCorrRow(row)
  if (!ex) {
    return (
      <div className="strat-corr-explain muted">
        Zeile in der Tabelle anklicken → Erklärung + Parameter-Grafik.
      </div>
    )
  }
  return (
    <div className="strat-corr-explain">
      <div className="strat-corr-explain-head">
        <strong>
          Erklärung · <code>{ex.metric}</code>
          {ex.condition ? <> · <code>{ex.condition}</code></> : null}
        </strong>
        {onClose ? (
          <button type="button" className="strat-corr-explain-close" onClick={onClose} aria-label="Schließen">
            ×
          </button>
        ) : null}
      </div>
      {ex.plain ? <p className="strat-corr-explain-plain">{ex.plain}</p> : null}
      <ul className="strat-corr-explain-list">
        <li>
          <strong>Metrik:</strong> {ex.metricDef}
        </li>
        <li>
          <strong>Regel:</strong> {ex.rulePlain}
          {ex.rule ? (
            <>
              {' '}
              (<code>{ex.rule}</code>)
            </>
          ) : null}
        </li>
        {ex.filterHint ? (
          <li>
            <strong>Filter:</strong> {ex.filterHint}
          </li>
        ) : null}
        {ex.edgeNote ? (
          <li>
            <strong>Wirkung:</strong> {ex.edgeNote} n={num(ex.n, 0)}, WR {num(ex.win_rate, 1)} %, ROI{' '}
            {num(ex.roi_pct, 1)} %.
          </li>
        ) : null}
      </ul>
    </div>
  )
}

export function CorrelationHelpPanel() {
  return (
    <details className="strat-help" open>
      <summary>Korrelation verstehen · richtig nutzen · Spalten</summary>
      <div className="strat-help-body">
        <h4 className="strat-help-h" style={{ marginTop: 0 }}>
          Was wird berechnet?
        </h4>
        <p>
          Kein klassischer Korrelationskoeffizient. Es ist ein <strong>Metric-Ranking</strong>: Ausgehend von
          deinen aktuellen Filtern (= <strong>Baseline</strong>) wird getestet, welche <em>eine</em> zusätzliche
          Schwelle auf einer Metrik den historischen ROI am stärksten verbessert hätte.
        </p>
        <ol className="strat-help-steps">
          <li>
            Alle Wetten mit deinen Filtern bilden die Baseline (n, ROI, Profit, Winrate).
          </li>
          <li>
            Für jede Metrik (Quote, Ratings, xG, xROI, …) werden Perzentil-Schwellen geprüft: Top ~30/20/10 % und
            Bottom ~30/20/10 %.
          </li>
          <li>
            Pro Schwelle entsteht eine Teilmenge → neu: n, WR, Profit, ROI.
          </li>
          <li>
            Vergleich zur Baseline: <strong>Δ ROI</strong> und <strong>Δ Profit</strong>. Sortierung wählbar (Δ ROI oder Δ Profit) ↓,
            dann Δ Profit, dann n.
          </li>
          <li>
            Zeilen mit zu kleinem n (unter min_n, oft ~40) fallen weg — sonst zu viel Zufall.
          </li>
        </ol>
        <p className="muted">
          Historisch / Look-ahead — kein Garant für die Zukunft. Es wird jeweils nur <strong>eine</strong> Metrik
          zur Zeit getestet (keine Kombi-Optimierung).
        </p>

        <h4 className="strat-help-h">So nutzt du es richtig</h4>
        <ol className="strat-help-steps">
          <li>
            Zuerst Markt + sinnvolle Basisfilter setzen → <strong>Analysieren</strong> (Baseline verstehen).
          </li>
          <li>
            Dann <strong>Korrelation berechnen</strong>. Oben stehen die stärksten Δ-ROI-Schwellen.
          </li>
          <li>
            Nicht die obersten 10 Zeilen stapeln — viele sagen dasselbe (z. B. „Away stark“ über
            rating_away, rating_diff, rating_ratio).
          </li>
          <li>
            <strong>1–2</strong> sinnvolle Schwellen wählen, als Filter übernehmen → erneut Analysieren.
            n und Δ ROI im Blick behalten (hoher ROI bei winzigem n = oft Overfit).
          </li>
          <li>
            Zeile anklicken → Alltagserklärung + Parameter-Grafik (Profit/ROI/<strong>n je Bereich</strong>).
            So siehst du, ob der Edge stabil über Bins geht oder nur ein Zufalls-Bin ist.
          </li>
          <li>
            Negative Δ-ROI-Zeilen eher meiden oder als „Gegenteil vermeiden“ lesen.
          </li>
        </ol>

        <h4 className="strat-help-h">Was zeigt jede Spalte?</h4>
        <dl className="strat-help-dl">
          {CORR_COLUMN_HELP.map((c) => (
            <div key={c.key} className="strat-help-item">
              <dt>{c.label}</dt>
              <dd>{c.text}</dd>
            </div>
          ))}
        </dl>
        <p className="muted" style={{ marginTop: '0.5rem' }}>
          Tipp: In der Tabelle auf einen Spaltenkopf zeigen → Kurzhilfe. Zeile klicken → ausführliche Erklärung.
        </p>

        <details className="strat-help-nested">
          <summary>Metriken in der Tabelle</summary>
          <dl className="strat-help-dl">
            {CORR_METRIC_HELP.map((m) => (
              <div key={m.key} className="strat-help-item">
                <dt>
                  <code>{m.label}</code>
                </dt>
                <dd>{m.text}</dd>
              </div>
            ))}
          </dl>
        </details>

        <details className="strat-help-nested">
          <summary>Regeln (Perzentile)</summary>
          <dl className="strat-help-dl">
            {CORR_RULE_HELP.map((r) => (
              <div key={r.key} className="strat-help-item">
                <dt>
                  <code>{r.key}</code>
                </dt>
                <dd>{r.text}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </details>
  )
}

export function MetrikenHelpPanel() {
  return (
    <details className="strat-help">
      <summary>Was bedeuten die Metriken?</summary>
      <div className="strat-help-body">
        <p className="muted">
          Die Werte sind <strong>Durchschnitte über die gefilterten Spiele</strong> deiner letzten Analyse
          (gleiche Parameter wie ROI/Ausgänge). Pre-match Glicko — nicht das Endergebnis.
        </p>

        <h4 className="strat-help-h">Analyse-Kennzahlen (ROI &amp; Co.)</h4>
        <dl className="strat-help-dl">
          {ANALYSE_METRIC_HELP.map((m) => (
            <div key={m.key} className="strat-help-item">
              <dt>{m.label}</dt>
              <dd>{m.text}</dd>
            </div>
          ))}
        </dl>

        <h4 className="strat-help-h">Glicko-Aggregate (dieser Tab)</h4>
        <dl className="strat-help-dl">
          {METRIKEN_HELP.map((m) => (
            <div key={m.key} className="strat-help-item">
              <dt>{m.label}</dt>
              <dd>{m.text}</dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  )
}
