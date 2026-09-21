import { AlertTriangle, Inbox, Loader2, RefreshCw, WifiOff } from 'lucide-react'
import { Button } from './Button'
import { errorMessage } from '../../utils/errors'

export function Spinner({ size = 20, className = '' }) {
  return <Loader2 size={size} className={`animate-spin text-forest-300 ${className}`} aria-hidden="true" />
}

export function LoadingBlock({ label = 'Loading' }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-12 text-sm text-ink-muted" role="status">
      <Spinner />
      <span>{label}…</span>
    </div>
  )
}

/** Shape-matched placeholders. `variant` picks the silhouette of what is loading. */
export function LoadingSkeleton({ variant = 'list', rows = 3, className = '' }) {
  if (variant === 'stats') {
    return (
      <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-4 ${className}`} aria-hidden="true">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="card p-5">
            <div className="skeleton h-3 w-24" />
            <div className="skeleton mt-4 h-8 w-16" />
          </div>
        ))}
      </div>
    )
  }
  if (variant === 'cards') {
    return (
      <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-3 ${className}`} aria-hidden="true">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-center gap-3">
              <div className="skeleton h-12 w-12 rounded-full" />
              <div className="flex-1">
                <div className="skeleton h-3.5 w-32" />
                <div className="skeleton mt-2 h-3 w-20" />
              </div>
            </div>
            <div className="skeleton mt-5 h-3 w-full" />
            <div className="skeleton mt-2 h-3 w-2/3" />
          </div>
        ))}
      </div>
    )
  }
  if (variant === 'table') {
    return (
      <div className={`card divide-y divide-line ${className}`} aria-hidden="true">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-5 py-4">
            <div className="skeleton h-3 w-1/4" />
            <div className="skeleton h-3 w-1/5" />
            <div className="skeleton h-3 w-1/6" />
            <div className="skeleton ml-auto h-6 w-20 rounded-full" />
          </div>
        ))}
      </div>
    )
  }
  return (
    <div className={`space-y-3 ${className}`} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="card p-5">
          <div className="skeleton h-3.5 w-1/3" />
          <div className="skeleton mt-3 h-3 w-1/2" />
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-surface/60 px-6 py-14 text-center ${className}`}>
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-forest-50 text-forest-400">
        <Icon size={22} aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-base font-semibold text-forest-700">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Renders a normalised API error. Never shows raw server internals. */
export function ErrorState({ error, onRetry, className = '', compact = false }) {
  const offline = error?.status === 0
  const Icon = offline ? WifiOff : AlertTriangle
  const title = offline
    ? 'Cannot reach Nivara'
    : error?.status === 403
      ? 'You do not have access to this'
      : error?.status === 404
        ? 'Not found'
        : 'That did not load'

  if (compact) {
    return (
      <div className={`flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 ${className}`} role="alert">
        <Icon size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
        <p className="text-sm text-forest-700">{errorMessage(error)}</p>
      </div>
    )
  }

  return (
    <div className={`flex flex-col items-center justify-center rounded-2xl border border-line bg-surface px-6 py-12 text-center ${className}`} role="alert">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-soft text-danger">
        <Icon size={22} aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-base font-semibold text-forest-700">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-ink-muted">{errorMessage(error)}</p>
      {error?.requestId && (
        <p className="mt-2 text-xs text-ink-faint">Reference {error.requestId}</p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-5" onClick={onRetry}>
          <RefreshCw size={15} aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  )
}

/**
 * One place that decides between loading / error / empty / content, so every
 * data-driven screen handles all four the same way.
 */
export function AsyncBoundary({
  loading,
  error,
  isEmpty,
  onRetry,
  skeleton = <LoadingSkeleton />,
  empty,
  children,
}) {
  if (loading) return skeleton
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (isEmpty && empty) return empty
  return children
}
