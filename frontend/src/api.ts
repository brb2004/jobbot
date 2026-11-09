// Typed client for the FastAPI backend. The token lives in memory only (not localStorage),
// so injected scripts can't read it from storage. Next step: httpOnly cookie.

export interface Preferences {
  include_titles: string[]
  exclude_titles: string[]
  locations: string[]
  remote_regions: string[]
  years_experience: number | null
  extra_skills: string[]
}

export interface MatchDetail {
  met: string[]
  partial: string[]
  missing: string[]
  soft: string[]
  years_asked?: number | null
  over_years?: boolean
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

export interface ResumeInfo {
  id: string
  filename: string | null
}

interface TokenOut {
  access_token: string
  token_type: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Fetch = (input: string, init?: RequestInit) => Promise<Response>

export function createApi(fetchFn: Fetch = (input, init) => fetch(input, init), base = '/api') {
  let token: string | null = null
  const unauthorized = new Set<() => void>()

  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const res = await fetchFn(`${base}${path}`, { ...init, headers })
    if (res.status === 401 && token) {      // session expired: forget it and tell the app
      token = null
      unauthorized.forEach((fn) => fn())
    }
    if (!res.ok) {
      let message = res.statusText
      try {
        const body = await res.json()
        if (typeof body.detail === 'string') message = body.detail
        else if (Array.isArray(body.detail))                     // FastAPI 422: list of field errors
          message = body.detail.map((d: { loc?: string[]; msg: string }) =>
            `${d.loc?.at(-1) ?? 'input'}: ${d.msg}`).join('; ')
      } catch {
        // not JSON: keep statusText
      }
      throw new ApiError(res.status, message)
    }
    return (res.status === 204 ? undefined : await res.json()) as T
  }

  async function authenticate(path: string, email: string, password: string): Promise<void> {
    const t = await call<TokenOut>(path, { method: 'POST', body: JSON.stringify({ email, password }) })
    token = t.access_token
  }

  return {
    register: (email: string, password: string) => authenticate('/auth/register', email, password),
    login: (email: string, password: string) => authenticate('/auth/login', email, password),
    logout: () => { token = null },
    isLoggedIn: () => token !== null,
    onUnauthorized: (fn: () => void) => { unauthorized.add(fn); return () => { unauthorized.delete(fn) } },
    listResumes: () => call<ResumeInfo[]>('/resumes'),
    getPreferences: () => call<Preferences>('/me/preferences'),
    savePreferences: (p: Preferences) => call<Preferences>('/me/preferences', { method: 'PUT', body: JSON.stringify(p) }),
    uploadResume: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return call<unknown>('/resumes', { method: 'POST', body: form })   // no Content-Type: browser adds the boundary
    },
    matches: () => call<Match[]>('/dashboard'),
  }
}

export const api = createApi()
export type Api = ReturnType<typeof createApi>
