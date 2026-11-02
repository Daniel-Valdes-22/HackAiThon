import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useFetch } from '../hooks.js'
import { Field, ErrorBox } from '../components/ui.jsx'

export default function Me() {
  const { data: profile } = useFetch(() => api.profile(), [])
  const { data: soul } = useFetch(() => api.soul(), [])
  const { data: mems, setData: setMems } = useFetch(() => api.memories(), [])
  const [f, setF] = useState({ name: '', about: '', location: '', interests: '' })
  const [saved, setSaved] = useState(false)
  const [note, setNote] = useState('')
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (profile) setF({ name: profile.name || '', about: profile.about || '', location: profile.location || '', interests: profile.interests || '' })
  }, [profile])

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    setErr(null)
    try {
      await api.saveProfile(f)
      setMems(await api.memories())
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e2) {
      setErr(e2.message)
    }
  }

  const add = async (e) => {
    e.preventDefault()
    if (!note.trim()) return
    try {
      await api.addMemory(note.trim())
      setNote('')
      setMems(await api.memories())
    } catch (e2) {
      setErr(e2.message)
    }
  }

  const del = async (id) => {
    await api.deleteMemory(id)
    setMems((m) => m.filter((x) => x.id !== id))
  }

  return (
    <div className="two-col">
      <div>
        <p className="eyebrow">🙋 You</p>
        <h1>Who I'm planning for</h1>
        <form className="form flat" onSubmit={save}>
          <Field label="Name"><input className="input" value={f.name} onChange={set('name')} placeholder="Tyler" /></Field>
          <Field label="Location" hint="Used for activity distance searches.">
            <input className="input" value={f.location} onChange={set('location')} placeholder="City, State" />
          </Field>
          <Field label="About you"><textarea className="input" rows={3} value={f.about} onChange={set('about')} placeholder="Job, schedule, experience, anything that shapes your plans." /></Field>
          <Field label="Interests"><input className="input" value={f.interests} onChange={set('interests')} placeholder="chess, flying, racing, camping" /></Field>
          {err && <ErrorBox>{err}</ErrorBox>}
          <button className="btn primary">{saved ? 'Saved ✓' : 'Save profile'}</button>
        </form>

        <h2 className="section-title">🧠 Frontier's memory</h2>
        <p className="muted">Everything Frontier will draw on when planning. Delete anything that's wrong.</p>
        <form className="inline-form" onSubmit={add}>
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Teach Frontier something: “I can't drive after dark”" />
          <button className="btn">Remember</button>
        </form>
        <ul className="memories">
          {(mems || []).map((m) => (
            <li key={m.id}>
              <span className={'kind ' + m.kind}>{m.kind}</span>
              <span className="mem-text">{m.text}</span>
              <button className="x" onClick={() => del(m.id)} aria-label="Forget this">×</button>
            </li>
          ))}
        </ul>
      </div>

      <aside>
        <p className="eyebrow">🔥 Frontier</p>
        <h2>Frontier's soul</h2>
        <p className="muted small">Loaded into every request. Edit <code>backend/soul.md</code> to change who Frontier is.</p>
        <pre className="soul">{soul?.soul || 'Loading…'}</pre>
      </aside>
    </div>
  )
}
