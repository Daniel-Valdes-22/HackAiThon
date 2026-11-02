import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useFetch } from '../hooks.js'
import { Bar, Check, Spinner, ErrorBox } from '../components/ui.jsx'

export default function ArtifactView({ id }) {
  const { data: art, setData, error } = useFetch(() => api.artifact(id), [id], {
    interval: 2000,
    until: (d) => d.status !== 'building',
  })
  const [done, setDone] = useState([])
  const [toast, setToast] = useState(null)
  const saveTimer = useRef()

  useEffect(() => {
    if (art?.status === 'ready') setDone(art.completed || [])
  }, [art?.status, art?.id])

  if (error && !art) return <ErrorBox>{error}</ErrorBox>
  if (!art || art.status === 'building') {
    return <Spinner label="Ember is building your plan — researching details and laying out every step…" />
  }
  if (art.status === 'failed') return <ErrorBox>{art.error || 'Could not build this plan.'}</ErrorBox>

  const c = art.content
  const xpMap = c.xp_map || {}
  const earned = computeXp(art.kind, c, done)

  const flash = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2600)
  }

  const toggle = (itemId, on) => {
    const next = on ? [...done, itemId] : done.filter((x) => x !== itemId)
    setDone(next)
    if (on) {
      flash(`+${xpMap[itemId] ?? 0} XP`)
      if (art.kind === 'goal') {
        const lvl = c.levels.find((l) => l.quests.some((q) => q.id === itemId))
        if (lvl && lvl.quests.every((q) => next.includes(q.id))) {
          setTimeout(() => flash(`🏆 ${lvl.name} cleared! +${lvl.bonus_xp} bonus XP`), 700)
        }
      }
    }
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      api.saveProgress(art.id, next).catch(() => flash('Could not save progress'))
    }, 250)
  }

  const pct = c.total_xp ? (earned / c.total_xp) * 100 : 0

  return (
    <div>
      {toast && <div className="toast">{toast}</div>}
      <p className="eyebrow">{art.kind === 'goal' ? `🎯 ${c.hero_class || 'Quest line'}` : '🏎️ Outing plan'}</p>
      <h1>{c.title}</h1>
      <p className="lead">{c.intro}</p>
      <div className="xp-panel">
        <div className="stat-top">
          <b>{earned} / {c.total_xp} XP</b>
          <span className="muted">{Math.round(pct)}% complete</span>
        </div>
        <Bar pct={pct} />
      </div>
      {art.kind === 'goal'
        ? <GoalBoard c={c} done={done} toggle={toggle} pct={pct} />
        : <ActivityBoard c={c} done={done} toggle={toggle} />}
    </div>
  )
}

function computeXp(kind, c, done) {
  const set = new Set(done)
  let xp = Object.entries(c.xp_map || {}).reduce((s, [k, v]) => s + (set.has(k) ? v : 0), 0)
  if (kind === 'goal') {
    for (const l of c.levels || []) {
      if (l.quests.length && l.quests.every((q) => set.has(q.id))) xp += l.bonus_xp || 0
    }
  }
  return xp
}

const TYPE_ICON = { learn: '📘', practice: '🛠️', milestone: '🚩', boss: '🐉' }

