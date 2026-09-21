import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import * as authApi from '../api/auth'
import * as doctorsApi from '../api/doctors'
import { loadToken, setToken, setUnauthorizedHandler } from '../api/client'
import { ROLES } from '../utils/constants'

const AuthContext = createContext(null)

/** Where a signed-in account belongs. Hospital administrators are ADMIN accounts
 *  with a `managed_hospital_ids` list — the backend has no separate hospital role. */
export function homePathFor(user) {
  if (!user) return '/login'
  if (user.role === ROLES.DOCTOR) return '/doctor'
  if (user.role === ROLES.ADMIN) return isHospitalAdmin(user) ? '/hospital' : '/admin'
  return '/dashboard'
}

export function isHospitalAdmin(user) {
  return user?.role === ROLES.ADMIN && Array.isArray(user.managed_hospital_ids)
}

export function isPlatformAdmin(user) {
  return user?.role === ROLES.ADMIN && !Array.isArray(user.managed_hospital_ids)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  /** DOCTOR only: the doctor profile behind the account (id, profile_status, intake…). */
  const [doctorProfile, setDoctorProfile] = useState(null)
  const [status, setStatus] = useState('loading') // loading | authenticated | anonymous
  const [sessionEnded, setSessionEnded] = useState(false)

  const clear = useCallback(() => {
    setToken(null)
    setUser(null)
    setDoctorProfile(null)
    setStatus('anonymous')
  }, [])

  const hydrate = useCallback(async (account) => {
    setUser(account)
    if (account.role === ROLES.DOCTOR) {
      try {
        setDoctorProfile(await doctorsApi.getMyDoctorProfile())
      } catch {
        // A doctor account without a profile can still sign in; the dashboard
        // shows what is missing rather than failing the whole session.
        setDoctorProfile(null)
      }
    } else {
      setDoctorProfile(null)
    }
    setStatus('authenticated')
  }, [])

  // Restore a stored session on first load by re-validating the token server-side.
  useEffect(() => {
    let cancelled = false
    const token = loadToken()
    if (!token) {
      setStatus('anonymous')
      return undefined
    }
    authApi
      .me()
      .then((account) => {
        if (!cancelled) hydrate(account)
      })
      .catch(() => {
        if (!cancelled) clear()
      })
    return () => {
      cancelled = true
    }
  }, [hydrate, clear])

  // A 401 from any request means the backend rejected the token — end the session.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser((current) => {
        if (current) setSessionEnded(true)
        return null
      })
      setDoctorProfile(null)
      setStatus('anonymous')
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  const signIn = useCallback(
    async (email, password, remember = true) => {
      const data = await authApi.login(email, password)
      setToken(data.access_token, { remember })
      setSessionEnded(false)
      await hydrate(data.user)
      return data.user
    },
    [hydrate],
  )

  const signUp = useCallback(
    async (payload) => {
      await authApi.register(payload)
      return signIn(payload.email, payload.password, true)
    },
    [signIn],
  )

  const signOut = useCallback(() => {
    setSessionEnded(false)
    clear()
  }, [clear])

  const refreshUser = useCallback(async () => {
    const account = await authApi.me()
    setUser(account)
    return account
  }, [])

  const refreshDoctorProfile = useCallback(async () => {
    const profile = await doctorsApi.getMyDoctorProfile()
    setDoctorProfile(profile)
    return profile
  }, [])

  const value = useMemo(
    () => ({
      user,
      doctorProfile,
      status,
      isLoading: status === 'loading',
      isAuthenticated: status === 'authenticated',
      sessionEnded,
      clearSessionEnded: () => setSessionEnded(false),
      isHospitalAdmin: isHospitalAdmin(user),
      isPlatformAdmin: isPlatformAdmin(user),
      managedHospitalIds: user?.managed_hospital_ids ?? null,
      signIn,
      signUp,
      signOut,
      refreshUser,
      refreshDoctorProfile,
      setDoctorProfile,
    }),
    [user, doctorProfile, status, sessionEnded, signIn, signUp, signOut, refreshUser, refreshDoctorProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
