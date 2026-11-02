import React from 'react'
import { useFetch, go, levelInfo } from '../hooks.js'
import { api } from '../api.js'
import { Bar } from '../components/ui.jsx'

export default function Dashboard() {
  const { data: profile } = useFetch(() => api.profile(), [])
  const { data: stats } = useFetch(() => api.stats(), [])
  const { data: artifacts } = useFetch(() => api.artifacts(), [])
  const { data: requests } = useFetch(() => api.requests(), [])
  const lv = levelInfo(stats?.xp ?? 0)
  const name = profile?.name || 'adventurer'

  return (
    <div>
      <section className="hero">
        <div>
          <p className="eyebrow">Welcome back</p>
          <h1>Hey {name}. What are we going after?</h1>
          <p className="muted">
            Tell me your aim or your itch. I'll check what I remember about you, search the web, and
            bring back real plans to pick from.
          </p>
          {!profile?.name && (
            <p className="nudge">
              👋 I don't know you yet — <a href="#/me">introduce yourself</a> so my plans fit you.
            </p>
          )}
        </div>
        <div className="stat-card">
          <div className="stat-top">
            <span className="stat-level">Level {lv.level}</span>
            <span className="muted">{stats?.xp ?? 0} XP</span>
          </div>
          <Bar pct={lv.pct} />
          <div className="stat-row">
            <div><b>{stats?.goals ?? 0}</b><span>quests</span></div>
            <div><b>{stats?.activities ?? 0}</b><span>outings</span></div>
            <div><b>{stats?.memories ?? 0}</b><span>memories</span></div>
          </div>
        </div>
      </section>

      <section className="choice-grid">
        <button className="choice goal" onClick={() => go('/new/goal')}>
          <span className="choice-emoji">🎯</span>
          <h2>I have a Goal</h2>
          <p>A specific aim — chess rating, pilot's license, CDL, a marathon. I build a gamified quest line.</p>
          <span className="choice-cta">Start a goal →</span>
        </button>
        <button className="choice activity" onClick={() => go('/new/activity')}>
          <span className="choice-emoji">🏎️</span>
          <h2>I want an Activity</h2>
          <p>Something to go do — off-roading, paintball, go-karts, hunting. I find real places and plan the day.</p>
          <span className="choice-cta">Plan an activity →</span>
        </button>
      </section>

      <section>
        <h3 className="section-title">Your quests &amp; outings</h3>
        {!artifacts?.length && <p className="muted">Nothing yet. Pick a card above to start your first one.</p>}
        <div className="list">
          {(artifacts || []).map((a) => (
            <a key={a.id} href={`#/artifact/${a.id}`} className="list-item">
              <span className="li-emoji">{a.kind === 'goal' ? '🎯' : '🏎️'}</span>
              <div className="li-main">
                <b>{a.title}</b>
                {a.status === 'ready' ? (
                  <>
                    <Bar pct={a.total_xp ? (a.xp_earned / a.total_xp) * 100 : 0} />
                    <span className="muted small">{a.xp_earned} / {a.total_xp} XP · {a.done}/{a.items} done</span>
                  </>
                ) : (
                  <span className="muted small">{a.status === 'failed' ? 'Failed to build' : 'Building…'}</span>
                )}
              </div>
            </a>
          ))}
        </div>
      </section>

      {requests?.some((r) => !r.artifact_id) && (
        <section>
          <h3 className="section-title">Plans waiting for you</h3>
          <div className="list">
            {requests.filter((r) => !r.artifact_id && r.status !== 'failed').map((r) => (
              <a key={r.id} href={`#/request/${r.id}`} className="list-item">
                <span className="li-emoji">{r.kind === 'goal' ? '🎯' : '🏎️'}</span>
                <div className="li-main">
                  <b>{r.kind === 'goal' ? r.params.goal : r.params.recreation}</b>
                  <span className="muted small">
                    {r.status === 'ready' ? 'Plans ready — choose one' : 'Ember is working…'}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
