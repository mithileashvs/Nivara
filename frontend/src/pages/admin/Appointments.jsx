import { useState } from 'react'
import { CalendarSearch, Eye } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { FilterBar } from '../../components/FilterBar'
import { Avatar } from '../../components/ui/Avatar'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Input } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listAppointments } from '../../api/admin'
import { APPOINTMENT_STATUS, APPOINTMENT_STATUS_LABEL, CONSULTATION_LABEL } from '../../utils/constants'
import { formatDate, formatTimeRange } from '../../utils/format'

/**
 * Read-only monitoring. The backend exposes no administrative mutation for an
 * appointment — accepting, declining, completing and no-show are the treating
 * doctor's alone — so this screen deliberately has no actions. It also excludes
 * the patient's free-text reason, which the backend never sends to an admin.
 */
export default function AdminAppointments({ hospitalScope = null }) {
  useDocumentTitle('Appointments')
  const { hospitals, departments, hospitalById, departmentById } = useDirectory()

  const scopedHospitals = hospitalScope
    ? hospitals.filter((h) => hospitalScope.includes(h.id))
    : hospitals

  const [filters, setFilters] = useState({
    status: '',
    hospital_id: hospitalScope?.length === 1 ? hospitalScope[0] : '',
    department_id: '',
    appointment_date: '',
  })

  const set = (k) => (v) => setFilters((f) => ({ ...f, [k]: v }))
  const hasActive = Object.values(filters).some(Boolean)

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
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="Platform monitoring. Only the treating doctor can accept, decline or complete an appointment."
      />

      <p className="flex items-start gap-2.5 rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-sm text-ink-muted">
        <Eye size={16} className="mt-0.5 shrink-0 text-forest-400" aria-hidden="true" />
        This view is read-only, and clinical detail such as the patient&apos;s reason for the visit
        is not included.
      </p>

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
            className="w-44"
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
    </div>
  )
}
