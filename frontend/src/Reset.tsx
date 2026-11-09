import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

export function Reset({ api, token, onDone }: { api: Api; token: string; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.resetPassword(token, password)
      setDone(true)
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
        <h1 className="text-2xl font-semibold">Set a new password</h1>
        {done ? (
          <>
            <p role="status" className="text-sm text-green-800">Password changed. You've been signed out everywhere else.</p>
            <button type="button" onClick={onDone}
                    className="w-full rounded-md bg-slate-900 py-2 font-medium text-white">Log in</button>
          </>
        ) : (
          <>
            <label htmlFor="new-password" className="block text-sm font-medium">New password</label>
            <input id="new-password" type="password" required minLength={8} autoComplete="new-password"
                   className={input} value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="text-xs text-slate-500">At least 8 characters.</p>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <button type="submit" disabled={busy}
                    className="w-full rounded-md bg-slate-900 py-2 font-medium text-white disabled:opacity-50">
              Set password
            </button>
          </>
        )}
      </form>
    </main>
  )
}
