import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'

/**
 * Split screen from the reference: form on one side, a calm green panel carrying
 * a short line of copy on the other.
 */
export function AuthLayout({ title, subtitle, panelText, children, footer }) {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <div className="flex flex-col px-4 py-8 sm:px-8 lg:px-12" style={{ paddingTop: 'calc(2rem + env(safe-area-inset-top, 0px))' }}>
        <Link to="/" className="mx-auto rounded focus-ring" aria-label="Nivara home">
          <Logo size="lg" />
        </Link>

        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-forest-700 sm:text-3xl">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-ink-muted">{subtitle}</p>}
          </div>

          <div className="mt-8">{children}</div>

          {footer && <div className="mt-6 text-center text-sm text-ink-muted">{footer}</div>}
        </div>
      </div>

      <aside className="relative hidden overflow-hidden bg-forest-100 lg:block" aria-hidden="true">
        <div className="absolute inset-0 bg-gradient-to-b from-sage-200/70 via-forest-100 to-forest-200/60" />
        <svg viewBox="0 0 400 800" className="absolute inset-0 h-full w-full text-forest-300/45" fill="none" preserveAspectRatio="xMidYMid slice">
          <path d="M210 800C210 640 150 560 60 500c120-10 190 40 220 130 20-150-10-280-60-390 90 80 140 210 150 360 40-90 100-150 180-180-70 80-110 190-120 330-5 60-5 110 0 160H210Z" fill="currentColor" opacity="0.5" />
          <path d="M320 800c0-120 40-200 110-250-90 0-150 40-180 110 0-110 25-200 70-270-70 60-110 160-120 280-25-70-70-120-135-145 55 60 85 140 90 250 2 8 2 17 2 25h163Z" fill="currentColor" opacity="0.35" />
        </svg>
        <p className="absolute left-12 top-24 max-w-[12rem] font-display text-4xl leading-[1.15] text-forest-700">
          {panelText}
        </p>
      </aside>
    </div>
  )
}
