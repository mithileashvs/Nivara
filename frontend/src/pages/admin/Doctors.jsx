import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { History, Stethoscope } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { RatingStars } from '../../components/RatingStars'
import { AuditDetailModal } from '../../components/audit/AuditDetailModal'
import { Avatar } from '../../components/ui/Avatar'
import { Badge, StatusBadge } from '../../components/ui/StatusBadge'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Modal } from '../../components/ui/Modal'
import { Select, Textarea } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, ErrorState, LoadingBlock, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  getDoctorVerificationHistory,
  listDoctorVerification,
  setDoctorAffiliations,
  updateDoctorVerification,
} from '../../api/admin'
import { AUDIT_SEVERITY_TONE, PROFILE_STATUS } from '../../utils/constants'
import { formatInstant, humanise, pluralise, relativeTime } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { key: '', label: 'All doctors', countKey: 'total' },
  { key: PROFILE_STATUS.PENDING, label: 'Pending verification', countKey: 'pending' },
  { key: PROFILE_STATUS.ACTIVE, label: 'Verified (Active)', countKey: 'active' },
  { key: PROFILE_STATUS.SUSPENDED, label: 'Suspended / Rejected', countKey: 'suspended' },
]

/**
 * Doctor verification queue & hospital/department affiliation management.
 * Powered by GET /admin/doctor-verification and PATCH /admin/doctor-verification/{id}.
 */
