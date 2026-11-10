import { useEffect, useState } from 'react'
import { ApiError, type Api } from './api'

export function Verify({ api, token, onDone }: { api: Api; token: string; onDone: () => void }) {
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.verifyEmail(token)
      .then(() => {
        setDone(true)
        try {                                   // tell the waiting tab, if it's in this browser
          const c = new BroadcastChannel('jobbot'); c.postMessage('email-confirmed'); c.close()
        } catch { /* no BroadcastChannel: the waiting tab polls instead */ }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not reach the server'))
  }, [api, token])

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Confirm your email</h1>
        {!done && !error && <p className="text-sm text-slate-600">Confirming…</p>}
        {done && <p role="status" className="text-sm text-green-800">Email confirmed. You'll get your top matches every week.</p>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {(done || error) && (
          <button type="button" onClick={onDone}
                  className="w-full rounded-md bg-slate-900 py-2 font-medium text-white">Continue</button>
        )}
      </div>
    </main>
  )
}
