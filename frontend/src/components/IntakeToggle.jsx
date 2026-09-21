import { useState } from 'react'
import { DoorClosed, DoorOpen } from 'lucide-react'
import { Button } from './ui/Button'
import { ConfirmationModal } from './ui/Modal'
import { Textarea } from './ui/Field'
import { INTAKE_STATUS } from '../utils/constants'

/**
 * Opens or closes NEW appointment intake for a hospital, department or doctor.
 * The copy states the rule the backend enforces: closing intake stops new
 * requests and never cancels appointments that already exist.
 */
export function IntakeToggle({ status, onChange, label, size = 'sm', disabled = false }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const closing = status === INTAKE_STATUS.OPEN
  const next = closing ? INTAKE_STATUS.CLOSED : INTAKE_STATUS.OPEN

  const confirm = async () => {
    setSaving(true)
    try {
      await onChange(next, reason.trim() || undefined)
      setOpen(false)
      setReason('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Button
        variant={closing ? 'outline' : 'primary'}
        size={size}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        {closing ? <DoorClosed size={15} aria-hidden="true" /> : <DoorOpen size={15} aria-hidden="true" />}
        {closing ? 'Close new appointments' : 'Reopen new appointments'}
      </Button>

      <ConfirmationModal
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={confirm}
        loading={saving}
        tone={closing ? 'danger' : 'primary'}
        title={closing ? `Close new appointments${label ? ` for ${label}` : ''}?` : `Reopen new appointments${label ? ` for ${label}` : ''}?`}
        confirmLabel={closing ? 'Close intake' : 'Reopen intake'}
        cancelLabel="Keep as is"
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {closing
              ? 'New requests will be turned away while intake is closed. Appointments that are already requested or confirmed stay exactly as they are — none of them are cancelled.'
              : 'Patients will be able to request new appointments again straight away.'}
          </p>
          <Textarea
            label="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            maxLength={300}
            placeholder="Recorded in the audit trail"
          />
        </div>
      </ConfirmationModal>
    </>
  )
}
