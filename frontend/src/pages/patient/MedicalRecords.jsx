import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  FileCheck,
  FileText,
  History,
  Image as ImageIcon,
  Link2,
  Paperclip,
  Search,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UploadCloud,
  UserCheck,
  X,
} from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/StatusBadge'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { DataTable } from '../../components/ui/DataTable'
import { Modal } from '../../components/ui/Modal'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { Tabs } from '../../components/ui/Tabs'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { searchDoctors } from '../../api/doctors'
import {
  addDocument,
  deletePatientDocument,
  downloadMedicalDocument,
  getMedicalAudits,
  getMedicalTimeline,
  listDocumentShares,
  listPatientDocuments,
  listRecords,
  removeDocument,
  revokeDocumentShare,
  shareDocumentWithDoctor,
  uploadMedicalDocument,
} from '../../api/medicalRecords'
import {
  DOCUMENT_TYPES,
  MEDICAL_CATEGORY_LABEL,
  MEDICAL_DOCUMENT_CATEGORIES,
} from '../../utils/constants'
import { formatBytes, formatDate, formatInstant, humanise } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const MAIN_TABS = [
  { value: 'documents', label: 'Medical Documents' },
  { value: 'timeline', label: 'Medical Timeline' },
  { value: 'notes', label: 'Consultation Notes' },
  { value: 'audits', label: 'Access History' },
]

const CATEGORY_TABS = [
  { value: '', label: 'All Categories' },
  ...MEDICAL_DOCUMENT_CATEGORIES.map((c) => ({ value: c.value, label: c.label })),
]

