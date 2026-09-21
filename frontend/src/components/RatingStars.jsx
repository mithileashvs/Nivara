import { Star } from 'lucide-react'
import { pluralise } from '../utils/format'

/**
 * Real ratings only. `rating_average` is null until a doctor has been reviewed,
 * and nothing is shown in that case rather than inventing a score.
 */
export function RatingStars({ average, count = 0, size = 14, showCount = true, className = '' }) {
  if (average === null || average === undefined) {
    return <span className={`text-xs text-ink-faint ${className}`}>No reviews yet</span>
  }
  if (showCount && !count) {
    return <span className={`text-xs text-ink-faint ${className}`}>No reviews yet</span>
  }
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-ink-muted ${className}`}>
      <Star size={size} className="fill-warn text-warn" aria-hidden="true" />
      <span className="font-semibold text-forest-700">{average.toFixed(1)}</span>
      {showCount && <span>({pluralise(count, 'review', 'reviews')})</span>}
    </span>
  )
}
