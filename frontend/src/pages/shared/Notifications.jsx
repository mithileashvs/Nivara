import { useEffect, useState } from 'react'
import { BellOff, CheckCheck, SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { NotificationItem } from '../../components/NotificationItem'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Tabs } from '../../components/ui/Tabs'
import { Modal } from '../../components/ui/Modal'
import { Checkbox } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useUnreadCount } from '../../hooks/useUnreadCount'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  deleteNotification,
  getNotificationPreferences,
  listNotifications,
  markAllRead,
  markRead,
  updateNotificationPreferences,
} from '../../api/notifications'
import { NOTIFICATION_CATEGORY } from '../../utils/constants'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { value: '', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: NOTIFICATION_CATEGORY.APPOINTMENT, label: 'Appointments' },
  { value: NOTIFICATION_CATEGORY.RESCHEDULING, label: 'Rescheduling' },
  { value: NOTIFICATION_CATEGORY.CANCELLATION, label: 'Cancellations' },
  { value: NOTIFICATION_CATEGORY.WAITLIST, label: 'Waitlist' },
  { value: NOTIFICATION_CATEGORY.SYSTEM, label: 'System' },
]

/** Shared notification centre for all roles. */
export default function Notifications({ appointmentPathPrefix = '/appointments' }) {
  useDocumentTitle('Notifications')
  const toast = useToast()
  const [filter, setFilter] = useState('')
  const [prefsOpen, setPrefsOpen] = useState(false)
  const { unread, refresh } = useUnreadCount()

  const isRead = filter === 'unread' ? false : undefined
  const category =
    filter && filter !== 'unread' && filter !== 'read' ? filter : undefined

  const paged = usePaged(
    (p) => listNotifications({ ...p, is_read: isRead, category }),
    [filter],
  )

  // Listen to real-time events to reload notification list live
  useEffect(() => {
    const handleRealtime = () => {
      paged.reload()
    }
    window.addEventListener('nivara:notification', handleRealtime)
    window.addEventListener('nivara:notification-read', handleRealtime)
    return () => {
      window.removeEventListener('nivara:notification', handleRealtime)
      window.removeEventListener('nivara:notification-read', handleRealtime)
    }
  }, [paged])

  const readOne = async (id) => {
    try {
      await markRead(id)
      paged.reload()
      refresh()
      window.dispatchEvent(new CustomEvent('nivara:notification-read'))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const deleteOne = async (id) => {
    try {
      await deleteNotification(id)
      toast.success('Notification dismissed.')
      paged.reload()
      refresh()
      window.dispatchEvent(new CustomEvent('nivara:notification-read'))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const readAll = async () => {
    try {
      const { message } = await markAllRead(category)
      toast.success(message)
      paged.reload()
      refresh()
      window.dispatchEvent(new CustomEvent('nivara:notification-read'))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Notifications"
        description={unread > 0 ? `${unread} unread` : 'You are all caught up.'}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPrefsOpen(true)}>
              <SlidersHorizontal size={14} aria-hidden="true" />
              Preferences
            </Button>
            {unread > 0 && (
              <Button variant="outline" size="sm" onClick={readAll}>
                <CheckCheck size={14} aria-hidden="true" />
                Mark all as read
              </Button>
            )}
          </div>
        }
      />

      <Tabs tabs={TABS} value={filter} onChange={setFilter} />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton rows={4} />}
        empty={
          <EmptyState
            icon={BellOff}
            title={filter === 'unread' ? 'No unread notifications' : 'Nothing here yet'}
            description="Updates about your appointments and activity will appear here."
          />
        }
      >
        <Card className="overflow-hidden">
          <ul className="divide-y divide-line">
            {paged.items.map((n) => (
              <NotificationItem
                key={n.id}
                notification={n}
                onMarkRead={readOne}
                onDelete={deleteOne}
                appointmentPathPrefix={appointmentPathPrefix}
              />
            ))}
          </ul>
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

      <NotificationPreferencesModal
        open={prefsOpen}
        onClose={() => setPrefsOpen(false)}
      />
    </div>
  )
}

function NotificationPreferencesModal({ open, onClose }) {
  const toast = useToast()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [prefs, setPrefs] = useState({
    appointment_updates: true,
    rescheduling_updates: true,
    cancellation_updates: true,
    waitlist_updates: true,
    system_announcements: true,
  })

  useEffect(() => {
    if (!open) return
    let active = true
    setLoading(true)
    getNotificationPreferences()
      .then((data) => {
        if (!active) return
        setPrefs({
          appointment_updates: data.appointment_updates ?? true,
          rescheduling_updates: data.rescheduling_updates ?? true,
          cancellation_updates: data.cancellation_updates ?? true,
          waitlist_updates: data.waitlist_updates ?? true,
          system_announcements: data.system_announcements ?? true,
        })
      })
      .catch((err) => {
        toast.error(errorMessage(err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [open, toast])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateNotificationPreferences(prefs)
      toast.success('Notification preferences updated.')
      onClose()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const toggle = (key) => (e) => {
    setPrefs((prev) => ({ ...prev, [key]: e.target.checked }))
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Notification Preferences"
      description="Choose the notification categories you want to receive."
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={saving} disabled={loading}>
            Save preferences
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="py-8 text-center text-sm text-ink-muted">Loading preferences...</div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <Checkbox
              id="pref-appt"
              label="Appointment updates"
              checked={prefs.appointment_updates}
              onChange={toggle('appointment_updates')}
            />
            <p className="ml-6 text-xs text-ink-muted">
              Notifications when appointments are requested, confirmed, or reminder alerts.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <Checkbox
              id="pref-resched"
              label="Rescheduling updates"
              checked={prefs.rescheduling_updates}
              onChange={toggle('rescheduling_updates')}
            />
            <p className="ml-6 text-xs text-ink-muted">
              Requests, approvals, and decisions on rescheduled appointment times.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <Checkbox
              id="pref-cancel"
              label="Cancellation notices"
              checked={prefs.cancellation_updates}
              onChange={toggle('cancellation_updates')}
            />
            <p className="ml-6 text-xs text-ink-muted">
              Alerts when appointments are cancelled by you or your healthcare provider.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <Checkbox
              id="pref-waitlist"
              label="Waitlist alerts"
              checked={prefs.waitlist_updates}
              onChange={toggle('waitlist_updates')}
            />
            <p className="ml-6 text-xs text-ink-muted">
              Alerts when an earlier slot opens up for your waitlisted appointments.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <Checkbox
              id="pref-system"
              label="System announcements"
              checked={prefs.system_announcements}
              onChange={toggle('system_announcements')}
            />
            <p className="ml-6 text-xs text-ink-muted">
              Platform notices, profile verification updates, and administrative announcements.
            </p>
          </div>
        </div>
      )}
    </Modal>
  )
}
