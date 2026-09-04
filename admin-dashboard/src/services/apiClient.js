const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const TOKEN_KEY = 'safezone.admin.access_token'
const PROFILE_KEY = 'safezone.admin.profile'

export class ApiError extends Error {
  constructor(message, status, details = null) { super(message); this.name = 'ApiError'; this.status = status; this.details = details }
}
export const hasToken = () => Boolean(sessionStorage.getItem(TOKEN_KEY))
export const getStoredProfile = () => { try { return JSON.parse(sessionStorage.getItem(PROFILE_KEY)) } catch { return null } }
export const storeProfile = (profile) => sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
export const clearSession = () => { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(PROFILE_KEY) }

function errorMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (Array.isArray(payload?.detail)) return payload.detail.map((item) => item.msg).join('; ')
  return fallback
}
async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  let response
  try { response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers }) }
  catch { throw new ApiError('Cannot reach the SafeZone API. Confirm the backend is running.', 0) }
  const payload = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && token) window.dispatchEvent(new Event('safezone:auth-expired'))
    throw new ApiError(errorMessage(payload, `Request failed (${response.status})`), response.status, payload)
  }
  return payload
}
function query(params) {
  const values = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => { if (value !== '' && value !== null && value !== undefined) values.set(key, value) })
  return values.size ? `?${values}` : ''
}

export const api = {
  async login(email, password) {
    const body = new URLSearchParams({ username: email, password })
    const token = await request('/auth/login', { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
    sessionStorage.setItem(TOKEN_KEY, token.access_token)
    try {
      const profile = await request('/auth/me')
      if (profile.role !== 'ADMIN') throw new ApiError('This account is not an administrator.', 403)
      return profile
    } catch (error) { clearSession(); throw error }
  },
  me: () => request('/auth/me'),
  crimes: (filters = {}) => request(`/crimes${query(filters)}`),
  createCrime: (data) => request('/crimes', { method: 'POST', body: JSON.stringify(data) }),
  updateCrime: (id, data) => request(`/crimes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deactivateCrime: (id) => request(`/crimes/${id}`, { method: 'DELETE' }),
  importCrimes: (file) => { const body = new FormData(); body.append('file', file); return request('/crimes/import/csv', { method: 'POST', body }) },
  activePrps: () => request('/prp/active'),
  generatePrps: (data) => request('/prp/generate', { method: 'POST', body: JSON.stringify(data) }),
  approvePrps: (id) => request(`/prp/runs/${id}/approve`, { method: 'POST' }),
  activatePrps: (id) => request(`/prp/runs/${id}/activate`, { method: 'POST' }),
  assignments: (params = {}) => request(`/patrols/assignments${query(params)}`),
  automaticAssignments: (id) => request('/patrols/assignments/automatic', { method: 'POST', body: JSON.stringify({ optimization_run_id: id }) }),
  overrideAssignment: (id, data) => request(`/patrols/assignments/${id}/override`, { method: 'PATCH', body: JSON.stringify(data) }),
  cancelAssignment: (id) => request(`/patrols/assignments/${id}/cancel`, { method: 'POST' }),
}
export { API_BASE_URL }
