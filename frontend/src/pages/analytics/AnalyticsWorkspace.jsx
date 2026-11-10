import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import {
  BarChart3,
  Building2,
  CalendarDays,
  FileSpreadsheet,
  LayoutGrid,
  Stethoscope,
  Users,
} from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { AnalyticsFilterBar } from '../../components/analytics/AnalyticsFilterBar'
import { useAuth } from '../../context/AuthContext'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import OverviewSection from './OverviewSection'
import AppointmentsSection from './AppointmentsSection'
import HospitalsSection from './HospitalsSection'
import DepartmentsSection from './DepartmentsSection'
import DoctorsSection from './DoctorsSection'
import PatientsSection from './PatientsSection'
import ReportsSection from './ReportsSection'

const TABS = [
  { to: '', label: 'Overview', icon: BarChart3, end: true },
  { to: 'appointments', label: 'Appointments', icon: CalendarDays },
  { to: 'hospitals', label: 'Hospitals', icon: Building2 },
  { to: 'departments', label: 'Departments', icon: LayoutGrid },
  { to: 'doctors', label: 'Doctors', icon: Stethoscope },
  { to: 'patients', label: 'Patients', icon: Users },
  { to: 'reports', label: 'Reports', icon: FileSpreadsheet },
]

/**
 * Shared Analytics Workspace mounted under both `/admin/analytics/*` (platform admin)
 * and `/hospital/analytics/*` (hospital-scoped admin).
 */
export default function AnalyticsWorkspace() {
  useDocumentTitle('Operational Analytics')
  const { isHospitalAdmin, isPlatformAdmin: authPlatformAdmin, managedHospitalIds } = useAuth()
  const isPlatformAdmin = authPlatformAdmin ?? !isHospitalAdmin
  const basePath = isPlatformAdmin ? '/admin/analytics' : '/hospital/analytics'
  const { hospitals, departments } = useDirectory()

  const defaultHospitalId = useMemo(() => {
    if (!isPlatformAdmin && managedHospitalIds?.length === 1) {
      return managedHospitalIds[0]
    }
    return ''
  }, [isPlatformAdmin, managedHospitalIds])

  const [filters, setFilters] = useState({
    preset: 'last_30_days',
    date_from: '',
    date_to: '',
    granularity: 'daily',
    hospital_id: defaultHospitalId,
    department_id: '',
    doctor_id: '',
    status: '',
  })
  const [periodMeta, setPeriodMeta] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (defaultHospitalId && !filters.hospital_id) {
      setFilters((prev) => ({ ...prev, hospital_id: defaultHospitalId }))
    }
  }, [defaultHospitalId, filters.hospital_id])

  const filterValid = useMemo(() => {
    if (filters.preset !== 'custom') return true
    if (!filters.date_from || !filters.date_to) return false
    return filters.date_from <= filters.date_to
  }, [filters.preset, filters.date_from, filters.date_to])

  const apiParams = useMemo(
    () => ({
      preset: filters.preset,
      ...(filters.preset === 'custom'
        ? { date_from: filters.date_from, date_to: filters.date_to }
        : {}),
      granularity: filters.granularity,
      hospital_id: filters.hospital_id || undefined,
      department_id: filters.department_id || undefined,
      doctor_id: filters.doctor_id || undefined,
      status: filters.status || undefined,
    }),
    [filters],
  )

  const handleReset = useCallback(() => {
    setFilters({
      preset: 'last_30_days',
      date_from: '',
      date_to: '',
      granularity: 'daily',
      hospital_id: defaultHospitalId,
      department_id: '',
      doctor_id: '',
      status: '',
    })
  }, [defaultHospitalId])

  const handlePeriodLoaded = useCallback((meta) => {
    if (meta) setPeriodMeta(meta)
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operational Analytics"
        description={
          isPlatformAdmin
            ? 'Platform-wide real-time healthcare activity, facility performance, and aggregate reports.'
            : 'Real-time operational performance and capacity metrics scoped to your assigned hospitals.'
        }
      />

      {/* Section Sub-Navigation */}
      <nav className="flex flex-wrap gap-1.5 border-b border-line pb-3" aria-label="Analytics sections">
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to || 'overview'}
            to={to ? `${basePath}/${to}` : basePath}
            end={Boolean(end)}
            className={({ isActive }) =>
              `inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-colors focus-ring ${
                isActive
                  ? 'bg-forest text-canvas shadow-sm'
                  : 'border border-line bg-surface text-ink-muted hover:border-forest-200 hover:text-forest-700'
              }`
            }
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Global Analytics Filters */}
      <AnalyticsFilterBar
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
        onRefresh={() => setRefreshKey((k) => k + 1)}
        isPlatformAdmin={isPlatformAdmin}
        managedHospitalIds={managedHospitalIds}
        hospitals={hospitals}
        departments={departments}
        periodMeta={periodMeta}
      />

      <Routes>
        <Route
          index
          element={
            <OverviewSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="appointments"
          element={
            <AppointmentsSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="hospitals"
          element={
            <HospitalsSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="departments"
          element={
            <DepartmentsSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="doctors"
          element={
            <DoctorsSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="patients"
          element={
            <PatientsSection
              apiParams={apiParams}
              filterValid={filterValid}
              onPeriodLoaded={handlePeriodLoaded}
              refreshKey={refreshKey}
            />
          }
        />
        <Route
          path="reports"
          element={
            <ReportsSection
              apiParams={apiParams}
              filterValid={filterValid}
              periodMeta={periodMeta}
              isPlatformAdmin={isPlatformAdmin}
            />
          }
        />
        <Route path="*" element={<Navigate to="." replace />} />
      </Routes>
    </div>
  )
}