function GoalBoard({ c, done, toggle, pct }) {
  const firstOpen = c.levels.findIndex((l) => !l.quests.every((q) => done.includes(q.id)))
  return (
    <div className="board">
      <div className="levels">
        {c.levels.map((l, i) => {
          const total = l.quests.length
          const n = l.quests.filter((q) => done.includes(q.id)).length
          const cleared = n === total && total > 0
          const locked = firstOpen !== -1 && i > firstOpen && n === 0
          return (
            <section key={l.id} className={'level' + (cleared ? ' cleared' : '') + (i === firstOpen ? ' current' : '') + (locked ? ' locked' : '')}>
              <header>
                <span className="level-num">{cleared ? '🏆' : locked ? '🔒' : '⚔️'}</span>
                <div>
                  <h3>{l.name}</h3>
                  <p className="muted small">{l.description}</p>
                </div>
                <span className="level-count">{n}/{total}</span>
              </header>
              <div className="quests">
                {l.quests.map((q) => (
                  <div key={q.id} className={'quest' + (done.includes(q.id) ? ' done' : '')}>
                    <Check checked={done.includes(q.id)} onChange={(on) => toggle(q.id, on)} xp={q.xp}>
                      <b>{TYPE_ICON[q.type] || '•'} {q.title}</b>
                      <span className="quest-desc">{q.description}</span>
                      <span className="muted small">
                        {q.est_time && <>⏱ {q.est_time}</>}
                        {(q.resources || []).filter((r) => r.url).map((r) => (
                          <a key={r.url} href={r.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                            {' '}· ↗ {r.title || r.url}
                          </a>
                        ))}
                      </span>
                    </Check>
                  </div>
                ))}
              </div>
              {l.boss && <p className="boss">🐉 <b>Level boss:</b> {l.boss}</p>}
            </section>
          )
        })}
      </div>

      <aside className="side">
        {c.achievements?.length > 0 && (
          <div className="card">
            <h4>Achievements</h4>
            <p className="muted small">Unlock as you progress.</p>
            {c.achievements.map((a, i) => {
              const unlocked = i === 0 ? pct > 0 : pct >= ((i + 1) / c.achievements.length) * 100 - 0.01
              return (
                <div key={i} className={'ach' + (unlocked ? ' on' : '')}>
                  <span>{unlocked ? a.icon || '🏅' : '🔒'}</span>
                  <div><b>{a.name}</b><span className="muted small">{a.description}</span></div>
                </div>
              )
            })}
          </div>
        )}
        {c.weekly_rhythm?.length > 0 && <ListCard title="Weekly rhythm" items={c.weekly_rhythm} />}
        {c.budget_breakdown?.length > 0 && <BudgetCard rows={c.budget_breakdown} />}
        {c.tips?.length > 0 && <ListCard title="Ember's tips" items={c.tips} />}
      </aside>
    </div>
  )
}

function ActivityBoard({ c, done, toggle }) {
  const groups = {}
  for (const it of c.checklist || []) (groups[it.group] ||= []).push(it)
  return (
    <div className="board">
      <div className="levels">
        {c.best_time && <p className="callout">🕒 <b>Best time:</b> {c.best_time}</p>}

        {c.venues?.length > 0 && (
          <section className="card">
            <h3>Where to go</h3>
            {c.venues.map((v, i) => (
              <div key={i} className="venue">
                <b>{v.url ? <a href={v.url} target="_blank" rel="noreferrer">{v.name} ↗</a> : v.name}</b>
                <span className="muted small">{[v.address, v.price].filter(Boolean).join(' · ')}</span>
                {v.why && <p>{v.why}</p>}
              </div>
            ))}
          </section>
        )}

        {c.itinerary?.length > 0 && (
          <section className="card">
            <h3>Itinerary</h3>
            <ol className="timeline">
              {c.itinerary.map((s, i) => (
                <li key={i}>
                  <span className="time">{s.time}</span>
                  <div><b>{s.title}</b><p>{s.details}</p></div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {Object.entries(groups).map(([g, items]) => (
          <section className="card" key={g}>
            <h3>{g}</h3>
            {items.map((it) => (
              <Check key={it.id} checked={done.includes(it.id)} onChange={(on) => toggle(it.id, on)} xp={it.xp}>
                <span className="strike">{it.text}</span>
              </Check>
            ))}
          </section>
        ))}

        {c.side_quests?.length > 0 && (
          <section className="card">
            <h3>🎲 Side quests</h3>
            {c.side_quests.map((s) => (
              <Check key={s.id} checked={done.includes(s.id)} onChange={(on) => toggle(s.id, on)} xp={s.xp}>
                <span className="strike">{s.title}</span>
              </Check>
            ))}
          </section>
        )}
      </div>

      <aside className="side">
        {c.budget?.length > 0 && <BudgetCard rows={c.budget} total={c.budget_total} />}
        {c.safety?.length > 0 && <ListCard title="⚠️ Safety" items={c.safety} />}
        {c.group_tips?.length > 0 && <ListCard title="Group tips" items={c.group_tips} />}
        {c.backup_plan && (
          <div className="card"><h4>Backup plan</h4><p>{c.backup_plan}</p></div>
        )}
      </aside>
    </div>
  )
}

function ListCard({ title, items }) {
  return (
    <div className="card">
      <h4>{title}</h4>
      <ul className="ticks">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </div>
  )
}

function BudgetCard({ rows, total }) {
  return (
    <div className="card">
      <h4>Budget</h4>
      <table className="budget">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}><td>{r.label}</td><td>{r.cost}</td></tr>
          ))}
          {total && <tr className="total"><td>Total</td><td>{total}</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
