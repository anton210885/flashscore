import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api'
import LeaguesPage from './pages/LeaguesPage'
import SstatsParamsPage from './pages/SstatsParamsPage'
import GamesPage from './pages/GamesPage'
import StatsPage from './pages/StatsPage'
import StrategyPage from './pages/StrategyPage'
import FeaturesPage from './pages/FeaturesPage'
import SettingsPage from './pages/SettingsPage'
import VerificationPage from './pages/VerificationPage'
import './App.css'

export default function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h))
      .catch(() => setHealth(false))
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          Flashscore <span>Analytics</span>
        </div>
        <nav className="nav">
          <NavLink to="/ligen">Ligen</NavLink>
          <NavLink to="/games">Spiele</NavLink>
          <NavLink to="/strategy">Strategie</NavLink>
          <NavLink to="/verification">Verifikation</NavLink>
          <NavLink to="/features">Features</NavLink>
          <NavLink to="/stats">DB Statistik</NavLink>
          <NavLink to="/sstats">SStats Params</NavLink>
        </nav>
        <div className={`status ${health ? 'ok' : ''}`}>
          {health === null ? 'API…' : health ? 'API online' : 'API offline – Backend starten'}
          {health?.version ? (
            <span className="app-version" title={`Stand: ${health.commit_date || '—'}`}>
              {' · '}
              {health.version}
            </span>
          ) : null}
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Navigate to="/ligen/meisterschaften" replace />} />
        <Route path="/ligen/*" element={<LeaguesPage />} />
        <Route path="/games" element={<GamesPage />} />
        <Route path="/strategy" element={<StrategyPage />} />
        <Route path="/verification" element={<VerificationPage />} />
        <Route path="/past" element={<Navigate to="/strategy" replace />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/european" element={<Navigate to="/ligen/european" replace />} />
        <Route path="/sstats" element={<SstatsParamsPage />} />
      </Routes>
    </div>
  )
}
