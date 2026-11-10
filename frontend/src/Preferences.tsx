import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ApiError, type Api, type Place, type Preferences as Prefs } from './api'

const TEXT = {
  include_titles: ['Job titles to include', 'Only titles containing one of these. Leave empty to use the defaults (engineer, developer, SRE, DevOps, architect, scientist). Anything you enter replaces them.'],
  exclude_titles: ['Job titles to exclude', 'Hide titles containing any of these, e.g. senior, staff. Excluded titles always win.'],
  extra_skills: ['Extra skills', "Skills you have that aren't on your resume."],
} as const
type TextKey = keyof typeof TEXT
type Draft = { text: Record<TextKey, string>; locations: string[]; regions: string[]; years: string; presales: boolean }

const REGIONS = ['United States', 'Canada', 'United Kingdom', 'Europe', 'Latin America', 'APAC']
const REMOTE = 'remote'

// Mirrors PRESALES_TITLES on the server: warn when the exclude list cancels the sales checkbox.
const SALES = ['customer engineer', 'solutions architect', 'solution architect', 'solutions engineer',
  'solution engineer', 'account executive', 'customer success']
const salesWord = (t: string) => /(^|[\s-])(pre-?)?sales([\s-]|$)/i.test(t) || SALES.includes(t.toLowerCase())

const toList = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean)
const addAll = (list: string[], items: string[]) => {
  const seen = new Set(list.map((x) => x.toLowerCase()))
  return [...list, ...items.filter((i) => !seen.has(i.toLowerCase()) && !!seen.add(i.toLowerCase()))]
}
const YEARS_OK = /^\d{1,2}$/
const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
const chip = 'inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-800'

