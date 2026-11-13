import { useEffect, useState } from 'react'
import { ApiError, type Api, type Match, type ResumeInfo } from './api'

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

// real names come as-is ("eBay", "Defense Unicorns"); a bare slug gets a capital letter
const company = (c: string | null) => (c ? (/[A-Z\s]/.test(c) ? c : c.charAt(0).toUpperCase() + c.slice(1)) : null)
// "2 of 3 skills": how much of what the posting asks for you already have
const skillCount = (d: Match['detail']) => {
  const total = (d?.met.length ?? 0) + (d?.partial?.length ?? 0) + (d?.missing.length ?? 0)
  return total ? `${d?.met.length ?? 0} of ${total} skills` : null
}
const message = (e: unknown) => (e instanceof ApiError ? e.message : 'Could not reach the server')

export function Matches({ api, onUpload, onPreferences }:
  { api: Api; onUpload?: () => void; onPreferences?: () => void }) {
  const [matches, setMatches] = useState<Match[] | null>(null)
  const [resumes, setResumes] = useState<ResumeInfo[] | null>(null)  // null = still checking
  const [pick, setPick] = useState<string | undefined>(undefined)     // which resume's matches; undefined = first
  const hasResume = resumes === null ? null : resumes.length > 0
  const [error, setError] = useState<string | null>(null)
  const [asking, setAsking] = useState<string | null>(null)          // opened this posting: "did you apply?"
  const [moved, setMoved] = useState<{ m: Match; hidden: boolean } | null>(null)  // last job moved or hidden (for Undo)
  const [notice, setNotice] = useState<string | null>(null)

  const load = (id = pick) => api.matches(id).then(setMatches).catch((e) => setError(message(e)))
  useEffect(() => {
    load()
    Promise.resolve().then(() => api.listResumes())
      .then(setResumes)
      .catch(() => setResumes([]))
  }, [api])                                                          // eslint-disable-line react-hooks/exhaustive-deps
  const choose = (id: string) => { setPick(id); setMoved(null); setAsking(null); load(id) }

  async function applied(m: Match) {
    setAsking(null)
    setNotice(null)
    try {
      await api.markApplied(m.job_id)
      setMoved({ m, hidden: false })
      await load()                                                   // the next match moves up
    } catch (e) {
      setNotice(message(e))
    }
  }

  async function hide(m: Match) {
    setAsking(null)
    setNotice(null)
    try {
      await api.dismiss(m.job_id)
      setMoved({ m, hidden: true })
      await load()                                                   // the next match moves up
    } catch (e) {
      setNotice(message(e))
    }
  }

  async function undo() {
    if (!moved) return
    try {
      await api.unmarkApplied(moved.m.job_id)
      setMoved(null)
      await load()
    } catch (e) {
      setNotice(message(e))
    }
  }

  if (error) return <p role="alert" className="text-red-600">{error}</p>
  if (matches === null) return <p className="text-slate-600">Loading…</p>
  if (!matches.length && hasResume === null) return <p className="text-slate-600">Loading…</p>

  const current = pick ?? resumes?.[0]?.id
  const tabs = resumes && resumes.length > 1 && (
    <div role="tablist" aria-label="Resume" className="flex flex-wrap gap-2">
      {resumes.map((r) => (
        <button key={r.id} role="tab" aria-selected={r.id === current} onClick={() => choose(r.id)}
                className={`rounded-full px-3 py-1 text-sm ${r.id === current ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 shadow-sm'}`}>
          {r.name ?? r.filename ?? 'Resume'}
        </button>
      ))}
    </div>
  )
  if (!matches.length && hasResume)            // resume is in, so the filters are what's empty
    return (
      <div className="max-w-3xl space-y-3">
        {tabs}
        <p className="text-slate-600">
          No jobs match your preferences right now.{' '}
          <button onClick={onPreferences} className="underline">Loosen your preferences</button>{' '}
          (fewer excluded titles, more locations) or check back after the next crawl.
        </p>
      </div>
    )
  if (!matches.length)
    return (
      <p className="text-slate-600">
        No matches yet.{' '}
        <button onClick={onUpload} className="underline">Upload your resume</button> to get your top 20.
      </p>
    )

  return (
    <div className="max-w-3xl space-y-3">
      {tabs}
      {moved && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
          {moved.hidden ? <>Hid “{moved.m.title}”.</> : <>Moved “{moved.m.title}” to Applied.</>}
          <button onClick={undo} className="underline">Undo</button>
        </p>
      )}
      {notice && <p role="alert" className="text-sm text-red-600">{notice}</p>}
      <ol className="space-y-3">
        {matches.map((m, i) => (
          <li key={m.job_id} className="rounded-lg bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0">
                <span className="mr-1 text-sm text-slate-400">#{i + 1}</span>
                {m.url
                  ? <a href={m.url} target="_blank" rel="noreferrer" onClick={() => setAsking(m.job_id)}
                       className="font-medium underline">{m.title}</a>
                  : <span className="font-medium">{m.title}</span>}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${BADGE[m.tier] ?? BADGE.Stretch}`}>{m.tier}</span>
              {skillCount(m.detail) && <span className="text-xs text-slate-600">{skillCount(m.detail)}</span>}
              {m.years_note && (
                <span className={`text-xs ${m.detail?.over_years ? 'text-amber-700' : 'text-slate-600'}`}>{m.years_note}</span>
              )}
              {m.detail?.clearance && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">May require clearance or U.S. citizenship</span>
              )}
            </div>
            {(m.company || m.location) && (
              <p className="text-sm text-slate-500">{[company(m.company), m.location].filter(Boolean).join(' · ')}</p>
            )}
            <Skills label="You have" items={m.detail?.met ?? []} />
            <Skills label="Missing" items={m.detail?.missing ?? []} />
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
              {asking === m.job_id ? (
                <>
                  <span>Did you apply?</span>
                  <button onClick={() => applied(m)} className="rounded-md bg-slate-900 px-3 py-1 text-white">Yes, move to Applied</button>
                  <button onClick={() => setAsking(null)} className="underline">Not yet</button>
                </>
              ) : m.url ? (
                <a href={m.url} target="_blank" rel="noreferrer" onClick={() => setAsking(m.job_id)}
                   className="rounded-md border border-slate-300 px-3 py-1">Apply ↗</a>
              ) : (
                <button onClick={() => applied(m)} className="rounded-md border border-slate-300 px-3 py-1">Mark applied</button>
              )}
              {asking !== m.job_id && (
                <button onClick={() => hide(m)} className="text-slate-500 underline">Not interested</button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
