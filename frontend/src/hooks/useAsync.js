import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Run an async loader and track { data, error, loading }.
 * `deps` behaves like a useEffect dependency list. Results from a stale run are
 * discarded, so fast filter changes can never render an out-of-date response.
 */
export function useAsync(loader, deps = [], { enabled = true, initial = null } = {}) {
  const [data, setData] = useState(initial)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const runId = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(async () => {
    const id = ++runId.current
    setLoading(true)
    setError(null)
    try {
      const result = await loader()
      if (mounted.current && id === runId.current) setData(result)
      return result
    } catch (err) {
      if (mounted.current && id === runId.current) {
        setError(err)
        setData(initial)
      }
      return undefined
    } finally {
      if (mounted.current && id === runId.current) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run])

  return { data, error, loading, reload: run, setData }
}
