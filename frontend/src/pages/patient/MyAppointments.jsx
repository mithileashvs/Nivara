import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarSearch } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { AppointmentCard } from '../../components/AppointmentCard'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listAppointments } from '../../api/appointments'
import { APPOINTMENT_STATUS } from '../../utils/constants'

/* Tabs map exactly onto the backend's AppointmentStatus values, so each one is a
   real server-side filter rather than client-side slicing of a partial page. */
const TABS = [
  { value: '', label: 'All' },
  { value: APPOINTMENT_STATUS.REQUESTED, label: 'Requested' },
  { value: APPOINTMENT_STATUS.CONFIRMED, label: 'Confirmed' },
  { value: APPOINTMENT_STATUS.COMPLETED, label: 'Completed' },
  { value: APPOINTMENT_STATUS.CANCELLED, label: 'Cancelled' },
  { value: APPOINTMENT_STATUS.REJECTED, label: 'Declined' },
  { value: APPOINTMENT_STATUS.NO_SHOW, label: 'No show' },
]

export default function MyAppointments() {
  useDocumentTitle('My appointments')
  const [status, setStatus] = useState('')
  const { hospitalName, departmentName } = useDirectory()

  const paged = usePaged((p) => listAppointments({ ...p, status: status || undefined }), [status])

  return (
    <div className="space-y-6">
      <PageHeader
        title="My appointments"
        description="Every request and consultation, with its current status."
      />

      <Tabs tabs={TABS} value={status} onChange={setStatus} />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton rows={3} />}
        empty={
          <EmptyState
            icon={CalendarSearch}
            title={status ? 'Nothing in this list' : 'No appointments yet'}
            description={
              status
                ? 'Try another tab to see the rest of your appointments.'
                : 'Once you request a time with a doctor it will appear here.'
            }
            action={
              !status && (
                <Link
                  to="/find-doctors"
                  className="inline-flex h-11 items-center rounded-xl bg-forest px-5 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                >
                  Find a doctor
                </Link>
              )
            }
          />
        }
      >
        <div className="space-y-3">
          {paged.items.map((a) => (
            <AppointmentCard
              key={a.id}
              appointment={a}
              perspective="patient"
              hospitalName={hospitalName(a.hospital_id)}
              departmentName={departmentName(a.department_id)}
            />
          ))}
        </div>
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
