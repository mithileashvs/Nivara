import { ArrowDownRight, ArrowUpRight, Info, Minus } from 'lucide-react'

const TONE_MAP = {
  default: 'bg-forest-50 text-forest-600',
  positive: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-info-soft text-info',
}

/**
 * Operational KPI card showing exact figure, previous-period comparison delta,
 * and optional metric formula hint.
 */
export function KpiCard({
  icon: Icon,
  label,
  value,
  suffix = '',
  comparison = null,
  isRate = false,
  invertTrend = false,
  tone = 'default',
  formula = null,
  subtitle = null,
}) {
  let deltaLabel = null
  let trendTone = 'text-ink-muted bg-sage-50'
  let TrendIcon = Minus

  if (comparison) {
    if (isRate) {
      const pts = Number(comparison.delta_points ?? 0)
      if (pts > 0) {
        TrendIcon = ArrowUpRight
        deltaLabel = `+${pts.toFixed(1)} pts`
        trendTone = invertTrend ? 'text-danger bg-danger-soft' : 'text-ok bg-ok-soft'
      } else if (pts < 0) {
        TrendIcon = ArrowDownRight
        deltaLabel = `${pts.toFixed(1)} pts`
        trendTone = invertTrend ? 'text-ok bg-ok-soft' : 'text-danger bg-danger-soft'
      } else {
        deltaLabel = '0.0 pts'
      }
    } else {
      const delta = Number(comparison.delta ?? 0)
      const pct = comparison.change_pct
      if (delta > 0) {
        TrendIcon = ArrowUpRight
        deltaLabel = pct !== null && pct !== undefined ? `+${pct}% (+${delta})` : `+${delta}`
        trendTone = invertTrend ? 'text-danger bg-danger-soft' : 'text-ok bg-ok-soft'
      } else if (delta < 0) {
        TrendIcon = ArrowDownRight
        deltaLabel = pct !== null && pct !== undefined ? `${pct}% (${delta})` : `${delta}`
        trendTone = invertTrend ? 'text-ok bg-ok-soft' : 'text-danger bg-danger-soft'
      } else {
        deltaLabel = 'No change'
      }
    }
  }

  return (
    <div className="card flex flex-col justify-between p-4 transition-colors hover:border-forest-200 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <span className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${TONE_MAP[tone] || TONE_MAP.default}`}>
          {Icon && <Icon size={18} aria-hidden="true" />}
        </span>
        {formula && (
          <span
            tabIndex={0}
            title={formula}
            aria-label={`${label} formula: ${formula}`}
            className="inline-flex cursor-help items-center gap-1 rounded-full border border-line bg-canvas px-2 py-0.5 text-[11px] text-ink-muted transition-colors hover:border-forest-200 hover:text-forest-700 focus-ring"
          >
            <Info size={12} aria-hidden="true" />
            <span>Formula</span>
          </span>
        )}
      </div>

      <div className="mt-3">
        <p className="text-2xl font-bold tabular-nums leading-tight text-forest-700 sm:text-3xl">
          {typeof value === 'number' ? value.toLocaleString() : value}
          {suffix && <span className="ml-0.5 text-lg font-semibold text-forest-500">{suffix}</span>}
        </p>
        <p className="mt-1 text-sm font-medium text-ink-muted">{label}</p>
        {subtitle && <p className="mt-0.5 text-xs text-ink-faint">{subtitle}</p>}
      </div>

      {comparison && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-1.5 border-t border-line pt-2.5 text-xs">
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium tabular-nums ${trendTone}`}>
            <TrendIcon size={12} aria-hidden="true" />
            {deltaLabel}
          </span>
          <span className="tabular-nums text-ink-faint">
            Prev: {comparison.previous}
            {suffix}
          </span>
        </div>
      )}
    </div>
  )
}
