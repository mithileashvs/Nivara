import { useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { LogOut, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'
import { Logo, LogoMark } from './Logo'

/**
 * Deep-forest navigation rail: collapsible on desktop, slide-in drawer below `lg`
 * with Escape-key dismissal and an unread badge for Notifications.
 */
export function Sidebar({
  items,
  unread = 0,
  roleLabel,
  onSignOut,
  open = false,
  onClose,
  collapsed = false,
  onToggleCollapse,
}) {
  useEffect(() => {
    if (!open) return undefined
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  const renderContent = (isDesktopCollapsed = false) => (
    <>
      <div
        className={`flex items-center border-b border-forest-500/30 ${
          isDesktopCollapsed ? 'justify-center px-2 py-5' : 'justify-between px-4 pb-4 pt-5'
        }`}
      >
        {isDesktopCollapsed ? (
          <LogoMark size={26} className="text-canvas" />
        ) : (
          <div className="min-w-0">
            <Logo tone="light" />
            {roleLabel && (
              <p className="mt-1 truncate text-[0.68rem] font-medium uppercase tracking-wider text-forest-200/80">
                {roleLabel}
              </p>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-forest-200 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring lg:hidden"
          aria-label="Close navigation menu"
        >
          <X size={18} />
        </button>

        {onToggleCollapse && !isDesktopCollapsed && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden rounded-lg p-1.5 text-forest-200 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring lg:inline-flex"
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <PanelLeftClose size={17} />
          </button>
        )}
      </div>

      {onToggleCollapse && isDesktopCollapsed && (
        <div className="hidden justify-center border-b border-forest-500/30 py-2.5 lg:flex">
          <button
            type="button"
            onClick={onToggleCollapse}
            className="rounded-lg p-1.5 text-forest-200 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring"
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <PanelLeftOpen size={17} />
          </button>
        </div>
      )}

      <nav aria-label="Main" className="scroll-x flex-1 overflow-y-auto px-2.5 py-3">
        <ul className="space-y-1">
          {items.map(({ to, label, icon: Icon, exact }) => {
            const hasUnread = label === 'Notifications' && unread > 0
            return (
              <li key={to}>
                <NavLink
                  to={to}
                  end={exact}
                  onClick={onClose}
                  title={isDesktopCollapsed ? label : undefined}
                  aria-label={isDesktopCollapsed ? label : undefined}
                  className={({ isActive }) =>
                    `relative flex items-center rounded-xl py-2.5 text-sm font-medium transition-colors focus-ring ${
                      isDesktopCollapsed ? 'justify-center px-2' : 'gap-3 px-3'
                    } ${
                      isActive
                        ? 'bg-forest-500 text-canvas shadow-sm'
                        : 'text-forest-100/80 hover:bg-forest-700 hover:text-canvas'
                    }`
                  }
                >
                  <Icon size={18} className="shrink-0" aria-hidden="true" />
                  {!isDesktopCollapsed && <span className="flex-1 truncate">{label}</span>}
                  {hasUnread && !isDesktopCollapsed && (
                    <span className="min-w-[1.25rem] rounded-full bg-sage-300 px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums text-forest-800">
                      {unread > 99 ? '99+' : unread}
                    </span>
                  )}
                  {hasUnread && isDesktopCollapsed && (
                    <span
                      className="absolute right-2 top-2 h-2 w-2 rounded-full bg-sage-300 ring-2 ring-forest"
                      aria-hidden="true"
                    />
                  )}
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="border-t border-forest-500/40 px-2.5 py-3.5">
        <button
          type="button"
          onClick={onSignOut}
          title={isDesktopCollapsed ? 'Logout' : undefined}
          aria-label={isDesktopCollapsed ? 'Logout' : undefined}
          className={`flex w-full items-center rounded-xl py-2.5 text-sm font-medium text-forest-100/80 transition-colors hover:bg-forest-700 hover:text-canvas focus-ring ${
            isDesktopCollapsed ? 'justify-center px-2' : 'gap-3 px-3'
          }`}
        >
          <LogOut size={18} className="shrink-0" aria-hidden="true" />
          {!isDesktopCollapsed && <span>Logout</span>}
        </button>
      </div>
    </>
  )

  return (
    <>
      {/* Desktop rail */}
      <aside
        className={`sticky top-0 hidden h-screen shrink-0 flex-col bg-forest transition-[width] duration-200 lg:flex ${
          collapsed ? 'w-[4.5rem]' : 'w-64'
        }`}
      >
        {renderContent(collapsed)}
      </aside>

      {/* Mobile drawer */}
      <div
        className={`fixed inset-0 z-50 lg:hidden ${open ? '' : 'pointer-events-none'}`}
        aria-hidden={!open}
      >
        <div
          className={`absolute inset-0 bg-forest-900/45 backdrop-blur-[1px] transition-opacity duration-200 ${
            open ? 'opacity-100' : 'opacity-0'
          }`}
          onClick={onClose}
        />
        <aside
          aria-label="Mobile navigation"
          className={`absolute inset-y-0 left-0 flex w-[17rem] max-w-[82%] flex-col bg-forest shadow-lift transition-transform duration-200 ${
            open ? 'translate-x-0' : '-translate-x-full'
          }`}
          style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
        >
          {renderContent(false)}
        </aside>
      </div>
    </>
  )
}
