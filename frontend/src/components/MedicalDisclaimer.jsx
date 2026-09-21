import { Info } from 'lucide-react'
import { ROUTING_DISCLAIMER } from '../utils/constants'

/**
 * Shown wherever symptoms or matching appear. Nivara routes appointments —
 * it does not diagnose, prescribe, or plan treatment, and says so plainly.
 * `text` defaults to our copy but the backend returns its own `disclaimer`
 * string, which callers pass straight through when they have it.
 */
export function MedicalDisclaimer({ text = ROUTING_DISCLAIMER, emergencyNotice, className = '' }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {emergencyNotice && (
        <p className="rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm font-medium text-forest-700" role="alert">
          {emergencyNotice}
        </p>
      )}
      <p className="flex items-start gap-2.5 rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-xs leading-relaxed text-ink-muted">
        <Info size={15} className="mt-0.5 shrink-0 text-forest-400" aria-hidden="true" />
        <span>{text}</span>
      </p>
    </div>
  )
}
