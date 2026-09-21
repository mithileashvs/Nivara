import { Link } from 'react-router-dom'
import { useAuth, homePathFor } from '../../context/AuthContext'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'

export default function NotFound() {
  useDocumentTitle('Page not found')
  const { user, isAuthenticated } = useAuth()
  const home = isAuthenticated ? homePathFor(user) : '/'

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-canvas px-6 text-center">
      <p className="font-display text-6xl text-forest-300">404</p>
      <h1 className="mt-4 text-xl font-semibold text-forest-700">This page does not exist</h1>
      <p className="mt-2 max-w-sm text-sm text-ink-muted">
        The link may be out of date, or the page may have moved.
      </p>
      <Link
        to={home}
        className="mt-8 inline-flex h-11 items-center rounded-xl bg-forest px-5 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
      >
        Back to Nivara
      </Link>
    </div>
  )
}
