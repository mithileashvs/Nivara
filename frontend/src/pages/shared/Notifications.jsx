import { useState } from 'react'
import { BellOff, CheckCheck } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { NotificationItem } from '../../components/NotificationItem'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useUnreadCount } from '../../hooks/useUnreadCount'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { listNotifications, markAllRead, markRead } from '../../api/notifications'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { value: '', label: 'All' },
  { value: 'unread', label: 'Unread' },
  { value: 'read', label: 'Read' },
]

/** Shared by every role — the notification endpoints are open to all of them. */
export default function Notifications({ appointmentPathPrefix = '/appointments' }) {
  useDocumentTitle('Notifications')
  const toast = useToast()
  const [filter, setFilter] = useState('')
  const { unread, refresh } = useUnreadCount()

  const isRead = filter === 'unread' ? false : filter === 'read' ? true : undefined
  const paged = usePaged((p) => listNotifications({ ...p, is_read: isRead }), [filter])

  const readOne = async (id) => {
    try {
      await markRead(id)
      paged.reload()
      refresh()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const readAll = async () => {
    try {
      const { message } = await markAllRead()
      toast.success(message)
      paged.reload()
      refresh()
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
          unread > 0 && (
            <Button variant="outline" onClick={readAll}>
              <CheckCheck size={16} aria-hidden="true" />
              Mark all as read
            </Button>
          )
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
            description="Updates about your appointments will show up here."
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
    </div>
  )
}
