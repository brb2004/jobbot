import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, type Api, type ResumeInfo } from './api'
import { ChipInput } from './ChipInput'
import { addAll, toList } from './lists'

const MAX = 2
const message = (e: unknown) => (e instanceof ApiError ? e.message : 'Could not reach the server')
const box = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
const fileBox = 'block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white'

export function Upload({ api, onDone }: { api: Api; onDone: () => void }) {
  const [resumes, setResumes] = useState<ResumeInfo[] | null>(null)
  const [ownYears, setOwnYears] = useState<number | null | undefined>(undefined)

  const load = () => api.listResumes().then(setResumes).catch(() => setResumes([]))
  useEffect(() => {
    load()
    Promise.resolve().then(() => api.getPreferences())
      .then((p) => setOwnYears(p.years_experience ?? null))
      .catch(() => {})
  }, [api])  // eslint-disable-line react-hooks/exhaustive-deps

  const list = resumes ?? []
  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Your resumes</h2>
        <p className="text-sm text-slate-600">
          Keep up to {MAX}, for example one for backend roles and one for DevOps. Each gets its own matches.
        </p>
      </div>
      {list.map((r) => <ResumeCard key={r.id} api={api} resume={r} ownYears={ownYears} several={list.length > 1}
                                   onChanged={load} onDone={onDone} />)}
      {resumes !== null && list.length < MAX && <AddResume api={api} first={list.length === 0} onDone={onDone} />}
    </div>
  )
}

function AddResume({ api, first, onDone }: { api: Api; first: boolean; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      await api.uploadResume(file, name.trim() ? { name: name.trim() } : {})
      onDone()
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-dashed border-slate-300 p-4">
      <h3 className="font-medium">{first ? 'Upload your resume' : 'Add a second resume'}</h3>
      <label htmlFor="resume" className="block text-sm font-medium">Resume (PDF, Word .docx, or plain text)</label>
      <input id="resume" type="file" accept=".pdf,.docx,.txt" className={fileBox}
             onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <label htmlFor="resume-name" className="block text-sm font-medium">Name (optional)</label>
      <input id="resume-name" maxLength={40} className={box} placeholder="e.g. Backend, DevOps"
             value={name} onChange={(e) => setName(e.target.value)} />
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button type="submit" disabled={!file || busy}
              className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50">
        Upload
      </button>
    </form>
  )
}

function ResumeCard({ api, resume, ownYears, several, onChanged, onDone }:
  { api: Api; resume: ResumeInfo; ownYears: number | null | undefined; several: boolean
    onChanged: () => void; onDone: () => void }) {
  const own = resume.own
  const [name, setName] = useState(resume.name ?? '')
  const [include, setInclude] = useState<string[]>(own?.include_titles ?? [])
  const [exclude, setExclude] = useState<string[]>(own?.exclude_titles ?? [])
  const [pendingIn, setPendingIn] = useState('')
  const [pendingEx, setPendingEx] = useState('')
  const [years, setYears] = useState(own?.years_experience?.toString() ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const id = resume.id.slice(0, 8)

  async function run(fn: () => Promise<unknown>, after: () => void) {
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      await fn()
      after()
    } catch (e) {
      setError(message(e))
    } finally {
      setBusy(false)
    }
  }

  const save = () => {
    const inc = addAll(include, toList(pendingIn))
    const exc = addAll(exclude, toList(pendingEx))
    return run(() => api.updateResume(resume.id, {
      name: name.trim() || undefined,
      own: { include_titles: inc.length ? inc : null, exclude_titles: exc.length ? exc : null,
             years_experience: years.trim() === '' ? null : Number(years) },
    }), () => { setSaved(true); onChanged() })
  }

  return (
    <section aria-label={resume.name ?? resume.filename ?? 'Resume'} className="space-y-3 rounded-lg bg-white p-4 shadow-sm">
      <div>
        <label htmlFor={`name-${id}`} className="block text-sm font-medium">Name</label>
        <input id={`name-${id}`} maxLength={40} className={box} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <p className="text-sm">Current: {resume.filename}</p>
      {resume.years_detected != null && (
        <p className="text-sm text-slate-600">
          Relevant experience detected: {resume.years_detected} years.
          {ownYears === null && !years && ' Used when "Years of experience" in Preferences is blank.'}
        </p>
      )}

      {(several || include.length > 0 || exclude.length > 0 || years !== '') && <>
        <ChipInput id={`include-${id}`} label="Job titles for this resume" values={include} onValues={setInclude}
                   pending={pendingIn} onPending={setPendingIn} placeholder="e.g. devops, platform"
                   hint="Empty = the titles in Preferences. Anything here replaces them for this resume only." />
        <ChipInput id={`exclude-${id}`} label="Titles to hide for this resume" values={exclude} onValues={setExclude}
                   pending={pendingEx} onPending={setPendingEx} placeholder="e.g. senior"
                   hint="Empty = the exclusions in Preferences." />
        <div>
          <label htmlFor={`years-${id}`} className="block text-sm font-medium">Years of experience for this resume</label>
          <input id={`years-${id}`} type="number" min={0} max={60} className={box} value={years}
                 placeholder="Empty = Preferences, or what was detected" onChange={(e) => setYears(e.target.value)} />
        </div>
      </>}

      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {saved && <p role="status" className="text-sm text-green-800">Saved. Matches for this resume are updated.</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" disabled={busy} onClick={save}
                className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50">Save</button>
        <button type="button" disabled={busy} className="text-sm text-red-700 underline"
                onClick={() => { if (window.confirm(`Delete "${resume.name ?? resume.filename}" and its matches?`))
                                   run(() => api.deleteResume(resume.id), onChanged) }}>Delete</button>
      </div>

      <div className="border-t pt-3">
        <label htmlFor={`replace-${id}`} className="block text-sm font-medium">Replace the file (keeps the name and settings)</label>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <input id={`replace-${id}`} type="file" accept=".pdf,.docx,.txt" className={fileBox}
                 onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button type="button" disabled={!file || busy}
                  onClick={() => file && run(() => api.uploadResume(file, { replace: resume.id }), onDone)}
                  className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-50">Replace</button>
        </div>
      </div>
    </section>
  )
}
