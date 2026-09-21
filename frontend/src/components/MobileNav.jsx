import { NavLink } from 'react-router-dom'

/** Bottom bar from the reference's mobile screen — four primary destinations. */
export function MobileNav({ items }) {
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <ul className="flex">
        {items.map(({ to, label, icon: Icon, exact }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 px-1 py-2.5 text-[0.7rem] font-medium transition-colors focus-ring ${
                  isActive ? 'text-forest' : 'text-ink-faint hover:text-forest-400'
                }`
              }
            >
              <Icon size={19} aria-hidden="true" />
              <span className="truncate">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
