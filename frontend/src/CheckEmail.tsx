import { useEffect, useState } from 'react'
import type { Api } from './api'

const POLL_MS = 5000

export function CheckEmail({ api, email, onConfirmed, onLogout }:
  { api: Api; email: string; onConfirmed: () => Promise<void>; onLogout: () => void }) {
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Moves on by itself once the link is clicked: instantly when the link opens in this browser
  // (the confirmation page broadcasts), within POLL_MS from another device, or on returning to this tab.
  useEffect(() => {
    const check = () => { if (!document.hidden) onConfirmed().catch(() => {}) }
    const timer = setInterval(check, POLL_MS)
    window.addEventListener('focus', check)
    const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('jobbot') : null
    if (channel) channel.onmessage = (e) => { if (e.data === 'email-confirmed') onConfirmed().catch(() => {}) }
    return () => { clearInterval(timer); window.removeEventListener('focus', check); channel?.close() }
  }, [onConfirmed])

  async function resend() {
    setError(null)
    try {
      await api.resendVerification()
      setSent(true)
    } catch {
      setError('Could not reach the server')
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Check your email</h1>
        <p className="text-sm text-slate-600">
          We sent a confirmation link to <span className="font-medium text-slate-900">{email}</span>.
          Click it to finish setting up your account. It works for 7 days. If it's not there, check spam.
        </p>
        <p className="text-sm text-slate-500">This page continues on its own once you've clicked the link.</p>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {sent
          ? <p role="status" className="text-center text-sm text-green-800">A new link is on its way.</p>
          : <button type="button" onClick={resend} className="w-full text-sm text-slate-600 underline">Send a new link</button>}
        <button type="button" onClick={onLogout} className="w-full text-sm text-slate-600 underline">Log out</button>
      </div>
    </main>
  )
}
