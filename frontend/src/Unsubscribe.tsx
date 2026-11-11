import { useState } from 'react'
import { ApiError, type Api } from './api'

// A click, not page load: link scanners open emailed links, and they mustn't unsubscribe anyone.
export function Unsubscribe({ api, token }: { api: Api; token: string }) {
  const [state, setState] = useState<'ask' | 'out' | 'in'>('ask')
  const [error, setError] = useState<string | null>(null)

  async function run(fn: (t: string) => Promise<void>, next: 'out' | 'in') {
    setError(null)
    try {
      await fn(token)
      setState(next)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the server')
    }
  }

  const button = 'w-full rounded-md bg-slate-900 py-2 font-medium text-white'
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Weekly email</h1>
        {state === 'ask' && <>
          <p className="text-sm text-slate-600">Stop getting your top job matches by email? Your account and matches stay.</p>
          <button type="button" className={button} onClick={() => run(api.unsubscribe, 'out')}>Unsubscribe</button>
        </>}
        {state === 'out' && <>
          <p role="status" className="text-sm text-green-800">Done. You won't get the weekly email anymore.</p>
          <button type="button" className="w-full text-sm text-slate-600 underline"
                  onClick={() => run(api.resubscribe, 'in')}>Changed your mind? Resubscribe</button>
        </>}
        {state === 'in' && <p role="status" className="text-sm text-green-800">You're subscribed again.</p>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <a href="/" className="block text-center text-sm text-slate-600 underline">Go to JobMatch</a>
      </div>
    </main>
  )
}
