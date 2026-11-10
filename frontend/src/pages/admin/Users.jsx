import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Eye, Lock, Plus, UserX } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { AuditDetailModal } from '../../components/audit/AuditDetailModal'
import { Avatar } from '../../components/ui/Avatar'
import { Badge, StatusBadge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Modal, ConfirmationModal } from '../../components/ui/Modal'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, ErrorState, LoadingBlock, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { createAdmin, getUserDetail, listUsers, setUserScope, updateUserStatus } from '../../api/admin'
import { AUDIT_SEVERITY_TONE, ROLES } from '../../utils/constants'
import { formatInstant, humanise, pluralise, relativeTime } from '../../utils/format'
import { errorMessage, fieldErrors } from '../../utils/errors'

/** Platform-admin only. Hospital-scoped admins are refused this endpoint (403). */
export default function AdminUsers() {
  useDocumentTitle('Users')
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const { user: me } = useAuth()
  const { hospitals } = useDirectory()

  const role = params.get('role') || ''
  const active = params.get('is_active') || ''
  const [searchInput, setSearchInput] = useState(params.get('q') || '')
  const debouncedQ = useDebounced(searchInput.trim())

  const [createOpen, setCreateOpen] = useState(false)
  const [detailUser, setDetailUser] = useState(null)
  const [scopeFor, setScopeFor] = useState(null)
  const [toggling, setToggling] = useState(null)
  const [toggleReason, setToggleReason] = useState('')
  const [busy, setBusy] = useState(false)

  const paged = usePaged(
    (p) =>
      listUsers({
        ...p,
        q: debouncedQ || undefined,
        role: role || undefined,
        is_active: active === '' ? undefined : active === 'true',
      }),
    [debouncedQ, role, active],
  )

  const setParam = (key) => (value) => {
    const next = Object.fromEntries(params)
    if (value) next[key] = value
    else delete next[key]
    setParams(next, { replace: true })
  }

  const handleSearchChange = (value) => {
    setSearchInput(value)
    setParam('q')(value.trim())
  }

  const openToggle = (userRow) => {
    setToggleReason('')
    setToggling(userRow)
  }

  const confirmToggle = async () => {
    if (!toggling) return
    setBusy(true)
    try {
      await updateUserStatus(toggling.id, !toggling.is_active, toggleReason.trim() || undefined)
      toast.success(toggling.is_active ? 'Account deactivated.' : 'Account reactivated.')
      setToggling(null)
      setToggleReason('')
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Search accounts, inspect activity summaries, manage administrator scope, and moderate access."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} aria-hidden="true" />
            New administrator
          </Button>
        }
      />

      <SearchBar
        value={searchInput}
        onChange={handleSearchChange}
        placeholder="Search by user name or email…"
        label="Search users"
      />

      <FilterBar
        hasActive={Boolean(role || active || debouncedQ)}
        onClear={() => {
          setSearchInput('')
          setParams({}, { replace: true })
        }}
        filters={[
          {
            key: 'role',
            label: 'Role',
            value: role,
            onChange: setParam('role'),
            options: Object.values(ROLES).map((r) => ({ value: r, label: humanise(r) })),
          },
          {
            key: 'is_active',
            label: 'Status',
            value: active,
            onChange: setParam('is_active'),
            options: [
              { value: 'true', label: 'Active' },
              { value: 'false', label: 'Deactivated' },
            ],
          },
        ]}
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={<EmptyState icon={UserX} title="No users match those filters" />}
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Platform users"
            rows={paged.items}
            onRowClick={setDetailUser}
            columns={[
              {
                key: 'name',
                header: 'Name',
                render: (u) => (
                  <span className="flex items-center gap-3">
                    <Avatar name={u.name} size="sm" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-forest-700">{u.name}</span>
                      <span className="block truncate text-xs text-ink-muted">{u.email}</span>
                    </span>
                  </span>
                ),
              },
              { key: 'role', header: 'Role', render: (u) => humanise(u.role) },
              {
                key: 'scope',
                header: 'Scope',
                hideOnMobile: true,
                render: (u) =>
                  u.role !== ROLES.ADMIN ? (
                    <span className="text-ink-faint">—</span>
                  ) : u.managed_hospital_ids === null ? (
                    <Badge tone="info">Platform-wide</Badge>
                  ) : (
                    <Badge tone="neutral">{pluralise(u.managed_hospital_ids.length, 'hospital', 'hospitals')}</Badge>
                  ),
              },
              {
                key: 'is_active',
                header: 'Status',
                render: (u) => (
                  <Badge tone={u.is_active ? 'positive' : 'negative'}>
                    {u.is_active ? 'Active' : 'Deactivated'}
                  </Badge>
                ),
              },
              {
                key: 'created_at',
                header: 'Joined',
                hideOnMobile: true,
                render: (u) => formatInstant(u.created_at),
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (u) => (
                  <span className="flex justify-end gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        setDetailUser(u)
                      }}
                    >
                      <Eye size={14} aria-hidden="true" />
                      Inspect
                    </Button>
                    {u.role === ROLES.ADMIN && u.id !== me?.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setScopeFor(u)
                        }}
                      >
                        Scope
                      </Button>
                    )}
                    {u.id !== me?.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className={u.is_active ? 'text-danger hover:bg-danger-soft' : 'text-ok hover:bg-ok-soft'}
                        onClick={(e) => {
                          e.stopPropagation()
                          openToggle(u)
                        }}
                      >
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    )}
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

      <CreateAdminModal
        open={createOpen}
        hospitals={hospitals}
        onClose={() => setCreateOpen(false)}
        onDone={() => {
          setCreateOpen(false)
          paged.reload()
        }}
      />

      <UserDetailModal
        userRow={detailUser}
        meId={me?.id}
        onClose={() => setDetailUser(null)}
        onRequestToggle={(u) => {
          setDetailUser(null)
          openToggle(u)
        }}
      />

      <ScopeModal
        user={scopeFor}
        hospitals={hospitals}
        onClose={() => setScopeFor(null)}
        onDone={() => {
          setScopeFor(null)
          paged.reload()
        }}
      />

      <ConfirmationModal
        open={Boolean(toggling)}
        onClose={() => setToggling(null)}
        onConfirm={confirmToggle}
        loading={busy}
        tone={toggling?.is_active ? 'danger' : 'primary'}
        title={toggling?.is_active ? 'Deactivate this account?' : 'Reactivate this account?'}
        confirmLabel={toggling?.is_active ? 'Deactivate' : 'Reactivate'}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {toggling?.is_active
              ? `${toggling?.name} loses access immediately across all sessions. Existing appointments remain untouched.`
              : `${toggling?.name} will regain sign-in access.`}
          </p>
          <Textarea
            label="Reason (recorded in audit log, optional)"
            value={toggleReason}
            onChange={(e) => setToggleReason(e.target.value)}
            rows={3}
            maxLength={300}
            placeholder="e.g. Verified request from compliance team"
          />
        </div>
      </ConfirmationModal>
    </div>
  )
}

