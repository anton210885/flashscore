import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Feste Reihenfolge, geprüft gegen die dunkle Fläche (#161d27) — Farbe bleibt an der Strategie
const SERIES_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']
const ALL_ID = '__all'
const SUM_ID = '__sum'
const SUM_COLOR = '#8b9bb0'

const RANGES = [
  { key: '7', label: '7 T' },
  { key: '30', label: '30 T' },
  { key: '90', label: '90 T' },
  { key: 'all', label: 'Alle' },
  { key: 'custom', label: 'Von–bis' },
]

const GRAINS = [
  { key: 'day', label: 'pro Tag' },
  { key: 'kickoff', label: 'pro Anstoß' },
]

const STORE_KEY = 'verification.profitChart'

function loadStored() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || '{}') || {}
  } catch {
    return {}
  }
}

function fmt(v, digits = 2) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  const n = Number(v)
  const s = n.toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: digits })
  return n > 0 ? `+${s}` : s
}

const tone = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')
// „2026-10-24“ → „24.10.“, „2026-10-24T20:30“ → „24.10. 20:30“
const dayLabel = (d) => (d ? `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.length > 10 ? ` ${d.slice(11, 16)}` : ''}` : '')

function isoDay(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function shiftDay(day, delta) {
  const d = new Date(`${day}T12:00:00`)
  d.setDate(d.getDate() + delta)
  return isoDay(d)
}

function ChartTooltip({ active, payload, label, series }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="profit-tooltip">
      <div className="profit-tooltip__date">{row.start ? 'Start' : dayLabel(label)}</div>
      {series.map((s) => (
        <div key={s.id} className="profit-tooltip__row">
          <span className="profit-swatch" style={{ background: s.color }} />
          <span className="profit-tooltip__name">{s.name}</span>
          <strong className={tone(row[s.id])}>{fmt(row[s.id])}</strong>
          {!row.start && row[`${s.id}_n`] ? (
            <span className="muted">
              {' '}
              ({fmt(row[`${s.id}_d`])} · {row[`${s.id}_n`]} W.)
            </span>
          ) : null}
        </div>
      ))}
    </div>
  )
}

