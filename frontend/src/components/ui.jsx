import React from 'react'

export function Chips({ value, onChange, options }) {
  return (
    <div className="chips" role="radiogroup">
      {options.map((o) => (
        <button
          type="button"
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          className={'chip' + (value === o.value ? ' on' : '')}
          onClick={() => onChange(o.value)}
        >
          <span className="chip-title">{o.icon ? o.icon + ' ' : ''}{o.label}</span>
          {o.hint && <span className="chip-hint">{o.hint}</span>}
        </button>
      ))}
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <div className="field">
      <label className="field-label">{label}</label>
      {hint && <p className="field-hint">{hint}</p>}
      {children}
    </div>
  )
}

export function Bar({ pct, tone = 'xp' }) {
  return (
    <div className={'bar bar-' + tone}>
      <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </div>
  )
}

export function Spinner({ label }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      {label && <p>{label}</p>}
    </div>
  )
}

export function ErrorBox({ children }) {
  return <div className="error-box">⚠️ {children}</div>
}

export function Check({ checked, onChange, children, xp }) {
  return (
    <label className={'check' + (checked ? ' done' : '')}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="box">{checked ? '✓' : ''}</span>
      <span className="check-text">{children}</span>
      {xp != null && <span className="xp-pill">+{xp} XP</span>}
    </label>
  )
}

export function Logo({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="fl-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7c5cff" />
          <stop offset="1" stopColor="#2ee6a6" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#fl-g)" />
      <rect x="11" y="6" width="2.6" height="20" rx="1.3" fill="#fff" />
      <path d="M15.6 7 L25 17.5 H15.6 Z" fill="#fff" />
      <path d="M15.6 20 L21 24.5 H15.6 Z" fill="#fff" opacity=".75" />
    </svg>
  )
}
