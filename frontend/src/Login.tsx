import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

export function Login({ api, onDone, onSignup }: { api: Api; onDone: () => void; onSignup?: () => void }) {
  const [forgot, setForgot] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const switchTo = (f: boolean) => { setForgot(f); setError(null); setSent(false) }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (forgot) {
        await api.forgotPassword(email)
        setSent(true)
      } else {
        await api.login(email, password)
        onDone()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server')
    } finally {
      setBusy(false)
    }
  }

  const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <div>
          <h1 className="text-2xl font-semibold">SkillFit</h1>
          <p className="text-sm text-slate-600">
            {forgot ? "Enter your email and we'll send a link to set a new password." : 'Log in to see your matches.'}
          </p>
        </div>

        <label htmlFor="email" className="block text-sm font-medium">Email</label>
        <input id="email" type="email" required autoComplete="email" className={input}
               value={email} onChange={(e) => setEmail(e.target.value)} />

        {!forgot && (
          <>
            <label htmlFor="password" className="block text-sm font-medium">Password</label>
            <input id="password" type="password" required autoComplete="current-password" className={input}
                   value={password} onChange={(e) => setPassword(e.target.value)} />
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
          {forgot ? 'Send reset link' : 'Log in'}
        </button>
        {!forgot && (
          <button type="button" onClick={() => switchTo(true)} className="w-full text-sm text-slate-600 underline">
            Forgot password?
          </button>
        )}
        <button type="button" onClick={() => (forgot ? switchTo(false) : onSignup?.())}
                className="w-full text-sm text-slate-600 underline">
          {forgot ? 'Back to log in' : 'Create an account'}
        </button>
        <a href="/privacy" className="block text-center text-xs text-slate-500 underline">Privacy</a>
      </form>
    </main>
  )
}
