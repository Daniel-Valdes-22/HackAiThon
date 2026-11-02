import React, { useState } from 'react'
import { api } from '../api.js'
import { useFetch, go } from '../hooks.js'
import { Spinner, ErrorBox } from '../components/ui.jsx'

const STEPS = [
  { key: 'soul', label: 'Reading my soul', sub: 'Remembering who I am' },
  { key: 'memory', label: 'Recalling what I know about you', sub: 'Profile + relevant memories' },
  { key: 'research', label: 'Searching the web', sub: 'Real options, real prices' },
  { key: 'plans', label: 'Crafting your plans', sub: 'Different strategies, honest trade-offs' },
]
const ORDER = ['queued', 'soul', 'memory', 'research', 'plans', 'done']

export default function RequestView({ id }) {
  const { data: req, error } = useFetch(() => api.request(id), [id], {
    interval: 1500,
    until: (d) => d.status === 'ready' || d.status === 'failed',
  })
  const [choosing, setChoosing] = useState(null)
  const [chooseErr, setChooseErr] = useState(null)

  if (error && !req) return <ErrorBox>{error}</ErrorBox>
  if (!req) return <Spinner label="Loading…" />

  const title = req.kind === 'goal' ? req.params.goal : req.params.recreation
  const idx = ORDER.indexOf(req.stage)

  const choose = async (planId) => {
    setChoosing(planId)
    setChooseErr(null)
    try {
      const a = await api.choosePlan(planId)
      go(`/artifact/${a.id}`)
    } catch (e) {
      setChooseErr(e.message)
      setChoosing(null)
    }
  }

  return (
    <div>
      <p className="eyebrow">{req.kind === 'goal' ? '🎯 Goal' : '🏎️ Activity'}</p>
      <h1>{title}</h1>

      {req.memories_used?.length > 0 && (
        <div className="memory-strip">
          <b>🧠 Ember remembered</b>
          <ul>
            {req.memories_used.slice(0, 4).map((m) => (
              <li key={m.id}>{m.text}</li>
            ))}
          </ul>
        </div>
      )}

      {req.status === 'failed' && <ErrorBox>{req.error || 'Something went wrong.'}</ErrorBox>}

      {(req.status === 'queued' || req.status === 'running') && (
        <ol className="steps">
          {STEPS.map((s) => {
            const si = ORDER.indexOf(s.key)
            const state = idx > si ? 'done' : idx === si ? 'active' : 'todo'
            return (
              <li key={s.key} className={'step ' + state}>
                <span className="step-dot">{state === 'done' ? '✓' : state === 'active' ? <i className="pulse" /> : ''}</span>
                <div>
                  <b>{s.label}</b>
                  <span className="muted small">{s.sub}</span>
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {req.status === 'ready' && (
        <>
          {req.note && <div className="banner inline">{req.note}</div>}
          <h2 className="section-title">Pick your path</h2>
          <p className="muted">I found {req.plans.length} different ways to do this. Each one trades something for something else.</p>
          {chooseErr && <ErrorBox>{chooseErr}</ErrorBox>}
          <div className="plan-grid">
            {req.plans.map((p) => (
              <PlanCard
                key={p.id}
                plan={p}
                busy={choosing === p.id}
                disabled={choosing !== null}
                existing={req.artifact_id && p.chosen ? req.artifact_id : null}
                onChoose={() => choose(p.id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function PlanCard({ plan, onChoose, busy, disabled, existing }) {
  return (
    <article className={'plan' + (plan.chosen ? ' chosen' : '')}>
      <header>
        <h3>{plan.title}</h3>
        <p className="tagline">{plan.tagline}</p>
      </header>
      <dl className="facts">
        <div><dt>💰 Cost</dt><dd>{plan.cost_estimate}</dd></div>
        <div><dt>⏱️ Time</dt><dd>{plan.time_commitment}</dd></div>
        <div><dt>📅 Timeline</dt><dd>{plan.timeline}</dd></div>
        <div><dt>🎚️ Difficulty</dt><dd>{plan.difficulty}</dd></div>
      </dl>
      <p>{plan.summary}</p>
      {plan.highlights?.length > 0 && (
        <ul className="ticks">
          {plan.highlights.map((h, i) => <li key={i}>{h}</li>)}
        </ul>
      )}
      {plan.why_it_fits && <p className="why"><b>Why it fits you:</b> {plan.why_it_fits}</p>}
      {plan.tradeoffs && <p className="trade"><b>Trade-off:</b> {plan.tradeoffs}</p>}
      {plan.sources?.length > 0 && (
        <div className="sources">
          {plan.sources.map((s) => (
            <a key={s.url} href={s.url} target="_blank" rel="noreferrer">↗ {s.title}</a>
          ))}
        </div>
      )}
      {existing ? (
        <a className="btn primary" href={`#/artifact/${existing}`}>Open your plan →</a>
      ) : (
        <button className="btn primary" disabled={disabled} onClick={onChoose}>
          {busy ? 'Starting…' : 'Choose this plan'}
        </button>
      )}
    </article>
  )
}