export default function MedicalRecords() {
  useDocumentTitle('Medical Records')
  const toast = useToast()

  const [activeTab, setActiveTab] = useState('documents')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [shareDoc, setShareDoc] = useState(null)
  const [deleteDoc, setDeleteDoc] = useState(null)
  const [attachToNote, setAttachToNote] = useState(null)

  // 1. Documents Paged Data
  const docPaged = usePaged(
    (p) => listPatientDocuments({ ...p, category: categoryFilter || undefined, search: searchQuery || undefined }),
    [categoryFilter, searchQuery],
  )

  // 2. Timeline Paged Data
  const timelinePaged = usePaged(
    (p) => getMedicalTimeline(p),
    [],
    { enabled: activeTab === 'timeline' },
  )

  // 3. Consultation Notes Paged Data
  const notesPaged = usePaged(
    (p) => listRecords(p),
    [],
    { enabled: activeTab === 'notes' },
  )

  // 4. Access Audits Paged Data
  const auditPaged = usePaged(
    (p) => getMedicalAudits(p),
    [],
    { enabled: activeTab === 'audits' },
  )

  // Handle document download
  const handleDownload = async (doc) => {
    try {
      toast.info(`Preparing download for ${doc.filename}...`)
      const blob = await downloadMedicalDocument(doc.id)
      const url = window.URL.createObjectURL(new Blob([blob.data || blob], { type: doc.file_type }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', doc.filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Download started.')
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medical Records"
        description="Securely manage your personal medical documents, view consultation history, and manage doctor sharing."
        actions={
          <Button variant="primary" onClick={() => setUploadOpen(true)}>
            <UploadCloud size={16} aria-hidden="true" />
            Upload Document
          </Button>
        }
      />

      <Tabs tabs={MAIN_TABS} value={activeTab} onChange={setActiveTab} />

      {/* ===================================================================
          TAB 1: MEDICAL DOCUMENTS
          =================================================================== */}
      {activeTab === 'documents' && (
        <div className="space-y-5">
          {/* Filters & Search */}
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <Tabs tabs={CATEGORY_TABS} value={categoryFilter} onChange={setCategoryFilter} />
            <div className="relative w-full md:w-72">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                type="text"
                placeholder="Search title or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-10 w-full rounded-xl border border-line bg-surface pl-10 pr-4 text-sm text-ink placeholder:text-ink-faint focus:border-forest focus:outline-none focus-visible:ring-1 focus-visible:ring-forest"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          <AsyncBoundary
            loading={docPaged.loading}
            error={docPaged.error}
            onRetry={docPaged.reload}
            isEmpty={docPaged.isEmpty}
            skeleton={<LoadingSkeleton rows={3} />}
            empty={
              <EmptyState
                icon={FileText}
                title="No medical documents found"
                description={
                  categoryFilter || searchQuery
                    ? 'No documents match the current filters. Try resetting search or category.'
                    : 'You have not uploaded any medical documents yet. Click "Upload Document" to add your lab results, prescriptions, or imaging.'
                }
                action={
                  <Button variant="outline" onClick={() => setUploadOpen(true)}>
                    <UploadCloud size={15} />
                    Upload your first document
                  </Button>
                }
              />
            }
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {docPaged.items.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  doc={doc}
                  onDownload={() => handleDownload(doc)}
                  onShare={() => setShareDoc(doc)}
                  onDelete={() => setDeleteDoc(doc)}
                />
              ))}
            </div>

            <Pagination
              className="mt-6"
              page={docPaged.page}
              totalPages={docPaged.totalPages}
              total={docPaged.total}
              pageSize={docPaged.pageSize}
              onChange={docPaged.setPage}
            />
          </AsyncBoundary>
        </div>
      )}

      {/* ===================================================================
          TAB 2: MEDICAL TIMELINE
          =================================================================== */}
      {activeTab === 'timeline' && (
        <AsyncBoundary
          loading={timelinePaged.loading}
          error={timelinePaged.error}
          onRetry={timelinePaged.reload}
          isEmpty={timelinePaged.isEmpty}
          skeleton={<LoadingSkeleton rows={4} />}
          empty={
            <EmptyState
              icon={History}
              title="No timeline events recorded"
              description="Your chronological clinical timeline will populate as you complete consultations, book appointments, and upload documents."
            />
          }
        >
          <Card>
            <CardBody className="p-6">
              <ol className="relative border-l border-line pl-6 space-y-6">
                {timelinePaged.items.map((item) => (
                  <TimelineItem key={item.id} item={item} />
                ))}
              </ol>

              <Pagination
                className="mt-8 border-t border-line pt-4"
                page={timelinePaged.page}
                totalPages={timelinePaged.totalPages}
                total={timelinePaged.total}
                pageSize={timelinePaged.pageSize}
                onChange={timelinePaged.setPage}
              />
            </CardBody>
          </Card>
        </AsyncBoundary>
      )}

      {/* ===================================================================
          TAB 3: CONSULTATION NOTES (PRESERVED)
          =================================================================== */}
      {activeTab === 'notes' && (
        <AsyncBoundary
          loading={notesPaged.loading}
          error={notesPaged.error}
          onRetry={notesPaged.reload}
          isEmpty={notesPaged.isEmpty}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={FileText}
              title="No consultation notes yet"
              description="Notes recorded by your doctors after confirmed appointments will appear here."
            />
          }
        >
          <div className="space-y-4">
            {notesPaged.items.map((record) => (
              <ConsultationNoteCard
                key={record.id}
                record={record}
                onAttach={() => setAttachToNote(record)}
                onChanged={notesPaged.reload}
              />
            ))}
          </div>
          <Pagination
            className="mt-6"
            page={notesPaged.page}
            totalPages={notesPaged.totalPages}
            total={notesPaged.total}
            pageSize={notesPaged.pageSize}
            onChange={notesPaged.setPage}
          />
        </AsyncBoundary>
      )}

      {/* ===================================================================
          TAB 4: ACCESS HISTORY / AUDIT LOG
          =================================================================== */}
      {activeTab === 'audits' && (
        <AsyncBoundary
          loading={auditPaged.loading}
          error={auditPaged.error}
          onRetry={auditPaged.reload}
          isEmpty={auditPaged.isEmpty}
          skeleton={<LoadingSkeleton rows={4} />}
          empty={
            <EmptyState
              icon={ShieldCheck}
              title="No access events logged"
              description="All access to your medical documents (views, downloads, shares) is securely audited here."
            />
          }
        >
          <Card>
            <CardHeader
              title="Security & Access Audit Trail"
              description="Chronological log of document uploads, authorized doctor views, downloads, and consent modifications."
            />
            <CardBody className="p-0">
              <DataTable
                caption="Medical document access history"
                rows={auditPaged.items}
                columns={[
                  {
                    key: 'action',
                    header: 'Action',
                    render: (a) => <AuditActionBadge action={a.action} />,
                  },
                  {
                    key: 'actor',
                    header: 'Actor',
                    render: (a) => (
                      <span className="font-medium text-forest-800">{humanise(a.actor_role)}</span>
                    ),
                  },
                  {
                    key: 'created_at',
                    header: 'Timestamp',
                    render: (a) => (
                      <span className="text-xs text-ink-muted">{formatInstant(a.created_at)}</span>
                    ),
                  },
                  {
                    key: 'details',
                    header: 'Details',
                    render: (a) => (
                      <span className="text-xs text-ink-muted">
                        {[
                          a.metadata?.title ? `Document: "${a.metadata.title}"` : null,
                          a.metadata?.doctor_name ? `Doctor: ${a.metadata.doctor_name}` : null,
                          a.reason || null,
                        ]
                          .filter(Boolean)
                          .join(' · ') || '—'}
                      </span>
                    ),
                  },
                ]}
              />
              <Pagination
                className="border-t border-line p-4"
                page={auditPaged.page}
                totalPages={auditPaged.totalPages}
                total={auditPaged.total}
                pageSize={auditPaged.pageSize}
                onChange={auditPaged.setPage}
              />
            </CardBody>
          </Card>
        </AsyncBoundary>
      )}

      {/* Modals */}
      <UploadDocumentModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={() => {
          setUploadOpen(false)
          docPaged.reload()
          timelinePaged.reload()
        }}
      />

      <ShareConsentModal
        doc={shareDoc}
        onClose={() => setShareDoc(null)}
        onChanged={() => {
          docPaged.reload()
        }}
      />

      <DeleteConfirmModal
        doc={deleteDoc}
        onClose={() => setDeleteDoc(null)}
        onSuccess={() => {
          setDeleteDoc(null)
          docPaged.reload()
          timelinePaged.reload()
        }}
      />

      <AttachDocumentModal
        record={attachToNote}
        onClose={() => setAttachToNote(null)}
        onDone={() => {
          setAttachToNote(null)
          notesPaged.reload()
        }}
      />
    </div>
  )
}

