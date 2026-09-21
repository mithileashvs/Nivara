import { Search, X } from 'lucide-react'

export function SearchBar({ value, onChange, placeholder = 'Search…', onSubmit, className = '', label }) {
  return (
    <form
      role="search"
      className={`relative ${className}`}
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit?.(value)
      }}
    >
      <Search
        size={18}
        className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        aria-label={label || placeholder}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-12 w-full rounded-xl border border-line bg-surface pl-11 pr-10 text-sm text-ink placeholder:text-ink-faint transition-colors hover:border-forest-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-ink-faint transition-colors hover:bg-forest-50 hover:text-forest focus-ring"
        >
          <X size={15} />
        </button>
      )}
    </form>
  )
}
