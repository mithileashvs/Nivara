import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth, homePathFor, isHospitalAdmin } from '../context/AuthContext'
import { Spinner } from '../components/ui/States'
import { ROLES } from '../utils/constants'

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas" role="status">
      <Spinner size={28} />
      <span className="sr-only">Loading</span>
    </div>
  )
}

/**
 * Requires a session. The backend is still the authority — these guards only
 * keep people out of screens whose requests would be refused anyway.
 */
export function RequireAuth() {
  const { isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageSpinner />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />
  return <Outlet />
}

/** Requires one of `roles`; anyone else is sent to their own home area. */
export function RequireRole({ roles, hospitalScope }) {
  const { isLoading, isAuthenticated, user } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageSpinner />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />
  if (!roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />

  // Admin area splits in two: platform-wide admins vs hospital administrators.
  if (user.role === ROLES.ADMIN && hospitalScope !== undefined) {
    const scoped = isHospitalAdmin(user)
    if (hospitalScope === true && !scoped) return <Navigate to="/admin" replace />
    if (hospitalScope === false && scoped) return <Navigate to="/hospital" replace />
  }

  return <Outlet />
}

/** Keeps signed-in people off the login and registration screens. */
export function RedirectIfAuthenticated() {
  const { isLoading, isAuthenticated, user } = useAuth()
  if (isLoading) return <FullPageSpinner />
  if (isAuthenticated) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}
