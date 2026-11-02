async function call(path, { method = 'GET', body } = {}) {
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    let msg = ''
    try {
      const j = JSON.parse(text)
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      msg = text.trim()
    }
    // Vite's dev proxy answers an empty 500/502/503/504 when nothing is listening on :8000.
    if (!msg && res.status >= 500) {
      msg = "Can't reach the backend on port 8000. Is it running? (cd backend && uvicorn main:app --reload --port 8000)"
    }
    throw new Error(msg || res.statusText)
  }
  return res.json()
}

export const api = {
  health: () => call('/health'),
  stats: () => call('/stats'),
  soul: () => call('/soul'),
  profile: () => call('/profile'),
  saveProfile: (p) => call('/profile', { method: 'PUT', body: p }),
  memories: () => call('/memories'),
  addMemory: (text) => call('/memories', { method: 'POST', body: { text } }),
  deleteMemory: (id) => call(`/memories/${id}`, { method: 'DELETE' }),
  requests: () => call('/requests'),
  request: (id) => call(`/requests/${id}`),
  createRequest: (kind, params) => call('/requests', { method: 'POST', body: { kind, params } }),
  choosePlan: (id) => call(`/plans/${id}/choose`, { method: 'POST' }),
  artifacts: () => call('/artifacts'),
  artifact: (id) => call(`/artifacts/${id}`),
  saveProgress: (id, completed) => call(`/artifacts/${id}/progress`, { method: 'PUT', body: { completed } }),
}
