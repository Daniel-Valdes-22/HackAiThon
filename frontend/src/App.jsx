import React from 'react'
import { useRoute, useFetch, go, levelInfo } from './hooks.js'
import { api } from './api.js'
import Dashboard from './views/Dashboard.jsx'
import Intake from './views/Intake.jsx'
import RequestView from './views/RequestView.jsx'
import ArtifactView from './views/ArtifactView.jsx'
import Me from './views/Me.jsx'

export default function App() {
  const parts = useRoute()
  const [page, arg] = parts
  const { data: health, error: healthErr } = useFetch(() => api.health(), [])
  const { data: stats } = useFetch(() => api.stats(), [page, arg], { interval: 0 })
  const lv = levelInfo(stats?.xp ?? 0)

  let view
  if (!page) view = <Dashboard />
  else if (page === 'new' && (arg === 'goal' || arg === 'activity')) view = <Intake kind={arg} />
  else if (page === 'request' && parts[1]) view = <RequestView id={Number(parts[1])} />
  else if (page === 'artifact' && parts[1]) view = <ArtifactView id={Number(parts[1])} />
  else if (page === 'me') view = <Me />
  else view = <Dashboard />

  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand">
          <span className="flame">🔥</span> Ember
        </a>
        <nav>
          <a href="#/" className={!page ? 'active' : ''}>Dashboard</a>
          <a href="#/me" className={page === 'me' ? 'active' : ''}>Me &amp; Memory</a>
        </nav>
        <div className="level-badge" title={`${stats?.xp ?? 0} XP`}>
          <span>LV {lv.level}</span>
          <div className="mini-bar"><div style={{ width: `${lv.pct}%` }} /></div>
        </div>
      </header>
      {healthErr && !health && (
        <div className="banner danger">
          Can't talk to the backend: {healthErr}
        </div>
      )}
      {health && !health.ai_enabled && (
        <div className="banner">
          Demo mode — no <code>ANTHROPIC_API_KEY</code> set, so plans come from offline templates (no live web search).
          Add a key to <code>backend/.env</code> and restart.
        </div>
      )}
      <main className="page">{view}</main>
      <footer className="foot">Ember remembers · plans from live web research · HackAiThon</footer>
    </div>
  )
}
