import { AlertCircle, AlertTriangle, CheckCircle2, Info, ShieldCheck } from 'lucide-react'

const TONES = {
  info: {
    box: 'border-info/25 bg-info-soft text-forest-800',
    icon: Info,
    iconColor: 'text-info',
    role: 'status',
  },
  warn: {
    box: 'border-warn/30 bg-warn-soft text-forest-800',
    icon: AlertTriangle,
    iconColor: 'text-warn',
    role: 'status',
  },
  danger: {
    box: 'border-danger/30 bg-danger-soft text-forest-800',
    icon: AlertCircle,
    iconColor: 'text-danger',
    role: 'alert',
  },
  positive: {
    box: 'border-ok/25 bg-ok-soft text-forest-800',
    icon: CheckCircle2,
    iconColor: 'text-ok',
    role: 'status',
  },
  neutral: {
    box: 'border-line bg-surface-muted text-forest-700',
    icon: ShieldCheck,
    iconColor: 'text-forest-500',
    role: 'status',
  },
}

/**
 * Semantic clinical & operational callout banner. Always pairs colour with a
 * status icon so state is never communicated by colour alone.
 */
export function Alert({
  tone = 'info',
  title,
  icon: CustomIcon,
  action,
  className = '',
  children,
}) {
  const cfg = TONES[tone] || TONES.info
  const Icon = CustomIcon || cfg.icon

  return (
    <div
      role={cfg.role}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm ${cfg.box} ${className}`}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon size={18} className={`mt-0.5 shrink-0 ${cfg.iconColor}`} aria-hidden="true" />
        <div className="min-w-0 flex-1 leading-relaxed">
          {title && <p className="font-semibold text-forest-800">{title}</p>}
          {children && (
            <div className={`${title ? 'mt-0.5 text-ink-muted' : 'text-forest-800'}`}>
              {children}
            </div>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
