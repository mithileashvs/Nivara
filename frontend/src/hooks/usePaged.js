import { useCallback, useEffect, useRef, useState } from 'react'
import { PAGE_SIZE } from '../utils/constants'

/**
 * Paged loader for the backend's Page<T> shape
 * ({ items, page, page_size, total, total_pages }).
 * `loader(pageParams)` receives { page, page_size } and must return that shape.
 */
export function usePaged(loader, deps = [], { pageSize = PAGE_SIZE, enabled = true } = {}) {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState({ items: [], page: 1, page_size: pageSize, total: 0, total_pages: 0 })
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

  // Any filter change restarts at page one.
  useEffect(() => {
    setPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  const run = useCallback(
    async (targetPage = page) => {
      const id = ++runId.current
      setLoading(true)
      setError(null)
      try {
        const data = await loader({ page: targetPage, page_size: pageSize })
        if (mounted.current && id === runId.current) setResult(data)
        return data
      } catch (err) {
        if (mounted.current && id === runId.current) {
          setError(err)
          setResult({ items: [], page: targetPage, page_size: pageSize, total: 0, total_pages: 0 })
        }
        return undefined
      } finally {
        if (mounted.current && id === runId.current) setLoading(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [...deps, page, pageSize],
  )

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    run(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run])

  return {
    items: result.items ?? [],
    total: result.total ?? 0,
    totalPages: result.total_pages ?? 0,
    page,
    pageSize,
    setPage,
    loading,
    error,
    reload: () => run(page),
    isEmpty: !loading && !error && (result.items ?? []).length === 0,
  }
}
