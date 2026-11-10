import { useEffect, useMemo, useState } from 'react'
import { Building2, Calendar, FilterX, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { Select } from '../ui/Field'
import {
  ANALYTICS_GRANULARITIES,
  ANALYTICS_PRESETS,
  APPOINTMENT_STATUS,
  APPOINTMENT_STATUS_LABEL,
} from '../../utils/constants'
import { getDoctorAnalytics } from '../../api/analytics'

/**
 * Shared analytical filter bar enforcing platform vs hospital-scoped admin visibility.
 */
export function AnalyticsFilterBar({
  filters,
  onChange,
  onReset,
  onRefresh,
  isPlatformAdmin,
  managedHospitalIds = [],
  hospitals = [],
  departments = [],
  periodMeta = null,
  showGranularity = true,
  showStatusFilter = true,
  showDoctorFilter = true,
}) {
  const [doctorOptions, setDoctorOptions] = useState([])

  // Determine hospitals visible in the selector based on admin scope
  const availableHospitals = useMemo(() => {
    if (isPlatformAdmin) return hospitals
    const allowed = new Set(managedHospitalIds || [])
    return hospitals.filter((h) => allowed.has(h.id))
  }, [isPlatformAdmin, managedHospitalIds, hospitals])

  const singleHospitalLocked = !isPlatformAdmin && availableHospitals.length === 1

  // Filter departments to selected hospital (or authorized hospitals)
  const availableDepartments = useMemo(() => {
    const allowedHospSet = new Set(availableHospitals.map((h) => h.id))
    return departments.filter((d) => {
      if (filters.hospital_id) return d.hospital_id === filters.hospital_id
      if (!isPlatformAdmin) return allowedHospSet.has(d.hospital_id)
      return true
    })
  }, [departments, filters.hospital_id, isPlatformAdmin, availableHospitals])

  // Load authorized doctor list for dropdown when facility filters change
  useEffect(() => {
    if (!showDoctorFilter) return
    let active = true
    const loadDoctors = async () => {
      try {
        const res = await getDoctorAnalytics({
          preset: 'last_30_days',
          hospital_id: filters.hospital_id || undefined,
          department_id: filters.department_id || undefined,
          page: 1,
          page_size: 100,
        })
        if (active) {
          setDoctorOptions(res?.doctors?.items || [])
        }
      } catch {
        if (active) setDoctorOptions([])
      }
    }
    loadDoctors()
    return () => {
      active = false
    }
  }, [showDoctorFilter, filters.hospital_id, filters.department_id])

  const handlePresetChange = (presetValue) => {
    if (presetValue === 'custom') {
      const today = new Date().toISOString().slice(0, 10)
      const fromDefault = periodMeta?.date_from || today
      const toDefault = periodMeta?.date_to || today
      onChange({
        ...filters,
        preset: 'custom',
        date_from: filters.date_from || fromDefault,
        date_to: filters.date_to || toDefault,
      })
    } else {
      onChange({
        ...filters,
        preset: presetValue,
        date_from: '',
        date_to: '',
      })
    }
  }

  const handleHospitalChange = (nextHospitalId) => {
    // Clear dependent department & doctor filters when facility changes
    onChange({
      ...filters,
      hospital_id: nextHospitalId,
      department_id: '',
      doctor_id: '',
    })
  }

  const handleDepartmentChange = (nextDeptId) => {
    onChange({
      ...filters,
      department_id: nextDeptId,
      doctor_id: '',
    })
  }

  const dateInvalid =
    filters.preset === 'custom' &&
    Boolean(filters.date_from && filters.date_to && filters.date_from > filters.date_to)

  return (
    <div className="card space-y-4 p-4 sm:p-5">
      {/* Top row: Quick time presets + grouping toggle + refresh/reset */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Time period preset">
          {ANALYTICS_PRESETS.map((p) => {
            const active = filters.preset === p.value
            return (
              <button
                key={p.value}
                type="button"
                aria-pressed={active}
                onClick={() => handlePresetChange(p.value)}
                className={`whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors focus-ring ${
                  active
                    ? 'bg-forest text-canvas shadow-sm'
                    : 'border border-line bg-canvas text-ink-muted hover:border-forest-200 hover:text-forest-700'
                }`}
              >
                {p.label}
              </button>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {showGranularity && (
            <div
              className="inline-flex rounded-xl border border-line bg-canvas p-0.5"
              role="group"
              aria-label="Time-series grouping"
            >
              {ANALYTICS_GRANULARITIES.map((g) => {
                const active = filters.granularity === g.value
                return (
                  <button
                    key={g.value}
                    type="button"
                    aria-pressed={active}
                    onClick={() => onChange({ ...filters, granularity: g.value })}
                    className={`whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-medium transition-colors focus-ring ${
                      active ? 'bg-surface text-forest-700 shadow-sm' : 'text-ink-muted hover:text-forest-700'
                    }`}
                  >
                    {g.label}
                  </button>
                )
              })}
            </div>
          )}

          {onReset && (
            <Button variant="ghost" size="sm" onClick={onReset} title="Reset filters">
              <FilterX size={14} aria-hidden="true" />
              Reset
            </Button>
          )}
          {onRefresh && (
            <Button variant="outline" size="sm" onClick={onRefresh} title="Refresh live metrics">
              <RefreshCw size={14} aria-hidden="true" />
              Refresh
            </Button>
          )}
        </div>
      </div>

      {/* Custom date range pickers */}
      {filters.preset === 'custom' && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-canvas/70 p-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-forest-700" htmlFor="analytics-date-from">
              From date
            </label>
            <input
              id="analytics-date-from"
              type="date"
              value={filters.date_from || ''}
              onChange={(e) => onChange({ ...filters, date_from: e.target.value })}
              className="h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink focus-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-forest-700" htmlFor="analytics-date-to">
              To date
            </label>
            <input
              id="analytics-date-to"
              type="date"
              value={filters.date_to || ''}
              onChange={(e) => onChange({ ...filters, date_to: e.target.value })}
              className="h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink focus-ring"
            />
          </div>
          {dateInvalid && (
            <p role="alert" className="text-xs font-medium text-danger">
              Start date cannot be later than end date.
            </p>
          )}
        </div>
      )}

      {/* Facility, Department, Doctor, Status dropdowns */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {singleHospitalLocked ? (
          <div className="flex flex-col justify-end">
            <span className="mb-1.5 block text-sm font-medium text-forest-700">Assigned facility scope</span>
            <div className="flex h-11 items-center gap-2 rounded-xl border border-forest-100 bg-forest-50/70 px-3.5 text-sm font-medium text-forest-700">
              <Building2 size={15} className="shrink-0 text-forest-500" aria-hidden="true" />
              <span className="truncate">{availableHospitals[0]?.name || 'Assigned Hospital'}</span>
            </div>
          </div>
        ) : (
          <Select
            label="Hospital"
            value={filters.hospital_id || ''}
            onChange={(e) => handleHospitalChange(e.target.value)}
            placeholder={isPlatformAdmin ? 'All hospitals' : 'All assigned hospitals'}
            options={availableHospitals.map((h) => ({ value: h.id, label: h.name }))}
          />
        )}

        <Select
          label="Department"
          value={filters.department_id || ''}
          onChange={(e) => handleDepartmentChange(e.target.value)}
          placeholder="All departments"
          options={availableDepartments.map((d) => ({
            value: d.id,
            label: filters.hospital_id
              ? d.name
              : `${d.name}${hospitals.find((h) => h.id === d.hospital_id)?.name ? ` (${hospitals.find((h) => h.id === d.hospital_id)?.name})` : ''}`,
          }))}
        />

        {showDoctorFilter && (
          <Select
            label="Doctor"
            value={filters.doctor_id || ''}
            onChange={(e) => onChange({ ...filters, doctor_id: e.target.value })}
            placeholder="All doctors"
            options={doctorOptions.map((doc) => ({
              value: doc.doctor_id,
              label: `${doc.doctor_name}${doc.specialty ? ` · ${doc.specialty}` : ''}`,
            }))}
          />
        )}

        {showStatusFilter && (
          <Select
            label="Status"
            value={filters.status || ''}
            onChange={(e) => onChange({ ...filters, status: e.target.value })}
            placeholder="All statuses"
            options={Object.values(APPOINTMENT_STATUS).map((s) => ({
              value: s,
              label: APPOINTMENT_STATUS_LABEL[s] || s,
            }))}
          />
        )}
      </div>

      {/* Period summary strip */}
      {periodMeta && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5 text-xs text-ink-muted">
          <div className="flex items-center gap-1.5">
            <Calendar size={13} className="text-forest-500" aria-hidden="true" />
            <span>
              Active window: <strong className="text-forest-700">{periodMeta.date_from}</strong> to{' '}
              <strong className="text-forest-700">{periodMeta.date_to}</strong> ({periodMeta.days}{' '}
              {periodMeta.days === 1 ? 'day' : 'days'}, {periodMeta.timezone})
            </span>
          </div>
          <span>
            Compared against previous period: {periodMeta.previous_date_from} to {periodMeta.previous_date_to}
          </span>
        </div>
      )}
    </div>
  )
}
