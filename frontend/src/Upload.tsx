import { useState, type FormEvent } from 'react'
import { ApiError, type Api } from './api'

export function Upload({ api, onDone }: { api: Api; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await api.uploadResume(file)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-md space-y-4">
      <h2 className="text-xl font-semibold">Your resume</h2>
      <p className="text-sm text-slate-600">Matches are built from the skills in your resume. Upload a new one any time.</p>
      <label htmlFor="resume" className="block text-sm font-medium">Resume (PDF or Word)</label>
      <input id="resume" type="file" accept=".pdf,.docx"
             onChange={(e) => setFile(e.target.files?.[0] ?? null)}
             className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white" />
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button type="submit" disabled={!file || busy}
              className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50">
        Upload
      </button>
    </form>
  )
}