function UserDetailModal({ userRow, meId, onClose, onRequestToggle }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [inspectLog, setInspectLog] = useState(null)

  const load = (id) => {
    setLoading(true)
    setError(null)
    getUserDetail(id)
      .then((res) => setData(res))
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!userRow?.id) {
      setData(null)
      return
    }
    load(userRow.id)
  }, [userRow?.id])

  const u = data?.user || userRow
  const profile = data?.profile_summary
  const history = data?.recent_activity || []

  return (
    <>
      <Modal
        open={Boolean(userRow)}
        onClose={onClose}
        title={u ? u.name : 'User detail'}
        description={u ? `${u.email} · ${humanise(u.role)}` : undefined}
        size="lg"
        footer={
          <div className="flex w-full flex-wrap items-center justify-between gap-2">
            {u && u.id !== meId ? (
              <Button
                variant={u.is_active ? 'outline' : 'primary'}
                size="sm"
                onClick={() => onRequestToggle(u)}
              >
                {u.is_active ? 'Deactivate account' : 'Reactivate account'}
              </Button>
            ) : (
              <span />
            )}
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        }
      >
        {loading ? (
          <LoadingBlock label="Loading account summary" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => load(userRow.id)} compact />
        ) : u ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-forest-50/40 p-4">
              <div className="flex items-center gap-3">
                <Avatar name={u.name} size="md" />
                <div>
                  <p className="text-sm font-semibold text-forest-700">{u.name}</p>
                  <p className="text-xs text-ink-muted">{u.email}</p>
                  {u.phone && <p className="text-xs text-ink-faint">{u.phone}</p>}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={u.is_active ? 'positive' : 'negative'}>
                  {u.is_active ? 'Active' : 'Deactivated'}
                </Badge>
                <Badge tone="neutral">{humanise(u.role)}</Badge>
              </div>
            </div>

            {profile && (
              <div className="rounded-xl border border-line p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  Role & Scope Summary
                </p>
                {u.role === ROLES.DOCTOR && profile.profile_id && (
                  <div className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
                    <div>
                      <span className="text-xs text-ink-muted">Specialty</span>
                      <p className="font-medium text-forest-700">{profile.specialty || '—'}</p>
                    </div>
                    <div>
                      <span className="text-xs text-ink-muted">Verification & Intake</span>
                      <div className="mt-0.5 flex flex-wrap gap-1.5">
                        <StatusBadge status={profile.profile_status} kind="generic" />
                        <StatusBadge status={profile.availability_status} kind="generic" />
                      </div>
                    </div>
                  </div>
                )}
                {u.role === ROLES.ADMIN && (
                  <div className="mt-2 text-sm text-forest-700">
                    {u.managed_hospital_ids === null ? (
                      <Badge tone="info">Platform-wide administrator</Badge>
                    ) : (
                      <div>
                        <p className="text-xs text-ink-muted">Managed hospitals</p>
                        <p className="mt-0.5 font-medium">
                          {profile.managed_hospitals?.length
                            ? profile.managed_hospitals.map((h) => h.name).join(', ')
                            : 'None assigned'}
                        </p>
                      </div>
                    )}
                  </div>
                )}
                {u.role === ROLES.PATIENT && (
                  <p className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
                    <Lock size={13} aria-hidden="true" />
                    Patient clinical records, diagnoses, and medical documents are closed to administrators.
                  </p>
                )}
              </div>
            )}

            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Recent Audit Activity
              </p>
              {history.length === 0 ? (
                <p className="mt-2 rounded-xl border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                  No recent audit events recorded for this account.
                </p>
              ) : (
                <ul className="mt-2 divide-y divide-line overflow-hidden rounded-xl border border-line">
                  {history.map((evt) => (
                    <li key={evt.id}>
                      <button
                        type="button"
                        onClick={() => setInspectLog(evt)}
                        className="flex w-full cursor-pointer flex-wrap items-start justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-forest-50/50 focus-ring"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={AUDIT_SEVERITY_TONE[evt.severity] || 'neutral'}>
                              {evt.severity}
                            </Badge>
                            <span className="text-xs font-semibold text-forest-700">
                              {humanise(evt.action)}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-ink-muted">{evt.description}</p>
                        </div>
                        <span className="shrink-0 text-xs text-ink-faint">
                          {relativeTime(evt.created_at) || formatInstant(evt.created_at)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </Modal>

      <AuditDetailModal log={inspectLog} onClose={() => setInspectLog(null)} />
    </>
  )
}

function CreateAdminModal({ open, hospitals, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ name: '', email: '', phone: '', password: '', scope: 'platform' })
  const [selected, setSelected] = useState([])
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setBusy(true)
    setErrors({})
    try {
      await createAdmin({
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
        managed_hospital_ids: form.scope === 'platform' ? null : selected,
      })
      toast.success('Administrator created.')
      setForm({ name: '', email: '', phone: '', password: '', scope: 'platform' })
      setSelected([])
      onDone()
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const valid =
    form.name.trim().length >= 2 &&
    form.email.includes('@') &&
    form.password.length >= 8 &&
    (form.scope === 'platform' || selected.length > 0)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create an administrator"
      description="Platform-wide, or limited to specific hospitals."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!valid}>
            Create administrator
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label="Full name" required value={form.name} onChange={set('name')} error={errors.name} />
        <Input label="Email" type="email" required value={form.email} onChange={set('email')} error={errors.email} />
        <Input label="Phone (optional)" type="tel" value={form.phone} onChange={set('phone')} error={errors.phone} />
        <Input
          label="Temporary password"
          type="password"
          required
          value={form.password}
          onChange={set('password')}
          error={errors.password}
          hint="At least 8 characters, with a letter and a number."
        />
        <Select
          label="Access"
          value={form.scope}
          onChange={set('scope')}
          options={[
            { value: 'platform', label: 'Platform-wide administrator' },
            { value: 'hospital', label: 'Hospital administrator' },
          ]}
        />
        {form.scope === 'hospital' && (
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-forest-700">Hospitals they manage</legend>
            <HospitalPicker hospitals={hospitals} selected={selected} onChange={setSelected} />
          </fieldset>
        )}
      </div>
    </Modal>
  )
}

function ScopeModal({ user, hospitals, onClose, onDone }) {
  const toast = useToast()
  const [scope, setScope] = useState('platform')
  const [selected, setSelected] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!user) return
    const scoped = Array.isArray(user.managed_hospital_ids)
    setScope(scoped ? 'hospital' : 'platform')
    setSelected(scoped ? user.managed_hospital_ids : [])
  }, [user])

  const submit = async () => {
    setBusy(true)
    try {
      await setUserScope(user.id, scope === 'platform' ? null : selected)
      toast.success('Access updated.')
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(user)}
      onClose={onClose}
      title={`Access for ${user?.name ?? ''}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={scope === 'hospital' && !selected.length}>
            Save access
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label="Access"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          options={[
            { value: 'platform', label: 'Platform-wide administrator' },
            { value: 'hospital', label: 'Hospital administrator' },
          ]}
        />
        {scope === 'hospital' && (
          <HospitalPicker hospitals={hospitals} selected={selected} onChange={setSelected} />
        )}
        <p className="text-xs leading-relaxed text-ink-muted">
          A hospital administrator manages only the hospitals listed here, and cannot reach
          platform-wide settings, user management or doctor verification.
        </p>
      </div>
    </Modal>
  )
}

function HospitalPicker({ hospitals, selected, onChange }) {
  const toggle = (id) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <ul className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-line p-2">
      {hospitals.map((h) => (
        <li key={h.id}>
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-forest-50">
            <input
              type="checkbox"
              checked={selected.includes(h.id)}
              onChange={() => toggle(h.id)}
              className="h-4 w-4 rounded border-line accent-[#173C2B] focus-ring"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-ink">{h.name}</span>
          </label>
        </li>
      ))}
      {hospitals.length === 0 && (
        <li className="px-2 py-3 text-sm text-ink-muted">No hospitals exist yet.</li>
      )}
    </ul>
  )
}
