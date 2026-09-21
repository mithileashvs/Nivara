import { Link } from 'react-router-dom'
import { Bell, Menu } from 'lucide-react'
import { Avatar } from './ui/Avatar'
import { Logo } from './Logo'

/** Mobile header (hamburger + mark + avatar) and the desktop bell/avatar cluster. */
export function Topbar({ user, unread = 0, onOpenMenu, notificationsPath = '/notifications', profilePath = '/profile' }) {
  return (
    <header
      className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur lg:hidden"
      style={{ paddingTop: 'calc(0.75rem + env(safe-area-inset-top, 0px))' }}
    >
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-lg p-2 text-forest-600 transition-colors hover:bg-forest-50 focus-ring"
        aria-label="Open menu"
      >
        <Menu size={20} />
      </button>
      <Logo size="sm" className="flex-1" />
      <NotificationBell unread={unread} to={notificationsPath} />
      <Link to={profilePath} aria-label="Profile" className="rounded-full focus-ring">
        <Avatar name={user?.name} size="sm" />
      </Link>
    </header>
  )
}

export function NotificationBell({ unread = 0, to = '/notifications' }) {
  return (
    <Link
      to={to}
      className="relative rounded-full border border-line bg-surface p-2.5 text-forest-600 transition-colors hover:border-forest-200 hover:text-forest focus-ring"
      aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
    >
      <Bell size={18} aria-hidden="true" />
      {unread > 0 && (
        <span className="absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-forest px-1 text-[0.65rem] font-semibold tabular-nums text-canvas">
          {unread > 9 ? '9+' : unread}
        </span>
      )}
    </Link>
  )
}

/** Page heading used across dashboards: greeting/title on the left, actions on the right. */
export function PageHeader({ eyebrow, title, description, actions, className = '' }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        {eyebrow && <p className="text-sm text-ink-muted">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight text-forest-700 sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
