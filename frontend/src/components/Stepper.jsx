/** Numbered progress used by the booking flow, as in the reference. */
export function Stepper({ steps, current }) {
  return (
    <ol className="flex items-start" aria-label="Booking progress">
      {steps.map((label, i) => {
        const index = i + 1
        const done = index < current
        const active = index === current
        return (
          <li key={label} className="flex flex-1 flex-col items-center text-center">
            <div className="flex w-full items-center">
              <span className={`h-px flex-1 ${i === 0 ? 'bg-transparent' : done || active ? 'bg-forest-300' : 'bg-line'}`} />
              <span
                aria-current={active ? 'step' : undefined}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                  done
                    ? 'bg-forest-300 text-canvas'
                    : active
                      ? 'bg-forest text-canvas'
                      : 'border border-line bg-surface text-ink-faint'
                }`}
              >
                {index}
              </span>
              <span
                className={`h-px flex-1 ${i === steps.length - 1 ? 'bg-transparent' : done ? 'bg-forest-300' : 'bg-line'}`}
              />
            </div>
            <span className={`mt-2 px-1 text-xs ${active ? 'font-semibold text-forest-700' : 'text-ink-muted'}`}>
              {label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
