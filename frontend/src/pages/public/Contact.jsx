import { useDocumentTitle } from '../../hooks/useDocumentTitle'

/* There is no contact-form or messaging endpoint on this backend, so this page
 * explains where to get help rather than posting into a void. */
export default function Contact() {
  useDocumentTitle('Contact')
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
      <h1 className="font-display text-4xl leading-tight text-forest-700 sm:text-5xl">Get in touch</h1>
      <p className="mt-5 text-base leading-relaxed text-ink-muted">
        Nivara is run by your hospital, so the fastest help comes from them directly.
      </p>

      <dl className="mt-10 space-y-6">
        <div className="card p-5">
          <dt className="text-sm font-semibold text-forest-700">About an appointment</dt>
          <dd className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            Open the appointment in your dashboard. You can cancel or move it there, and the status
            history shows every change and who made it.
          </dd>
        </div>
        <div className="card p-5">
          <dt className="text-sm font-semibold text-forest-700">About your account</dt>
          <dd className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            Contact the administrator at your hospital. They can activate, suspend or correct
            accounts and doctor profiles.
          </dd>
        </div>
        <div className="card border-danger/30 bg-danger-soft p-5">
          <dt className="text-sm font-semibold text-forest-700">In an emergency</dt>
          <dd className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            Do not use Nivara. Contact your local emergency services immediately.
          </dd>
        </div>
      </dl>
    </div>
  )
}
