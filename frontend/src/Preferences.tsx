import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ApiError, type Api, type Place, type Preferences as Prefs } from './api'
import { ChipInput } from './ChipInput'
import { addAll, canonFrom, toList } from './lists'

type ListKey = 'include_titles' | 'exclude_titles' | 'locations' | 'extra_skills'
type Draft = { lists: Record<ListKey, string[]>; remote: boolean; onsite: boolean; years: string; presales: boolean }
const NO_PENDING: Record<ListKey, string> = { include_titles: '', exclude_titles: '', locations: '', extra_skills: '' }

const INCLUDE_TIPS = ['software engineer', 'backend', 'frontend', 'full stack', 'platform', 'infrastructure', 'sre',
  'devops', 'data engineer', 'machine learning', 'security', 'mobile', 'cloud'].map((name) => ({ name }))
const EXCLUDE_TIPS = ['senior', 'staff', 'principal', 'lead', 'manager', 'director', 'intern', 'contract', 'sr.',
  'head of'].map((name) => ({ name }))

const SALES = ['customer engineer', 'solutions architect', 'solution architect', 'solutions engineer',
  'solution engineer', 'account executive', 'customer success']
const salesWord = (t: string) => /(^|[\s-])(pre-?)?sales([\s-]|$)/i.test(t) || SALES.includes(t.toLowerCase())

const YEARS_OK = /^\d{1,2}$/
const includes = (label: string, aliases: string[]) => {
  const names = aliases.filter((a) => a.length > 3 && !a.includes('.') && !label.toLowerCase().includes(a))
    .map((a) => a.replace(/\b\w/g, (c) => c.toUpperCase())).slice(0, 3)
  return names.length ? `includes ${names.join(', ')}` : undefined
}
const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'

