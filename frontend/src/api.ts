// Typed client for the FastAPI backend. The session is an httpOnly cookie set by the server:
// page JavaScript never sees the token, so an injected script can't steal it.

export interface Preferences {
  include_titles: string[]
  exclude_titles: string[]
  locations: string[]
  remote_regions: string[]
  years_experience: number | null
  extra_skills: string[]
  include_presales: boolean
}

export interface MatchDetail {
  met: string[]
  partial: string[]
  missing: string[]
  soft: string[]
  years_asked?: number | null
  over_years?: boolean
  no_language?: boolean
  clearance?: boolean
}

export interface Match {
  job_id: string
  title: string
  score: number
  tier: string
  company: string | null
  location: string | null
  years_note: string | null
  url: string | null
  detail: MatchDetail | null
}

export interface Place {
  name: string
  aliases: string[]
}

export interface ResumeInfo {
  id: string
  filename: string | null
  years_detected?: number | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// 'include_titles' -> 'Include titles' for error messages
const label = (field: string) => field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, ' ')

type Fetch = (input: string, init?: RequestInit) => Promise<Response>

export function createApi(fetchFn: Fetch = (input, init) => fetch(input, init), base = '/api') {
  let loggedIn = false
  const unauthorized = new Set<() => void>()

  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const res = await fetchFn(`${base}${path}`, { ...init, headers, credentials: 'same-origin' })
    if (res.status === 401 && loggedIn) {       // session expired: tell the app
      loggedIn = false
      unauthorized.forEach((fn) => fn())
    }
    if (!res.ok) {
      let message = res.statusText
      try {
        const body = await res.json()
        if (typeof body.detail === 'string') message = body.detail
        else if (Array.isArray(body.detail))     // FastAPI 422: list of field errors
          message = body.detail.map((d: { loc?: string[]; msg: string }) =>
            String(d.loc?.at(-1) ?? 'input') === 'body'          // whole-form error: no field label
              ? d.msg
              : `${label(String(d.loc?.at(-1) ?? 'input'))}: ${d.msg}`).join('; ')
      } catch {
        // not JSON: keep statusText
      }
      throw new ApiError(res.status, message)
    }
    return (res.status === 204 ? undefined : await res.json()) as T
  }

  async function authenticate(path: string, email: string, password: string): Promise<void> {
    await call(path, { method: 'POST', body: JSON.stringify({ email, password }) })   // server sets the cookie
    loggedIn = true
  }

  return {
    register: (email: string, password: string) => authenticate('/auth/register', email, password),
    login: (email: string, password: string) => authenticate('/auth/login', email, password),
    logout: async () => {
      loggedIn = false
      await call('/auth/logout', { method: 'POST' }).catch(() => {})
    },
    restore: async () => {                       // on page load: is the cookie still valid?
      try {
        await call('/auth/me')
        loggedIn = true
      } catch {
        loggedIn = false
      }
      return loggedIn
    },
    isLoggedIn: () => loggedIn,
    onUnauthorized: (fn: () => void) => { unauthorized.add(fn); return () => { unauthorized.delete(fn) } },
    getPreferences: () => call<Preferences>('/me/preferences'),
    savePreferences: (p: Preferences) => call<Preferences>('/me/preferences', { method: 'PUT', body: JSON.stringify(p) }),
    uploadResume: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return call<unknown>('/resumes', { method: 'POST', body: form })   // no Content-Type: browser adds the boundary
    },
    listResumes: () => call<ResumeInfo[]>('/resumes'),
    listPlaces: () => call<Place[]>('/places'),
    listSkills: () => call<Place[]>('/skills'),   // same shape: name + aliases
    me: () => call<{ id: string; email: string; email_verified_at: string | null }>('/auth/me'),
    verifyEmail: (token: string) => call<void>('/auth/verify', { method: 'POST', body: JSON.stringify({ token }) }),
    resendVerification: () => call<unknown>('/auth/verify/resend', { method: 'POST' }),
    forgotPassword: (email: string) => call<unknown>('/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
    resetPassword: (token: string, password: string) =>
      call<void>('/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) }),
    deleteAccount: async () => {
      await call('/me', { method: 'DELETE' })
      loggedIn = false
    },
    matches: () => call<Match[]>('/dashboard'),
  }
}

export const api = createApi()
export type Api = ReturnType<typeof createApi>
