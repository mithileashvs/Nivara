import { useEffect, useState } from 'react'
import { Plus, ShieldCheck, X } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { MedicalDisclaimer } from '../../components/MedicalDisclaimer'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Modal, ConfirmationModal } from '../../components/ui/Modal'
import { Checkbox, Input } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  createRoutingRule, deleteRoutingRule, listRoutingRules, updateRoutingRule,
} from '../../api/admin'
import { errorMessage, fieldErrors } from '../../utils/errors'

/**
 * The keyword rules behind symptom routing. These map symptom words to a
 * department name for booking. They are not diagnostic rules and must not be
 * written as though they were.
 */
export default function AdminRoutingRules() {
  useDocumentTitle('Symptom routing rules')
  const toast = useToast()
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(false)

  const paged = usePaged((p) => listRoutingRules(p), [])

  const remove = async () => {
    setBusy(true)
    try {
      await deleteRoutingRule(toDelete.id)
      toast.success('Rule deleted.')
      setToDelete(null)
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (rule) => {
    try {
      await updateRoutingRule(rule.id, { is_active: !rule.is_active })
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Symptom routing rules"
        description="Maps what a patient describes to the department they should book with."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden="true" />
            New rule
          </Button>
        }
      />

      <MedicalDisclaimer />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={
          <EmptyState
            icon={ShieldCheck}
            title="No routing rules"
            description="Without rules, symptom routing has nothing to match against."
            action={<Button onClick={() => setCreating(true)}>New rule</Button>}
          />
        }
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Department routing rules"
            rows={paged.items}
            columns={[
              {
                key: 'department_name',
                header: 'Routes to',
                render: (r) => <span className="font-medium text-forest-700">{r.department_name}</span>,
              },
              {
                key: 'keywords',
                header: 'Keywords',
                render: (r) => (
                  <span className="flex flex-wrap gap-1">
                    {r.keywords.slice(0, 6).map((k) => (
                      <span key={k} className="rounded-md bg-forest-50 px-1.5 py-0.5 text-[0.7rem] text-forest-500">
                        {k}
                      </span>
                    ))}
                    {r.keywords.length > 6 && (
                      <span className="text-[0.7rem] text-ink-faint">+{r.keywords.length - 6}</span>
                    )}
                  </span>
                ),
              },
              { key: 'weight', header: 'Weight', hideOnMobile: true, render: (r) => r.weight },
              {
                key: 'flags',
                header: 'Flags',
                render: (r) => (
                  <span className="flex flex-wrap gap-1.5">
                    <Badge tone={r.is_active ? 'positive' : 'neutral'}>
                      {r.is_active ? 'Active' : 'Off'}
                    </Badge>
                    {r.is_emergency && <Badge tone="negative">Emergency notice</Badge>}
                  </span>
                ),
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (r) => (
                  <span className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => toggleActive(r)}>
                      {r.is_active ? 'Turn off' : 'Turn on'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setEditing(r)}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setToDelete(r)}>
                      Delete
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

      <RuleModal
        open={creating || Boolean(editing)}
        rule={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onDone={() => {
          setCreating(false)
          setEditing(null)
          paged.reload()
          toast.success('Rule saved.')
        }}
      />

      <ConfirmationModal
        open={Boolean(toDelete)}
        onClose={() => setToDelete(null)}
        onConfirm={remove}
        loading={busy}
        tone="danger"
        title="Delete this rule?"
        confirmLabel="Delete rule"
      >
        <p className="text-sm text-ink-muted">
          Symptom routing will stop suggesting {toDelete?.department_name} for these keywords.
        </p>
      </ConfirmationModal>
    </div>
  )
}

function RuleModal({ open, rule, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({
    department_name: '',
    weight: '1',
    is_emergency: false,
    is_active: true,
  })
  const [keywords, setKeywords] = useState([])
  const [draft, setDraft] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setErrors({})
    setDraft('')
    if (rule) {
      setForm({
        department_name: rule.department_name,
        weight: String(rule.weight),
        is_emergency: rule.is_emergency,
        is_active: rule.is_active,
      })
      setKeywords(rule.keywords)
    } else {
      setForm({ department_name: '', weight: '1', is_emergency: false, is_active: true })
      setKeywords([])
    }
  }, [open, rule])

  const addKeyword = () => {
    const v = draft.trim().toLowerCase()
    if (!v || keywords.includes(v) || keywords.length >= 100) return
    setKeywords((k) => [...k, v.slice(0, 60)])
    setDraft('')
  }

  const submit = async () => {
    setBusy(true)
    setErrors({})
    const payload = {
      department_name: form.department_name.trim(),
      keywords,
      weight: Number(form.weight),
      is_emergency: form.is_emergency,
      is_active: form.is_active,
    }
    try {
      if (rule) await updateRoutingRule(rule.id, payload)
      else await createRoutingRule(payload)
      onDone()
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={rule ? 'Edit routing rule' : 'New routing rule'}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            loading={busy}
            disabled={form.department_name.trim().length < 2 || keywords.length === 0}
          >
            Save rule
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label="Department name"
          required
          value={form.department_name}
          onChange={(e) => setForm((f) => ({ ...f, department_name: e.target.value }))}
          maxLength={80}
          error={errors.department_name}
          hint="Matched against real department names when suggesting where to book."
        />

        <div>
          <label htmlFor="keyword" className="mb-1.5 block text-sm font-medium text-forest-700">
            Keywords
          </label>
          <div className="flex gap-2">
            <input
              id="keyword"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addKeyword()
                }
              }}
              maxLength={60}
              placeholder="chest pain"
              className="h-11 flex-1 rounded-xl border border-line bg-surface px-3.5 text-sm placeholder:text-ink-faint hover:border-forest-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
            />
            <Button variant="secondary" onClick={addKeyword} disabled={!draft.trim()}>
              Add
            </Button>
          </div>
          {errors.keywords && <p className="mt-1.5 text-xs text-danger">{errors.keywords}</p>}
          {keywords.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {keywords.map((k) => (
                <li key={k}>
                  <button
                    type="button"
                    onClick={() => setKeywords((prev) => prev.filter((x) => x !== k))}
                    className="inline-flex items-center gap-1 rounded-full border border-forest-200 bg-forest-50 px-2.5 py-1 text-xs text-forest-700 transition-colors hover:border-danger/40 hover:bg-danger-soft focus-ring"
                  >
                    {k}
                    <X size={12} aria-hidden="true" />
                    <span className="sr-only">Remove {k}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <Input
          label="Weight"
          type="number"
          min="0.1"
          max="100"
          step="0.1"
          value={form.weight}
          onChange={(e) => setForm((f) => ({ ...f, weight: e.target.value }))}
          error={errors.weight}
          hint="Higher weights rank this department above others that also match."
        />

        <Checkbox
          label="Show an emergency notice when this rule matches"
          checked={form.is_emergency}
          onChange={(e) => setForm((f) => ({ ...f, is_emergency: e.target.checked }))}
        />
        <Checkbox
          label="Rule is active"
          checked={form.is_active}
          onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
        />
      </div>
    </Modal>
  )
}
