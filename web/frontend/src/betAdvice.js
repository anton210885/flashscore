/** Gemeinsame Logik für Wett-Assistent und Swisslos-App. */

export function num(v, digits = 2) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n)
    ? n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : '—'
}

export const signed = (v, digits = 2) =>
  v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) > 0 ? '+' : ''}${num(v, digits)}`

export const fmtKickoff = (d) => String(d || '').slice(0, 16).replace('T', ' ')

/** Pinnacle-Vergleichsquote: Closing (vor Anpfiff aufgefrischt), sonst Quote laut Strategie */
export const pinnacleOdds = (b) => b.odds_closing || b.odds_used

/** Empfehlung: setzen, wenn Swisslos-Liga, Quote vorhanden und nicht zu weit unter Pinnacle. */
export function advice(b, maxShortfall) {
  if (!b.swisslos) return { key: 'no_sl', text: 'Liga nicht bei Swisslos', tone: 'muted' }
  if (!b.odds_swisslos) return { key: 'no_odds', text: 'Swisslos-Quote fehlt noch', tone: 'muted' }
  const pin = pinnacleOdds(b)
  const diff = pin ? (b.odds_swisslos / pin - 1) * 100 : null
  if (diff != null && diff < -maxShortfall) {
    return { key: 'low', text: `Quote zu tief (${num(diff, 1)} %)`, tone: 'neg', diff }
  }
  return { key: 'bet', text: 'setzen', tone: 'pos', diff }
}

/** Einstellungen des Assistenten (gleich in Wett-Assistent und Swisslos-App) */
export function readSetting(key, fallback) {
  try {
    const v = localStorage.getItem(`assistant.${key}`)
    return v == null ? fallback : JSON.parse(v)
  } catch {
    return fallback
  }
}

export function writeSetting(key, value) {
  try {
    localStorage.setItem(`assistant.${key}`, JSON.stringify(value))
  } catch {
    // privater Modus o. ä. — Einstellung gilt dann nur bis zum Neuladen
  }
}

/** Offene Wette noch vor Anpfiff (laut Live-Stand aus dem Sync) */
export const notStarted = (b) => b.settled_at == null && (!b.live || b.live.phase === 'scheduled')

/** Kennzahlen einer Wetten-Liste mit gegebenem Profit-Feld; Serie nach Datum (Verlust = Profit <= 0). */
export function stats(rows, profitKey = 'profit') {
  const done = rows.filter((b) => b[profitKey] != null)
  const won = done.filter((b) => Number(b[profitKey]) > 0).length
  const profit = done.reduce((s, b) => s + (Number(b[profitKey]) || 0), 0)
  let lose = 0
  let win = 0
  let maxLose = 0
  let maxWin = 0
  for (const b of [...done].sort((a, c) => String(a.date).localeCompare(String(c.date)))) {
    if (Number(b[profitKey]) > 0) {
      win += 1
      lose = 0
    } else {
      lose += 1
      win = 0
    }
    maxLose = Math.max(maxLose, lose)
    maxWin = Math.max(maxWin, win)
  }
  return {
    n: rows.length,
    settled: done.length,
    open: rows.length - done.length,
    won,
    lost: done.length - won,
    profit,
    roi: done.length ? (profit / done.length) * 100 : null,
    losing: lose,
    winning: win,
    maxLose,
    maxWin,
  }
}
