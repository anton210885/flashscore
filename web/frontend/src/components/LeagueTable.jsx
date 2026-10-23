import { useMemo, useState } from 'react'

function fmtDiff(v) {
  if (v == null || Number.isNaN(v)) return 'N/A'
  const n = Number(v)
  const cls = n > 0 ? 'diff-pos' : n < 0 ? 'diff-neg' : ''
  const arrow = n > 0 ? '▲' : n < 0 ? '▼' : '·'
  return <span className={cls}>{arrow}{n > 0 ? '+' : ''}{n.toFixed(1)}%</span>
}

function streakCell(v) {
  const n = Number(v) || 0
  if (!n) return <span className="badge empty">0</span>
  // Under-Serie (aktuell): je länger, desto auffälliger
  const cls = n >= 5 ? 'diff-neg' : n >= 3 ? 'diff-pos' : ''
  return <span className={cls}>{n}</span>
}

export default function LeagueTable({
  leagues,
  years,
  metric,
  selectedId,
  onSelect,
  onlyToday,
}) {
  const [sortKey, setSortKey] = useState('today')
  const [sortDir, setSortDir] = useState('desc')
  const [q, setQ] = useState('')

  const prefix = metric === '35' ? 'over35' : metric === '45' ? 'over45' : 'over25'
  const streakKey = metric === '35' ? 'streak35_2026' : metric === '45' ? 'streak45_2026' : 'streak25_2026'
  const avgKey = metric === '35' ? 'avg_over35' : metric === '45' ? 'avg_over45' : 'avg_over25'
  const diffKey = metric === '35' ? 'diff_over35' : metric === '45' ? 'diff_over45' : 'diff_over25'
  const yearsRev = [...(years || [])].reverse()

  const filtered = useMemo(() => {
    let rows = leagues || []
    const query = q.trim().toLowerCase()
    if (query) {
      rows = rows.filter(
        (r) =>
          String(r.name || '').toLowerCase().includes(query) ||
          String(r.country || '').toLowerCase().includes(query) ||
          String(r.id).includes(query) ||
          String(r.source_id || '').includes(query),
      )
    }
    if (onlyToday) rows = rows.filter((r) => (r.today || 0) > 0)

    const dir = sortDir === 'asc' ? 1 : -1
    rows = [...rows].sort((a, b) => {
      let av = a[sortKey]
      let bv = b[sortKey]
      if (sortKey.startsWith('over') || sortKey.startsWith('avg') || sortKey.startsWith('last')) {
        av = parseFloat(String(av || '0').replace('%', '')) || 0
        bv = parseFloat(String(bv || '0').replace('%', '')) || 0
      } else {
        av = typeof av === 'number' ? av : parseFloat(av) || 0
        bv = typeof bv === 'number' ? bv : parseFloat(bv) || 0
      }
      if (av < bv) return -1 * dir
      if (av > bv) return 1 * dir
      return 0
    })
    return rows
  }, [leagues, q, onlyToday, sortKey, sortDir])

  function toggleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir(key === 'name' || key === 'country' ? 'asc' : 'desc')
    }
  }

  return (
    <>
      <div className="toolbar">
        <input
          placeholder="Suche Land / Liga / ID…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
          {filtered.length} Zeilen
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('country')}>Land</th>
              <th onClick={() => toggleSort('id')}>ID</th>
              <th onClick={() => toggleSort('name')}>Liga</th>
              <th className="num" onClick={() => toggleSort('today')}>Heute</th>
              <th className="num" onClick={() => toggleSort('games_2026')}>Spiele</th>
              <th className="num" onClick={() => toggleSort(streakKey)}>Streak</th>
              {yearsRev.map((y) => (
                <th key={y} className="num" onClick={() => toggleSort(`${prefix}_${y}`)}>
                  O{label(metric)} '{String(y).slice(2)}
                </th>
              ))}
              <th className="num" onClick={() => toggleSort(`last10_${prefix}_2026`)}>L10</th>
              <th className="num" onClick={() => toggleSort(avgKey)}>Avg</th>
              <th className="num" onClick={() => toggleSort(diffKey)}>Diff</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const rid = row.id
              const isSel = selectedId === rid
              const isPhase = row.phase && row.phase !== 'all'
              return (
                <tr
                  key={rid}
                  className={`${isSel ? 'selected' : ''} ${row.today ? 'today' : ''}`}
                  onClick={() => onSelect(row)}
                >
                  <td>{row.country}</td>
                  <td className="num">{row.source_id || row.id}</td>
                  <td className={isPhase ? 'phase-indent' : ''}>{row.name}</td>
                  <td className="num">
                    {row.today > 0 ? (
                      <span className="badge today">Ja · {row.today}</span>
                    ) : (
                      <span className="badge empty">—</span>
                    )}
                  </td>
                  <td className="num">{row.games_2026 ?? 0}</td>
                  <td className="num">{streakCell(row[streakKey])}</td>
                  {yearsRev.map((y) => (
                    <td key={y} className="num">
                      {row[`${prefix}_${y}`] ?? '0.0%'}
                    </td>
                  ))}
                  <td className="num">{row[`last10_${prefix}_2026`] ?? '0.0%'}</td>
                  <td className="num">{row[avgKey] ?? 'N/A'}</td>
                  <td className="num">{fmtDiff(row[diffKey])}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

function label(metric) {
  if (metric === '35') return '3.5'
  if (metric === '45') return '4.5'
  return '2.5'
}
