import axios from 'axios'

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

/** The backend mounts every business route under this prefix (Settings.api_prefix). */
export const API_PREFIX = '/api/v1'
export const API_ROOT = `${BASE}${API_PREFIX}`

export const api = axios.create({
  baseURL: API_ROOT,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
})

/* ------------------------------------------------------------------ token ---
 * The JWT lives in module scope and is mirrored into storage so a reload keeps
 * the session. "Remember me" decides localStorage vs sessionStorage.
 */
const KEY = 'smartcare.token'
let accessToken = null
let onUnauthorized = null

function readStored() {
  try {
    return window.localStorage.getItem(KEY) || window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function loadToken() {
  accessToken = readStored()
  return accessToken
}

export function setToken(token, { remember = true } = {}) {
  accessToken = token || null
  try {
    window.localStorage.removeItem(KEY)
    window.sessionStorage.removeItem(KEY)
    if (token) (remember ? window.localStorage : window.sessionStorage).setItem(KEY, token)
  } catch {
    /* storage unavailable — the in-memory token still works for this tab */
  }
}

export function getToken() {
  return accessToken
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

/* Normalise every failure into { status, code, message, details, requestId }.
 * The backend always answers with {"error": {code, message, details?}, "request_id"}.
 * It never returns stack traces, and none are ever surfaced here. */
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status ?? 0
    const body = error.response?.data
    const err = {
      status,
      code: body?.error?.code || (status === 0 ? 'network_error' : 'http_error'),
      message: body?.error?.message || fallbackMessage(status),
      details: body?.error?.details ?? null,
      requestId: body?.request_id ?? null,
      retryAfter: error.response?.headers?.['retry-after'] ?? null,
    }
    if (status === 401) {
      const path = error.config?.url || ''
      // A failed sign-in is a credential error, not an expired session.
      if (!path.startsWith('/auth/login') && !path.startsWith('/auth/token')) {
        setToken(null)
        onUnauthorized?.(err)
      }
    }
    return Promise.reject(err)
  },
)

function fallbackMessage(status) {
  switch (status) {
    case 0:
      return 'Cannot reach the Nivara server. Check your connection and try again.'
    case 401:
      return 'Your session has ended. Sign in again to continue.'
    case 403:
      return 'You do not have permission to do this.'
    case 404:
      return 'We could not find what you were looking for.'
    case 409:
      return 'That action conflicts with the current state. Refresh and try again.'
    case 422:
      return 'Some of the information provided is not valid.'
    case 429:
      return 'Too many attempts. Wait a moment and try again.'
    default:
      return 'Something went wrong on our side. Try again in a moment.'
  }
}

/** Drop empty values so we never send query params the backend would reject. */
export function clean(params = {}) {
  const out = {}
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    out[k] = v
  }
  return out
}

export const healthUrl = `${BASE}/health`
