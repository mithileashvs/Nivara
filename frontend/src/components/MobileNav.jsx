import { NavLink } from 'react-router-dom'

/** Bottom bar for mobile viewports — four primary destinations with crisp active indicator. */
export function MobileNav({ items }) {
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <ul className="flex">
        {items.map(({ to, label, icon: Icon, exact }) => (
          <li key={to} className="flex-1 min-w-0">
            <NavLink
              to={to}
              end={exact}
              className={({ isActive }) =>
                `relative flex flex-col items-center gap-1 px-1 py-2 text-[0.68rem] transition-colors focus-ring ${
                  isActive ? 'font-semibold text-forest' : 'font-medium text-ink-faint hover:text-forest-500'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`flex h-7 w-11 items-center justify-center rounded-full transition-colors ${
                      isActive ? 'bg-forest-50 text-forest' : ''
                    }`}
                  >
                    <Icon size={18} aria-hidden="true" />
                  </span>
                  <span className="max-w-full truncate px-1">{label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
