import { initials } from '../../utils/format'

const SIZES = {
  sm: 'h-9 w-9 text-xs',
  md: 'h-11 w-11 text-sm',
  lg: 'h-14 w-14 text-base',
  xl: 'h-20 w-20 text-xl',
}

/** Initials only — the backend stores no profile photos, so none are invented. */
export function Avatar({ name = '', size = 'md', className = '' }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full bg-sage-100 font-semibold text-forest-600 ${SIZES[size]} ${className}`}
    >
      {initials(name) || '–'}
    </span>
  )
}
