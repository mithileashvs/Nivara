import { parseDateString } from '../utils/format'

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

/** The day/month tile that anchors every appointment row in the reference. */
export function DateBlock({ date, size = 'md' }) {
  const d = parseDateString(date)
  const dims = size === 'sm' ? 'h-12 w-12' : 'h-16 w-16'
  const day = size === 'sm' ? 'text-base' : 'text-xl'
  return (
    <div
      className={`flex ${dims} shrink-0 flex-col items-center justify-center rounded-xl bg-forest-50 text-forest-600`}
    >
      <span className={`${day} font-bold leading-none tabular-nums`}>{d ? d.getDate() : '–'}</span>
      <span className="mt-1 text-[0.6rem] font-semibold tracking-wide text-forest-400">
        {d ? MONTHS[d.getMonth()] : ''}
      </span>
    </div>
  )
}
