import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BellRing,
  CheckCircle2,
  Clock,
  Plus,
  Sparkles,
  Users,
  XCircle,
} from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ConfirmationModal, Modal } from '../../components/ui/Modal'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  acceptOffer,
  declineOffer,
  getMyWaitlistHistory,
  joinWaitlist,
  leaveWaitlist,
  listMyOffers,
  listMyWaitlist,
} from '../../api/waitlist'
import {
  CONSULTATION_TYPES,
  WAITLIST_OFFER_STATUS,
  WAITLIST_STATUS,
} from '../../utils/constants'
import { addDays, formatDate, formatInstant, formatLongDate, formatTime, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const MAIN_TABS = [
  { value: 'active', label: 'My Waitlist' },
  { value: 'offers', label: 'Slot Offers' },
  { value: 'history', label: 'Waitlist History' },
]

export default function Waitlist() {
  useDocumentTitle('Waitlist & Slot Offers')
  const [params] = useSearchParams()
  const [mainTab, setMainTab] = useState(params.get('tab') || 'active')
  const [openJoin, setOpenJoin] = useState(Boolean(params.get('doctor_id')))
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()

  // Offers state
  const [offers, setOffers] = useState([])
  const [loadingOffers, setLoadingOffers] = useState(false)
  const [offerError, setOfferError] = useState(null)
  const [activeOfferAction, setActiveOfferAction] = useState(null) // { offer, type: 'accept' | 'decline' }
  const [decisionReason, setDecisionReason] = useState('')
  const [decisionBusy, setDecisionBusy] = useState(false)
  const [leaveTarget, setLeaveTarget] = useState(null)
  const [leaving, setLeaving] = useState(false)

  // Active waitlist entries paged
  const activePaged = usePaged((p) => listMyWaitlist({ ...p, status: WAITLIST_STATUS.ACTIVE }), [])

  // History entries paged
  const historyPaged = usePaged((p) => getMyWaitlistHistory(p), [])

  const reloadOffers = async () => {
    setLoadingOffers(true)
    setOfferError(null)
    try {
      const data = await listMyOffers()
      setOffers(data || [])
    } catch (err) {
      setOfferError(err)
    } finally {
      setLoadingOffers(false)
    }
  }

  useEffect(() => {
    reloadOffers()
  }, [])

  const pendingOffersCount = offers.filter((o) => o.status === WAITLIST_OFFER_STATUS.PENDING).length

  const handleLeaveConfirm = async () => {
    if (!leaveTarget) return
    setLeaving(true)
    try {
      await leaveWaitlist(leaveTarget.id)
      toast.success('Removed from the waitlist.')
      setLeaveTarget(null)
      activePaged.reload()
      historyPaged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLeaving(false)
    }
  }

  const handleDecisionSubmit = async () => {
    if (!activeOfferAction) return
    const { offer, type } = activeOfferAction
    setDecisionBusy(true)
    try {
      if (type === 'accept') {
        await acceptOffer(offer.id, decisionReason)
        toast.success(
          'Slot offer accepted! Your appointment request has been submitted to the doctor for confirmation.',
        )
      } else {
        await declineOffer(offer.id, decisionReason)
        toast.success('Offer declined. The slot has been released for the next patient in line.')
      }
      setActiveOfferAction(null)
      setDecisionReason('')
      reloadOffers()
      activePaged.reload()
      historyPaged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setDecisionBusy(false)
    }
  }

  const tabsWithBadges = MAIN_TABS.map((t) => {
    if (t.value === 'offers' && pendingOffersCount > 0) {
      return { ...t, label: `Slot Offers (${pendingOffersCount})` }
    }
    return t
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Waitlist & Reallocation"
        description="Track your queue position, manage preferences, and respond to exclusive slot offers."
        actions={
          <Button onClick={() => setOpenJoin(true)}>
            <Plus size={16} aria-hidden="true" />
            Join a waitlist
          </Button>
        }
      />

      <Alert tone="info" icon={Sparkles} title="Intelligent Automated Slot Reallocation" className="text-xs">
        When another patient reschedules or cancels, Nivara reserves the freed slot exclusively for the next
        eligible waitlisted patient. Accepting an offer submits your booking request to the doctor for approval.
      </Alert>

      <Tabs tabs={tabsWithBadges} value={mainTab} onChange={setMainTab} />

      {/* TAB 1: ACTIVE WAITLIST */}
      {mainTab === 'active' && (
        <AsyncBoundary
          loading={activePaged.loading}
          error={activePaged.error}
          onRetry={activePaged.reload}
          isEmpty={activePaged.isEmpty}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={BellRing}
              title="No active waitlist entries"
              description="Add a doctor, department or specialty and Nivara will watch for openings."
              action={<Button onClick={() => setOpenJoin(true)}>Join a waitlist</Button>}
            />
          }
        >
          <div className="space-y-4">
            {activePaged.items.map((entry) => (
              <Card key={entry.id} className="transition-all hover:border-forest-300">
                <CardBody className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-base font-semibold text-forest-800">
                        {entry.specialty ||
                          departmentById[entry.department_id]?.name ||
                          hospitalById[entry.hospital_id]?.name ||
                          'Any matching appointment'}
                      </p>
                      {entry.queue_position !== undefined && entry.queue_position !== null && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-forest-100 px-2.5 py-0.5 text-xs font-semibold text-forest-700">
                          <Users size={12} aria-hidden="true" />
                          Queue Position #{entry.queue_position}
                        </span>
                      )}
                      {entry.patients_ahead > 0 && (
                        <span className="text-xs text-ink-muted">
                          ({entry.patients_ahead} patient{entry.patients_ahead === 1 ? '' : 's'} ahead)
                        </span>
                      )}
                      {entry.queue_position === 1 && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-ok-soft px-2.5 py-0.5 text-xs font-semibold text-ok">
                          <CheckCircle2 size={12} aria-hidden="true" />
                          Next in line!
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-ink-muted">
                      Preferred dates: <strong className="text-ink">{formatDate(entry.date_from)}</strong> –{' '}
                      <strong className="text-ink">{formatDate(entry.date_to)}</strong>
                      {entry.time_from && entry.time_to && (
                        <> · Preferred window: {formatTime(entry.time_from)} – {formatTime(entry.time_to)}</>
                      )}
                    </p>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
                      {entry.hospital_id && (
                        <span>Hospital: {hospitalById[entry.hospital_id]?.name || 'Affiliated'}</span>
                      )}
                      {entry.department_id && (
                        <span>Department: {departmentById[entry.department_id]?.name}</span>
                      )}
                      {entry.consultation_type && (
                        <span>Type: {entry.consultation_type.replace('_', ' ')}</span>
                      )}
                      <span>Joined: {formatDate(entry.created_at)}</span>
                    </div>

                    {entry.notified_slot_ids?.length > 0 && (
                      <p className="mt-1 text-xs font-medium text-forest-600">
                        Received {entry.notified_slot_ids.length} opening notification
                        {entry.notified_slot_ids.length === 1 ? '' : 's'}.
                      </p>
                    )}
                  </div>

                  <div className="flex shrink-0 items-center gap-3">
                    <StatusBadge status={entry.status} kind="generic" />
                    <Button variant="ghost" size="sm" onClick={() => setLeaveTarget(entry)}>
                      Leave waitlist
                    </Button>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          <Pagination
            className="mt-6"
            page={activePaged.page}
            totalPages={activePaged.totalPages}
            total={activePaged.total}
            pageSize={activePaged.pageSize}
            onChange={activePaged.setPage}
          />
        </AsyncBoundary>
      )}

      {/* TAB 2: SLOT OFFERS */}
      {mainTab === 'offers' && (
        <AsyncBoundary
          loading={loadingOffers}
          error={offerError}
          onRetry={reloadOffers}
          isEmpty={offers.length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={Sparkles}
              title="No slot offers currently available"
              description="When a compatible slot is cancelled or rescheduled by another patient, Nivara will reserve it and display your offer here."
            />
          }
        >
          <div className="space-y-4">
            {offers.map((offer) => {
              const isPending = offer.status === WAITLIST_OFFER_STATUS.PENDING
              const isAccepted = offer.status === WAITLIST_OFFER_STATUS.ACCEPTED
              const isDeclined = offer.status === WAITLIST_OFFER_STATUS.DECLINED
              const isExpired = offer.status === WAITLIST_OFFER_STATUS.EXPIRED

              return (
                <Card
                  key={offer.id}
                  className={`overflow-hidden border transition-all ${
                    isPending
                      ? 'border-forest-400 bg-white shadow-md ring-1 ring-forest-400/30'
                      : 'border-line bg-surface'
                  }`}
                >
                  <CardHeader
                    className={`${isPending ? 'bg-forest-50/70' : 'bg-surface-sunken/40'} border-b border-line py-3`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink">
                          {offer.doctor_name ? `Dr. ${offer.doctor_name}` : 'Doctor Slot Offer'}
                        </span>
                        {offer.specialty && (
                          <span className="text-xs text-ink-muted">({offer.specialty})</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {isPending && (
                          <OfferCountdown
                            expiresAt={offer.expires_at}
                            onExpire={() => reloadOffers()}
                          />
                        )}
                        <StatusBadge status={offer.status} kind="generic" />
                      </div>
                    </div>
                  </CardHeader>

                  <CardBody className="space-y-4 pt-4">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <p className="text-xs text-ink-muted">Date</p>
                        <p className="text-sm font-semibold text-ink">
                          {offer.appointment_date ? formatLongDate(offer.appointment_date) : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted">Time Window</p>
                        <p className="text-sm font-semibold text-ink">
                          {offer.start_time && offer.end_time
                            ? `${formatTime(offer.start_time)} – ${formatTime(offer.end_time)}`
                            : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted">Hospital</p>
                        <p className="text-sm font-medium text-ink">
                          {offer.hospital_name || hospitalById[offer.hospital_id]?.name || 'Hospital Clinic'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted">Department</p>
                        <p className="text-sm font-medium text-ink">
                          {offer.department_name || departmentById[offer.department_id]?.name || 'Outpatient'}
                        </p>
                      </div>
                    </div>

                    {isPending && (
                      <Alert tone="warn" title="Exclusive Time-Limited Reservation" className="text-xs">
                        This slot is currently held exclusively for you. If accepted, an appointment request
                        is submitted for doctor approval. If you decline or take no action before the timer expires,
                        the slot is automatically offered to the next waitlisted patient.
                      </Alert>
                    )}

                    {isAccepted && (
                      <p className="flex items-center gap-1.5 text-xs text-ok">
                        <CheckCircle2 size={14} />
                        Accepted on {formatInstant(offer.responded_at || offer.updated_at)}. Appointment request submitted.
                      </p>
                    )}

                    {isDeclined && (
                      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                        <XCircle size={14} />
                        Declined on {formatInstant(offer.responded_at || offer.updated_at)}. Slot released to queue.
                      </p>
                    )}

                    {isExpired && (
                      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                        <Clock size={14} />
                        Offer expired. The slot was automatically offered to the next patient in line.
                      </p>
                    )}

                    {isPending && (
                      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setActiveOfferAction({ offer, type: 'decline' })
                            setDecisionReason('')
                          }}
                        >
                          Decline offer
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setActiveOfferAction({ offer, type: 'accept' })
                            setDecisionReason('')
                          }}
                        >
                          <CheckCircle2 size={15} aria-hidden="true" />
                          Accept & Book Slot
                        </Button>
                      </div>
                    )}
                  </CardBody>
                </Card>
              )
            })}
          </div>
        </AsyncBoundary>
      )}

      {/* TAB 3: WAITLIST HISTORY */}
      {mainTab === 'history' && (
        <AsyncBoundary
          loading={historyPaged.loading}
          error={historyPaged.error}
          onRetry={historyPaged.reload}
          isEmpty={historyPaged.isEmpty}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={Clock}
              title="No past waitlist history"
              description="Fulfilled, expired and cancelled waitlist requests will be logged here."
            />
          }
        >
          <div className="space-y-3">
            {historyPaged.items.map((entry) => (
              <Card key={entry.id} className="border-line bg-surface-sunken/20">
                <CardBody className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-semibold text-ink">
                      {entry.specialty ||
                        departmentById[entry.department_id]?.name ||
                        hospitalById[entry.hospital_id]?.name ||
                        'Appointment Waitlist'}
                    </p>
                    <p className="text-xs text-ink-muted">
                      Requested: {formatDate(entry.date_from)} – {formatDate(entry.date_to)}
                    </p>
                    <p className="text-xs text-ink-muted">
                      Entry created {formatDate(entry.created_at)} · Resolved {formatDate(entry.updated_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusBadge status={entry.status} kind="generic" />
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          <Pagination
            className="mt-6"
            page={historyPaged.page}
            totalPages={historyPaged.totalPages}
            total={historyPaged.total}
            pageSize={historyPaged.pageSize}
            onChange={historyPaged.setPage}
          />
        </AsyncBoundary>
      )}

      {/* JOIN WAITLIST MODAL */}
      <JoinModal
        open={openJoin}
        onClose={() => setOpenJoin(false)}
        presetDoctorId={params.get('doctor_id')}
        onDone={() => {
          setOpenJoin(false)
          setMainTab('active')
          activePaged.reload()
        }}
      />

      {/* OFFER DECISION MODAL */}
      {activeOfferAction && (
        <Modal
          open={Boolean(activeOfferAction)}
          onClose={() => setActiveOfferAction(null)}
          title={
            activeOfferAction.type === 'accept'
              ? 'Accept Slot & Submit Appointment Request'
              : 'Decline Slot Offer'
          }
          description={
            activeOfferAction.type === 'accept'
              ? 'Confirming will immediately reserve this slot and send an appointment request to the doctor for confirmation.'
              : 'Declining will release this held slot immediately, making it available for the next patient in line.'
          }
          footer={
            <>
              <Button
                variant="ghost"
                onClick={() => setActiveOfferAction(null)}
                disabled={decisionBusy}
              >
                Cancel
              </Button>
              <Button
                variant={activeOfferAction.type === 'accept' ? 'primary' : 'danger'}
                onClick={handleDecisionSubmit}
                loading={decisionBusy}
              >
                {activeOfferAction.type === 'accept' ? 'Accept Offer' : 'Decline & Release Slot'}
              </Button>
            </>
          }
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-surface-sunken/40 p-3 text-xs space-y-1">
              <p>
                <strong>Doctor:</strong> {activeOfferAction.offer.doctor_name || 'Assigned Doctor'}
              </p>
              <p>
                <strong>Date & Time:</strong>{' '}
                {activeOfferAction.offer.appointment_date}{' '}
                {activeOfferAction.offer.start_time && `at ${formatTime(activeOfferAction.offer.start_time)}`}
              </p>
            </div>
            <Textarea
              label="Optional Note or Clinical Context"
              placeholder={
                activeOfferAction.type === 'accept'
                  ? 'Briefly describe your symptoms or reason for visit...'
                  : 'Optional reason for declining (e.g., schedule conflict)...'
              }
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
              rows={3}
            />
          </div>
        </Modal>
      )}

      <ConfirmationModal
        open={Boolean(leaveTarget)}
        onClose={() => setLeaveTarget(null)}
        onConfirm={handleLeaveConfirm}
        loading={leaving}
        tone="danger"
        title="Leave this waitlist?"
        confirmLabel="Leave waitlist"
        cancelLabel="Stay in queue"
      >
        <p className="text-sm text-ink-muted">
          You will lose your current queue position for{' '}
          <strong className="text-forest-700">
            {leaveTarget?.specialty ||
              departmentById[leaveTarget?.department_id]?.name ||
              hospitalById[leaveTarget?.hospital_id]?.name ||
              'this waitlist request'}
          </strong>
          . You can always rejoin later, though you will start at the back of the queue.
        </p>
      </ConfirmationModal>
    </div>
  )
}

function OfferCountdown({ expiresAt, onExpire }) {
  const [timeLeft, setTimeLeft] = useState(() =>
    Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000)),
  )

  useEffect(() => {
    const timer = setInterval(() => {
      const remaining = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))
      setTimeLeft(remaining)
      if (remaining <= 0) {
        clearInterval(timer)
        onExpire?.()
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [expiresAt, onExpire])

  if (timeLeft <= 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-semibold text-danger">
        <Clock size={12} />
        Expired
      </span>
    )
  }

  const mins = Math.floor(timeLeft / 60)
  const secs = timeLeft % 60
  const isUrgent = mins < 3

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        isUrgent
          ? 'bg-danger-soft text-danger animate-pulse border border-danger/30'
          : 'bg-warn-soft text-warn border border-warn/30'
      }`}
    >
      <Clock size={12} aria-hidden="true" />
      Expires in {mins}m {secs.toString().padStart(2, '0')}s
    </span>
  )
}

function JoinModal({ open, onClose, presetDoctorId, onDone }) {
  const toast = useToast()
  const { hospitals, departments } = useDirectory()
  const today = todayString()

  const [form, setForm] = useState({
    doctor_id: presetDoctorId || '',
    hospital_id: '',
    department_id: '',
    specialty: '',
    date_from: today,
    date_to: addDays(today, 30),
    time_from: '',
    time_to: '',
    consultation_type: '',
  })
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const valid =
    Boolean(form.doctor_id || form.department_id || form.hospital_id || form.specialty.trim()) &&
    form.date_from &&
    form.date_to

  const submit = async () => {
    setBusy(true)
    try {
      await joinWaitlist({
        doctor_id: form.doctor_id || undefined,
        hospital_id: form.hospital_id || undefined,
        department_id: form.department_id || undefined,
        specialty: form.specialty.trim() || undefined,
        date_from: form.date_from,
        date_to: form.date_to,
        time_from: form.time_from || undefined,
        time_to: form.time_to || undefined,
        consultation_type: form.consultation_type || undefined,
      })
      toast.success("You're on the waitlist! We'll reserve any compatible slot that frees up and notify you.")
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Join a waitlist"
      description="Tell Nivara what doctor, department or time window you're waiting for."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!valid}>
            Join waitlist
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-xs text-ink-muted">
          Specify at least one criteria: hospital, department, specialty or doctor.
        </p>
        <Select
          label="Hospital"
          placeholder="Any hospital"
          value={form.hospital_id}
          onChange={(e) => setForm((f) => ({ ...f, hospital_id: e.target.value, department_id: '' }))}
          options={hospitals.map((h) => ({ value: h.id, label: h.name }))}
        />
        <Select
          label="Department"
          placeholder="Any department"
          value={form.department_id}
          onChange={set('department_id')}
          options={departments
            .filter((d) => !form.hospital_id || d.hospital_id === form.hospital_id)
            .map((d) => ({ value: d.id, label: d.name }))}
        />
        <Input
          label="Specialty"
          value={form.specialty}
          onChange={set('specialty')}
          maxLength={80}
          placeholder="e.g. Cardiology, Dermatology"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="From" type="date" required min={today} value={form.date_from} onChange={set('date_from')} />
          <Input label="To" type="date" required min={form.date_from} value={form.date_to} onChange={set('date_to')} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Earliest time (optional)" type="time" value={form.time_from} onChange={set('time_from')} />
          <Input label="Latest time (optional)" type="time" value={form.time_to} onChange={set('time_to')} />
        </div>
        <Select
          label="Consultation type (optional)"
          placeholder="Any type"
          value={form.consultation_type}
          onChange={set('consultation_type')}
          options={CONSULTATION_TYPES}
        />
      </div>
    </Modal>
  )
}
