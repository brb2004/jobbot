import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

type Mode = 'login' | 'register' | 'forgot'

export function Login({ api, onDone }: { api: Api; onDone: () => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const isLogin = mode === 'login'
  const forgot = mode === 'forgot'
  const switchTo = (m: Mode) => { setMode(m); setError(null); setSent(false) }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (forgot) {
        await api.forgotPassword(email)
        setSent(true)
      } else {
        await (isLogin ? api.login : api.register)(email, password)
        onDone()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server')
    } finally {
      setBusy(false)
    }
  }

  const subtitle = forgot ? "Enter your email and we'll send a link to set a new password."
    : isLogin ? 'Log in to see your matches.' : 'Create an account to get weekly matches.'
  const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <div>
          <h1 className="text-2xl font-semibold">JobBot</h1>
          <p className="text-sm text-slate-600">{subtitle}</p>
        </div>

        <label htmlFor="email" className="block text-sm font-medium">Email</label>
        <input id="email" type="email" required autoComplete="email" className={input}
               value={email} onChange={(e) => setEmail(e.target.value)} />

        {!forgot && (
          <>
            <label htmlFor="password" className="block text-sm font-medium">Password</label>
            <input id="password" type="password" required className={input}
                   autoComplete={isLogin ? 'current-password' : 'new-password'}
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            {!isLogin && <p className="text-xs text-slate-500">At least 8 characters.</p>}
          </>
        )}

        {sent && (
          <p role="status" className="text-sm text-green-800">
            If an account exists for {email}, a reset link is on its way. It works for 30 minutes.
          </p>
        )}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <button type="submit" disabled={busy}
                className="w-full rounded-md bg-slate-900 py-2 font-medium text-white disabled:opacity-50">
          {forgot ? 'Send reset link' : isLogin ? 'Log in' : 'Sign up'}
        </button>
        {isLogin && (
          <button type="button" onClick={() => switchTo('forgot')} className="w-full text-sm text-slate-600 underline">
            Forgot password?
          </button>
        )}
        <button type="button" onClick={() => switchTo(isLogin ? 'register' : 'login')}
                className="w-full text-sm text-slate-600 underline">
          {forgot ? 'Back to log in' : isLogin ? 'Create an account' : 'I already have an account'}
        </button>
      </form>
    </main>
  )
}