export function Preferences({ api, onSaved, onDeleted, onDirty }:
  { api: Api; onSaved: () => void; onDeleted?: () => void; onDirty?: (dirty: boolean) => void }) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saved, setSaved] = useState('')                       // the last loaded or saved draft, as JSON
  const [pending, setPending] = useState('')                   // typed in the location box, not added yet
  const [places, setPlaces] = useState<Place[] | null>(null)
  const [detected, setDetected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Could not reach the server')

  useEffect(() => {
    api.getPreferences()
      .then((p) => {
        const d: Draft = {
          text: { include_titles: p.include_titles.join(', '), exclude_titles: p.exclude_titles.join(', '),
                  extra_skills: p.extra_skills.join(', ') },
          locations: p.locations, regions: p.remote_regions,
          years: p.years_experience?.toString() ?? '', presales: p.include_presales,
        }
        setDraft(d)
        setSaved(JSON.stringify(d))
      })
      .catch(fail)
    Promise.resolve().then(() => api.listResumes()).then((rs) => setDetected(rs[0]?.years_detected ?? null)).catch(() => {})
    Promise.resolve().then(() => api.listPlaces()).then(setPlaces).catch(() => {})
  }, [api])

  // any spelling -> canonical place name ("usa" -> "United States")
  const canonOf = useMemo(() => {
    const m = new Map<string, string>()
    for (const p of places ?? []) {
      m.set(p.name.toLowerCase(), p.name)
      for (const a of p.aliases) m.set(a.toLowerCase(), p.name)
    }
    return m
  }, [places])
  const canon = (v: string) => canonOf.get(v.toLowerCase()) ?? REGIONS.find((r) => r.toLowerCase() === v.toLowerCase())

  const dirty = draft !== null && (JSON.stringify(draft) !== saved || pending.trim() !== '')
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
      const final = { ...draft, locations: addAll(draft.locations, toList(pending)) }   // typed but not added: keep it
      await api.savePreferences({
        include_titles: toList(final.text.include_titles), exclude_titles: toList(final.text.exclude_titles),
        extra_skills: toList(final.text.extra_skills), locations: final.locations, remote_regions: final.regions,
        years_experience: years === '' ? null : Number(years), include_presales: final.presales,
      } satisfies Prefs)
      setDraft(final)
      setPending('')
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

  const { text, years, presales, locations, regions } = draft
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch })
  const clash = presales ? toList(text.exclude_titles).filter(salesWord) : []
  const remoteOn = locations.some((l) => l.toLowerCase() === REMOTE)
  const places_ = locations.filter((l) => l.toLowerCase() !== REMOTE)
  const otherRegions = regions.filter((r) => !REGIONS.includes(canon(r) ?? ''))

  const addPending = () => {
    if (!toList(pending).length) return
    set({ locations: addAll(locations, toList(pending).map((p) => canon(p) ?? p)) })
    setPending('')
  }
  const onAddKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); addPending() }
  }
  const toggleRegion = (r: string) => set({
    regions: regions.some((v) => canon(v) === r) ? regions.filter((v) => canon(v) !== r) : [...regions, r],
  })

  const textField = (key: TextKey) => (
    <div key={key}>
      <label htmlFor={key} className="block text-sm font-medium">{TEXT[key][0]}</label>
      <textarea id={key} rows={2} aria-describedby={`${key}-hint`} className={`${input} resize-y`}
                value={text[key]} onChange={(e) => set({ text: { ...text, [key]: e.target.value } })} />
      <p id={`${key}-hint`} className="mt-1 text-xs text-slate-500">{TEXT[key][1]}</p>
      {key === 'exclude_titles' && (text.include_titles.trim() !== '' || text.exclude_titles.trim() !== '') && (
        <button type="button" className="mt-1 text-xs text-slate-600 underline"
                onClick={() => set({ text: { ...text, include_titles: '', exclude_titles: '' } })}>
          Reset job titles to defaults
        </button>
      )}
    </div>
  )

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4">
      <h2 className="text-xl font-semibold">Preferences</h2>
      <p className="text-sm text-slate-600">Separate title and skill entries with commas or new lines. Saving updates your matches right away.</p>
      {textField('include_titles')}
      {textField('exclude_titles')}

      <fieldset aria-describedby="locations-hint">
        <legend className="text-sm font-medium">Locations</legend>
        <label className="mt-1 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={remoteOn}
                 onChange={() => set({ locations: remoteOn ? places_ : [REMOTE, ...places_] })} />
          Remote
        </label>
        {places_.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {places_.map((l) => (
              <span key={l} className={chip}>
                {canon(l) ?? l}
                {places && !canon(l) && <span className="text-amber-700">(not a known place)</span>}
                <button type="button" aria-label={`Remove ${l}`} className="text-slate-500"
                        onClick={() => set({ locations: locations.filter((x) => x !== l) })}>×</button>
              </span>
            ))}
          </div>
        )}
        <div className="mt-2 flex gap-2">
          <input id="location-add" aria-label="Add a location" list="place-options" placeholder="Add a city, metro or country"
                 className={input.replace('mt-1 ', '')} value={pending} onChange={(e) => setPending(e.target.value)} onKeyDown={onAddKey} />
          <button type="button" onClick={addPending} className="rounded-md border border-slate-300 px-3 text-sm">Add</button>
        </div>
        <datalist id="place-options">
          {(places ?? []).map((p) => <option key={p.name} value={p.name} label={p.aliases.slice(0, 5).join(', ')} />)}
        </datalist>
        <p id="locations-hint" className="mt-1 text-xs text-slate-500">
          Dallas-Fort Worth also covers Plano, Richardson and Frisco; a country covers all its cities. Nothing picked = anywhere.
        </p>
      </fieldset>

      <fieldset aria-describedby="regions-hint">
        <legend className="text-sm font-medium">Remote regions</legend>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
          {REGIONS.map((r) => (
            <label key={r} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={regions.some((v) => canon(v) === r)} onChange={() => toggleRegion(r)} />
              {r}
            </label>
          ))}
        </div>
        {otherRegions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {otherRegions.map((r) => (
              <span key={r} className={chip}>
                {r}
                <button type="button" aria-label={`Remove ${r}`} className="text-slate-500"
                        onClick={() => set({ regions: regions.filter((x) => x !== r) })}>×</button>
              </span>
            ))}
          </div>
        )}
        <p id="regions-hint" className="mt-1 text-xs text-slate-500">
          Only applies to remote jobs. None checked = remote jobs from anywhere.
        </p>
      </fieldset>

      {textField('extra_skills')}

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
            <button type="button" onClick={() => { setDraft(JSON.parse(saved)); setPending('') }}
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
