import { useEffect, useState } from 'react'
import { api } from '../api'
import LeagueTable from '../components/LeagueTable'
import DetailPanel from '../components/DetailPanel'

export default function EuropeanPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [metric, setMetric] = useState('25')
  const [onlyToday, setOnlyToday] = useState(false)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    setLoading(true)
    api
      .european()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Lade European Competitions…</div>
  if (error) return <div className="error">Fehler: {error}</div>

  return (
    <div className="layout">
      <div className="main">
        <div className="toolbar">
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
