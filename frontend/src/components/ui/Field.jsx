import { useId } from 'react'
import { ChevronDown } from 'lucide-react'

const CONTROL =
  'w-full rounded-xl border bg-surface px-3.5 text-sm text-ink placeholder:text-ink-faint transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-forest focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:bg-surface-muted disabled:text-ink-faint disabled:cursor-not-allowed'

function wrapperClass(error) {
  return `${CONTROL} ${error ? 'border-danger/60' : 'border-line hover:border-forest-200'}`
}

export function Field({ label, hint, error, required, children, htmlFor, hintId, errorId, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-forest-700">
          {label}
          {required && <span className="ml-0.5 text-danger" aria-hidden="true">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p id={errorId} role="alert" className="mt-1.5 text-xs font-medium text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-1.5 text-xs text-ink-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function Input({ label, hint, error, icon: Icon, className = '', id, ...props }) {
  const generated = useId()
  const inputId = id || generated
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = errorId || hintId

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      htmlFor={inputId}
      hintId={hintId}
      errorId={errorId}
      required={props.required}
      className={className}
    >
      <div className="relative">
        {Icon && (
          <Icon
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint"
            aria-hidden="true"
          />
        )}
        <input
          id={inputId}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={describedBy}
          className={`${wrapperClass(error)} h-11 ${Icon ? 'pl-10' : ''}`}
          {...props}
        />
      </div>
    </Field>
  )
}

export function Textarea({ label, hint, error, className = '', rows = 4, id, ...props }) {
  const generated = useId()
  const inputId = id || generated
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = errorId || hintId

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      htmlFor={inputId}
      hintId={hintId}
      errorId={errorId}
      required={props.required}
      className={className}
    >
      <textarea
        id={inputId}
        rows={rows}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={describedBy}
        className={`${wrapperClass(error)} py-2.5 leading-relaxed`}
        {...props}
      />
    </Field>
  )
}

export function Select({ label, hint, error, options = [], placeholder, className = '', id, children, ...props }) {
  const generated = useId()
  const inputId = id || generated
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  const describedBy = errorId || hintId

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      htmlFor={inputId}
      hintId={hintId}
      errorId={errorId}
      required={props.required}
      className={className}
    >
      <div className="relative">
        <select
          id={inputId}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={describedBy}
          className={`${wrapperClass(error)} h-11 appearance-none pr-9`}
          {...props}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
          {children}
        </select>
        <ChevronDown
          size={16}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint"
          aria-hidden="true"
        />
      </div>
    </Field>
  )
}

export function Checkbox({ label, id, className = '', ...props }) {
  const generated = useId()
  const inputId = id || generated
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <input
        id={inputId}
        type="checkbox"
        className="h-4 w-4 rounded border-line text-forest accent-[#173C2B] focus-ring"
        {...props}
      />
      <label htmlFor={inputId} className="select-none text-sm text-ink">
        {label}
      </label>
    </div>
  )
}
