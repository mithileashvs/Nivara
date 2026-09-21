import { Link } from 'react-router-dom'

/** Reference stat tile: icon chip, large figure, quiet label. */
export function StatCard({ icon: Icon, value, label, hint, to, tone = 'default' }) {
  const chip =
    tone === 'warn'
      ? 'bg-warn-soft text-warn'
      : tone === 'positive'
        ? 'bg-ok-soft text-ok'
        : 'bg-forest-50 text-forest-500'

  const body = (
    <>
      <span className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl ${chip}`}>
        <Icon size={19} aria-hidden="true" />
      </span>
      <p className="text-3xl font-bold tabular-nums leading-none text-forest-700">{value}</p>
      <p className="mt-2 text-sm text-ink-muted">{label}</p>
      {hint && <p className="mt-1 text-xs text-ink-faint">{hint}</p>}
    </>
  )

  if (to) {
    return (
      <Link to={to} className="card block p-5 transition-colors hover:border-forest-200 focus-ring">
        {body}
      </Link>
    )
  }
  return <div className="card p-5">{body}</div>
}