/* ===========================================================================
   DOCUMENT CARD COMPONENT
   =========================================================================== */
function DocumentCard({ doc, onDownload, onShare, onDelete }) {
  const activeShares = (doc.shares || []).filter((s) => s.consent_status === 'GRANTED')
  const isShared = activeShares.length > 0

  return (
    <Card interactive className="flex flex-col justify-between">
      <CardBody className="space-y-3.5 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <div className="shrink-0 rounded-xl bg-forest-50 p-2.5 text-forest">
              {doc.category === 'IMAGING' ? <ImageIcon size={20} /> : <FileText size={20} />}
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-forest-800" title={doc.title}>
                {doc.title}
              </h3>
              <p className="mt-0.5 truncate text-xs text-ink-muted" title={doc.filename}>
                {doc.filename} · {formatBytes(doc.file_size)}
              </p>
            </div>
          </div>
          <span className="shrink-0 rounded-md bg-forest-50 px-2.5 py-1 text-[0.7rem] font-medium text-forest-700">
            {MEDICAL_CATEGORY_LABEL[doc.category] || humanise(doc.category)}
          </span>
        </div>

        {doc.description && (
          <p className="line-clamp-2 rounded-lg bg-forest-50/40 p-2.5 text-xs leading-relaxed text-ink-muted">
            {doc.description}
          </p>
        )}

        {/* Sharing status badge */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          {isShared ? (
            <Badge tone="positive" icon={ShieldCheck}>
              Shared with {activeShares.length} {activeShares.length === 1 ? 'doctor' : 'doctors'}
            </Badge>
          ) : (
            <Badge tone="neutral" icon={ShieldAlert}>
              Private (Only you)
            </Badge>
          )}
          <span className="ml-auto text-[0.7rem] text-ink-faint">
            Uploaded {formatDate(doc.created_at)}
          </span>
        </div>
      </CardBody>

      <div className="flex items-center justify-between border-t border-line bg-surface-muted/60 px-5 py-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onDownload} title="Download file securely">
            <Download size={14} />
            Download
          </Button>
          <Button variant="ghost" size="sm" onClick={onShare} title="Manage doctor sharing and consent">
            <Share2 size={14} />
            {isShared ? 'Manage Sharing' : 'Share with Doctor'}
          </Button>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="rounded p-1.5 text-ink-faint transition-colors hover:text-danger focus-ring"
          title="Delete document"
          aria-label={`Delete ${doc.title}`}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </Card>
  )
}

/* ===========================================================================
   UPLOAD DOCUMENT MODAL
   =========================================================================== */
function UploadDocumentModal({ open, onClose, onSuccess }) {
  const toast = useToast()
  const fileInputRef = useRef(null)

  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('LAB_REPORT')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragActive, setDragActive] = useState(false)

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0]
    if (selected) {
      if (selected.size > 25 * 1024 * 1024) {
        toast.error('File size exceeds the 25 MB limit.')
        return
      }
      setFile(selected)
      if (!title.trim()) {
        const baseName = selected.name.replace(/\.[^/.]+$/, '')
        setTitle(baseName)
      }
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) {
      if (dropped.size > 25 * 1024 * 1024) {
        toast.error('File size exceeds the 25 MB limit.')
        return
      }
      setFile(dropped)
      if (!title.trim()) {
        const baseName = dropped.name.replace(/\.[^/.]+$/, '')
        setTitle(baseName)
      }
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) {
      toast.error('Please choose a file to upload.')
      return
    }
    if (!title.trim()) {
      toast.error('Please provide a document title.')
      return
    }

    setBusy(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title.trim())
      formData.append('category', category)
      if (description.trim()) {
        formData.append('description', description.trim())
      }

      await uploadMedicalDocument(formData)
      toast.success('Medical document uploaded securely.')
      setFile(null)
      setTitle('')
      setDescription('')
      onSuccess()
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
      title="Upload Medical Document"
      description="Upload private medical reports, imaging, or prescriptions (PDF, JPG, PNG, WebP, TIFF up to 25MB)."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="upload-document-form" loading={busy} disabled={!file || !title.trim()}>
            Upload Document
          </Button>
        </>
      }
    >
      <form id="upload-document-form" onSubmit={handleSubmit} className="space-y-4">
        {/* Drag & Drop Area */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Choose a medical document file to upload"
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          className={`relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-colors focus-ring ${
            dragActive
              ? 'border-forest bg-forest-50/80'
              : file
              ? 'border-ok/40 bg-ok-soft/45'
              : 'border-line bg-forest-50/20 hover:border-forest-300'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.tiff,.tif"
            onChange={handleFileChange}
            className="hidden"
          />

          {file ? (
            <div className="flex flex-col items-center">
              <CheckCircle2 size={32} className="mb-2 text-ok" />
              <p className="text-sm font-semibold text-forest-800">{file.name}</p>
              <p className="mt-0.5 text-xs text-ink-muted">{formatBytes(file.size)}</p>
              <span className="mt-2 text-xs text-forest underline">Click or drop to replace</span>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <UploadCloud size={32} className="mb-2 text-forest" />
              <p className="text-sm font-semibold text-forest-800">
                Click to browse or drag and drop file here
              </p>
              <p className="mt-1 text-xs text-ink-muted">PDF, JPEG, PNG, WebP, TIFF (Max 25 MB)</p>
            </div>
          )}
        </div>

        <Input
          label="Document title"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Complete Blood Count (CBC) Report"
        />

        <Select
          label="Category"
          required
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          options={MEDICAL_DOCUMENT_CATEGORIES}
        />

        <Textarea
          label="Description / Clinical Notes (optional)"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Routine 6-month follow-up lab test performed at Apollo Clinic"
        />
      </form>
    </Modal>
  )
}

/* ===========================================================================
   SHARE & CONSENT MANAGEMENT MODAL
   =========================================================================== */
function ShareConsentModal({ doc, onClose, onChanged }) {
  const toast = useToast()
  const [shares, setShares] = useState([])
  const [loadingShares, setLoadingShares] = useState(false)
  const [doctorsList, setDoctorsList] = useState([])
  const [selectedDoctor, setSelectedDoctor] = useState('')
  const [shareNotes, setShareNotes] = useState('')
  const [busy, setBusy] = useState(false)

  // Fetch active shares for this document
  const reloadShares = async () => {
    if (!doc) return
    setLoadingShares(true)
    try {
      const data = await listDocumentShares(doc.id)
      setShares(data || [])
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLoadingShares(false)
    }
  }

  // Fetch verified active doctors
  useEffect(() => {
    if (doc) {
      reloadShares()
      searchDoctors({ page: 1, page_size: 50 })
        .then((res) => {
          setDoctorsList(res.items || [])
        })
        .catch(() => {})
    }
  }, [doc])

  const handleGrant = async () => {
    if (!selectedDoctor) {
      toast.error('Please choose a doctor to share with.')
      return
    }
    setBusy(true)
    try {
      await shareDocumentWithDoctor(doc.id, {
        doctor_id: selectedDoctor,
        notes: shareNotes.trim() || undefined,
      })
      toast.success('Document access granted to doctor.')
      setSelectedDoctor('')
      setShareNotes('')
      await reloadShares()
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleRevoke = async (doctorId) => {
    setBusy(true)
    try {
      await revokeDocumentShare(doc.id, doctorId)
      toast.success('Doctor access revoked immediately.')
      await reloadShares()
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const activeShares = shares.filter((s) => s.consent_status === 'GRANTED')
  const revokedShares = shares.filter((s) => s.consent_status === 'REVOKED')

  // Doctors who don't already have an active share
  const availableDoctors = doctorsList.filter(
    (d) => !activeShares.some((s) => s.doctor_id === d.id),
  )

  return (
    <Modal
      open={Boolean(doc)}
      onClose={onClose}
      title="Medical Document Consent & Sharing"
      description={`Manage which doctors have authorized access to "${doc?.title}". Access can be revoked at any time.`}
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Currently Authorized Doctors */}
        <div>
          <h4 className="text-xs font-semibold text-forest uppercase tracking-wider mb-2.5">
            Currently Authorized Doctors ({activeShares.length})
          </h4>
          {loadingShares ? (
            <div className="skeleton h-12 w-full" />
          ) : activeShares.length === 0 ? (
            <p className="rounded-xl border border-line bg-forest-50/40 p-3.5 text-xs text-ink-muted">
              This document is completely private. No doctors currently have access.
            </p>
          ) : (
            <ul className="divide-y divide-line rounded-xl border border-line overflow-hidden">
              {activeShares.map((s) => (
                <li key={s.id} className="flex items-center justify-between p-3.5 bg-surface text-sm">
                  <div>
                    <p className="font-semibold text-forest-800">
                      Dr. {s.doctor_name || 'Doctor'}
                    </p>
                    <p className="text-xs text-ink-muted mt-0.5">
                      {s.doctor_specialty || 'General Practitioner'} · Granted {formatDate(s.granted_at)}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRevoke(s.doctor_id)}
                    disabled={busy}
                    className="text-danger hover:bg-danger/10 border-danger/30"
                  >
                    Revoke Access
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Share with a New Doctor */}
        <div className="rounded-xl border border-line bg-forest-50/30 p-4 space-y-3.5">
          <h4 className="text-xs font-semibold text-forest-800 uppercase tracking-wider">
            Grant Access to a Doctor
          </h4>
          <Select
            label="Select doctor"
            value={selectedDoctor}
            onChange={(e) => setSelectedDoctor(e.target.value)}
            options={[
              { value: '', label: 'Select a verified doctor...' },
              ...availableDoctors.map((d) => ({
                value: d.id,
                label: `Dr. ${d.name} (${d.specialty || 'General'})`,
              })),
            ]}
          />
          <Input
            label="Note for doctor (optional)"
            value={shareNotes}
            onChange={(e) => setShareNotes(e.target.value)}
            placeholder="e.g. Please review before our follow-up consultation"
          />
          <Button
            variant="primary"
            size="sm"
            onClick={handleGrant}
            loading={busy}
            disabled={!selectedDoctor}
          >
            <UserCheck size={14} />
            Grant Sharing Consent
          </Button>
        </div>

        {/* Revoked history if any */}
        {revokedShares.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-ink-faint uppercase tracking-wider mb-2">
              Past Access History
            </h4>
            <ul className="text-xs text-ink-muted space-y-1.5 pl-2 border-l-2 border-line">
              {revokedShares.map((s) => (
                <li key={s.id}>
                  Dr. {s.doctor_name || 'Doctor'} · Revoked on {formatDate(s.revoked_at || s.updated_at)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  )
}

/* ===========================================================================
   DELETE CONFIRMATION MODAL
   =========================================================================== */
function DeleteConfirmModal({ doc, onClose, onSuccess }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)

  const handleDelete = async () => {
    if (!doc) return
    setBusy(true)
    try {
      await deletePatientDocument(doc.id)
      toast.success('Document deleted.')
      onSuccess()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(doc)}
      onClose={onClose}
      title="Delete Medical Document"
      description={`Are you sure you want to permanently delete "${doc?.title}"?`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} loading={busy}>
            Delete Permanently
          </Button>
        </>
      }
    >
      <Alert tone="danger" icon={AlertTriangle} title="Warning: Immediate Revocation" className="text-xs">
        Deleting this document will immediately remove the private file and permanently revoke access
        for all doctors it was previously shared with.
      </Alert>
    </Modal>
  )
}

/* ===========================================================================
   TIMELINE ITEM COMPONENT
   =========================================================================== */
function TimelineItem({ item }) {
  let icon = <Clock size={16} className="text-ink-muted" />
  let badgeTone = 'neutral'

  if (item.item_type === 'DOCUMENT') {
    icon = <FileText size={16} className="text-info" />
    badgeTone = 'info'
  } else if (item.item_type === 'APPOINTMENT') {
    icon = <Calendar size={16} className="text-ok" />
    badgeTone = 'positive'
  } else if (item.item_type === 'CONSULTATION_NOTE') {
    icon = <FileCheck size={16} className="text-forest-500" />
    badgeTone = 'neutral'
  }

  return (
    <li className="relative">
      <span className="absolute -left-9 flex h-7 w-7 items-center justify-center rounded-full border-2 border-forest-200 bg-surface shadow-sm">
        {icon}
      </span>
      <div className="rounded-xl border border-line bg-surface p-4 shadow-sm transition-shadow hover:shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-forest-800">{item.title}</h4>
            <Badge tone={badgeTone}>{humanise(item.item_type)}</Badge>
          </div>
          <span className="text-xs text-ink-muted">{formatDate(item.date)}</span>
        </div>

        {item.doctor_name && (
          <p className="mt-1 text-xs font-medium text-forest-600">Dr. {item.doctor_name}</p>
        )}

        {item.description && (
          <p className="mt-2 whitespace-pre-wrap rounded-lg bg-forest-50/40 p-2.5 text-xs leading-relaxed text-ink-muted">
            {item.description}
          </p>
        )}
      </div>
    </li>
  )
}

/* ===========================================================================
   AUDIT ACTION BADGE
   =========================================================================== */
function AuditActionBadge({ action }) {
  switch (action) {
    case 'UPLOAD':
      return <Badge tone="info">Uploaded</Badge>
    case 'VIEW':
      return <Badge tone="positive">Viewed</Badge>
    case 'DOWNLOAD':
      return <Badge tone="info">Downloaded</Badge>
    case 'SHARE_GRANTED':
      return <Badge tone="positive">Shared</Badge>
    case 'SHARE_REVOKED':
      return <Badge tone="pending">Revoked</Badge>
    case 'DELETE':
      return <Badge tone="negative">Deleted</Badge>
    case 'UNAUTHORIZED_ATTEMPT':
      return <Badge tone="negative">Blocked</Badge>
    default:
      return <Badge tone="neutral">{humanise(action)}</Badge>
  }
}

/* ===========================================================================
   CONSULTATION NOTE CARD (PRESERVED)
   =========================================================================== */
function ConsultationNoteCard({ record, onAttach, onChanged }) {
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
            Link reference
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

/* ===========================================================================
   ATTACH DOCUMENT MODAL (LEGACY LINK PRESERVED)
   =========================================================================== */
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
      title="Link a document reference"
      description="Nivara stores the reference URL linked to this consultation note."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!form.filename.trim() || !form.file_url.trim()}>
            Link reference
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label="Document name"
          required
          value={form.filename}
          onChange={set('filename')}
          maxLength={200}
          placeholder="Blood test results, March"
        />
        <Input
          label="Link URL"
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
