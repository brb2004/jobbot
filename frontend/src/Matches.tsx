import { useEffect, useState } from 'react'
import { ApiError, type Api, type Match } from './api'

const BADGE: Record<string, string> = {
  'Strong match': 'bg-green-100 text-green-800',
  'Worth applying': 'bg-amber-100 text-amber-800',
  Stretch: 'bg-slate-200 text-slate-700',
}

function Skills({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null
  return (
    <p className="text-sm">
      <span className="font-medium">{label}: </span>
      <span>{items.join(', ')}</span>
    </p>
  )
}

export function Matches({ api }: { api: Api }) {
  const [matches, setMatches] = useState<Match[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.matches()
      .then(setMatches)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not reach the server'))
  }, [api])

  if (error) return <p role="alert" className="text-red-600">{error}</p>
  if (matches === null) return <p className="text-slate-600">Loading…</p>
  if (!matches.length) return <p className="text-slate-600">No matches yet. Upload your resume to get your top 20.</p>

  return (
    <ol className="max-w-3xl space-y-3">
      {matches.map((m) => (
        <li key={m.job_id} className="rounded-lg bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            {m.url
              ? <a href={m.url} target="_blank" rel="noreferrer" className="font-medium underline">{m.title}</a>
              : <span className="font-medium">{m.title}</span>}
            <span className={`rounded-full px-2 py-0.5 text-xs ${BADGE[m.tier] ?? BADGE.Stretch}`}>{m.tier}</span>
            {m.years_note && (
              <span className={`text-xs ${m.detail?.over_years ? 'text-amber-700' : 'text-slate-600'}`}>{m.years_note}</span>
            )}
          </div>
          <Skills label="You have" items={m.detail?.met ?? []} />
          <Skills label="Missing" items={m.detail?.missing ?? []} />
        </li>
      ))}
    </ol>
  )
}
