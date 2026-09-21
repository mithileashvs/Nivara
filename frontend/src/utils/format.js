/* The backend returns clinic-local wall-clock strings for dates and times
 * ("2026-03-04", "09:30") and true UTC instants for audit timestamps. */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

/** Parse "YYYY-MM-DD" without letting the local timezone shift the day. */
export function parseDateString(value) {
  if (!value) return null
  const [y, m, d] = String(value).split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

export function toDateString(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function todayString() {
  return toDateString(new Date())
}

export function addDays(dateString, days) {
  const d = parseDateString(dateString) || new Date()
  d.setDate(d.getDate() + days)
  return toDateString(d)
}

/** "4 Mar 2026" */
export function formatDate(value) {
  const d = parseDateString(value)
  if (!d) return '—'
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

/** "Wednesday, 4 March" */
export function formatLongDate(value) {
  const d = parseDateString(value)
  if (!d) return '—'
  return `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]}`
}

export function weekdayShort(value) {
  const d = parseDateString(value)
  return d ? DAYS[d.getDay()].slice(0, 3) : ''
}

/** "09:30" → "9:30 am" */
export function formatTime(value) {
  if (!value) return '—'
  const [h, m] = String(value).split(':').map(Number)
  if (Number.isNaN(h)) return value
  const suffix = h >= 12 ? 'pm' : 'am'
  const hour = h % 12 === 0 ? 12 : h % 12
  return `${hour}:${String(m ?? 0).padStart(2, '0')} ${suffix}`
}

export function formatTimeRange(start, end) {
  return `${formatTime(start)} – ${formatTime(end)}`
}

/** UTC instant → local "4 Mar 2026, 9:30 am" */
export function formatInstant(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  const hour = d.getHours() % 12 === 0 ? 12 : d.getHours() % 12
  const suffix = d.getHours() >= 12 ? 'pm' : 'am'
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${hour}:${String(
    d.getMinutes(),
  ).padStart(2, '0')} ${suffix}`
}

export function relativeTime(value) {
  if (!value) return ''
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Math.round((Date.now() - then) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)} d ago`
  return formatInstant(value)
}

export function greeting(date = new Date()) {
  const h = date.getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export function initials(name = '') {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

export function currency(value) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

export function pluralise(n, one, many) {
  return `${n} ${n === 1 ? one : many}`
}

/** Turn a snake/upper-case enum into readable text: NO_SHOW → "No show". */
export function humanise(value) {
  if (!value) return ''
  const s = String(value).replace(/_/g, ' ').toLowerCase()
  return s.charAt(0).toUpperCase() + s.slice(1)
}
