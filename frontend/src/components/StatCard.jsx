import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const TONE_CHIP = {
  warn: 'bg-warn-soft text-warn',
  positive: 'bg-ok-soft text-ok',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-info-soft text-info',
  default: 'bg-forest-50 text-forest-500',
}

/** Reference stat tile: icon chip, large figure, quiet label. */
export function StatCard({ icon: Icon, value, label, hint, to, tone = 'default' }) {
  const chip = TONE_CHIP[tone] || TONE_CHIP.default

  const body = (
    <>
      <div className="mb-4 flex items-start justify-between gap-2">
        <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${chip}`}>
          <Icon size={19} aria-hidden="true" />
        </span>
        {to && (
          <ArrowUpRight
            size={15}
            className="text-ink-faint transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-forest-500"
            aria-hidden="true"
          />
        )}
      </div>
      <p className="text-3xl font-bold tabular-nums leading-none tracking-tight text-forest-700">{value}</p>
      <p className="mt-2 text-sm font-medium text-ink-muted">{label}</p>
      {hint && <p className="mt-1 text-xs leading-relaxed text-ink-faint">{hint}</p>}
    </>
  )

  if (to) {
    return (
      <Link to={to} className="group card-interactive block p-5 focus-ring">
        {body}
      </Link>
    )
  }
  return <div className="card p-5">{body}</div>
}
