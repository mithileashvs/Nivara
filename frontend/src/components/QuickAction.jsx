import { Link } from 'react-router-dom'

/** The four dashboard shortcuts from the reference. */
export function QuickAction({ icon: Icon, title, description, to, onClick }) {
  const inner = (
    <>
      <span className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-full bg-forest-50 text-forest-500 transition-colors group-hover:bg-forest-100">
        <Icon size={19} aria-hidden="true" />
      </span>
      <p className="text-sm font-semibold text-forest-700">{title}</p>
      <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{description}</p>
    </>
  )
  const cls =
    'group card flex flex-col items-start p-4 text-left transition-colors hover:border-forest-200 focus-ring'
  return to ? (
    <Link to={to} className={cls}>
      {inner}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  )
}
