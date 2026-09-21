import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'

/* Describes only what the system actually does — no statistics, awards or
 * partner counts, none of which the backend exposes. */
export default function About() {
  useDocumentTitle('About')
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
      <h1 className="font-display text-4xl leading-tight text-forest-700 sm:text-5xl">
        How Nivara works
      </h1>
      <p className="mt-5 text-base leading-relaxed text-ink-muted">
        Nivara connects patients with verified doctors at the hospitals and departments they
        actually work in. It handles one job carefully: getting you to the right consultation at a
        time that is genuinely free.
      </p>

      <div className="mt-10 space-y-8">
        <section>
          <h2 className="text-lg font-semibold text-forest-700">Your doctor decides, not an algorithm</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            When you pick a time, Nivara holds it and sends the request to that doctor. They
            accept or decline it themselves. Administrators manage hospitals, departments and
            accounts — they never approve or reject an individual appointment.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-forest-700">Availability you can trust</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Every time you see comes from a doctor&apos;s published working hours. If a hospital,
            department or doctor stops taking new appointments, those times stop being offered —
            but appointments already booked stay exactly as they are.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-forest-700">Routing, not diagnosis</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Tell Nivara what you are feeling and it suggests which department to book with. That
            is the whole of it. Nivara does not diagnose conditions, predict diseases, prescribe
            medicines, recommend dosages or plan treatment. For anything medical, speak to a
            qualified doctor — and in an emergency, contact your local emergency services.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-forest-700">Who can see your records</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            Consultation notes are written by your treating doctor and visible to you and to them.
            Administrators cannot open medical records at all.
          </p>
        </section>
      </div>

      <Link
        to="/register"
        className="mt-12 inline-flex h-12 items-center rounded-full bg-forest px-6 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
      >
        Create your account
      </Link>
    </div>
  )
}
