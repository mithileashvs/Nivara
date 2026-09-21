import { useState } from 'react'
import { FileText, Link2, Paperclip, Trash2 } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Card, CardBody } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { Input, Select } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { addDocument, listRecords, removeDocument } from '../../api/medicalRecords'
import { DOCUMENT_TYPES } from '../../utils/constants'
import { formatInstant, humanise } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Records are written by the treating doctor; patients read them and may attach
 * document references. The backend stores metadata plus an https link to a file
 * already in object storage — there is no upload endpoint, so this page asks for
 * a link rather than pretending to accept a file.
 */
export default function MedicalRecords() {
  useDocumentTitle('Medical records')
  const paged = usePaged((p) => listRecords(p), [])
  const [attachTo, setAttachTo] = useState(null)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medical records"
        description="Consultation notes written by your doctors, and documents linked to them."
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton rows={3} />}
        empty={
          <EmptyState
            icon={FileText}
            title="No records yet"
            description="After a consultation, your doctor's notes appear here. Only you and the doctor who wrote them can see them."
          />
        }
      >
        <div className="space-y-4">
          {paged.items.map((record) => (
            <RecordCard
              key={record.id}
              record={record}
              onAttach={() => setAttachTo(record)}
              onChanged={paged.reload}
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

      <AttachDocumentModal
        record={attachTo}
        onClose={() => setAttachTo(null)}
        onDone={() => {
          setAttachTo(null)
          paged.reload()
        }}
      />
    </div>
  )
}

function RecordCard({ record, onAttach, onChanged }) {
  const toast = useToast()
  const [removing, setRemoving] = useState(null)

  const remove = async (documentId) => {
    setRemoving(documentId)
    try {
      await removeDocument(record.id, documentId)
      toast.success('Document removed.')
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setRemoving(null)
    }
  }

  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-forest-700">Consultation notes</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              Written {formatInstant(record.created_at)}
              {record.updated_at !== record.created_at && ` · updated ${formatInstant(record.updated_at)}`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onAttach}>
            <Paperclip size={14} aria-hidden="true" />
            Link a document
          </Button>
        </div>

        <p className="whitespace-pre-wrap rounded-xl bg-forest-50/60 px-4 py-3.5 text-sm leading-relaxed text-ink">
          {record.notes}
        </p>

        {record.documents?.length > 0 && (
          <ul className="space-y-2 border-t border-line pt-4">
            {record.documents.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3">
                <Link2 size={15} className="shrink-0 text-ink-faint" aria-hidden="true" />
                <a
                  href={doc.file_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="min-w-0 flex-1 truncate rounded text-sm text-forest transition-colors hover:text-forest-400 focus-ring"
                >
                  {doc.filename}
                </a>
                <span className="shrink-0 rounded-md bg-forest-50 px-2 py-0.5 text-[0.7rem] text-forest-500">
                  {humanise(doc.document_type)}
                </span>
                <button
                  type="button"
                  onClick={() => remove(doc.id)}
                  disabled={removing === doc.id}
                  aria-label={`Remove ${doc.filename}`}
                  className="rounded p-1 text-ink-faint transition-colors hover:text-danger focus-ring disabled:opacity-50"
                >
                  <Trash2 size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}

function AttachDocumentModal({ record, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ filename: '', file_url: '', document_type: 'OTHER' })
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setBusy(true)
    try {
      await addDocument(record.id, {
        filename: form.filename.trim(),
        file_url: form.file_url.trim(),
        document_type: form.document_type,
      })
      toast.success('Document linked.')
      setForm({ filename: '', file_url: '', document_type: 'OTHER' })
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(record)}
      onClose={onClose}
      title="Link a document"
      description="Nivara stores the reference, not the file itself."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!form.filename.trim() || !form.file_url.trim()}>
            Link document
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-xs leading-relaxed text-ink-muted">
          Paste the https link to a file that is already stored somewhere — a lab portal, for
          example. Your hospital decides which locations are accepted, so a link elsewhere will be
          refused.
        </p>
        <Input
          label="Document name"
          required
          value={form.filename}
          onChange={set('filename')}
          maxLength={200}
          placeholder="Blood test results, March"
        />
        <Input
          label="Link"
          type="url"
          required
          value={form.file_url}
          onChange={set('file_url')}
          placeholder="https://…"
        />
        <Select
          label="Type"
          value={form.document_type}
          onChange={set('document_type')}
          options={DOCUMENT_TYPES}
        />
      </div>
    </Modal>
  )
}
