/** Filter tabs. Rendered as a scrollable row so long status lists work on a phone. */
export function Tabs({ tabs, value, onChange, className = '', countFor }) {
  return (
    <div className={`scroll-x -mx-1 px-1 pb-1 ${className}`}>
      <div
        role="tablist"
        aria-label="Filter"
        className="inline-flex gap-1 rounded-xl border border-line/70 bg-surface-muted p-1"
      >
        {tabs.map((tab) => {
          const active = tab.value === value
          const count = countFor?.(tab.value)
          return (
            <button
              key={tab.value ?? 'all'}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => onChange(tab.value)}
              className={`whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150 focus-ring ${
                active
                  ? 'bg-surface text-forest-700 shadow-card'
                  : 'text-ink-muted hover:bg-surface/60 hover:text-forest-600'
              }`}
            >
              {tab.label}
              {count !== undefined && count !== null && (
                <span
                  className={`ml-1.5 inline-flex min-w-[1.25rem] justify-center rounded-full px-1.5 py-0.5 text-[0.7rem] tabular-nums ${
                    active ? 'bg-forest-50 text-forest-600' : 'text-ink-faint'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
