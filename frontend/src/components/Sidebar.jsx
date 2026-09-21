import { NavLink } from 'react-router-dom'
import { LogOut, X } from 'lucide-react'
import { Logo } from './Logo'

/**
 * Deep-forest navigation rail from the reference: logo, icon+label items with a
 * lighter active pill, and logout separated at the foot. Becomes a slide-in
 * drawer below `lg`.
 */
export function Sidebar({ items, unread = 0, onSignOut, open = false, onClose }) {
  const content = (
    <>
      <div className="flex items-center justify-between px-5 pb-6 pt-6">
        <Logo tone="light" />
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-forest-200 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring lg:hidden"
          aria-label="Close menu"
        >
          <X size={18} />
        </button>
      </div>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3">
        <ul className="space-y-1">
          {items.map(({ to, label, icon: Icon, exact }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={exact}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors focus-ring ${
                    isActive
                      ? 'bg-forest-500 text-canvas'
                      : 'text-forest-100/80 hover:bg-forest-700 hover:text-canvas'
                  }`
                }
              >
                <Icon size={18} className="shrink-0" aria-hidden="true" />
                <span className="flex-1 truncate">{label}</span>
                {label === 'Notifications' && unread > 0 && (
                  <span className="min-w-[1.25rem] rounded-full bg-sage-300 px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums text-forest-700">
                    {unread > 99 ? '99+' : unread}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-forest-500/40 px-3 py-4">
        <button
          type="button"
          onClick={onSignOut}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-forest-100/80 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring"
        >
          <LogOut size={18} aria-hidden="true" />
          Logout
        </button>
      </div>
    </>
  )

  return (
    <>
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-forest lg:flex">{content}</aside>

      {/* Mobile drawer */}
      <div
        className={`fixed inset-0 z-50 lg:hidden ${open ? '' : 'pointer-events-none'}`}
        aria-hidden={!open}
      >
        <div
          className={`absolute inset-0 bg-forest-900/40 transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0'}`}
          onClick={onClose}
        />
        <aside
          className={`absolute inset-y-0 left-0 flex w-[17rem] max-w-[82%] flex-col bg-forest transition-transform duration-200 ${
            open ? 'translate-x-0' : '-translate-x-full'
          }`}
          style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
        >
          {content}
        </aside>
      </div>
    </>
  )
}
