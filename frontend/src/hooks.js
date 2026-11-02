import { useEffect, useRef, useState } from 'react'

export function useRoute() {
  const read = () => (window.location.hash.replace(/^#/, '') || '/').split('/').filter(Boolean)
  const [parts, setParts] = useState(read)
  useEffect(() => {
    const on = () => setParts(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return parts
}

export const go = (path) => {
  window.location.hash = path
}

/** Fetch once, or keep polling until `until(data)` is true. */
export function useFetch(fetcher, deps, { interval = 0, until = () => true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const fetchRef = useRef(fetcher)
  fetchRef.current = fetcher
  useEffect(() => {
    let alive = true
    let timer
    setData(null)
    const tick = async () => {
      try {
        const d = await fetchRef.current()
        if (!alive) return
        setData(d)
        setError(null)
        if (interval && !until(d)) timer = setTimeout(tick, interval)
      } catch (e) {
        if (!alive) return
        setError(e.message)
        if (interval) timer = setTimeout(tick, interval * 2)
      }
    }
    tick()
    return () => {
      alive = false
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, setData, error }
}

export const levelInfo = (xp) => {
  const level = Math.floor(Math.sqrt(xp / 60)) + 1
  const start = 60 * (level - 1) ** 2
  const next = 60 * level ** 2
  return { level, start, next, pct: Math.min(100, ((xp - start) / (next - start)) * 100) }
}
