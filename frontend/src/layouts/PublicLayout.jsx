import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { Logo } from '../components/Logo'
import { Button } from '../components/ui/Button'
import { useAuth, homePathFor } from '../context/AuthContext'

const LINKS = [
  { to: '/', label: 'Home', exact: true },
  { to: '/find-doctors', label: 'Find doctors' },
  { to: '/hospitals', label: 'Hospitals' },
  { to: '/about', label: 'About' },
  { to: '/contact', label: 'Contact' },
]

/** Marketing chrome for the landing page and other signed-out pages. */
export function PublicLayout() {
  const { user, isAuthenticated } = useAuth()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header
        className="sticky top-0 z-40 border-b border-line/70 bg-canvas/85 backdrop-blur"
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
      >
        <div className="mx-auto flex h-16 w-full max-w-[80rem] items-center gap-6 px-4 sm:px-6 lg:px-8">
          <Link to="/" className="rounded focus-ring" aria-label="Nivara home">
            <Logo />
          </Link>

          <nav aria-label="Site" className="hidden flex-1 items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.exact}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm transition-colors focus-ring ${
                    isActive ? 'font-semibold text-forest-700' : 'text-ink-muted hover:text-forest-700'
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto hidden items-center gap-2 md:flex">
            {isAuthenticated ? (
              <Link
                to={homePathFor(user)}
                className="inline-flex h-10 items-center rounded-xl bg-forest px-4 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
              >
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="inline-flex h-10 items-center rounded-xl border border-line px-4 text-sm font-medium text-forest-700 transition-colors hover:border-forest-200 hover:bg-forest-50 focus-ring"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  className="inline-flex h-10 items-center rounded-xl bg-forest px-4 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                >
                  Sign up
                </Link>
              </>
            )}
          </div>

          <button
            type="button"
            className="ml-auto rounded-lg p-2 text-forest-700 transition-colors hover:bg-forest-50 focus-ring md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? 'Close menu' : 'Open menu'}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {open && (
          <div className="border-t border-line bg-canvas px-4 py-4 md:hidden">
            <nav aria-label="Site" className="grid gap-1">
              {LINKS.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.exact}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-2.5 text-sm transition-colors focus-ring ${
                      isActive ? 'bg-forest-50 font-semibold text-forest-700' : 'text-ink-muted'
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </nav>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {isAuthenticated ? (
                <Link to={homePathFor(user)} className="col-span-2">
                  <Button className="w-full">Go to dashboard</Button>
                </Link>
              ) : (
                <>
                  <Link to="/login">
                    <Button variant="outline" className="w-full">
                      Login
                    </Button>
                  </Link>
                  <Link to="/register">
                    <Button className="w-full">Sign up</Button>
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex w-full max-w-[80rem] flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <div>
            <Logo size="sm" />
            <p className="mt-2 max-w-sm text-sm text-ink-muted">
              Find a doctor, request an appointment and keep your care in one place.
            </p>
          </div>
          <p className="max-w-md text-xs leading-relaxed text-ink-faint">
            Nivara helps you reach the right department and book a consultation. It does not
            diagnose conditions or recommend medicines. For a medical emergency, contact your local
            emergency services.
          </p>
        </div>
      </footer>
    </div>
  )
}
