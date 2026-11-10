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

const company = (slug: string | null) => (slug ? slug.charAt(0).toUpperCase() + slug.slice(1) : null)

export function Matches({ api, onUpload, onPreferences }:
  { api: Api; onUpload?: () => void; onPreferences?: () => void }) {
  const [matches, setMatches] = useState<Match[] | null>(null)
  const [hasResume, setHasResume] = useState<boolean | null>(null)   // null = still checking
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.matches()
      .then(setMatches)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not reach the server'))
    Promise.resolve().then(() => api.listResumes())
      .then((rs) => setHasResume(rs.length > 0))
      .catch(() => setHasResume(false))
  }, [api])

  if (error) return <p role="alert" className="text-red-600">{error}</p>
  if (matches === null) return <p className="text-slate-600">Loading…</p>
  if (!matches.length && hasResume === null) return <p className="text-slate-600">Loading…</p>
  if (!matches.length && hasResume)            // resume is in, so the filters are what's empty
    return (
      <p className="text-slate-600">
        No jobs match your preferences right now.{' '}
        <button onClick={onPreferences} className="underline">Loosen your preferences</button>{' '}
        (fewer excluded titles, more locations) or check back after the next crawl.
      </p>
    )
  if (!matches.length)
    return (
      <p className="text-slate-600">
        No matches yet.{' '}
        <button onClick={onUpload} className="underline">Upload your resume</button> to get your top 20.
      </p>
    )

  return (
    <ol className="max-w-3xl space-y-3">
      {matches.map((m, i) => (
        <li key={m.job_id} className="rounded-lg bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="min-w-0">
              <span className="mr-1 text-sm text-slate-400">#{i + 1}</span>
              {m.url
                ? <a href={m.url} target="_blank" rel="noreferrer" className="font-medium underline">{m.title}</a>
                : <span className="font-medium">{m.title}</span>}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${BADGE[m.tier] ?? BADGE.Stretch}`}>{m.tier}</span>
            {m.years_note && (
              <span className={`text-xs ${m.detail?.over_years ? 'text-amber-700' : 'text-slate-600'}`}>{m.years_note}</span>
            )}
          </div>
          {(m.company || m.location) && (
            <p className="text-sm text-slate-500">{[company(m.company), m.location].filter(Boolean).join(' · ')}</p>
          )}
          <Skills label="You have" items={m.detail?.met ?? []} />
          <Skills label="Missing" items={m.detail?.missing ?? []} />
        </li>
      ))}
    </ol>
  )
}
