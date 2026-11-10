import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'
import { Topbar } from '../components/Topbar'
import { MobileNav } from '../components/MobileNav'
import { useAuth } from '../context/AuthContext'
import { useUnreadCount } from '../hooks/useUnreadCount'
import { useNotificationsWebSocket } from '../hooks/useNotificationsWebSocket'
import { ROLES } from '../utils/constants'
import { mobileNavFor } from '../utils/nav'

const SIDEBAR_STORAGE_KEY = 'nivara.sidebar.collapsed'

/**
 * The shell every signed-in area uses: dark collapsible rail + sticky topbar
 * on desktop, drawer + topbar + bottom bar on mobile.
 */
export function DashboardLayout({ nav, notificationsPath = '/notifications', profilePath = '/profile' }) {
  const { user, isHospitalAdmin, managedHospitalIds, signOut } = useAuth()
  const { unread, refresh } = useUnreadCount()
  useNotificationsWebSocket()
  const [menuOpen, setMenuOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })
  const location = useLocation()

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev
      try {
        window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next))
      } catch {
        // Ignore storage quota errors
      }
      return next
    })
  }

  const roleLabel =
    user?.role === ROLES.DOCTOR
      ? 'Doctor Portal'
      : user?.role === ROLES.ADMIN
        ? isHospitalAdmin
          ? 'Hospital Admin'
          : 'Platform Admin'
        : 'Patient Portal'

  // Close the drawer and refresh the badge whenever the route changes.
  useEffect(() => {
    setMenuOpen(false)
    refresh()
  }, [location.pathname, refresh])

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar
        items={nav}
        unread={unread}
        roleLabel={roleLabel}
        onSignOut={signOut}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={user}
          nav={nav}
          unread={unread}
          isHospitalAdmin={isHospitalAdmin}
          managedHospitalIds={managedHospitalIds}
          onOpenMenu={() => setMenuOpen(true)}
          onSignOut={signOut}
          notificationsPath={notificationsPath}
          profilePath={profilePath}
        />

        <a
          href="#main"
          className="sr-only-focusable absolute left-4 top-4 z-40 rounded-lg bg-forest px-4 py-2 text-sm text-canvas"
        >
          Skip to content
        </a>

        <main
          id="main"
          className="mx-auto w-full max-w-[84rem] flex-1 px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10 lg:pt-7"
        >
          <Outlet context={{ unread, refreshUnread: refresh }} />
        </main>
      </div>

      <MobileNav items={mobileNavFor(nav)} />
    </div>
  )
}
