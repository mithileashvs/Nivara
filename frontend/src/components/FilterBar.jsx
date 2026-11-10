import { ChevronDown, SlidersHorizontal, X } from 'lucide-react'
import { Button } from './ui/Button'

/**
 * The dropdown row under the search field in the reference.
 * `filters`: [{ key, label, value, options:[{value,label}], onChange }]
 */
export function FilterBar({ filters, onClear, hasActive, extra, className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {filters.map((f) => (
        <label key={f.key} className="relative">
          <span className="sr-only">{f.label}</span>
          <select
            value={f.value ?? ''}
            onChange={(e) => f.onChange(e.target.value)}
            className={`h-10 cursor-pointer appearance-none rounded-xl border bg-surface pl-3.5 pr-9 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas ${
              f.value ? 'border-forest-300 bg-forest-50 font-medium text-forest-700' : 'border-line text-ink-muted hover:border-forest-200'
            }`}
          >
            <option value="">{f.label}</option>
            {f.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={15}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint"
            aria-hidden="true"
          />
        </label>
      ))}

      {extra}

      {hasActive && (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X size={15} aria-hidden="true" />
          Clear filters
        </Button>
      )}

      {!hasActive && (
        <span className="ml-auto hidden items-center gap-1.5 text-xs text-ink-faint sm:inline-flex">
          <SlidersHorizontal size={14} aria-hidden="true" />
          Narrow your results
        </span>
      )}
    </div>
  )
}