export default function AdminDoctors() {
  useDocumentTitle('Doctors')
  const [params, setParams] = useSearchParams()
  const toast = useToast()

  const profileStatus = params.get('profile_status') || ''
  const [searchInput, setSearchInput] = useState(params.get('q') || '')
  const debouncedQ = useDebounced(searchInput.trim())
  const [counts, setCounts] = useState({ total: 0, pending: 0, active: 0, suspended: 0 })

  const [statusFor, setStatusFor] = useState(null)
  const [affiliationsFor, setAffiliationsFor] = useState(null)
  const [historyFor, setHistoryFor] = useState(null)

  const paged = usePaged(
    async (p) => {
      const res = await listDoctorVerification({
        ...p,
        profile_status: profileStatus || undefined,
        q: debouncedQ || undefined,
      })
      if (res?.counts) setCounts(res.counts)
      return res
    },
    [profileStatus, debouncedQ],
  )

  const setTab = (nextStatus) => {
    const next = Object.fromEntries(params)
    if (nextStatus) next.profile_status = nextStatus
    else delete next.profile_status
    setParams(next, { replace: true })
  }

  const handleSearch = (val) => {
    setSearchInput(val)
    const next = Object.fromEntries(params)
    if (val.trim()) next.q = val.trim()
    else delete next.q
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctors & verification"
        description="Verify doctor profiles, inspect verification audit history, and manage hospital/department affiliations."
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-line pb-3" role="tablist" aria-label="Doctor verification queues">
        {TABS.map((tab) => {
          const active = profileStatus === tab.key
          const count = counts[tab.countKey] ?? 0
          return (
            <button
              key={tab.key || 'all'}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(tab.key)}
              className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-colors focus-ring ${
                active
                  ? 'bg-forest text-canvas'
                  : 'bg-surface text-ink-muted border border-line hover:border-forest-200 hover:text-forest-700'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs tabular-nums ${
                  active ? 'bg-forest-700/70 text-canvas' : 'bg-forest-50 text-forest-700'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      <SearchBar
        value={searchInput}
        onChange={handleSearch}
        placeholder="Search doctors by name, specialty, or email…"
        label="Search doctors"
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={<EmptyState icon={Stethoscope} title="No doctor profiles match" />}
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Doctor profiles"
            rows={paged.items}
            columns={[
              {
                key: 'name',
                header: 'Doctor',
                render: (d) => (
                  <span className="flex items-center gap-3">
                    <Avatar name={d.name} size="sm" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-forest-700">{d.name}</span>
                      <span className="block truncate text-xs text-ink-muted">
                        {d.specialty}
                        {d.email ? ` · ${d.email}` : ''}
                      </span>
                    </span>
                  </span>
                ),
              },
              {
                key: 'profile_status',
                header: 'Verification',
                render: (d) => (
                  <div>
                    <StatusBadge status={d.profile_status} kind="generic" />
                    {d.latest_verification_reason && (
                      <p className="mt-1 max-w-[13rem] truncate text-xs text-ink-muted" title={d.latest_verification_reason}>
                        Note: {d.latest_verification_reason}
                      </p>
                    )}
                  </div>
                ),
              },
              {
                key: 'availability_status',
                header: 'Intake',
                render: (d) => <StatusBadge status={d.availability_status} kind="generic" />,
              },
              {
                key: 'affiliations',
                header: 'Affiliations',
                hideOnMobile: true,
                render: (d) =>
                  d.hospital_ids?.length ? (
                    <span className="text-xs text-ink-muted">
                      {d.hospital_names?.join(', ') || 'Assigned hospitals'}
                      {' · '}
                      {pluralise(d.department_ids?.length ?? 0, 'department', 'departments')}
                    </span>
                  ) : (
                    <span className="text-xs text-warn">Not assigned</span>
                  ),
              },
              {
                key: 'rating',
                header: 'Rating',
                hideOnMobile: true,
                render: (d) => <RatingStars average={d.rating_average} count={d.rating_count} />,
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (d) => (
                  <span className="flex justify-end gap-1.5">
                    <Button variant="ghost" size="sm" onClick={() => setHistoryFor(d)}>
                      <History size={14} aria-hidden="true" />
                      History
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setAffiliationsFor(d)}>
                      Affiliations
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setStatusFor(d)}>
                      Verify / Status
                    </Button>
                  </span>
                ),
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

      <StatusModal
        doctor={statusFor}
        onClose={() => setStatusFor(null)}
        onDone={() => {
          setStatusFor(null)
          paged.reload()
          toast.success('Doctor verification status updated.')
        }}
      />

      <AffiliationsModal
        doctor={affiliationsFor}
        onClose={() => setAffiliationsFor(null)}
        onDone={() => {
          setAffiliationsFor(null)
          paged.reload()
          toast.success('Affiliations updated.')
        }}
      />

      <VerificationHistoryModal
        doctor={historyFor}
        onClose={() => setHistoryFor(null)}
      />
    </div>
  )
}

function StatusModal({ doctor, onClose, onDone }) {
  const toast = useToast()
  const [status, setStatus] = useState(PROFILE_STATUS.ACTIVE)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (doctor) {
      setStatus(doctor.profile_status)
      setReason(doctor.latest_verification_reason || '')
    }
  }, [doctor])

  const submit = async () => {
    setBusy(true)
    try {
      await updateDoctorVerification(doctor.id, status, reason.trim() || undefined)
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(doctor)}
      onClose={onClose}
      title={`Verification decision — ${doctor?.name ?? ''}`}
      description="Changes are logged in the centralized audit trail and notify the doctor."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy}>
            Save verification status
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label="Verification Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: PROFILE_STATUS.PENDING, label: 'Pending — awaiting verification review' },
            { value: PROFILE_STATUS.ACTIVE, label: 'Verified (Active) — can publish availability & accept patients' },
            { value: PROFILE_STATUS.SUSPENDED, label: 'Suspended / Rejected — blocked from publishing or intake' },
          ]}
        />
        <Textarea
          label="Verification or suspension reason (recorded in audit log)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={300}
          placeholder="e.g. Medical license registration verified, or missing affiliation details"
        />
        <Alert tone="info">
          A doctor needs an active verified profile plus at least one affiliated hospital and department before patients can book with them.
        </Alert>
      </div>
    </Modal>
  )
}

function VerificationHistoryModal({ doctor, onClose }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [inspectLog, setInspectLog] = useState(null)

  const load = (id) => {
    setLoading(true)
    setError(null)
    getDoctorVerificationHistory(id)
      .then((res) => setHistory(Array.isArray(res) ? res : (res?.items || [])))
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!doctor?.id) {
      setHistory([])
      return
    }
    load(doctor.id)
  }, [doctor?.id])

  return (
    <>
      <Modal
        open={Boolean(doctor)}
        onClose={onClose}
        title={`Verification history — ${doctor?.name ?? ''}`}
        description="Chronological audit trail of verification, suspension, intake, and affiliation decisions."
        size="lg"
        footer={
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        }
      >
        {loading ? (
          <LoadingBlock label="Loading verification history" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => load(doctor.id)} compact />
        ) : history.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
            No verification audit events recorded yet for this doctor profile.
          </p>
        ) : (
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
            {history.map((evt) => (
              <li key={evt.id}>
                <button
                  type="button"
                  onClick={() => setInspectLog(evt)}
                  className="flex w-full cursor-pointer flex-wrap items-start justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-forest-50/50 focus-ring"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={AUDIT_SEVERITY_TONE[evt.severity] || 'neutral'}>
                        {evt.severity}
                      </Badge>
                      <span className="text-xs font-semibold text-forest-700">
                        {humanise(evt.action)}
                      </span>
                      {evt.actor_name && (
                        <span className="text-xs text-ink-faint">by {evt.actor_name}</span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-ink-muted">{evt.description}</p>
                    {evt.metadata?.reason && (
                      <p className="mt-1 text-xs font-medium text-forest-700">
                        Reason: {evt.metadata.reason}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs text-ink-muted">{formatInstant(evt.created_at)}</p>
                    <p className="text-xs text-ink-faint">{relativeTime(evt.created_at)}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <AuditDetailModal log={inspectLog} onClose={() => setInspectLog(null)} />
    </>
  )
}

function AffiliationsModal({ doctor, onClose, onDone }) {
  const toast = useToast()
  const { hospitals, departments } = useDirectory()
  const [hospitalIds, setHospitalIds] = useState([])
  const [departmentIds, setDepartmentIds] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (doctor) {
      setHospitalIds(doctor.hospital_ids ?? [])
      setDepartmentIds(doctor.department_ids ?? [])
    }
  }, [doctor])

  const selectableDepartments = departments.filter((d) => hospitalIds.includes(d.hospital_id))

  const toggle = (list, setList) => (id) =>
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])

  const submit = async () => {
    setBusy(true)
    try {
      await setDoctorAffiliations(doctor.id, {
        hospital_ids: hospitalIds,
        department_ids: departmentIds.filter((id) =>
          selectableDepartments.some((d) => d.id === id),
        ),
      })
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(doctor)}
      onClose={onClose}
      title={`Affiliations for ${doctor?.name ?? ''}`}
      description="Replaces the doctor's current hospitals and departments."
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy}>
            Save affiliations
          </Button>
        </>
      }
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-forest-700">Hospitals</legend>
          <CheckList
            items={hospitals.map((h) => ({ id: h.id, label: h.name }))}
            selected={hospitalIds}
            onToggle={(id) => {
              const next = hospitalIds.includes(id)
                ? hospitalIds.filter((x) => x !== id)
                : [...hospitalIds, id]
              setHospitalIds(next)
              setDepartmentIds((ds) =>
                ds.filter((did) => departments.find((d) => d.id === did && next.includes(d.hospital_id))),
              )
            }}
          />
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-forest-700">Departments</legend>
          <CheckList
            items={selectableDepartments.map((d) => ({ id: d.id, label: d.name }))}
            selected={departmentIds}
            onToggle={toggle(departmentIds, setDepartmentIds)}
            empty="Choose a hospital first."
          />
        </fieldset>
      </div>
    </Modal>
  )
}

function CheckList({ items, selected, onToggle, empty = 'Nothing to choose from.' }) {
  if (!items.length) return <p className="rounded-xl border border-line px-3 py-4 text-sm text-ink-muted">{empty}</p>
  return (
    <ul className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-line p-2">
      {items.map((item) => (
        <li key={item.id}>
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-forest-50">
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              onChange={() => onToggle(item.id)}
              className="h-4 w-4 rounded border-line accent-[#173C2B] focus-ring"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-ink">{item.label}</span>
          </label>
        </li>
      ))}
    </ul>
  )
}
