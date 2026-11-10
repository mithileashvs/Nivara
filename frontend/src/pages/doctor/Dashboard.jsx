import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BellRing, CalendarCheck, CalendarClock, CheckCircle2, RotateCw, Users } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { AppointmentCard } from '../../components/AppointmentCard'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { ConfirmationModal } from '../../components/ui/Modal'
import { Textarea } from '../../components/ui/Field'
import { Card, CardBody } from '../../components/ui/Card'
import { AsyncBoundary, EmptyState, LoadingSkeleton, ErrorState } from '../../components/ui/States'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getMyStatistics, setDoctorIntake } from '../../api/doctors'
import { getDoctorWaitlistStats } from '../../api/waitlist'
import {
  approveRescheduleRequest,
  listAppointments,
  listDoctorRescheduleRequests,
  rejectRescheduleRequest,
} from '../../api/appointments'
import { APPOINTMENT_STATUS, MAX_PAGE_SIZE, PROFILE_STATUS } from '../../utils/constants'
import { formatDate, greeting, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Doctor home. The four figures come straight from GET /doctors/me/statistics,
 * which the backend computes live from appointment records.
 */
export default function DoctorDashboard() {
  useDocumentTitle('Dashboard')
  const { user, doctorProfile, refreshDoctorProfile } = useAuth()
  const { hospitalName, departmentName } = useDirectory()
  const toast = useToast()

  const stats = useAsync(() => getMyStatistics(), [])
  const waitlistStats = useAsync(() => getDoctorWaitlistStats(), [])
  const today = todayString()

  const pending = useAsync(
    () =>
      listAppointments({
        status: APPOINTMENT_STATUS.REQUESTED,
        page: 1,
        page_size: 5,
      }),
    [],
  )

  const pendingReschedules = useAsync(
    () =>
      listDoctorRescheduleRequests({
        status: 'REQUESTED',
        page: 1,
        page_size: 5,
      }),
    [],
  )

  const [rescheduleDecision, setRescheduleDecision] = useState(null)
  const [decisionNote, setDecisionNote] = useState('')
  const [busy, setBusy] = useState(false)

  const handleRescheduleSubmit = async () => {
    if (!rescheduleDecision) return
    const { request, action } = rescheduleDecision
    setBusy(true)
    try {
      if (action === 'approve') {
        await approveRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success(`Reschedule approved. Appointment moved to ${formatDate(request.requested_appointment_date)} at ${request.requested_start_time}.`)
      } else {
        await rejectRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success('Reschedule request declined. Original appointment remains confirmed.')
      }
      setRescheduleDecision(null)
      setDecisionNote('')
      pendingReschedules.reload()
      stats.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const todays = useAsync(
    () => listAppointments({ date_from: today, date_to: today, page: 1, page_size: MAX_PAGE_SIZE }),
    [today],
  )

  const todaysConfirmed = useMemo(
    () =>
      (todays.data?.items ?? [])
        .filter((a) => a.status === APPOINTMENT_STATUS.CONFIRMED)
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [todays.data],
  )

  const changeIntake = async (status, reason) => {
    try {
      await setDoctorIntake(doctorProfile.id, status, reason)
      await refreshDoctorProfile()
      toast.success(
        status === 'OPEN'
          ? 'You are accepting new requests again.'
          : 'New requests are paused. Existing appointments are unchanged.',
      )
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const firstName = user?.name?.split(' ')[0] || 'Doctor'

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={greeting()}
        title={firstName}
        description="Review appointment requests, today's confirmed consultations, and schedule updates."
      />

      {/* A pending or suspended profile cannot publish availability or take requests. */}
      {doctorProfile && doctorProfile.profile_status !== PROFILE_STATUS.ACTIVE && (
        <Alert tone="warn">
          {doctorProfile.profile_status === PROFILE_STATUS.PENDING
            ? 'Your profile is awaiting verification. An administrator needs to activate it and assign your hospital and department before you can publish availability or receive requests.'
            : 'Your profile is suspended. Contact your administrator to restore it.'}
        </Alert>
      )}

      {doctorProfile?.profile_status === PROFILE_STATUS.ACTIVE && (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-forest-700">New appointment requests</p>
              <p className="mt-0.5 text-sm text-ink-muted">
                Pausing stops new requests reaching you. Appointments you have already accepted stay
                exactly as they are.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge tone={doctorProfile.availability_status === 'OPEN' ? 'positive' : 'negative'}>
                {doctorProfile.availability_status === 'OPEN' ? 'Accepting' : 'Paused'}
              </Badge>
              <IntakeToggle status={doctorProfile.availability_status} onChange={changeIntake} />
            </div>
          </CardBody>
        </Card>
      )}

      <section aria-label="Your statistics">
        {stats.loading ? (
          <LoadingSkeleton variant="stats" rows={4} />
        ) : stats.error ? (
          <ErrorState error={stats.error} onRetry={stats.reload} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard
              icon={CalendarClock}
              value={stats.data.todays_appointments}
              label="Today's appointments"
              to="/doctor/appointments"
            />
            <StatCard
              icon={CalendarCheck}
              value={stats.data.pending_requests}
              label="Pending requests"
              tone={stats.data.pending_requests > 0 ? 'warn' : 'default'}
              to="/doctor/appointments?status=REQUESTED"
            />
            <StatCard
              icon={RotateCw}
              value={stats.data.pending_reschedule_requests ?? 0}
              label="Reschedule requests"
              tone={(stats.data.pending_reschedule_requests ?? 0) > 0 ? 'warn' : 'default'}
              to="/doctor/appointments?status=RESCHEDULE_REQUESTS"
            />
            <StatCard
              icon={BellRing}
              value={waitlistStats.data?.active_waitlist_patients ?? 0}
              label="Waitlist patients"
              tone={(waitlistStats.data?.active_waitlist_patients ?? 0) > 0 ? 'warn' : 'default'}
              to="/doctor/appointments?status=WAITLIST_QUEUE"
            />
            <StatCard
              icon={CheckCircle2}
              value={stats.data.confirmed_appointments}
              label="Confirmed appointments"
              to="/doctor/appointments?status=CONFIRMED"
            />
            <StatCard icon={Users} value={stats.data.total_patients} label="Patients seen" to="/doctor/patients" />
          </div>
        )}
      </section>

      <section aria-labelledby="pending-heading">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 id="pending-heading" className="text-lg font-semibold text-forest-700">
            Waiting for your decision
          </h2>
          <Link
            to="/doctor/appointments?status=REQUESTED"
            className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
          >
            View all
          </Link>
        </div>

        <AsyncBoundary
          loading={pending.loading}
          error={pending.error}
          onRetry={pending.reload}
          isEmpty={(pending.data?.items ?? []).length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={CheckCircle2}
              title="No requests waiting"
              description="Every appointment request has had a decision."
            />
          }
        >
          <div className="space-y-3">
            {(pending.data?.items ?? []).map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="doctor"
                hospitalName={hospitalName(a.hospital_id)}
                departmentName={departmentName(a.department_id)}
              />
            ))}
          </div>
        </AsyncBoundary>
      </section>

      {/* Reschedule requests section */}
      <section aria-labelledby="reschedule-heading">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <h2 id="reschedule-heading" className="text-lg font-semibold text-forest-700">
              Reschedule requests
            </h2>
            {(pendingReschedules.data?.total ?? 0) > 0 && (
              <Badge tone="warn">{pendingReschedules.data.total}</Badge>
            )}
          </div>
          <Link
            to="/doctor/appointments?status=RESCHEDULE_REQUESTS"
            className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
          >
            View all
          </Link>
        </div>

        <AsyncBoundary
          loading={pendingReschedules.loading}
          error={pendingReschedules.error}
          onRetry={pendingReschedules.reload}
          isEmpty={(pendingReschedules.data?.items ?? []).length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={CheckCircle2}
              title="No reschedule requests"
              description="No patients are currently requesting to reschedule."
            />
          }
        >
          <div className="space-y-3">
            {(pendingReschedules.data?.items ?? []).map((req) => (
              <Card key={req.id}>
                <CardBody className="p-4 sm:p-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-forest-900">{req.patient_name}</span>
                        <Badge tone="warn">Reschedule Requested</Badge>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-sm text-forest-800">
                        <span className="rounded-lg bg-surface-sunken px-2.5 py-1 text-xs text-ink-muted line-through">
                          Current: {formatDate(req.old_appointment_date)} at {req.old_start_time}
                        </span>
                        <ArrowRight className="h-4 w-4 text-forest-400" aria-hidden="true" />
                        <span className="rounded-lg border border-ok/30 bg-ok-soft px-2.5 py-1 text-xs font-semibold text-forest-800">
                          Requested: {formatDate(req.requested_appointment_date)} at {req.requested_start_time}
                        </span>
                      </div>

                      {req.reason && (
                        <p className="text-xs text-ink-muted">
                          <span className="font-medium text-forest-800">Patient&apos;s Reason:</span> &ldquo;{req.reason}&rdquo;
                        </p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => setRescheduleDecision({ request: req, action: 'approve' })}
                      >
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-danger/30 text-danger hover:border-danger/50 hover:bg-danger-soft"
                        onClick={() => setRescheduleDecision({ request: req, action: 'reject' })}
                      >
                        Decline
                      </Button>
                      <Link
                        to={`/doctor/appointments/${req.appointment_id}`}
                        className="inline-flex h-9 items-center rounded-lg border border-line bg-surface px-3 text-xs font-medium text-forest-700 transition-colors hover:border-forest-200 hover:bg-forest-50 focus-ring"
                      >
                        Details
                      </Link>
                    </div>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        </AsyncBoundary>
      </section>

      <section aria-labelledby="today-heading">
        <h2 id="today-heading" className="mb-4 text-lg font-semibold text-forest-700">
          Confirmed for today
        </h2>
        <AsyncBoundary
          loading={todays.loading}
          error={todays.error}
          onRetry={todays.reload}
          isEmpty={todaysConfirmed.length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={<EmptyState title="Nothing confirmed today" description="Your day is clear." />}
        >
          <div className="space-y-3">
            {todaysConfirmed.map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="doctor"
                hospitalName={hospitalName(a.hospital_id)}
                departmentName={departmentName(a.department_id)}
              />
            ))}
          </div>
        </AsyncBoundary>
      </section>

      {/* Reschedule confirmation modal */}
      <ConfirmationModal
        open={Boolean(rescheduleDecision)}
        onClose={() => {
          if (!busy) {
            setRescheduleDecision(null)
            setDecisionNote('')
          }
        }}
        title={
          rescheduleDecision?.action === 'approve'
            ? 'Approve appointment reschedule?'
            : 'Decline appointment reschedule?'
        }
        confirmLabel={
          rescheduleDecision?.action === 'approve'
            ? 'Approve Reschedule'
            : 'Decline Reschedule'
        }
        tone={rescheduleDecision?.action === 'approve' ? 'primary' : 'danger'}
        onConfirm={handleRescheduleSubmit}
        loading={busy}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {rescheduleDecision?.action === 'approve'
              ? `You are confirming the appointment change for ${rescheduleDecision?.request?.patient_name} to ${formatDate(rescheduleDecision?.request?.requested_appointment_date)} at ${rescheduleDecision?.request?.requested_start_time}. The previous slot will be released atomically.`
              : `You are declining this reschedule request. The original appointment on ${formatDate(rescheduleDecision?.request?.old_appointment_date)} at ${rescheduleDecision?.request?.old_start_time} will remain active.`}
          </p>
          <Textarea
            label={rescheduleDecision?.action === 'approve' ? 'Optional note for patient' : 'Reason / note for declining'}
            placeholder={
              rescheduleDecision?.action === 'approve'
                ? 'e.g. Approved. Please arrive 10 minutes early.'
                : 'e.g. I am unavailable at this requested time. Please request an alternative slot.'
            }
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.target.value)}
            rows={3}
          />
        </div>
      </ConfirmationModal>
    </div>
  )
}
