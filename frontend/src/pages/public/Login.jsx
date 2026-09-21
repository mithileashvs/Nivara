import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { AuthLayout } from '../../layouts/AuthLayout'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/Field'
import { ErrorState } from '../../components/ui/States'
import { useAuth, homePathFor } from '../../context/AuthContext'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { ROLES } from '../../utils/constants'
import { fieldErrors } from '../../utils/errors'

/** Send people back where they were headed, but only if that area is theirs. */
function destinationFor(user, from) {
  const home = homePathFor(user)
  if (!from) return home
  const AREAS = ['/doctor', '/admin', '/hospital']
  const fromArea = AREAS.find((a) => from === a || from.startsWith(`${a}/`)) ?? null
  const homeArea = AREAS.find((a) => home === a) ?? null
  return fromArea === homeArea ? from : home
}

/* The reference shows Patient / Doctor / Admin / Hospital tabs. The backend has
 * exactly three roles — PATIENT, DOCTOR, ADMIN — and models a hospital
 * administrator as an ADMIN carrying `managed_hospital_ids`. So there are three
 * tabs and a note explaining where hospital administrators sign in. The tab is a
 * convenience only: the account's real role comes back from the backend and
 * decides where you land. */
const TABS = [
  { value: ROLES.PATIENT, label: 'Patient' },
  { value: ROLES.DOCTOR, label: 'Doctor' },
  { value: ROLES.ADMIN, label: 'Admin' },
]

export default function Login() {
  useDocumentTitle('Sign in')
  const { signIn, sessionEnded, clearSessionEnded } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [tab, setTab] = useState(ROLES.PATIENT)
  const [form, setForm] = useState({ email: '', password: '' })
  const [remember, setRemember] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const invalid = useMemo(() => fieldErrors(error), [error])
  const from = location.state?.from?.pathname

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    clearSessionEnded()
    try {
      const user = await signIn(form.email.trim().toLowerCase(), form.password, remember)
      navigate(destinationFor(user, from), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue your health journey"
      panelText="Small steps, healthier you"
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link to="/register" className="rounded font-semibold text-forest transition-colors hover:text-forest-400 focus-ring">
            Sign up
          </Link>
        </>
      }
    >
      {sessionEnded && (
        <p className="mb-5 rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700" role="status">
          Your session ended. Sign in again to pick up where you left off.
        </p>
      )}

      <div role="tablist" aria-label="Account type" className="mb-6 grid grid-cols-3 gap-1 rounded-xl bg-forest-50 p-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={tab === t.value}
            onClick={() => setTab(t.value)}
            className={`rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-ring ${
              tab === t.value ? 'bg-forest text-canvas' : 'text-ink-muted hover:text-forest-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} noValidate className="space-y-4">
        {error && <ErrorState error={error} compact />}

        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-forest-700">
            Email
          </label>
          <div className="relative">
            <Mail size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={set('email')}
              placeholder="you@example.com"
              aria-invalid={invalid.email ? 'true' : undefined}
              className={`h-12 w-full rounded-xl border bg-surface pl-11 pr-3.5 text-sm placeholder:text-ink-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas ${
                invalid.email ? 'border-danger/60' : 'border-line hover:border-forest-200'
              }`}
            />
          </div>
          {invalid.email && <p className="mt-1.5 text-xs text-danger">{invalid.email}</p>}
        </div>

        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-forest-700">
            Password
          </label>
          <div className="relative">
            <Lock size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={form.password}
              onChange={set('password')}
              placeholder="Your password"
              aria-invalid={invalid.password ? 'true' : undefined}
              className={`h-12 w-full rounded-xl border bg-surface pl-11 pr-11 text-sm placeholder:text-ink-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas ${
                invalid.password ? 'border-danger/60' : 'border-line hover:border-forest-200'
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-ink-faint transition-colors hover:text-forest focus-ring"
            >
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {invalid.password && <p className="mt-1.5 text-xs text-danger">{invalid.password}</p>}
        </div>

        <Checkbox
          label="Remember me on this device"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
        />

        <Button type="submit" size="lg" loading={submitting} className="w-full justify-center">
          Login
        </Button>
      </form>

      {tab === ROLES.ADMIN && (
        <p className="mt-5 rounded-xl border border-line bg-forest-50/70 px-4 py-3 text-xs leading-relaxed text-ink-muted">
          Hospital administrators sign in here too. Nivara gives an administrator access to the
          hospitals assigned to their account, so you will land on your hospital dashboard.
        </p>
      )}

      {/* There is no password-reset endpoint and no social sign-in on this backend,
          so neither is offered here rather than linking to something that cannot work. */}
      <p className="mt-5 text-center text-xs text-ink-faint">
        Trouble signing in? Ask your Nivara administrator to reset your account.
      </p>
    </AuthLayout>
  )
}
