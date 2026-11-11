import { useEffect, useState } from 'react'
import { ApiError, type Api, type Application } from './api'

const company = (slug: string | null) => (slug ? slug.charAt(0).toUpperCase() + slug.slice(1) : null)
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

export function Applied({ api }: { api: Api }) {
  const [items, setItems] = useState<Application[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Could not reach the server')

  const load = () => api.applications().then(setItems).catch(fail)
  useEffect(() => { load() }, [api])                                 // eslint-disable-line react-hooks/exhaustive-deps

  async function moveBack(a: Application) {
    try {
      await api.unmarkApplied(a.job_id)
      await load()
    } catch (e) {
      fail(e)
    }
  }

  if (error) return <p role="alert" className="text-red-600">{error}</p>
  if (items === null) return <p className="text-slate-600">Loading…</p>
  if (!items.length) return <p className="text-slate-600">Nothing here yet. When you apply to a match, it moves here.</p>

  return (
    <div className="max-w-3xl space-y-3">
      <h2 className="text-xl font-semibold">Applied ({items.length})</h2>
      <ul className="space-y-3">
        {items.map((a) => (
          <li key={a.job_id} className="rounded-lg bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              {a.url ? <a href={a.url} target="_blank" rel="noreferrer" className="font-medium underline">{a.title}</a>
                     : <span className="font-medium">{a.title}</span>}
              {a.closed && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-700">Closed</span>}
            </div>
            <p className="text-sm text-slate-500">
              {[company(a.company), a.location, `Applied ${day(a.applied_at)}`].filter(Boolean).join(' · ')}
            </p>
            <button onClick={() => moveBack(a)} className="mt-2 text-sm text-slate-600 underline">Move back to matches</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
