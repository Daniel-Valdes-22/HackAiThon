import React, { useState } from 'react'
import { api } from '../api.js'
import { go } from '../hooks.js'
import { Chips, Field, ErrorBox } from '../components/ui.jsx'

const RECS = ['Off-roading', 'Paintball', 'Hunting', 'Go-karts', 'Bowling', 'Escape room', 'Hiking', 'Axe throwing']

export default function Intake({ kind }) {
  return kind === 'goal' ? <GoalForm /> : <ActivityForm />
}

function useSubmit(kind, buildParams) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.createRequest(kind, buildParams())
      go(`/request/${r.id}`)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return { busy, error, submit }
}

function GoalForm() {
  const [f, setF] = useState({
    goal: '', duration: 'long', time_investment: 'casual', budget: 'moderate',
    budget_amount: '', level: 'beginner', details: '', gamify: true,
  })
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))
  const { busy, error, submit } = useSubmit('goal', () => ({
    ...f,
    budget_amount: f.budget_amount ? `$${f.budget_amount}` : '',
  }))

  return (
    <form className="form" onSubmit={submit}>
      <p className="eyebrow">🎯 New goal</p>
      <h1>What do you want to achieve?</h1>

      <Field label="Your goal" hint="Be specific — a finish line, not a topic.">
        <input
          className="input big" autoFocus required value={f.goal}
          onChange={(e) => set('goal')(e.target.value)}
          placeholder="e.g. Earn my private pilot's license · Reach 1500 chess rating · Pass the CDL exam"
        />
      </Field>

      <Field label="Duration" hint="How long a journey is this?">
        <Chips value={f.duration} onChange={set('duration')} options={[
          { value: 'short', label: 'Short term', hint: 'Weeks to ~3 months', icon: '⚡' },
          { value: 'long', label: 'Long term', hint: '6+ months', icon: '🏔️' },
        ]} />
      </Field>

      <Field label="Time investment">
        <Chips value={f.time_investment} onChange={set('time_investment')} options={[
          { value: 'casual', label: 'Casual', hint: 'A few hours a week', icon: '☕' },
          { value: 'grind', label: 'Grind', hint: 'Daily, all in', icon: '🔥' },
        ]} />
      </Field>

      <Field label="Budget">
        <Chips value={f.budget} onChange={set('budget')} options={[
          { value: 'cheap', label: 'Cheap', hint: 'Free & frugal', icon: '🪙' },
          { value: 'moderate', label: 'Moderate', hint: 'Worth paying for', icon: '💵' },
          { value: 'expensive', label: 'Expensive', hint: 'Money is no object', icon: '💎' },
        ]} />
        <div className="inline-input">
          <span>Spending cap (optional)</span>
          <span className="prefix">$</span>
          <input className="input narrow" type="number" min="0" value={f.budget_amount}
            onChange={(e) => set('budget_amount')(e.target.value)} placeholder="500" />
        </div>
      </Field>

      <Field label="Advancement level">
        <Chips value={f.level} onChange={set('level')} options={[
          { value: 'beginner', label: 'Beginner', hint: 'Starting from zero', icon: '🌱' },
          { value: 'intermediate', label: 'Intermediate', hint: 'Know the basics', icon: '🌿' },
          { value: 'pro', label: 'Pro', hint: 'Sharpening the edge', icon: '🌳' },
        ]} />
      </Field>

      <Field label="Goal details" hint="Anything Ember should know — deadlines, constraints, what you've tried.">
        <textarea className="input" rows={3} value={f.details}
          onChange={(e) => set('details')(e.target.value)} placeholder="e.g. I work nights, and I want to be done before next summer." />
      </Field>

      <label className="toggle">
        <input type="checkbox" checked={f.gamify} onChange={(e) => set('gamify')(e.target.checked)} />
        <span className="switch" />
        <span><b>Gamify it</b> — levels, quests, XP and boss fights</span>
      </label>

      {error && <ErrorBox>{error}</ErrorBox>}
      <button className="btn primary" disabled={busy || !f.goal.trim()}>
        {busy ? 'Sending to Ember…' : 'Find my plans →'}
      </button>
    </form>
  )
}

function ActivityForm() {
  const [f, setF] = useState({
    recreation: '', location: 'either', distance_miles: 30, group_size: 4, more_info: '',
  })
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))
  const { busy, error, submit } = useSubmit('activity', () => ({ ...f }))

  return (
    <form className="form" onSubmit={submit}>
      <p className="eyebrow">🏎️ New activity</p>
      <h1>What are you in the mood to do?</h1>

      <Field label="Recreation" hint="What's the actual activity?">
        <input className="input big" autoFocus required value={f.recreation}
          onChange={(e) => set('recreation')(e.target.value)} placeholder="e.g. Off-road trails, paintball, hunting, go-karts" />
        <div className="suggest">
          {RECS.map((r) => (
            <button type="button" key={r} className="tag" onClick={() => set('recreation')(r)}>{r}</button>
          ))}
        </div>
      </Field>

      <Field label="Location">
        <Chips value={f.location} onChange={set('location')} options={[
          { value: 'indoor', label: 'Indoor', icon: '🏢' },
          { value: 'outdoor', label: 'Outdoor', icon: '🌲' },
          { value: 'either', label: 'Either', icon: '🤷' },
        ]} />
      </Field>

      <Field label={`Distance — within ${f.distance_miles} miles of me`} hint="Uses the location in your profile.">
        <input type="range" min="5" max="250" step="5" value={f.distance_miles}
          onChange={(e) => set('distance_miles')(Number(e.target.value))} className="range" />
      </Field>

      <Field label="Group size" hint="How many people will be attending?">
        <div className="stepper">
          <button type="button" onClick={() => set('group_size')(Math.max(1, f.group_size - 1))}>−</button>
          <b>{f.group_size}</b>
          <button type="button" onClick={() => set('group_size')(Math.min(100, f.group_size + 1))}>+</button>
        </div>
      </Field>

      <Field label="More info" hint="Ages, skill levels, budget per person, dates — anything useful.">
        <textarea className="input" rows={3} value={f.more_info}
          onChange={(e) => set('more_info')(e.target.value)} placeholder="e.g. Birthday for a 16-year-old, Saturday afternoon, under $50 each." />
      </Field>

      {error && <ErrorBox>{error}</ErrorBox>}
      <button className="btn primary" disabled={busy || !f.recreation.trim()}>
        {busy ? 'Sending to Ember…' : 'Find my plans →'}
      </button>
    </form>
  )
}
