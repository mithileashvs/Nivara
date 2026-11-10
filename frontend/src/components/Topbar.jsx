import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Bell,
  Building2,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  LifeBuoy,
  LogOut,
  Menu,
  ShieldCheck,
  Stethoscope,
  User,
} from 'lucide-react'
import { Avatar } from './ui/Avatar'
import { Badge } from './ui/StatusBadge'
import { Logo } from './Logo'
import { listNotifications, markAllRead, markRead } from '../api/notifications'
import { NOTIFICATION_LABEL, ROLES } from '../utils/constants'
import { pluralise, relativeTime } from '../utils/format'

const DYNAMIC_TAIL_LABELS = {
  appointments: 'Appointment details',
  doctors: 'Doctor profile',
  book: 'Book appointment',
  hospitals: 'Hospital details',
  analytics: 'Analytics section',
}

function buildBreadcrumbs(pathname, nav = []) {
  if (!pathname) return []
  const sorted = [...nav].sort((a, b) => b.to.length - a.to.length)
  const matched = sorted.find((item) =>
    item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`),
  )
  if (!matched) {
    return [{ label: 'Workspace', to: null }]
  }
  if (pathname === matched.to) {
    return [{ label: matched.label, to: null }]
  }
  const rest = pathname.slice(matched.to.length).replace(/^\/+/, '').split('/').filter(Boolean)
  let detailLabel = 'Details'
  if (matched.to.endsWith('/analytics') && rest[0]) {
    detailLabel = rest[0].charAt(0).toUpperCase() + rest[0].slice(1).replace(/-/g, ' ')
  } else {
    const seg = matched.to.split('/').filter(Boolean).pop()
    if (seg && DYNAMIC_TAIL_LABELS[seg]) detailLabel = DYNAMIC_TAIL_LABELS[seg]
  }
  return [
    { label: matched.label, to: matched.to },
    { label: detailLabel, to: null },
  ]
}

/** Unified sticky topbar on desktop & mobile: breadcrumbs / menu, role scope pill, notifications & account dropdown. */
export function Topbar({
  user,
  nav = [],
  unread = 0,
  isHospitalAdmin = false,
  managedHospitalIds = null,
  onOpenMenu,
  onSignOut,
  notificationsPath = '/notifications',
  profilePath = '/profile',
}) {
  const { pathname } = useLocation()
  const breadcrumbs = useMemo(() => buildBreadcrumbs(pathname, nav), [pathname, nav])

  const roleMeta = useMemo(() => {
    if (!user) return null
    if (user.role === ROLES.DOCTOR) {
      return { label: 'Doctor workspace', icon: Stethoscope, tone: 'info' }
    }
    if (user.role === ROLES.ADMIN) {
      if (isHospitalAdmin) {
        const count = managedHospitalIds?.length ?? 0
        return {
          label: count ? `Hospital admin · ${pluralise(count, 'site', 'sites')}` : 'Hospital admin',
          icon: Building2,
          tone: 'info',
        }
      }
      return { label: 'Platform admin', icon: ShieldCheck, tone: 'positive' }
    }
    return { label: 'Patient portal', icon: User, tone: 'neutral' }
  }, [user, isHospitalAdmin, managedHospitalIds])

  const helpPath =
    user?.role === ROLES.DOCTOR ? '/doctor/help' : user?.role === ROLES.PATIENT ? '/help' : null

  return (
    <header
      className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur sm:px-6 lg:px-8"
      style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
    >
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onOpenMenu}
          className="rounded-lg p-2 text-forest-600 transition-colors hover:bg-forest-50 focus-ring lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu size={20} />
        </button>

        <Logo size="sm" className="lg:hidden" />

        <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1.5 text-sm lg:flex">
          {breadcrumbs.map((crumb, idx) => (
            <span key={`${crumb.label}-${idx}`} className="flex min-w-0 items-center gap-1.5">
              {idx > 0 && <ChevronRight size={14} className="shrink-0 text-ink-faint" aria-hidden="true" />}
              {crumb.to ? (
                <Link
                  to={crumb.to}
                  className="truncate rounded px-1 py-0.5 text-ink-muted transition-colors hover:text-forest-700 focus-ring"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="truncate font-semibold text-forest-700" aria-current="page">
                  {crumb.label}
                </span>
              )}
            </span>
          ))}
        </nav>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {roleMeta && (
          <Badge tone={roleMeta.tone} icon={roleMeta.icon} className="hidden sm:inline-flex">
            {roleMeta.label}
          </Badge>
        )}

        <NotificationBell unread={unread} to={notificationsPath} />

        <AccountMenu
          user={user}
          roleLabel={roleMeta?.label}
          profilePath={profilePath}
          notificationsPath={notificationsPath}
          helpPath={helpPath}
          onSignOut={onSignOut}
        />
      </div>
    </header>
  )
}

function AccountMenu({ user, roleLabel, profilePath, notificationsPath, helpPath, onSignOut }) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const handleOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false)
    }
    const handleKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-2 rounded-full border border-line bg-surface p-1 pr-2.5 text-left transition-colors hover:border-forest-200 focus-ring"
      >
        <Avatar name={user?.name} size="sm" />
        <span className="hidden max-w-[8.5rem] truncate text-xs font-semibold text-forest-700 md:inline">
          {user?.name || 'Account'}
        </span>
        <ChevronDown
          size={14}
          className={`hidden text-ink-muted transition-transform duration-150 md:inline ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-line bg-surface shadow-lift animate-rise"
        >
          <div className="border-b border-line bg-surface-muted/50 px-4 py-3">
            <p className="truncate text-sm font-semibold text-forest-800">{user?.name || 'User'}</p>
            {user?.email && <p className="mt-0.5 truncate text-xs text-ink-muted">{user.email}</p>}
            {roleLabel && <p className="mt-1.5 text-[0.68rem] font-semibold uppercase tracking-wider text-forest-500">{roleLabel}</p>}
          </div>

          <div className="p-1.5">
            <Link
              role="menuitem"
              to={profilePath}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-ink transition-colors hover:bg-forest-50 hover:text-forest-700 focus-ring"
            >
              <User size={15} className="text-ink-muted" aria-hidden="true" />
              {profilePath.endsWith('/profile') ? 'Profile & preferences' : 'Workspace overview'}
            </Link>
            <Link
              role="menuitem"
              to={notificationsPath}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-ink transition-colors hover:bg-forest-50 hover:text-forest-700 focus-ring"
            >
              <Bell size={15} className="text-ink-muted" aria-hidden="true" />
              Notifications
            </Link>
            {helpPath && (
              <Link
                role="menuitem"
                to={helpPath}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-ink transition-colors hover:bg-forest-50 hover:text-forest-700 focus-ring"
              >
                <LifeBuoy size={15} className="text-ink-muted" aria-hidden="true" />
                Help &amp; support
              </Link>
            )}
          </div>

          {onSignOut && (
            <div className="border-t border-line p-1.5">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false)
                  onSignOut()
                }}
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger-soft focus-ring"
              >
                <LogOut size={15} aria-hidden="true" />
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function NotificationBell({ unread = 0, to = '/notifications' }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef(null)
  const navigate = useNavigate()

  const loadRecent = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listNotifications({ page: 1, page_size: 5 })
      setItems(data.items ?? [])
    } catch {
      // Ignore network errors in dropdown preview
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      loadRecent()
    }
  }, [open, loadRecent])

  useEffect(() => {
    const handleNotification = () => {
      if (open) loadRecent()
    }
    window.addEventListener('nivara:notification', handleNotification)
    return () => window.removeEventListener('nivara:notification', handleNotification)
  }, [open, loadRecent])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const handleMarkAllRead = async (e) => {
    e.stopPropagation()
    try {
      await markAllRead()
      window.dispatchEvent(new CustomEvent('nivara:notification-read'))
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch {
      // Ignore
    }
  }

  const handleItemClick = async (n) => {
    setOpen(false)
    if (!n.is_read) {
      try {
        await markRead(n.id)
        window.dispatchEvent(new CustomEvent('nivara:notification-read'))
      } catch {
        // Ignore
      }
    }
    const dest =
      n.action_url ||
      (n.related_appointment_id
        ? `${
            to.startsWith('/doctor')
              ? '/doctor/appointments'
              : to.startsWith('/admin')
                ? '/admin/appointments'
                : to.startsWith('/hospital')
                  ? '/hospital/appointments'
                  : '/appointments'
          }/${n.related_appointment_id}`
        : to)
    navigate(dest)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="relative rounded-full border border-line bg-surface p-2.5 text-forest-600 transition-colors hover:border-forest-200 hover:bg-forest-50 hover:text-forest focus-ring"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell size={18} aria-hidden="true" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-forest px-1 text-[0.65rem] font-semibold tabular-nums text-canvas">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-2xl border border-line bg-surface shadow-lift animate-rise sm:w-96">
          <div className="flex items-center justify-between border-b border-line bg-surface-muted/50 px-4 py-3">
            <span className="text-sm font-semibold text-forest-700">Notifications</span>
            {unread > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-forest-600 hover:bg-forest-50 hover:text-forest focus-ring"
              >
                <CheckCheck size={14} />
                Mark all read
              </button>
            )}
          </div>

          <div className="scroll-x max-h-80 divide-y divide-line overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center text-xs text-ink-muted">Loading notifications...</div>
            ) : items.length === 0 ? (
              <div className="p-6 text-center text-xs text-ink-muted">No notifications yet.</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className={`flex w-full items-start gap-3 p-3.5 text-left transition-colors hover:bg-forest-50/70 focus-visible:bg-forest-50 focus-visible:outline-none ${
                    n.is_read ? 'opacity-75' : 'bg-forest-50/35'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-forest-800">
                      {n.title || NOTIFICATION_LABEL[n.type] || n.type}
                    </p>
                    <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-ink-muted">
                      {n.message}
                    </p>
                    <span className="mt-1 block text-[0.7rem] text-ink-faint">
                      {relativeTime(n.created_at)}
                    </span>
                  </div>
                  {!n.is_read && (
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-forest" aria-hidden="true" />
                  )}
                </button>
              ))
            )}
          </div>

          <div className="border-t border-line bg-surface-muted/40 p-2.5 text-center">
            <Link
              to={to}
              onClick={() => setOpen(false)}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium text-forest hover:bg-forest-50 hover:text-forest-700 focus-ring"
            >
              View all notifications
              <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

/** Page heading used across dashboards: greeting/title on the left, actions on the right. */
export function PageHeader({ eyebrow, title, description, actions, className = '' }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-wider text-forest-500">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-forest-700 sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