/** Kumulierter Profit (Einsatz 1) pro Spieltag, wahlweise pro Strategie. */
export default function ProfitChart({ bets, strategies }) {
  const [stored] = useState(loadStored)
  const [today] = useState(() => isoDay(new Date()))
  const [range, setRange] = useState(stored.range || '30')
  const [grain, setGrain] = useState(stored.grain || 'day')
  const [from, setFrom] = useState(stored.from || '')
  const [to, setTo] = useState(stored.to || '')
  // id → Farb-Slot; ein neuer Eintrag nimmt den kleinsten freien Slot
  const [slots, setSlots] = useState(stored.slots || {})

  const known = useMemo(() => new Set(strategies.map((s) => s.strategy_id)), [strategies])
  const names = useMemo(
    () => Object.fromEntries(strategies.map((s) => [s.strategy_id, s.strategy])),
    [strategies],
  )
  // Gelöschte Strategien fallen aus der Auswahl
  const activeSlots = useMemo(
    () => Object.fromEntries(Object.entries(slots).filter(([id]) => !strategies.length || known.has(id))),
    [slots, known, strategies.length],
  )
  const selected = useMemo(
    () => Object.keys(activeSlots).sort((a, b) => activeSlots[a] - activeSlots[b]),
    [activeSlots],
  )

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ range, grain, from, to, slots: activeSlots }))
    } catch {
      /* Speicher nicht verfügbar — Auswahl gilt nur bis zum Neuladen */
    }
  }, [range, grain, from, to, activeSlots])

  const toggle = (id) => {
    setSlots((prev) => {
      const next = { ...prev }
      if (id in next) {
        delete next[id]
        return next
      }
      const used = new Set(Object.values(next))
      const free = SERIES_COLORS.findIndex((_, i) => !used.has(i))
      if (free < 0) return prev
      next[id] = free
      return next
    })
  }

  const bounds = useMemo(() => {
    if (range === 'all') return { from: '', to: '' }
    if (range === 'custom') return { from, to }
    return { from: shiftDay(today, -(Number(range) - 1)), to: today }
  }, [range, from, to, today])

  const series = useMemo(() => {
    if (!selected.length) return [{ id: ALL_ID, name: 'Alle Strategien', color: SERIES_COLORS[0] }]
    const list = selected.map((id) => ({
      id,
      name: names[id] || id,
      color: SERIES_COLORS[activeSlots[id]],
    }))
    if (list.length > 1) list.push({ id: SUM_ID, name: 'Summe Auswahl', color: SUM_COLOR, dashed: true })
    return list
  }, [selected, names, activeSlots])

  const { points, stats } = useMemo(() => {
    const inSel = (b) => !selected.length || b.strategy_id in activeSlots
    const settled = bets
      .filter((b) => b.settled_at != null && inSel(b))
      .map((b) => ({ ...b, day: String(b.date || '').slice(0, 10) }))
      .filter((b) => b.day && (!bounds.from || b.day >= bounds.from) && (!bounds.to || b.day <= bounds.to))

    // Punkt = Spieltag bzw. Anstoßzeit (lokal, wie in der Wetten-Liste)
    const keyOf = (b) => (grain === 'day' ? b.day : String(b.date).slice(0, 16))
    const byDay = {}
    for (const b of settled) (byDay[keyOf(b)] ||= []).push(b)
    const days = Object.keys(byDay).sort()

    const ids = series.map((s) => s.id)
    const cum = Object.fromEntries(ids.map((id) => [id, 0]))
    const rows = []
    if (days.length) {
      const start = { day: grain === 'day' ? shiftDay(days[0], -1) : 'Start', start: true }
      for (const id of ids) start[id] = 0
      rows.push(start)
    }
    for (const day of days) {
      const row = { day }
      for (const id of ids) {
        const items = byDay[day].filter((b) =>
          id === ALL_ID || id === SUM_ID ? true : b.strategy_id === id,
        )
        const p = items.reduce((sum, b) => sum + (Number(b.profit) || 0), 0)
        cum[id] += p
        row[id] = Math.round(cum[id] * 100) / 100
        row[`${id}_d`] = p
        row[`${id}_n`] = items.length
      }
      rows.push(row)
    }
    const profit = settled.reduce((sum, b) => sum + (Number(b.profit) || 0), 0)
    const won = settled.filter((b) => b.won === 1).length
    return {
      points: rows,
      stats: {
        n: settled.length,
        won,
        profit,
        roi: settled.length ? (profit / settled.length) * 100 : null,
        days: days.length,
      },
    }
  }, [bets, bounds, grain, series, selected.length, activeSlots])

  const lastIndex = points.length - 1
  // Endbeschriftungen: gleich hohe Linien nicht übereinander schreiben — jede Linie weicht
  // den Linien vor ihr (Reihenfolge der Serien) um mind. eine Zeile aus
  const labelY = useRef({})
  const endLabel = (s, order) =>
    function EndLabel({ x, y, index, value }) {
      if (index !== lastIndex || series.length > 4) return null
      const taken = series.slice(0, order).map((p) => labelY.current[p.id]).filter((v) => v != null)
      let ly = y
      for (const t of [...taken].sort((a, b) => a - b)) if (Math.abs(ly - t) < 14) ly = t + 14
      labelY.current[s.id] = ly
      return (
        <text x={x + 6} y={ly} dy={4} fontSize={11} fill="#e8eef6">
          {s.id === ALL_ID ? fmt(value) : `${s.name} ${fmt(value)}`}
        </text>
      )
    }

  return (
    <section className="profit-chart">
      <div className="profit-chart__filters">
        <div className="detail-tabs" role="group" aria-label="Zeitraum">
          {RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              className={range === r.key ? 'active' : ''}
              onClick={() => setRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
        <div className="detail-tabs" role="group" aria-label="Auflösung">
          {GRAINS.map((g) => (
            <button
              key={g.key}
              type="button"
              className={grain === g.key ? 'active' : ''}
              onClick={() => setGrain(g.key)}
            >
              {g.label}
            </button>
          ))}
        </div>
        {range === 'custom' ? (
          <span className="profit-chart__dates">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="Von" />
            –
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} aria-label="Bis" />
          </span>
        ) : null}
        <span className="profit-chart__stats">
          {stats.n} abgerechnet · {stats.won}/{stats.n} gewonnen · Profit{' '}
          <strong className={tone(stats.profit)}>{fmt(stats.profit)}</strong> · ROI{' '}
          <strong className={tone(stats.roi)}>{stats.roi == null ? '—' : `${fmt(stats.roi, 1)}%`}</strong>
        </span>
      </div>

      <div className="profit-chart__picker" role="group" aria-label="Strategien im Diagramm">
        <button
          type="button"
          className={`profit-chip ${selected.length ? '' : 'active'}`}
          onClick={() => setSlots({})}
          title="Alle Strategien zusammen als eine Linie"
        >
          Alle zusammen
        </button>
        {strategies.map((s) => {
          const on = s.strategy_id in activeSlots
          const full = !on && selected.length >= SERIES_COLORS.length
          return (
            <button
              key={s.strategy_id}
              type="button"
              className={`profit-chip ${on ? 'active' : ''}`}
              onClick={() => toggle(s.strategy_id)}
              disabled={full}
              title={full ? 'Höchstens 8 Strategien gleichzeitig' : 'Als eigene Linie ein-/ausblenden'}
            >
              {on ? (
                <span className="profit-swatch" style={{ background: SERIES_COLORS[activeSlots[s.strategy_id]] }} />
              ) : null}
              {s.strategy}
            </button>
          )
        })}
      </div>

      {points.length < 2 ? (
        <p className="muted profit-chart__empty">Keine abgerechneten Wetten in diesem Zeitraum.</p>
      ) : (
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={points} margin={{ top: 12, right: series.length > 4 ? 16 : 150, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#2a3544" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="day"
                tickFormatter={(d) => (d === 'Start' ? d : dayLabel(d))}
                stroke="#8b9bb0"
                fontSize={12}
                minTickGap={24}
              />
              <YAxis stroke="#8b9bb0" fontSize={12} tickFormatter={(v) => fmt(v, 0)} width={48} />
              <ReferenceLine y={0} stroke="#8b9bb0" />
              <Tooltip
                content={<ChartTooltip series={series} />}
                cursor={{ stroke: '#8b9bb0', strokeDasharray: '3 3' }}
              />
              {series.map((s, i) => (
                <Line
                  key={s.id}
                  type="linear"
                  dataKey={s.id}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={2}
                  strokeDasharray={s.dashed ? '5 4' : undefined}
                  dot={false}
                  activeDot={{ r: 5, stroke: '#161d27', strokeWidth: 2 }}
                  isAnimationActive={false}
                  label={endLabel(s, i)}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          {series.length > 1 ? (
            <div className="profit-legend">
              {series.map((s) => (
                <span key={s.id}>
                  <span
                    className={`profit-swatch ${s.dashed ? 'profit-swatch--dashed' : ''}`}
                    style={{ background: s.dashed ? 'transparent' : s.color, borderColor: s.color }}
                  />
                  {s.name}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}
