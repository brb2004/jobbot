import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, type Api, type Preferences as Prefs } from './api'

const LISTS = [
  ['include_titles', 'Job titles to include', 'Only titles containing one of these. Empty = all titles.'],
  ['exclude_titles', 'Job titles to exclude', 'Hide titles containing any of these, e.g. senior, staff.'],
  ['locations', 'Locations', 'e.g. remote, dallas. Empty = anywhere.'],
  ['remote_regions', 'Remote regions', 'Remote jobs must also name one of these, e.g. us, usa.'],
  ['extra_skills', 'Extra skills', "Skills you have that aren't on your resume."],
] as const
type ListKey = (typeof LISTS)[number][0]

const toList = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)
const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'

export function Preferences({ api, onSaved }: { api: Api; onSaved: () => void }) {
  const [text, setText] = useState<Record<ListKey, string> | null>(null)
  const [years, setYears] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Could not reach the server')

  useEffect(() => {
    api.getPreferences()
      .then((p) => {
        setText(Object.fromEntries(LISTS.map(([k]) => [k, p[k].join(', ')])) as Record<ListKey, string>)
        setYears(p.years_experience?.toString() ?? '')
      })
      .catch(fail)
  }, [api])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text) return
    setBusy(true)
    setError(null)
    try {
      const lists = Object.fromEntries(LISTS.map(([k]) => [k, toList(text[k])])) as Pick<Prefs, ListKey>
      await api.savePreferences({ ...lists, years_experience: years === '' ? null : Number(years) })
      onSaved()
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  if (error && !text) return <p role="alert" className="text-red-600">{error}</p>
  if (!text) return <p className="text-slate-600">Loading…</p>

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4">
      <h2 className="text-xl font-semibold">Preferences</h2>
      <p className="text-sm text-slate-600">Separate entries with commas. Saving updates your matches right away.</p>
      {LISTS.map(([key, label, hint]) => (
        <div key={key}>
          <label htmlFor={key} className="block text-sm font-medium">{label}</label>
          <input id={key} className={input} value={text[key]}
                 onChange={(e) => setText({ ...text, [key]: e.target.value })} />
          <p className="mt-1 text-xs text-slate-500">{hint}</p>
        </div>
      ))}
      <div>
        <label htmlFor="years" className="block text-sm font-medium">Years of experience</label>
        <input id="years" type="number" min={0} max={60} className={`${input} max-w-32`}
               value={years} onChange={(e) => setYears(e.target.value)} />
        <p className="mt-1 text-xs text-slate-500">Jobs asking for more than this + 1 rank lower. Blank = don't check.</p>
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button type="submit" disabled={busy}
              className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50">
        Save
      </button>
    </form>
  )
}
