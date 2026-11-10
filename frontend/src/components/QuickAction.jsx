import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

/** The four dashboard shortcuts from the reference. */
export function QuickAction({ icon: Icon, title, description, to, onClick }) {
  const inner = (
    <>
      <div className="mb-3 flex w-full items-center justify-between gap-2">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-forest-50 text-forest-500 transition-colors group-hover:bg-forest-100">
          <Icon size={19} aria-hidden="true" />
        </span>
        <ChevronRight
          size={16}
          className="text-ink-faint opacity-0 transition-all duration-150 group-hover:translate-x-0.5 group-hover:opacity-100 group-hover:text-forest-500"
          aria-hidden="true"
        />
      </div>
      <p className="text-sm font-semibold text-forest-700">{title}</p>
      <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{description}</p>
    </>
  )
  const cls =
    'group card-interactive flex flex-col items-start p-4 text-left focus-ring'
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
