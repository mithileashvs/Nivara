import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail, Phone, Stethoscope, User } from 'lucide-react'
import { AuthLayout } from '../../layouts/AuthLayout'
import { Button } from '../../components/ui/Button'
import { Checkbox, Input, Select } from '../../components/ui/Field'
import { ErrorState } from '../../components/ui/States'
import { useAuth, homePathFor } from '../../context/AuthContext'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { CONSULTATION_TYPES, GENDERS, ROLES } from '../../utils/constants'
import { fieldErrors } from '../../utils/errors'

/* Only PATIENT and DOCTOR can self-register — the backend rejects role=ADMIN
 * outright — so the reference's Admin and Hospital tabs are replaced by a note
 * saying how those accounts are created. */
const TABS = [
  { value: ROLES.PATIENT, label: 'Patient' },
  { value: ROLES.DOCTOR, label: 'Doctor' },
]

const EMPTY = {
  name: '',
  email: '',
  phone: '',
  password: '',
  confirm: '',
  date_of_birth: '',
  gender: '',
  specialty: '',
  experience: '',
  consultation_fee: '',
  consultation_types: [],
}

export default function Register() {
  useDocumentTitle('Create your account')
  const { signUp } = useAuth()
  const navigate = useNavigate()

  const [role, setRole] = useState(ROLES.PATIENT)
  const [form, setForm] = useState(EMPTY)
  const [agreed, setAgreed] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [local, setLocal] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const serverErrors = useMemo(() => fieldErrors(error), [error])
  const errorFor = (k) => local[k] || serverErrors[k]
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const toggleType = (value) =>
    setForm((f) => ({
      ...f,
      consultation_types: f.consultation_types.includes(value)
        ? f.consultation_types.filter((v) => v !== value)
        : [...f.consultation_types, value],
    }))

  /** Mirrors the backend's own rules so people get feedback before a round trip. */
  function validate() {
    const next = {}
    if (form.name.trim().length < 2) next.name = 'Enter your full name.'
    if (!form.email.includes('@')) next.email = 'Enter a valid email address.'
    if (form.password.length < 8) next.password = 'Use at least 8 characters.'
    else if (!/[a-zA-Z]/.test(form.password) || !/\d/.test(form.password))
      next.password = 'Include at least one letter and one number.'
    if (form.confirm !== form.password) next.confirm = 'Both passwords must match.'
    if (role === ROLES.DOCTOR && form.specialty.trim().length < 2)
      next.specialty = 'Enter the specialty you practise.'
    if (!agreed) next.agreed = 'Accept the terms to continue.'
    setLocal(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setError(null)

    const payload = {
      name: form.name.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
      role,
      ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
    }
    if (role === ROLES.PATIENT) {
      if (form.date_of_birth) payload.date_of_birth = form.date_of_birth
      if (form.gender) payload.gender = form.gender
    } else {
      payload.specialty = form.specialty.trim()
      if (form.experience !== '') payload.experience = Number(form.experience)
      if (form.consultation_fee !== '') payload.consultation_fee = Number(form.consultation_fee)
      if (form.consultation_types.length) payload.consultation_types = form.consultation_types
    }

    try {
      const user = await signUp(payload)
      navigate(homePathFor(user), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join us for a healthier tomorrow"
      panelText="Good health, happier people"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="rounded font-semibold text-forest transition-colors hover:text-forest-400 focus-ring">
            Login
          </Link>
        </>
      }
    >
      <div role="tablist" aria-label="Account type" className="mb-6 grid grid-cols-2 gap-1 rounded-xl bg-forest-50 p-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={role === t.value}
            onClick={() => setRole(t.value)}
            className={`rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-ring ${
              role === t.value ? 'bg-forest text-canvas' : 'text-ink-muted hover:text-forest-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} noValidate className="space-y-4">
        {error && <ErrorState error={error} compact />}

        <IconInput
          icon={User}
          id="name"
          label="Full name"
          required
          autoComplete="name"
          value={form.name}
          onChange={set('name')}
          error={errorFor('name')}
          placeholder="Your full name"
        />

        <IconInput
          icon={Mail}
          id="email"
          type="email"
          label="Email"
          required
          autoComplete="email"
          value={form.email}
          onChange={set('email')}
          error={errorFor('email')}
          placeholder="you@example.com"
        />

        <IconInput
          icon={Phone}
          id="phone"
          type="tel"
          label="Phone (optional)"
          autoComplete="tel"
          value={form.phone}
          onChange={set('phone')}
          error={errorFor('phone')}
          placeholder="+91 98765 43210"
        />

        <IconInput
          icon={Lock}
          id="password"
          type={showPassword ? 'text' : 'password'}
          label="Password"
          required
          autoComplete="new-password"
          value={form.password}
          onChange={set('password')}
          error={errorFor('password')}
          hint="At least 8 characters, including a letter and a number."
          placeholder="Create a password"
          trailing={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="rounded p-1 text-ink-faint transition-colors hover:text-forest focus-ring"
            >
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          }
        />

        <IconInput
          icon={Lock}
          id="confirm"
          type={showPassword ? 'text' : 'password'}
          label="Confirm password"
          required
          autoComplete="new-password"
          value={form.confirm}
          onChange={set('confirm')}
          error={errorFor('confirm')}
          placeholder="Repeat your password"
        />

        {role === ROLES.PATIENT ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              id="dob"
              type="date"
              label="Date of birth (optional)"
              value={form.date_of_birth}
              max={new Date().toISOString().slice(0, 10)}
              onChange={set('date_of_birth')}
              error={errorFor('date_of_birth')}
            />
            <Select
              id="gender"
              label="Gender (optional)"
              placeholder="Prefer not to say"
              options={GENDERS}
              value={form.gender}
              onChange={set('gender')}
              error={errorFor('gender')}
            />
          </div>
        ) : (
          <div className="space-y-4 rounded-xl border border-line bg-forest-50/50 p-4">
            <IconInput
              icon={Stethoscope}
              id="specialty"
              label="Specialty"
              required
              value={form.specialty}
              onChange={set('specialty')}
              error={errorFor('specialty')}
              placeholder="Cardiology, Dermatology, …"
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                id="experience"
                type="number"
                min="0"
                max="70"
                label="Years of experience"
                value={form.experience}
                onChange={set('experience')}
                error={errorFor('experience')}
                placeholder="0"
              />
              <Input
                id="fee"
                type="number"
                min="0"
                step="1"
                label="Consultation fee"
                value={form.consultation_fee}
                onChange={set('consultation_fee')}
                error={errorFor('consultation_fee')}
                placeholder="0"
              />
            </div>
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-forest-700">
                Consultation types you offer
              </legend>
              <div className="space-y-2">
                {CONSULTATION_TYPES.map((t) => (
                  <Checkbox
                    key={t.value}
                    label={t.label}
                    checked={form.consultation_types.includes(t.value)}
                    onChange={() => toggleType(t.value)}
                  />
                ))}
              </div>
            </fieldset>
            <p className="text-xs leading-relaxed text-ink-muted">
              Your profile starts as pending. An administrator verifies it and assigns your hospital
              and department before you can publish availability or receive requests.
            </p>
          </div>
        )}

        <div>
          <Checkbox
            label="I agree to the terms and conditions"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
          />
          {errorFor('agreed') && <p className="mt-1.5 text-xs text-danger">{errorFor('agreed')}</p>}
        </div>

        <Button type="submit" size="lg" loading={submitting} className="w-full justify-center">
          Sign up
        </Button>
      </form>

      <p className="mt-5 rounded-xl border border-line bg-forest-50/70 px-4 py-3 text-xs leading-relaxed text-ink-muted">
        Administrator and hospital-administrator accounts are created by an existing Nivara
        administrator, not through this form.
      </p>
    </AuthLayout>
  )
}

/** Input with a leading icon, as used throughout the reference's auth screens. */
function IconInput({ icon: Icon, id, label, error, hint, trailing, required, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-forest-700">
        {label}
        {required && <span className="ml-0.5 text-danger" aria-hidden="true">*</span>}
      </label>
      <div className="relative">
        <Icon size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
        <input
          id={id}
          required={required}
          aria-invalid={error ? 'true' : undefined}
          className={`h-12 w-full rounded-xl border bg-surface pl-11 text-sm placeholder:text-ink-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas ${
            trailing ? 'pr-11' : 'pr-3.5'
          } ${error ? 'border-danger/60' : 'border-line hover:border-forest-200'}`}
          {...props}
        />
        {trailing && <span className="absolute right-3 top-1/2 -translate-y-1/2">{trailing}</span>}
      </div>
      {error ? (
        <p className="mt-1.5 text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>
      ) : null}
    </div>
  )
}
