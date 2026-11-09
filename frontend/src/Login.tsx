import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

type Mode = 'login' | 'register'

export function Login({ api, onDone }: { api: Api; onDone: () => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isLogin = mode === 'login'

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await (isLogin ? api.login : api.register)(email, password)
      onDone()
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
          <h1 className="text-2xl font-semibold">JobBot</h1>
          <p className="text-sm text-slate-600">
            {isLogin ? 'Log in to see your matches.' : 'Create an account to get weekly matches.'}
          </p>
        </div>

        <label htmlFor="email" className="block text-sm font-medium">Email</label>
        <input id="email" type="email" required autoComplete="email" className={input}
               value={email} onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password" className="block text-sm font-medium">Password</label>
        <input id="password" type="password" required className={input}
               autoComplete={isLogin ? 'current-password' : 'new-password'}
               value={password} onChange={(e) => setPassword(e.target.value)} />
        {!isLogin && <p className="text-xs text-slate-500">At least 8 characters.</p>}

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <button type="submit" disabled={busy}
                className="w-full rounded-md bg-slate-900 py-2 font-medium text-white disabled:opacity-50">
          {isLogin ? 'Log in' : 'Sign up'}
        </button>
        <button type="button" onClick={() => { setMode(isLogin ? 'register' : 'login'); setError(null) }}
                className="w-full text-sm text-slate-600 underline">
          {isLogin ? 'Create an account' : 'I already have an account'}
        </button>
      </form>
    </main>
  )
}
