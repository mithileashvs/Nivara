import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary:
    'bg-forest text-canvas hover:bg-forest-700 active:bg-forest-800 disabled:bg-forest-300',
  secondary:
    'bg-forest-50 text-forest-700 border border-forest-100 hover:bg-forest-100 disabled:opacity-60',
  outline:
    'bg-transparent text-forest-700 border border-line hover:border-forest-200 hover:bg-forest-50 disabled:opacity-60',
  ghost: 'bg-transparent text-ink-muted hover:bg-forest-50 hover:text-forest-700 disabled:opacity-60',
  danger: 'bg-danger text-white hover:brightness-95 disabled:opacity-60',
  quiet: 'bg-sage-100 text-forest-700 hover:bg-sage-200 disabled:opacity-60',
}

const SIZES = {
  sm: 'h-9 px-3 text-sm gap-1.5 rounded-lg',
  md: 'h-11 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-12 px-6 text-base gap-2 rounded-xl',
  icon: 'h-10 w-10 justify-center rounded-xl',
}

export const Button = forwardRef(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, className = '', children, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex select-none items-center font-medium transition-colors duration-150 disabled:cursor-not-allowed focus-ring ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
})
