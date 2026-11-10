import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BellRing, CalendarSearch, Eye, Users } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { FilterBar } from '../../components/FilterBar'
import { Alert } from '../../components/ui/Alert'
import { Avatar } from '../../components/ui/Avatar'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Input } from '../../components/ui/Field'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listAppointments } from '../../api/admin'
import { listAdminWaitlist } from '../../api/waitlist'
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_LABEL, CONSULTATION_LABEL, WAITLIST_STATUS } from '../../utils/constants'
import { formatDate, formatTimeRange } from '../../utils/format'

const TABS = [
  { value: 'appointments', label: 'Appointments' },
  { value: 'waitlist', label: 'Waitlist Queues' },
]

/**
 * Read-only monitoring. The backend exposes no administrative mutation for an
 * appointment or waitlist — decisions belong to treating doctors and patients.
 */
export default function AdminAppointments({ hospitalScope = null }) {
  useDocumentTitle('Appointments & Waitlist')
  const [searchParams, setSearchParams] = useSearchParams()
  const { hospitals, departments, hospitalById, departmentById } = useDirectory()

  const currentTab = searchParams.get('tab') === 'waitlist' ? 'waitlist' : 'appointments'

  const scopedHospitals = hospitalScope
    ? hospitals.filter((h) => hospitalScope.includes(h.id))
    : hospitals

  const [filters, setFilters] = useState({
    status: '',
    hospital_id: hospitalScope?.length === 1 ? hospitalScope[0] : '',
    department_id: '',
    appointment_date: '',
  })

  const [waitlistFilters, setWaitlistFilters] = useState({
    status: '',
    hospital_id: hospitalScope?.length === 1 ? hospitalScope[0] : '',
    department_id: '',
  })

  const set = (k) => (v) => setFilters((f) => ({ ...f, [k]: v }))
  const setW = (k) => (v) => setWaitlistFilters((f) => ({ ...f, [k]: v }))

  const hasActive = Object.values(filters).some(Boolean)
  const hasActiveW = Object.values(waitlistFilters).some(Boolean)

  const paged = usePaged(
    (p) =>
      listAppointments({
        ...p,
        status: filters.status || undefined,
        hospital_id: filters.hospital_id || undefined,
        department_id: filters.department_id || undefined,
        appointment_date: filters.appointment_date || undefined,
      }),
    [filters],
    { enabled: currentTab === 'appointments' }
  )

  const pagedWaitlist = usePaged(
    (p) =>
      listAdminWaitlist({
        ...p,
        status: waitlistFilters.status || undefined,
        hospital_id: waitlistFilters.hospital_id || undefined,
        department_id: waitlistFilters.department_id || undefined,
      }),
    [waitlistFilters],
    { enabled: currentTab === 'waitlist' }
  )

  const handleTabChange = (tab) => {
    setSearchParams(tab === 'waitlist' ? { tab: 'waitlist' } : {}, { replace: true })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations Monitoring"
        description="Platform oversight. Only treating doctors can accept, decline or complete consultations."
      />

      <Tabs tabs={TABS} value={currentTab} onChange={handleTabChange} />

      {currentTab === 'appointments' ? (
        <>
          <Alert tone="info" icon={Eye}>
            This view is read-only, and clinical detail such as the patient&apos;s reason for the visit
            is excluded to maintain patient privacy.
          </Alert>

          <FilterBar
            hasActive={hasActive}
            onClear={() =>
              setFilters({
                status: '',
                hospital_id: hospitalScope?.length === 1 ? hospitalScope[0] : '',
                department_id: '',
                appointment_date: '',
              })
            }
            filters={[
              {
                key: 'status',
                label: 'Status',
                value: filters.status,
                onChange: set('status'),
                options: Object.values(APPOINTMENT_STATUS).map((s) => ({
                  value: s,
                  label: APPOINTMENT_STATUS_LABEL[s],
                })),
              },
              {
                key: 'hospital_id',
                label: 'Hospital',
                value: filters.hospital_id,
                onChange: (v) => setFilters((f) => ({ ...f, hospital_id: v, department_id: '' })),
                options: scopedHospitals.map((h) => ({ value: h.id, label: h.name })),
              },
              {
                key: 'department_id',
                label: 'Department',
                value: filters.department_id,
                onChange: set('department_id'),
                options: departments
                  .filter((d) => !filters.hospital_id || d.hospital_id === filters.hospital_id)
                  .filter((d) => !hospitalScope || hospitalScope.includes(d.hospital_id))
                  .map((d) => ({ value: d.id, label: d.name })),
              },
            ]}
            extra={
              <Input
                type="date"
                aria-label="Appointment date"
                value={filters.appointment_date}
                onChange={(e) => setFilters((f) => ({ ...f, appointment_date: e.target.value }))}
                className="w-full sm:w-44"
              />
            }
          />

          <AsyncBoundary
            loading={paged.loading}
            error={paged.error}
            onRetry={paged.reload}
            isEmpty={paged.isEmpty}
            skeleton={<LoadingSkeleton variant="table" rows={6} />}
            empty={<EmptyState icon={CalendarSearch} title="No appointments match those filters" />}
          >
            <Card className="overflow-hidden">
              <DataTable
                caption="Appointments across the platform"
                rows={paged.items}
                columns={[
                  {
                    key: 'when',
                    header: 'When',
                    render: (a) => (
                      <span className="min-w-0">
                        <span className="block font-medium text-forest-700">
                          {formatDate(a.appointment_date)}
                        </span>
                        <span className="block text-xs text-ink-muted">
                          {formatTimeRange(a.start_time, a.end_time)}
                        </span>
                      </span>
                    ),
                  },
                  {
                    key: 'patient',
                    header: 'Patient',
                    render: (a) => (
                      <span className="flex items-center gap-2.5">
                        <Avatar name={a.patient_name} size="sm" />
                        <span className="truncate">{a.patient_name}</span>
                      </span>
                    ),
                  },
                  { key: 'doctor', header: 'Doctor', render: (a) => a.doctor_name },
                  {
                    key: 'where',
                    header: 'Where',
                    hideOnMobile: true,
                    render: (a) =>
                      [
                        a.hospital_name || hospitalById[a.hospital_id]?.name,
                        a.department_name || departmentById[a.department_id]?.name,
                      ]
                        .filter(Boolean)
                        .join(' · ') || '—',
                  },
                  {
                    key: 'type',
                    header: 'Type',
                    hideOnMobile: true,
                    render: (a) => CONSULTATION_LABEL[a.consultation_type] || a.consultation_type,
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    className: 'text-right',
                    render: (a) => <StatusBadge status={a.status} />,
                  },
                ]}
              />
            </Card>
            <Pagination
              className="mt-6"
              page={paged.page}
              totalPages={paged.totalPages}
              total={paged.total}
              pageSize={paged.pageSize}
              onChange={paged.setPage}
            />
          </AsyncBoundary>
        </>
      ) : (
        <>
          <Alert tone="info" icon={BellRing}>
            Monitoring patient waitlist registrations, queue positions, and automated slot reallocation activity.
          </Alert>

          <FilterBar
            hasActive={hasActiveW}
            onClear={() =>
              setWaitlistFilters({
                status: '',
                hospital_id: hospitalScope?.length === 1 ? hospitalScope[0] : '',
                department_id: '',
              })
            }
            filters={[
              {
                key: 'status',
                label: 'Status',
                value: waitlistFilters.status,
                onChange: setW('status'),
                options: Object.values(WAITLIST_STATUS).map((s) => ({
                  value: s,
                  label: s,
                })),
              },
              {
                key: 'hospital_id',
                label: 'Hospital',
                value: waitlistFilters.hospital_id,
                onChange: (v) => setWaitlistFilters((f) => ({ ...f, hospital_id: v, department_id: '' })),
                options: scopedHospitals.map((h) => ({ value: h.id, label: h.name })),
              },
              {
                key: 'department_id',
                label: 'Department',
                value: waitlistFilters.department_id,
                onChange: setW('department_id'),
                options: departments
                  .filter((d) => !waitlistFilters.hospital_id || d.hospital_id === waitlistFilters.hospital_id)
                  .filter((d) => !hospitalScope || hospitalScope.includes(d.hospital_id))
                  .map((d) => ({ value: d.id, label: d.name })),
              },
            ]}
          />

          <AsyncBoundary
            loading={pagedWaitlist.loading}
            error={pagedWaitlist.error}
            onRetry={pagedWaitlist.reload}
            isEmpty={pagedWaitlist.isEmpty}
            skeleton={<LoadingSkeleton variant="table" rows={6} />}
            empty={<EmptyState icon={Users} title="No waitlist entries found" />}
          >
            <Card className="overflow-hidden">
              <DataTable
                caption="Waitlist registrations across the platform"
                rows={pagedWaitlist.items}
                columns={[
                  {
                    key: 'position',
                    header: 'Queue Pos.',
                    render: (w) => (
                      <span className="font-semibold text-forest-800">
                        {w.queue_position ? `#${w.queue_position}` : '—'}
                      </span>
                    ),
                  },
                  {
                    key: 'patient',
                    header: 'Patient ID',
                    render: (w) => (
                      <span className="font-mono text-xs text-ink-muted">
                        {w.patient_id?.slice(-8) || 'N/A'}
                      </span>
                    ),
                  },
                  {
                    key: 'where',
                    header: 'Hospital / Department',
                    render: (w) => (
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-ink">
                          {hospitalById[w.hospital_id]?.name || 'Any Hospital'}
                        </span>
                        <span className="block text-xs text-ink-muted">
                          {departmentById[w.department_id]?.name || w.specialty || 'General'}
                        </span>
                      </span>
                    ),
                  },
                  {
                    key: 'dates',
                    header: 'Preferred Window',
                    render: (w) => (
                      <span className="text-xs text-ink">
                        {formatDate(w.date_from)} – {formatDate(w.date_to)}
                      </span>
                    ),
                  },
                  {
                    key: 'joined',
                    header: 'Joined',
                    hideOnMobile: true,
                    render: (w) => formatDate(w.created_at),
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    className: 'text-right',
                    render: (w) => <StatusBadge status={w.status} kind="generic" />,
                  },
                ]}
              />
            </Card>
            <Pagination
              className="mt-6"
              page={pagedWaitlist.page}
              totalPages={pagedWaitlist.totalPages}
              total={pagedWaitlist.total}
              pageSize={pagedWaitlist.pageSize}
              onChange={pagedWaitlist.setPage}
            />
          </AsyncBoundary>
        </>
      )}
    </div>
  )
}
