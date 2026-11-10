import { useState } from 'react'
import type { Api } from './api'

export function CheckEmail({ api, email, onConfirmed, onLogout }:
  { api: Api; email: string; onConfirmed: () => Promise<void>; onLogout: () => void }) {
  const [sent, setSent] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function resend() {
    setNote(null)
    try {
      await api.resendVerification()
      setSent(true)
    } catch {
      setNote('Could not reach the server')
    }
  }

  async function check() {
    setBusy(true)
    setNote(null)
    await onConfirmed()                     // if confirmed, the app moves on and this page goes away
    setBusy(false)
    setNote('Not confirmed yet. Click the link in the email first.')
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Check your email</h1>
        <p className="text-sm text-slate-600">
          We sent a confirmation link to <span className="font-medium text-slate-900">{email}</span>.
          Click it to finish setting up your account. It works for 7 days. If it's not there, check spam.
        </p>
        {note && <p role="alert" className="text-sm text-amber-800">{note}</p>}
        <button type="button" onClick={check} disabled={busy}
                className="w-full rounded-md bg-slate-900 py-2 font-medium text-white disabled:opacity-50">
          I've confirmed, continue
        </button>
        {sent
          ? <p role="status" className="text-center text-sm text-green-800">A new link is on its way.</p>
          : <button type="button" onClick={resend} className="w-full text-sm text-slate-600 underline">Send a new link</button>}
        <button type="button" onClick={onLogout} className="w-full text-sm text-slate-600 underline">Log out</button>
      </div>
    </main>
  )
}
