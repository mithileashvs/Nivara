import { Lock } from 'lucide-react'
import { formatTime } from '../utils/format'
import { EmptyState, LoadingBlock, ErrorState } from './ui/States'
import { CalendarOff } from 'lucide-react'

/**
 * Time chips for one day. Bookability is taken verbatim from the backend's
 * `bookable` flag — the UI never works it out for itself — and a slot that is
 * not bookable shows the backend's own `unavailable_reason`.
 */
export function SlotSelector({ slots, value, onChange, loading, error, onRetry, showUnavailable = false }) {
  if (loading) return <LoadingBlock label="Loading availability" />
  if (error) return <ErrorState error={error} onRetry={onRetry} compact />

  const visible = showUnavailable ? slots : slots.filter((s) => s.bookable)

  if (!visible.length) {
    return (
      <EmptyState
        icon={CalendarOff}
        title="No open times on this day"
        description="Pick another date, or join the waitlist to hear when something frees up."
      />
    )
  }

  return (
    <div role="radiogroup" aria-label="Available times" className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {visible.map((slot) => {
        const selected = slot.id === value
        const disabled = !slot.bookable
        return (
          <button
            key={slot.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            title={disabled ? slot.unavailable_reason || 'Not available' : undefined}
            onClick={() => onChange(slot)}
            className={`flex items-center justify-center gap-1.5 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors focus-ring ${
              selected
                ? 'border-forest bg-forest text-canvas'
                : disabled
                  ? 'cursor-not-allowed border-line bg-forest-50/50 text-ink-faint line-through'
                  : 'border-line bg-surface text-forest-700 hover:border-forest-300 hover:bg-forest-50'
            }`}
          >
            {disabled && <Lock size={12} aria-hidden="true" />}
            {formatTime(slot.start_time)}
          </button>
        )
      })}
    </div>
  )
}
