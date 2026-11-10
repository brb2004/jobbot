import { useEffect, useState } from 'react'
import type { Api } from './api'

export function VerifyBanner({ api }: { api: Api }) {
  const [unconfirmed, setUnconfirmed] = useState(false)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    Promise.resolve().then(() => api.me())
      .then((u) => setUnconfirmed(!u.email_verified_at))
      .catch(() => {})
  }, [api])

  if (!unconfirmed) return null
  return (
    <p role="status" className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
      Confirm your email to get your weekly matches.{' '}
      {sent ? 'A new link is on its way.' : (
        <>Check your inbox, or{' '}
          <button type="button" className="underline"
                  onClick={() => api.resendVerification().then(() => setSent(true)).catch(() => {})}>
            send a new link
          </button>.
        </>
      )}
    </p>
  )
}
