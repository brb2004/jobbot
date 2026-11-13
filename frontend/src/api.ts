
export interface Preferences {
  include_titles: string[]
  exclude_titles: string[]
  locations: string[]
  remote: boolean
  onsite: boolean
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

export interface Application {
  job_id: string
  title: string | null
  company: string | null
  location: string | null
  url: string | null
  closed: boolean
  applied_at: string
}

export interface Place {
  name: string
  label?: string
  kind?: 'metro' | 'country' | 'region' | null
  aliases: string[]
}

export interface ResumeOwn {
  include_titles: string[] | null
  exclude_titles: string[] | null
  years_experience: number | null
}

export interface ResumeInfo {
  id: string
  name?: string | null
  filename: string | null
  years_detected?: number | null
  own?: ResumeOwn
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const label = (field: string) => field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, ' ')

type Fetch = (input: string, init?: RequestInit) => Promise<Response>

export function createApi(fetchFn: Fetch = (input, init) => fetch(input, init), base = '/api') {
  let loggedIn = false
  const unauthorized = new Set<() => void>()

  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const res = await fetchFn(`${base}${path}`, { ...init, headers, credentials: 'same-origin' })
    if (res.status === 401 && loggedIn) {
      loggedIn = false
      unauthorized.forEach((fn) => fn())
    }
    if (!res.ok) {
      let message = res.statusText
      try {
        const body = await res.json()
        if (typeof body.detail === 'string') message = body.detail
        else if (Array.isArray(body.detail))
          message = body.detail.map((d: { loc?: string[]; msg: string }) =>
            String(d.loc?.at(-1) ?? 'input') === 'body'
              ? d.msg
              : `${label(String(d.loc?.at(-1) ?? 'input'))}: ${d.msg}`).join('; ')
      } catch {}
      throw new ApiError(res.status, message)
    }
    return (res.status === 204 ? undefined : await res.json()) as T
  }

  async function authenticate(path: string, email: string, password: string): Promise<void> {
    await call(path, { method: 'POST', body: JSON.stringify({ email, password }) })
    loggedIn = true
  }

  return {
    register: async (email: string, password: string) => {
      await call('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) })
    },
    login: (email: string, password: string) => authenticate('/auth/login', email, password),
    logout: async () => {
      loggedIn = false
      await call('/auth/logout', { method: 'POST' }).catch(() => {})
    },
    restore: async () => {
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
    uploadResume: (file: File, opts: { name?: string; replace?: string } = {}) => {
      const form = new FormData()
      form.append('file', file)
      if (opts.name) form.append('name', opts.name)
      const q = opts.replace ? `?replace=${encodeURIComponent(opts.replace)}` : ''
      return call<ResumeInfo>(`/resumes${q}`, { method: 'POST', body: form })
    },
    updateResume: (id: string, body: { name?: string; own?: ResumeOwn }) =>
      call<ResumeInfo>(`/resumes/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteResume: (id: string) => call<void>(`/resumes/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    listResumes: () => call<ResumeInfo[]>('/resumes'),
    listPlaces: () => call<Place[]>('/places'),
    listSkills: () => call<Place[]>('/skills'),
    me: () => call<{ id: string; email: string; email_verified_at: string | null }>('/auth/me'),
    unsubscribe: (token: string) => call<void>('/email/unsubscribe', { method: 'POST', body: JSON.stringify({ token }) }),
    resubscribe: (token: string) => call<void>('/email/resubscribe', { method: 'POST', body: JSON.stringify({ token }) }),
    verifyEmail: (token: string) => call<void>('/auth/verify', { method: 'POST', body: JSON.stringify({ token }) }),
    resendVerification: () => call<unknown>('/auth/verify/resend', { method: 'POST' }),
    forgotPassword: (email: string) => call<unknown>('/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
    resetPassword: (token: string, password: string) =>
      call<void>('/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) }),
    deleteAccount: async () => {
      await call('/me', { method: 'DELETE' })
      loggedIn = false
    },
    matches: (resumeId?: string) => call<Match[]>(`/dashboard${resumeId ? `?resume=${encodeURIComponent(resumeId)}` : ''}`),
    sendFeedback: (body: { kind: string; message: string }) =>
      call<{ ref: string; detail: string }>('/feedback', { method: 'POST', body: JSON.stringify(body) }),
    applications: () => call<Application[]>('/applications'),
    markApplied: (jobId: string) => call<void>(`/applications/${jobId}`, { method: 'PUT' }),
    dismiss: (jobId: string) => call<void>(`/applications/${jobId}?status=dismissed`, { method: 'PUT' }),
    unmarkApplied: (jobId: string) => call<void>(`/applications/${jobId}`, { method: 'DELETE' }),
  }
}

export const api = createApi()
export type Api = ReturnType<typeof createApi>
