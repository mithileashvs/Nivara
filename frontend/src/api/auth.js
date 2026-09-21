import { api } from './client'

/** POST /auth/register → 201 UserOut. PATIENT or DOCTOR only (admins are created by an admin). */
export const register = (payload) => api.post('/auth/register', payload).then((r) => r.data)

/** POST /auth/login → { access_token, token_type, expires_in, user }. */
export const login = (email, password) =>
  api.post('/auth/login', { email, password }).then((r) => r.data)

/** GET /auth/me → UserOut for the bearer token. */
export const me = () => api.get('/auth/me').then((r) => r.data)
