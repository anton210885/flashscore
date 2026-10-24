import { useState } from 'react'

/** Strategie-Name, eingefärbt nach Profit (rot = Verlust, grün = Gewinn), mit farbigem
 * Hover-Fenster: Backtest + Verifikation (Profit, ROI, aktuelle/max. Serien).
 * Position fixed — wird von scrollenden Tabellen nicht abgeschnitten. Antippen öffnet/schließt (Handy). */

function n(v, digits = 2) {
  if (v == null || v === '' || !Number.isFinite(Number(v))) return '—'
  return Number(v).toLocaleString('de-DE', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

const signed = (v, digits = 2) =>
  v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) > 0 ? '+' : ''}${n(v, digits)}`

const tone = (v) => (v == null ? '' : Number(v) > 0 ? 'pos' : Number(v) < 0 ? 'neg' : '')

function Current({ losing, winning }) {
  if (losing > 0) return <span className="neg">−{losing} verloren in Folge</span>
  if (winning > 0) return <span className="pos">+{winning} gewonnen in Folge</span>
  return <span>0</span>
}

function Block({ title, s }) {
  return (
    <div className="strat-pop-block">
      <div className="strat-pop-title">{title}</div>
      <div>
        {n(s.n, 0)} Wetten{s.open ? ` (${s.open} offen)` : ''} · Profit{' '}
        <b className={tone(s.profit)}>{signed(s.profit)}</b> · ROI{' '}
        <b className={tone(s.roi)}>{s.roi == null ? '—' : `${signed(s.roi, 1)} %`}</b>
      </div>
      {s.losing != null || s.winning != null ? (
        <div>
          aktuelle Serie: <Current losing={s.losing || 0} winning={s.winning || 0} />
        </div>
      ) : null}
      <div>
        max. Serie: <span className="neg">−{n(s.maxLose, 0)}</span> / <span className="pos">+{n(s.maxWin, 0)}</span>
        {s.medLose != null || s.medWin != null ? (
          <span className="muted">
            {' '}
            · typisch −{n(s.medLose, 1)} / +{n(s.medWin, 1)}
          </span>
        ) : null}
      </div>
    </div>
  )
}

/** Backtest-Kennzahlen (history_stats) → einheitliche Form */
export function fromHistory(h) {
  if (!h) return null
  return {
    n: h.n_bets,
    profit: h.profit,
    roi: h.roi_pct,
    losing: h.current_losing_streak ?? h.losing_streak,
    winning: h.current_winning_streak ?? h.winning_streak,
    maxLose: h.max_losing_streak,
    maxWin: h.max_winning_streak,
    medLose: h.median_losing_streak,
    medWin: h.median_winning_streak,
  }
}

/** Verifikations-Kennzahlen (Zusammenfassung pro Strategie) → einheitliche Form */
export function fromForward(s) {
  if (!s || !s.bets) return null
  return {
    n: s.bets,
    open: s.open,
    profit: s.profit,
    roi: s.roi_pct,
    losing: s.losing_streak,
    winning: s.winning_streak,
    maxLose: s.max_losing_streak,
    maxWin: s.max_winning_streak,
  }
}

/**
 * name      Strategie-Name
 * backtest  fromHistory(...) oder null
 * forward   fromForward(...) oder null
 * forwardTitle  Überschrift des Vorwärts-Blocks (z. B. „Verifikation (Swisslos-Quoten)“)
 * colorBy   Profit, nach dem der Name eingefärbt wird (Standard: Vorwärts-, sonst Backtest-Profit)
 */
export default function StrategyHover({ name, backtest, forward, forwardTitle = 'Verifikation (ab Start)', colorBy }) {
  const [pos, setPos] = useState(null)
  const basis = colorBy !== undefined ? colorBy : forward?.profit ?? backtest?.profit
  const open = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const width = 320
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8))
    const below = r.bottom + 6
    // Unten zu wenig Platz → über dem Namen anzeigen
    const top = below + 190 > window.innerHeight ? Math.max(8, r.top - 196) : below
    setPos({ left, top, width })
  }
  return (
    <span
      className={`strat-hover ${tone(basis)}`}
      onMouseEnter={open}
      onMouseLeave={() => setPos(null)}
      onClick={(e) => (pos ? setPos(null) : open(e))}
    >
      {name}
      {pos ? (
        <span className="strat-pop" style={{ left: pos.left, top: pos.top, width: pos.width }}>
          <span className={`strat-pop-name ${tone(basis)}`}>{name}</span>
          {backtest ? (
            <Block title="Backtest (gesamte Vergangenheit)" s={backtest} />
          ) : (
            <span className="muted">Backtest: noch keine Werte</span>
          )}
          {forward ? <Block title={forwardTitle} s={forward} /> : null}
        </span>
      ) : null}
    </span>
  )
}
