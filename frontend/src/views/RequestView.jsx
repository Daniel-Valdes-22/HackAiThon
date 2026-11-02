import React, { useState } from 'react'
import { api } from '../api.js'
import { useFetch, go } from '../hooks.js'
import { Spinner, ErrorBox } from '../components/ui.jsx'

const STEPS = [
  { key: 'soul', label: 'Waking up', sub: '' },
  { key: 'memory', label: 'Recalling you', sub: '' },
  { key: 'research', label: 'Searching the web', sub: '' },
  { key: 'plans', label: 'Drafting plans', sub: '' },
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

      {req.memories_used?.length > 0 && req.status !== 'ready' && (
        <p className="muted small">🧠 Using what I know about you · {req.memories_used.length} memories</p>
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
                  
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {req.status === 'ready' && (
        <>
          {req.note && <div className="banner inline">{req.note}</div>}
          <h2 className="section-title">Pick a path</h2>
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
      <p>{plan.summary}</p>
      <dl className="facts">
        <div><dt>💰 Cost</dt><dd>{plan.cost_estimate}</dd></div>
        <div><dt>⏱️ Time</dt><dd>{plan.time_commitment}</dd></div>
        <div><dt>🎚️ Level</dt><dd>{plan.difficulty}</dd></div>
      </dl>
      {plan.why_it_fits && <p className="why">{plan.why_it_fits}</p>}
      {plan.sources?.length > 0 && (
        <div className="sources">
          {plan.sources.slice(0, 2).map((s) => (
            <a key={s.url} href={s.url} target="_blank" rel="noreferrer">↗ {s.title}</a>
          ))}
        </div>
      )}
      {existing ? (
        <a className="btn primary" href={`#/artifact/${existing}`}>Open →</a>
      ) : (
        <button className="btn primary" disabled={disabled} onClick={onChoose}>
          {busy ? 'Starting…' : 'Choose'}
        </button>
      )}
    </article>
  )
}
