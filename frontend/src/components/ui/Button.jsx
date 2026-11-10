import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary:
    'bg-forest text-canvas shadow-sm hover:bg-forest-700 active:bg-forest-800 disabled:bg-forest-300',
  secondary:
    'bg-forest-50 text-forest-700 border border-forest-100 hover:bg-forest-100 disabled:opacity-60',
  outline:
    'bg-surface text-forest-700 border border-line hover:border-forest-200 hover:bg-forest-50 disabled:opacity-60',
  ghost: 'bg-transparent text-ink-muted hover:bg-forest-50 hover:text-forest-700 disabled:opacity-60',
  danger: 'bg-danger text-white shadow-sm hover:brightness-95 active:brightness-90 disabled:opacity-60',
  destructive: 'bg-danger text-white shadow-sm hover:brightness-95 active:brightness-90 disabled:opacity-60',
  quiet: 'bg-sage-100 text-forest-700 hover:bg-sage-200 disabled:opacity-60',
}

const SIZES = {
  sm: 'h-9 px-3 text-sm gap-1.5 rounded-lg',
  md: 'h-10 sm:h-11 px-4 text-sm gap-2 rounded-xl',
  lg: 'h-12 px-6 text-base gap-2 rounded-xl',
  icon: 'h-10 w-10 justify-center rounded-xl',
}

export const Button = forwardRef(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, className = '', children, type = 'button', ...props },
  ref,
) {
  const resolvedVariant = VARIANTS[variant] || VARIANTS.primary
  const resolvedSize = SIZES[size] || SIZES.md
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex select-none items-center justify-center whitespace-nowrap font-medium transition-all duration-150 disabled:cursor-not-allowed focus-ring ${resolvedVariant} ${resolvedSize} ${className}`}
      {...props}
    >
      {loading && <Loader2 size={16} className="shrink-0 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
})
