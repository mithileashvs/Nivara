import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'
import { Topbar } from '../components/Topbar'
import { MobileNav } from '../components/MobileNav'
import { useAuth } from '../context/AuthContext'
import { useUnreadCount } from '../hooks/useUnreadCount'
import { mobileNavFor } from '../utils/nav'

/**
 * The shell every signed-in area uses: dark rail on desktop, drawer + bottom bar
 * on mobile. The unread badge comes from the real notification count endpoint.
 */
export function DashboardLayout({ nav, notificationsPath = '/notifications', profilePath = '/profile' }) {
  const { user, signOut } = useAuth()
  const { unread, refresh } = useUnreadCount()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

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
        onSignOut={signOut}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={user}
          unread={unread}
          onOpenMenu={() => setMenuOpen(true)}
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
          className="mx-auto w-full max-w-[84rem] flex-1 px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8"
        >
          <Outlet context={{ unread, refreshUnread: refresh }} />
        </main>
      </div>

      <MobileNav items={mobileNavFor(nav)} />
    </div>
  )
}
