/** Änderungsverlauf gespeicherter Strategien (Version/Änderungen führt der Server). */
import { metricName } from './metricNames'

export const fmtDay = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? String(iso).slice(0, 10)
    : d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function value(v) {
  if (v == null) return '—'
  if (Array.isArray(v)) {
    return v
      .map((c) =>
        c && typeof c === 'object'
          ? `${metricName(c.attr1, c.attr1)} ${c.operation} ${metricName(c.attr2, c.attr2)} ${c.comparison_operator} ${c.comparison_value}`
          : String(c),
      )
      .join('; ')
  }
  if (typeof v === 'boolean') return v ? 'an' : 'aus'
  return typeof v === 'string' ? metricName(v, v) : String(v)
}

/** „odds_away_max: 1.3 → 1.4“ */
export const changeLine = (c) => `${c.key}: ${value(c.old)} → ${value(c.new)}`

/** Mehrzeiliger Hover-Text: alle Versionen mit ihren Änderungen, neueste zuerst. */
export function historyTitle(history) {
  if (!history?.length) return 'Seit dem Speichern nicht geändert'
  return [...history]
    .reverse()
    .map((h) => [`v${h.version} · ${fmtDay(h.at)}`, ...(h.changes || []).map((c) => `  ${changeLine(c)}`)].join('\n'))
    .join('\n\n')
}