export function Preferences({ api, onSaved, onDeleted, onDirty }:
  { api: Api; onSaved: () => void; onDeleted?: () => void; onDirty?: (dirty: boolean) => void }) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saved, setSaved] = useState('')
  const [pending, setPending] = useState(NO_PENDING)
  const [places, setPlaces] = useState<Place[] | null>(null)
  const [skills, setSkills] = useState<Place[] | null>(null)
  const [detected, setDetected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Could not reach the server')

  useEffect(() => {
    api.getPreferences()
      .then((p) => {
        const d: Draft = {
          lists: { include_titles: p.include_titles, exclude_titles: p.exclude_titles, locations: p.locations,
                   extra_skills: p.extra_skills },
          remote: p.remote ?? true, onsite: p.onsite ?? true,
          years: p.years_experience?.toString() ?? '', presales: p.include_presales,
        }
        setDraft(d)
        setSaved(JSON.stringify(d))
      })
      .catch(fail)
    Promise.resolve().then(() => api.listResumes()).then((rs) => setDetected(rs[0]?.years_detected ?? null)).catch(() => {})
    Promise.resolve().then(() => api.listPlaces()).then(setPlaces).catch(() => {})
    Promise.resolve().then(() => api.listSkills()).then(setSkills).catch(() => {})
  }, [api])

  const placeOf = useMemo(() => canonFrom(places), [places])
  const skillOf = useMemo(() => canonFrom(skills), [skills])
  const labelOf = useMemo(() => new Map((places ?? []).map((p) => [p.name, p.label ?? p.name])), [places])
  const placeOptions = useMemo(() => (places ?? []).map((p) => (
    { ...p, detail: p.kind === 'metro' ? includes(p.label ?? p.name, p.aliases) : undefined })), [places])

  const dirty = draft !== null && (JSON.stringify(draft) !== saved || Object.values(pending).some((v) => v.trim() !== ''))
  useEffect(() => { onDirty?.(dirty) }, [dirty, onDirty])
  useEffect(() => () => onDirty?.(false), [onDirty])
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
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
    if (!draft.remote && !draft.onsite) {
      setError('Work setup: pick on-site, remote, or both.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const canonFor: Record<ListKey, (v: string) => string | undefined> = {
        include_titles: () => undefined, exclude_titles: () => undefined, locations: placeOf, extra_skills: skillOf,
      }
      const lists = Object.fromEntries((Object.keys(draft.lists) as ListKey[]).map((k) =>
        [k, addAll(draft.lists[k], (k === 'locations' ? [pending[k].trim()].filter(Boolean) : toList(pending[k]))
          .map((v) => canonFor[k](v) ?? v))])) as Record<ListKey, string[]>
      const final = { ...draft, lists }
      await api.savePreferences({ ...lists, remote: final.remote, onsite: final.onsite,
        years_experience: years === '' ? null : Number(years), include_presales: final.presales } satisfies Prefs)
      setDraft(final)
      setPending(NO_PENDING)
      setSaved(JSON.stringify(final))
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

  const { lists, remote, onsite, years, presales } = draft
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch })
  const setList = (k: ListKey, v: string[]) => set({ lists: { ...lists, [k]: v } })
  const typed = (k: ListKey) => ({ pending: pending[k], onPending: (v: string) => setPending({ ...pending, [k]: v }) })
  const clash = presales ? lists.exclude_titles.filter(salesWord) : []

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5">
      <h2 className="text-xl font-semibold">Preferences</h2>
      <p className="text-sm text-slate-600">
        Type an entry and press Enter (or type a comma) to add it. Saving updates your matches right away.
      </p>

      <ChipInput id="include_titles" label="Job titles to include" values={lists.include_titles}
                 onValues={(v) => setList('include_titles', v)} {...typed('include_titles')} options={INCLUDE_TIPS}
                 placeholder="e.g. backend, platform"
                 hint="Only titles containing one of these. Leave empty to use the defaults (engineer, developer, SRE, DevOps, architect, scientist). Anything you add replaces them." />
      <ChipInput id="exclude_titles" label="Job titles to exclude" values={lists.exclude_titles}
                 onValues={(v) => setList('exclude_titles', v)} {...typed('exclude_titles')} options={EXCLUDE_TIPS}
                 placeholder="e.g. senior, staff"
                 hint="Hide titles containing any of these. Excluded titles always win.">
        {(lists.include_titles.length > 0 || lists.exclude_titles.length > 0) && (
          <button type="button" className="mt-1 text-xs text-slate-600 underline"
                  onClick={() => {
                    set({ lists: { ...lists, include_titles: [], exclude_titles: [] } })
                    setPending({ ...pending, include_titles: '', exclude_titles: '' })
                  }}>
            Reset job titles to defaults
          </button>
        )}
      </ChipInput>

      <fieldset aria-describedby="setup-hint">
        <legend className="text-sm font-medium">Work setup</legend>
        <div className="mt-1 flex flex-wrap gap-x-6 gap-y-1">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={onsite} onChange={() => set({ onsite: !onsite })} />
            On-site or hybrid
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={remote} onChange={() => set({ remote: !remote })} />
            Remote
          </label>
        </div>
        <p id="setup-hint" className="mt-1 text-xs text-slate-500">
          Remote jobs count when they're open to your locations: "Remote - US" fits Dallas-Fort Worth.
        </p>
      </fieldset>

      <ChipInput id="locations" label="Locations" values={lists.locations}
                 onValues={(v) => setList('locations', v)} {...typed('locations')}
                 options={placeOptions} canon={placeOf} display={(n) => labelOf.get(n) ?? n} splitOnComma={false}
                 placeholder="Add a city, metro, country or region"
                 unknown={(v) => (places && !placeOf(v) ? 'not a known place, matched as text' : null)}
                 hint="Where you'd work on-site, and where you're based for remote. A country covers its cities. Nothing picked = anywhere." />

      <ChipInput id="extra_skills" label="Extra skills" values={lists.extra_skills}
                 onValues={(v) => setList('extra_skills', v)} {...typed('extra_skills')}
                 options={skills ?? []} canon={skillOf} placeholder="e.g. Kubernetes, Go"
                 unknown={(v) => (skills && !skillOf(v) ? "not a known skill: won't affect matching" : null)}
                 hint="Skills you have that aren't on your resume. Known aliases become the proper name (k8s → Kubernetes)." />

      <div>
        <label htmlFor="years" className="block text-sm font-medium">Years of experience</label>
        <input id="years" type="text" inputMode="numeric" maxLength={2} aria-describedby="years-hint"
               className={`${input} max-w-32`} value={years} onChange={(e) => set({ years: e.target.value })} />
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
            <button type="button" className="underline" onClick={() => set({ years: '' })}>Use resume ({detected})</button>
          </p>
        )}
      </div>
      <div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={presales} aria-describedby="presales-hint"
                 onChange={(e) => set({ presales: e.target.checked })} />
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
            <button type="button" onClick={() => { setDraft(JSON.parse(saved)); setPending(NO_PENDING) }}
                    className="text-sm text-slate-600 underline">Discard</button>
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