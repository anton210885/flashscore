/** Hover-Text zu einer Strategie: Profit, aktuelle Serie, Max-Serien (Backtest + Verifikation). */

function n(v, digits = 2) {
  if (v == null || v === '' || !Number.isFinite(Number(v))) return '—'
  return Number(v).toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

const signed = (v, digits = 2) =>
  v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) > 0 ? '+' : ''}${n(v, digits)}`

/** „−3 verloren in Folge“ / „+2 gewonnen in Folge“ */
function current(losing, winning) {
  if (losing > 0) return `−${losing} (verloren in Folge)`
  if (winning > 0) return `+${winning} (gewonnen in Folge)`
  return '0'
}

function historyLines(h) {
  if (!h) return ['Backtest: noch keine Werte (nächste Prüfung abwarten oder „Jetzt prüfen“)']
  const lines = [
    `Backtest (gesamte Vergangenheit): ${n(h.n_bets, 0)} Wetten · Profit ${signed(h.profit)} · ROI ${signed(h.roi_pct, 1)} %`,
  ]
  if (h.current_losing_streak != null || h.current_winning_streak != null) {
    lines.push(`  aktuelle Serie: ${current(h.current_losing_streak || 0, h.current_winning_streak || 0)}`)
  }
  lines.push(`  max. Serie: −${n(h.max_losing_streak, 0)} verloren · +${n(h.max_winning_streak, 0)} gewonnen`)
  if (h.median_losing_streak != null || h.median_winning_streak != null) {
    lines.push(
      `  typische Serie (Median): −${n(h.median_losing_streak, 1)} · +${n(h.median_winning_streak, 1)}`,
    )
  }
  return lines
}

/** s = Zeile aus /api/verification → summary (backtest + Vorwärts-Kennzahlen) */
export function strategyTooltipFromSummary(name, s) {
  if (!s) return name
  const lines = [name, ...historyLines(s.backtest)]
  if (s.bets) {
    lines.push(
      `Verifikation (ab Start): ${s.bets} Wetten (${s.open} offen) · Profit ${signed(s.profit)} · ROI ${signed(s.roi_pct, 1)} %`,
      `  aktuelle Serie: ${current(s.losing_streak || 0, s.winning_streak || 0)}`,
      `  max. Serie: −${n(s.max_losing_streak, 0)} verloren · +${n(s.max_winning_streak, 0)} gewonnen`,
    )
  }
  return lines.join('\n')
}

/** h = Backtest-Kennzahlen aus dem Upcoming-Überblick (/api/strategy/presets/upcoming) */
export function strategyTooltipFromHistory(name, h) {
  if (!h) return name
  return [name, ...historyLines({
    ...h,
    current_losing_streak: h.current_losing_streak ?? h.losing_streak,
    current_winning_streak: h.current_winning_streak ?? h.winning_streak,
  })].join('\n')
}
