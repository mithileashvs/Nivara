import { useCallback, useEffect, useMemo, useState } from 'react'
import { listHospitals } from '../api/hospitals'
import { listDepartments } from '../api/departments'
import { MAX_PAGE_SIZE } from '../utils/constants'
import { useAuth } from '../context/AuthContext'

/**
 * Hospitals and departments are referenced by id all over the API (doctors,
 * appointments, slots), so they are fetched once and shared. This replaces a
 * per-row lookup and means names shown in the UI are always real records.
 */
export function useDirectory() {
  const { isAuthenticated } = useAuth()
  const [hospitals, setHospitals] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [h, d] = await Promise.all([
        listHospitals({ page: 1, page_size: MAX_PAGE_SIZE }),
        listDepartments({ page: 1, page_size: MAX_PAGE_SIZE }),
      ])
      setHospitals(h.items ?? [])
      setDepartments(d.items ?? [])
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    load()
  }, [load])

  const hospitalById = useMemo(
    () => Object.fromEntries(hospitals.map((h) => [h.id, h])),
    [hospitals],
  )
  const departmentById = useMemo(
    () => Object.fromEntries(departments.map((d) => [d.id, d])),
    [departments],
  )

  return {
    hospitals,
    departments,
    hospitalById,
    departmentById,
    hospitalName: (id) => hospitalById[id]?.name,
    departmentName: (id) => departmentById[id]?.name,
    hospitalNames: (ids = []) => ids.map((id) => hospitalById[id]?.name).filter(Boolean),
    /** Distinct city list for the location filter, built from real hospital records. */
    cities: useMemo(
      () =>
        [...new Set(hospitals.map((h) => h.location?.city).filter(Boolean))].sort((a, b) =>
          a.localeCompare(b),
        ),
      [hospitals],
    ),
    loading,
    error,
    reload: load,
  }
}
