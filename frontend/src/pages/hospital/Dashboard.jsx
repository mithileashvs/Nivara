import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarCheck, CalendarDays, LayoutGrid, Stethoscope } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Select } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getHospital, getHospitalAvailability, setHospitalIntake } from '../../api/hospitals'
import { searchDoctors } from '../../api/doctors'
import { listAppointments } from '../../api/admin'
import {
  APPOINTMENT_STATUS, APPOINTMENT_STATUS_LABEL, MAX_PAGE_SIZE,
} from '../../utils/constants'
import { addDays, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const STATUS_COLOUR = {
  REQUESTED: '#A4762A',
  CONFIRMED: '#3F7D5B',
  COMPLETED: '#3D6379',
  CANCELLED: '#8B978F',
  REJECTED: '#A8503F',
  NO_SHOW: '#A8503F',
}

/**
 * Hospital administration.
 *
 * Nivara's backend has three roles — PATIENT, DOCTOR and ADMIN — and models a
 * hospital administrator as an ADMIN whose `managed_hospital_ids` lists the
 * hospitals they run. There is no separate hospital login, and none is invented
 * here. Every figure below is counted from a real endpoint:
 *   appointments  GET /admin/appointments (already scoped to this admin's hospitals)
 *   doctors       GET /doctors?hospital_id=…
 *   departments   GET /hospitals/{id}
 *   open slots    GET /hospitals/{id}/availability
 * There is no patient count here, because the endpoint that provides one is
 * restricted to platform administrators.
 */
export default function HospitalDashboard() {
  useDocumentTitle('Hospital dashboard')
  const { managedHospitalIds } = useAuth()
  const { hospitalById } = useDirectory()
  const toast = useToast()

  const ids = managedHospitalIds ?? []
  const [hospitalId, setHospitalId] = useState(ids[0] ?? '')

  useEffect(() => {
    if (!hospitalId && ids.length) setHospitalId(ids[0])
  }, [ids, hospitalId])

  const from = todayString()
  const to = useMemo(() => addDays(from, 14), [from])

  const hospital = useAsync(() => getHospital(hospitalId), [hospitalId], {
    enabled: Boolean(hospitalId),
  })
  const availability = useAsync(
    () => getHospitalAvailability(hospitalId, { date_from: from, date_to: to }),
    [hospitalId, from, to],
    { enabled: Boolean(hospitalId) },
  )
  const doctors = useAsync(
    () => searchDoctors({ hospital_id: hospitalId, page: 1, page_size: 1 }),
    [hospitalId],
    { enabled: Boolean(hospitalId) },
  )
  const appointments = useAsync(
    () => listAppointments({ hospital_id: hospitalId, page: 1, page_size: MAX_PAGE_SIZE }),
    [hospitalId],
    { enabled: Boolean(hospitalId) },
  )

  const byStatus = useMemo(() => {
    const counts = {}
    for (const a of appointments.data?.items ?? []) counts[a.status] = (counts[a.status] || 0) + 1
    return Object.values(APPOINTMENT_STATUS)
      .map((status) => ({
        status,
        label: APPOINTMENT_STATUS_LABEL[status],
        count: counts[status] || 0,
      }))
      .filter((e) => e.count > 0)
  }, [appointments.data])

  const changeIntake = async (status, reason) => {
    try {
      const r = await setHospitalIntake(hospitalId, status, reason)
      toast.success(`${r.message} ${r.active_appointments_unaffected} existing appointment(s) left untouched.`)
      hospital.reload()
      availability.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  if (!ids.length) {
    return (
      <EmptyState
        title="No hospitals assigned to your account"
        description="A platform administrator needs to assign the hospitals you manage before this dashboard can show anything."
      />
    )
  }

  const h = hospital.data

  return (
    <div className="space-y-8">
      <PageHeader
        title="Hospital dashboard"
        description={h?.address}
        actions={
          ids.length > 1 ? (
            <Select
              aria-label="Hospital"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              options={ids.map((id) => ({ value: id, label: hospitalById[id]?.name || 'Hospital' }))}
              className="min-w-[13rem]"
            />
          ) : (
            <span className="text-sm font-medium text-forest-700">{hospitalById[hospitalId]?.name}</span>
          )
        }
      />

      {hospital.error ? (
        <ErrorState error={hospital.error} onRetry={hospital.reload} />
      ) : hospital.loading || !h ? (
        <LoadingSkeleton variant="stats" rows={4} />
      ) : (
        <>
          <Card>
            <CardBody className="flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-forest-700">New appointment intake</p>
                <p className="mt-0.5 text-sm text-ink-muted">
                  Closing stops new requests across the whole hospital. Appointments already
                  requested or confirmed stay exactly as they are.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <StatusBadge status={h.appointment_intake_status} kind="generic" />
                <IntakeToggle status={h.appointment_intake_status} label={h.name} onChange={changeIntake} />
              </div>
            </CardBody>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={CalendarDays}
              value={appointments.loading ? '—' : (appointments.data?.total ?? 0)}
              label="Appointments"
              hint="All statuses, this hospital"
              to="/hospital/appointments"
            />
            <StatCard
              icon={Stethoscope}
              value={doctors.loading ? '—' : (doctors.data?.total ?? 0)}
              label="Doctors"
              to="/hospital/doctors"
            />
            <StatCard
              icon={LayoutGrid}
              value={h.departments?.length ?? 0}
              label="Departments"
              to="/hospital/departments"
            />
            <StatCard
              icon={CalendarCheck}
              value={availability.loading ? '—' : (availability.data?.total_bookable_slots ?? 0)}
              label="Open slots, next 14 days"
              hint="Counted from real slots"
              tone={availability.data?.total_bookable_slots ? 'positive' : 'warn'}
            />
          </div>

          <Card>
            <CardHeader
              title="Appointments by status"
              description={`Most recent ${MAX_PAGE_SIZE} appointments at this hospital.`}
              action={
                <Link
                  to="/hospital/appointments"
                  className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
                >
                  View all
                </Link>
              }
            />
            <CardBody>
              {appointments.loading ? (
                <div className="skeleton h-64 w-full" />
              ) : appointments.error ? (
                <ErrorState error={appointments.error} onRetry={appointments.reload} compact />
              ) : byStatus.length === 0 ? (
                <EmptyState title="No appointments yet" description="This chart fills in as patients book." />
              ) : (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={byStatus} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 11, fill: '#5C6B61' }}
                        axisLine={{ stroke: '#E4E7DF' }}
                        tickLine={false}
                        interval={0}
                      />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        cursor={{ fill: '#EEF3F0' }}
                        contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }}
                      />
                      <Bar dataKey="count" name="Appointments" radius={[6, 6, 0, 0]} maxBarSize={56}>
                        {byStatus.map((e) => (
                          <Cell key={e.status} fill={STATUS_COLOUR[e.status]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Departments"
              description="Open or close intake per department — Cardiology can close while General Medicine stays open."
              action={
                <Link
                  to="/hospital/departments"
                  className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
                >
                  Manage
                </Link>
              }
            />
            {h.departments?.length ? (
              <ul className="divide-y divide-line">
                {h.departments.map((d) => {
                  const avail = (availability.data?.departments ?? []).find(
                    (x) => x.department_id === d.id,
                  )
                  return (
                    <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-forest-700">{d.name}</p>
                        {avail && (
                          <p className="text-xs text-ink-muted">
                            {avail.bookable_slots} open slot{avail.bookable_slots === 1 ? '' : 's'}
                          </p>
                        )}
                      </div>
                      <StatusBadge status={d.appointment_intake_status} kind="generic" />
                    </li>
                  )
                })}
              </ul>
            ) : (
              <CardBody>
                <EmptyState title="No departments yet" description="Add one so doctors can be assigned." />
              </CardBody>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
