import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, UserX } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { FilterBar } from '../../components/FilterBar'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Modal, ConfirmationModal } from '../../components/ui/Modal'
import { Input, Select } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { createAdmin, listUsers, setUserActive, setUserScope } from '../../api/admin'
import { ROLES } from '../../utils/constants'
import { formatInstant, humanise } from '../../utils/format'
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

  const [createOpen, setCreateOpen] = useState(false)
  const [scopeFor, setScopeFor] = useState(null)
  const [toggling, setToggling] = useState(null)
  const [busy, setBusy] = useState(false)

  const paged = usePaged(
    (p) =>
      listUsers({
        ...p,
        role: role || undefined,
        is_active: active === '' ? undefined : active === 'true',
      }),
    [role, active],
  )

  const setParam = (key) => (value) => {
    const next = Object.fromEntries(params)
    if (value) next[key] = value
    else delete next[key]
    setParams(next, { replace: true })
  }

  const confirmToggle = async () => {
    setBusy(true)
    try {
      await setUserActive(toggling.id, !toggling.is_active)
      toast.success(toggling.is_active ? 'Account deactivated.' : 'Account reactivated.')
      setToggling(null)
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
        description="Every account on the platform."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} aria-hidden="true" />
            New administrator
          </Button>
        }
      />

      <FilterBar
        hasActive={Boolean(role || active)}
        onClear={() => setParams({}, { replace: true })}
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
                    <Badge tone="neutral">{u.managed_hospital_ids.length} hospital(s)</Badge>
                  ),
              },
              {
                key: 'is_active',
                header: 'Status',
                render: (u) => (
                  <Badge tone={u.is_active ? 'positive' : 'neutral'}>
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
                  <span className="flex justify-end gap-2">
                    {u.role === ROLES.ADMIN && u.id !== me?.id && (
                      <Button variant="ghost" size="sm" onClick={() => setScopeFor(u)}>
                        Scope
                      </Button>
                    )}
                    {u.id !== me?.id && (
                      <Button variant="ghost" size="sm" onClick={() => setToggling(u)}>
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
        <p className="text-sm text-ink-muted">
          {toggling?.is_active
            ? `${toggling?.name} loses access immediately, on every device. Their appointments are not changed.`
            : `${toggling?.name} will be able to sign in again.`}
        </p>
      </ConfirmationModal>
    </div>
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
        // null means platform-wide; a list creates a hospital administrator.
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

  // Seed from the account being edited whenever a different one is opened.
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
