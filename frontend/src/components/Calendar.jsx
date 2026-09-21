import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { parseDateString, toDateString, todayString } from '../utils/format'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/**
 * Month grid from the reference. It never guesses availability: a day is only
 * marked when its date appears in `availableDates`, which the caller derives
 * from real slots returned by the backend.
 */
export function Calendar({ value, onChange, availableDates = null, minDate, maxDate, className = '' }) {
  const selected = parseDateString(value)
  const [cursor, setCursor] = useState(() => {
    const base = selected || new Date()
    return { year: base.getFullYear(), month: base.getMonth() }
  })

  const available = useMemo(() => (availableDates ? new Set(availableDates) : null), [availableDates])
  const today = todayString()
  const min = minDate ?? today

  const days = useMemo(() => {
    const first = new Date(cursor.year, cursor.month, 1)
    const total = new Date(cursor.year, cursor.month + 1, 0).getDate()
    const lead = first.getDay()
    const cells = Array.from({ length: lead }, () => null)
    for (let d = 1; d <= total; d += 1) cells.push(new Date(cursor.year, cursor.month, d))
    while (cells.length % 7 !== 0) cells.push(null)
    return cells
  }, [cursor])

  const shift = (delta) => {
    const next = new Date(cursor.year, cursor.month + delta, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }

  return (
    <div className={className}>
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => shift(-1)}
          aria-label="Previous month"
          className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-forest-50 hover:text-forest focus-ring"
        >
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm font-semibold text-forest-700" aria-live="polite">
          {MONTHS[cursor.month]} {cursor.year}
        </p>
        <button
          type="button"
          onClick={() => shift(1)}
          aria-label="Next month"
          className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-forest-50 hover:text-forest focus-ring"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1" role="grid">
        {WEEKDAYS.map((d) => (
          <div key={d} className="py-1 text-center text-[0.7rem] font-medium text-ink-faint" role="columnheader">
            {d}
          </div>
        ))}

        {days.map((day, i) => {
          if (!day) return <div key={`pad-${i}`} aria-hidden="true" />
          const iso = toDateString(day)
          const isSelected = iso === value
          const outOfRange = (min && iso < min) || (maxDate && iso > maxDate)
          const hasSlots = available ? available.has(iso) : true
          const disabled = outOfRange || (available !== null && !hasSlots)

          return (
            <button
              key={iso}
              type="button"
              role="gridcell"
              disabled={disabled}
              aria-selected={isSelected}
              aria-label={`${day.getDate()} ${MONTHS[day.getMonth()]}${available && hasSlots ? ', slots available' : ''}`}
              onClick={() => onChange(iso)}
              className={`relative flex aspect-square items-center justify-center rounded-full text-sm tabular-nums transition-colors focus-ring ${
                isSelected
                  ? 'bg-forest font-semibold text-canvas'
                  : disabled
                    ? 'cursor-not-allowed text-ink-faint/50'
                    : 'text-ink hover:bg-forest-50'
              }`}
            >
              {day.getDate()}
              {!isSelected && available && hasSlots && (
                <span className="absolute bottom-1 h-1 w-1 rounded-full bg-forest-300" aria-hidden="true" />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
