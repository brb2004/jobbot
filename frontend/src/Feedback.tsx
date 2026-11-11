import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

const KINDS = [
  ['bug', 'Something is broken'],
  ['feedback', 'General feedback'],
  ['idea', 'Feature idea'],
] as const

export function Feedback({ api }: { api: Api }) {
  const [kind, setKind] = useState<string>('bug')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [ref, setRef] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setRef((await api.sendFeedback({ kind, message: text.trim() })).ref)
      setText('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server')
    } finally {
      setBusy(false)
    }
  }

  if (ref)
    return (
      <div className="max-w-xl space-y-2">
        <p role="status" className="rounded-md bg-green-50 px-3 py-2 text-green-800">
          Thanks! Your report is #{ref}. We've emailed you a confirmation.
        </p>
        <button onClick={() => setRef(null)} className="text-sm underline">Send another</button>
      </div>
    )

  return (
    <form onSubmit={submit} className="max-w-xl space-y-3">
      <h2 className="text-xl font-semibold">Report a bug or send feedback</h2>
      <fieldset className="flex flex-wrap gap-3">
        <legend className="sr-only">Type</legend>
        {KINDS.map(([value, label]) => (
          <label key={value} className="flex items-center gap-1 text-sm">
            <input type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)} />
            {label}
          </label>
        ))}
      </fieldset>
      <label className="block text-sm">
        <span className="font-medium">{kind === 'bug' ? 'What happened, and what did you expect?' : 'Your message'}</span>
        <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={5000} rows={6}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2" />
      </label>
      <p className="text-xs text-slate-500">{text.length}/5000</p>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button type="submit" disabled={busy || !text.trim()}
              className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-50">
        {busy ? 'Sending…' : 'Send'}
      </button>
    </form>
  )
}
