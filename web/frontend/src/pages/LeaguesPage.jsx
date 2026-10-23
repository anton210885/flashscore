import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { api } from '../api'
import LeagueTable from '../components/LeagueTable'
import DetailPanel from '../components/DetailPanel'

const GROUPS = [
  {
    key: 'meisterschaften',
    path: 'meisterschaften',
    label: 'Meisterschaften',
    hint: 'Saison 26/27 — Start 2026, Ende 2027',
  },
  {
    key: 'liga128',
    path: 'liga128',
    label: 'Liga 128',
    hint: 'Kalenderjahr 2026 — Start und Ende im selben Jahr',
  },
  {
    key: 'european',
    path: 'european',
    label: 'European',
    hint: 'UEFA Club-Wettbewerbe',
  },
]

function LeagueGroupView() {
  const { groupKey } = useParams()
  const group = GROUPS.find((g) => g.path === groupKey) || GROUPS[0]
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [metric, setMetric] = useState('25')
  const [onlyToday, setOnlyToday] = useState(false)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let cancelled = false
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 120000)
    setLoading(true)
    setError('')
    setSelected(null)
    api
      .leaguesGroup(group.key, undefined, ctrl.signal)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => {
        if (cancelled) return
        const msg =
          e?.name === 'AbortError'
            ? 'Timeout — Ligen-Laden dauerte zu lange. API neu starten und Seite aktualisieren.'
            : e.message
        setError(msg)
      })
      .finally(() => {
        clearTimeout(timer)
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [group.key])

  if (loading) {
    return (
      <div className="loading">
        Lade {group.label}… (viele Ligen, kann 20–60 s dauern)
      </div>
    )
  }
  if (error) return <div className="error">Fehler: {error}</div>

  return (
    <div className={`layout ${selected ? 'layout-with-detail' : ''}`}>
      <div className="main">
        <div className="toolbar" style={{ justifyContent: 'space-between' }}>
          <div>
            <div className="page-title" style={{ fontSize: '1.05rem' }}>
              {data?.label || group.label}
            </div>
            <div className="page-sub">{group.hint}</div>
          </div>
          <div className="toolbar" style={{ marginBottom: 0 }}>
            <div className="metric-tabs">
              {['25', '35', '45'].map((m) => (
                <button
                  key={m}
                  type="button"
                  className={metric === m ? 'active' : ''}
                  onClick={() => setMetric(m)}
                >
                  Over {m[0]}.{m[1]}
                </button>
              ))}
            </div>
            <label>
              <input
                type="checkbox"
                checked={onlyToday}
                onChange={(e) => setOnlyToday(e.target.checked)}
              />
              nur Heute offen
            </label>
          </div>
        </div>
        <LeagueTable
          leagues={data?.leagues || []}
          years={data?.years || []}
          metric={metric}
          selectedId={selected?.id}
          onSelect={setSelected}
          onlyToday={onlyToday}
        />
      </div>
      <DetailPanel selection={selected} metric={metric} />
    </div>
  )
}

export default function LeaguesPage() {
  return (
    <div className="leagues-hub">
      <div className="subnav">
        {GROUPS.map((g) => (
          <NavLink key={g.key} to={`/ligen/${g.path}`} className={({ isActive }) => (isActive ? 'active' : '')}>
            {g.label}
          </NavLink>
        ))}
      </div>
      <Routes>
        <Route index element={<Navigate to="meisterschaften" replace />} />
        <Route path=":groupKey" element={<LeagueGroupView />} />
      </Routes>
    </div>
  )
}
