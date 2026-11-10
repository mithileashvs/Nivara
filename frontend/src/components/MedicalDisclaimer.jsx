import { Alert } from './ui/Alert'
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
        <Alert tone="danger">
          <span className="font-medium">{emergencyNotice}</span>
        </Alert>
      )}
      <Alert tone="info" className="text-xs">
        {text}
      </Alert>
    </div>
  )
}
