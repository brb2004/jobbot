import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, type Api, type Preferences as Prefs } from './api'

const LISTS = [
  ['include_titles', 'Job titles to include', 'Only titles containing one of these. Leave empty to use the defaults (engineer, developer, SRE, DevOps, architect, scientist). Anything you enter replaces them.'],
  ['exclude_titles', 'Job titles to exclude', 'Hide titles containing any of these, e.g. senior, staff. Excluded titles always win.'],
  ['locations', 'Locations', 'e.g. remote, dallas, united states. Cities, metros and countries all work: dallas also covers Plano, Richardson and Frisco. Empty = anywhere.'],
  ['remote_regions', 'Remote regions', 'Only applies to remote jobs (add remote to Locations to see them). e.g. united states, canada, europe. us, usa and united states mean the same.'],
  ['extra_skills', 'Extra skills', "Skills you have that aren't on your resume."],
] as const
type ListKey = (typeof LISTS)[number][0]
type Draft = { text: Record<ListKey, string>; years: string; presales: boolean }

// Mirrors PRESALES_TITLES on the server: warn when the exclude list cancels the sales checkbox.
const SALES = ['customer engineer', 'solutions architect', 'solution architect', 'solutions engineer',
  'solution engineer', 'account executive', 'customer success']
const salesWord = (t: string) => /(^|[\s-])(pre-?)?sales([\s-]|$)/i.test(t) || SALES.includes(t.toLowerCase())

const toList = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean)
const YEARS_OK = /^\d{1,2}$/
const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'

export function Preferences({ api, onSaved, onDeleted, onDirty }:
  { api: Api; onSaved: () => void; onDeleted?: () => void; onDirty?: (dirty: boolean) => void }) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saved, setSaved] = useState('')                       // the last loaded or saved draft, as JSON
  const [detected, setDetected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Could not reach the server')

  useEffect(() => {
    api.getPreferences()
      .then((p) => {
        const d: Draft = {
          text: Object.fromEntries(LISTS.map(([k]) => [k, p[k].join(', ')])) as Record<ListKey, string>,
          years: p.years_experience?.toString() ?? '',
          presales: p.include_presales,
        }
        setDraft(d)
        setSaved(JSON.stringify(d))
      })
      .catch(fail)
    Promise.resolve().then(() => api.listResumes())
      .then((rs) => setDetected(rs[0]?.years_detected ?? null))
      .catch(() => {})
  }, [api])

  const dirty = draft !== null && JSON.stringify(draft) !== saved
  useEffect(() => { onDirty?.(dirty) }, [dirty, onDirty])
  useEffect(() => () => onDirty?.(false), [onDirty])           // leaving the page clears the flag
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }   // reload / close tab
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function deleteAccount() {
    try {
      await api.deleteAccount()
      onDeleted?.()
    } catch (err) {
      fail(err)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!draft) return
    const years = draft.years.trim()
    if (years !== '' && !YEARS_OK.test(years)) {
      setError('Years of experience: enter a whole number from 0 to 60, or leave it blank.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const lists = Object.fromEntries(LISTS.map(([k]) => [k, toList(draft.text[k])])) as Pick<Prefs, ListKey>
      await api.savePreferences({ ...lists, years_experience: years === '' ? null : Number(years), include_presales: draft.presales })
      setSaved(JSON.stringify(draft))
      onDirty?.(false)
      onSaved()
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  if (error && !draft) return <p role="alert" className="text-red-600">{error}</p>
  if (!draft) return <p className="text-slate-600">Loading…</p>

  const { text, years, presales } = draft
  const setText = (k: ListKey, v: string) => setDraft({ ...draft, text: { ...text, [k]: v } })
  const clash = presales ? toList(text.exclude_titles).filter(salesWord) : []

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4">
      <h2 className="text-xl font-semibold">Preferences</h2>
      <p className="text-sm text-slate-600">Separate entries with commas or new lines. Saving updates your matches right away.</p>
      {LISTS.map(([key, label, hint]) => (
        <div key={key}>
          <label htmlFor={key} className="block text-sm font-medium">{label}</label>
          <textarea id={key} rows={2} aria-describedby={`${key}-hint`} className={`${input} resize-y`}
                    value={text[key]} onChange={(e) => setText(key, e.target.value)} />
          <p id={`${key}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>
          {key === 'exclude_titles' && (text.include_titles.trim() !== '' || text.exclude_titles.trim() !== '') && (
            <button type="button" className="mt-1 text-xs text-slate-600 underline"
                    onClick={() => setDraft({ ...draft, text: { ...text, include_titles: '', exclude_titles: '' } })}>
              Reset job titles to defaults
            </button>
          )}
        </div>
      ))}
      <div>
        <label htmlFor="years" className="block text-sm font-medium">Years of experience</label>
        <input id="years" type="text" inputMode="numeric" maxLength={2} aria-describedby="years-hint"
               className={`${input} max-w-32`} value={years} onChange={(e) => setDraft({ ...draft, years: e.target.value })} />
        <p id="years-hint" className="mt-1 text-xs text-slate-500">
          Jobs asking for 2 or more years beyond this rank lower; 4 or more beyond aren't shown.
          {detected === null && ' Leave blank to use the years detected from your resume.'}
        </p>
        {detected !== null && years === '' && (
          <p className="mt-1 text-xs text-slate-700">Using {detected} years of relevant experience from your resume.</p>
        )}
        {detected !== null && years !== '' && Number(years) !== detected && (
          <p className="mt-1 text-xs text-amber-700">
            Your resume shows {detected} years of relevant experience. Your value ({years}) is used instead.{' '}
            <button type="button" className="underline" onClick={() => setDraft({ ...draft, years: '' })}>Use resume ({detected})</button>
          </p>
        )}
      </div>
      <div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={presales} aria-describedby="presales-hint"
                 onChange={(e) => setDraft({ ...draft, presales: e.target.checked })} />
          <span>Include sales &amp; pre-sales roles</span>
        </label>
        <p id="presales-hint" className="ml-6 text-xs text-slate-500">
          Sales Engineer, Customer Engineer, Customer Success, Solutions Architect. Hidden by default.
        </p>
        {clash.length > 0 && (
          <p className="ml-6 mt-1 text-xs text-amber-800">
            Your excluded titles still hide some of these: {clash.join(', ')}. Excluded titles always win, so remove them to see these roles.
          </p>
        )}
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="sticky bottom-0 flex items-center gap-3 border-t border-slate-200 bg-slate-50 py-3">
        <button type="submit" disabled={busy}
                className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50">
          Save
        </button>
        {dirty && (
          <>
            <span className="text-sm text-amber-800">Unsaved changes</span>
            <button type="button" onClick={() => setDraft(JSON.parse(saved))} className="text-sm text-slate-600 underline">Discard</button>
          </>
        )}
      </div>
      <section aria-labelledby="delete-heading" className="border-t pt-4">
        <h3 id="delete-heading" className="text-sm font-medium text-red-700">Delete account</h3>
        <p className="text-xs text-slate-500">Removes your account, resume and matches. This can't be undone.</p>
        {!confirming ? (
          <button type="button" onClick={() => setConfirming(true)} className="mt-2 text-sm text-red-700 underline">
            Delete my account
          </button>
        ) : (
          <div className="mt-2 flex gap-3">
            <button type="button" onClick={deleteAccount} className="rounded-md bg-red-700 px-3 py-1 text-sm text-white">
              Yes, delete everything
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="text-sm underline">Cancel</button>
          </div>
        )}
      </section>
    </form>
  )
}
