import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './Button'

export function Pagination({ page, totalPages, total, pageSize, onChange, className = '' }) {
  if (!totalPages || totalPages <= 1) return null
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <nav
      className={`flex flex-wrap items-center justify-between gap-3 ${className}`}
      aria-label="Pagination"
    >
      <p className="text-sm text-ink-muted">
        Showing {first}–{last} of {total}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft size={15} aria-hidden="true" />
          Previous
        </Button>
        <span className="px-1 text-sm tabular-nums text-ink-muted" aria-current="page">
          {page} / {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
        >
          Next
          <ChevronRight size={15} aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}
