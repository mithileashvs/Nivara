import { Link } from 'react-router-dom'
import { ArrowRight, CalendarCheck, PlayCircle, ShieldCheck, Sparkles, UserCheck } from 'lucide-react'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'

/* Every claim below describes something the backend actually does:
 *   Trusted doctors   — admins verify a doctor profile before it can take requests
 *   Smart suggestions — POST /smart/department-suggestion routes symptoms to a department
 *   Easy booking      — POST /appointments requests a real slot; the doctor then decides
 *   Safe & secure     — JWT auth, role-based access, records limited to patient + doctor
 * No counts, ratings or testimonials appear here, because no public endpoint exposes them.
 */

const FEATURES = [
  {
    icon: UserCheck,
    title: 'Trusted doctors',
    body: 'Every doctor profile is verified by an administrator before it can take appointments.',
  },
  {
    icon: Sparkles,
    title: 'Smart suggestions',
    body: 'Describe what you are feeling and Nivara points you to the right department to book with.',
  },
  {
    icon: CalendarCheck,
    title: 'Easy booking',
    body: 'Pick a real open time. Your doctor reviews the request and confirms it.',
  },
  {
    icon: ShieldCheck,
    title: 'Safe & secure',
    body: 'Your records stay between you and your treating doctor. Administrators cannot open them.',
  },
]

function HeroArt() {
  return (
    <div className="relative aspect-[4/3] w-full overflow-hidden rounded-3xl bg-sage-100 sm:aspect-[16/11] lg:aspect-auto lg:h-full">
      <div className="absolute inset-0 bg-gradient-to-br from-sage-200/80 via-forest-50 to-sage-300/50" />
      {/* A quiet botanical arch — the calm, planted look of the reference. */}
      <svg
        viewBox="0 0 520 460"
        className="absolute inset-0 h-full w-full text-forest-300/55"
        fill="none"
        preserveAspectRatio="xMidYMax slice"
        aria-hidden="true"
      >
        <path d="M300 40c80 0 145 65 145 145v250H155V185C155 105 220 40 300 40Z" fill="currentColor" opacity="0.22" />
        <path d="M330 460c0-105 35-175 105-215-85 5-142 45-172 120-5-130 15-230 62-300-70 55-113 155-128 300-30-80-80-135-150-165 60 65 96 150 104 260h179Z" fill="currentColor" opacity="0.5" />
        <path d="M150 460c8-70 44-118 108-145-60 0-102 25-125 75 5-80 22-142 52-188-52 38-84 105-96 195-18-48-49-84-92-104 36 42 60 97 66 167h87Z" fill="currentColor" opacity="0.32" />
      </svg>
      <p className="absolute left-6 top-8 max-w-[9rem] font-display text-2xl leading-[1.2] text-forest-700 sm:left-10 sm:top-12 sm:max-w-[11rem] sm:text-3xl">
        Better care, brighter tomorrows
      </p>
    </div>
  )
}

export default function Landing() {
  useDocumentTitle('Healthcare appointments')

  return (
    <>
      <section className="mx-auto w-full max-w-[80rem] px-4 pb-4 pt-8 sm:px-6 lg:px-8 lg:pt-14">
        <div className="grid items-stretch gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-12">
          <div className="flex flex-col justify-center">
            <p className="text-xs font-medium tracking-[0.18em] text-ink-muted">
              CARE TODAY, HEALTHIER TOMORROW
            </p>

            <h1 className="mt-5 font-display text-[2.75rem] font-normal leading-[1.05] tracking-tight text-forest-700 sm:text-6xl lg:text-[4.25rem]">
              Your health
              <br />
              our priority
            </h1>

            <p className="mt-5 max-w-lg text-base leading-relaxed text-ink-muted sm:text-lg">
              Find trusted doctors, request appointments that fit your week, and keep your care
              history in one place.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                to="/register"
                className="inline-flex h-12 items-center gap-2 rounded-full bg-forest px-6 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
              >
                Get started
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
              <Link
                to="/about"
                className="inline-flex items-center gap-2.5 rounded-full px-1 py-2 text-sm font-medium text-forest-700 transition-colors hover:text-forest focus-ring"
              >
                <PlayCircle size={28} strokeWidth={1.4} aria-hidden="true" />
                How Nivara works
              </Link>
            </div>
          </div>

          <HeroArt />
        </div>
      </section>

      <section aria-label="What Nivara offers" className="mx-auto w-full max-w-[80rem] px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
        <ul className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <li key={title} className="bg-canvas px-6 py-8 text-center">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-forest-50 text-forest-500">
                <Icon size={21} aria-hidden="true" />
              </span>
              <h2 className="mt-4 text-sm font-semibold text-forest-700">{title}</h2>
              <p className="mx-auto mt-2 max-w-[18rem] text-xs leading-relaxed text-ink-muted">{body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto w-full max-w-[80rem] px-4 pb-16 sm:px-6 lg:px-8 lg:pb-24">
        <div className="rounded-3xl bg-forest px-6 py-12 text-center sm:px-12 lg:py-16">
          <h2 className="font-display text-3xl leading-tight text-canvas sm:text-4xl">
            Three steps to a confirmed appointment
          </h2>
          <ol className="mx-auto mt-10 grid max-w-3xl gap-8 text-left sm:grid-cols-3">
            {[
              ['You request', 'Choose a doctor and a time that is genuinely open.'],
              ['Your doctor reviews', 'They accept or decline the request themselves.'],
              ['You are confirmed', 'The time is held for you and you get a reminder.'],
            ].map(([title, body], i) => (
              <li key={title}>
                <span className="flex h-8 w-8 items-center justify-center rounded-full border border-forest-300/60 text-sm font-semibold text-sage-300">
                  {i + 1}
                </span>
                <h3 className="mt-3 text-sm font-semibold text-canvas">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-forest-100/75">{body}</p>
              </li>
            ))}
          </ol>
          <Link
            to="/register"
            className="mt-10 inline-flex h-12 items-center gap-2 rounded-full bg-canvas px-6 text-sm font-medium text-forest-700 transition-colors hover:bg-sage-100 focus-ring"
          >
            Create your account
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </>
  )
}
