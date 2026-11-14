import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, type Api, type Links } from './api'

const FIELDS = [
  { key: 'linkedin', label: 'LinkedIn', placeholder: 'linkedin.com/in/you' },
  { key: 'github', label: 'GitHub', placeholder: 'github.com/you' },
  { key: 'website', label: 'Website', placeholder: 'you.dev' },
] as const
const EMPTY: Links = { linkedin: null, github: null, website: null }
const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'

function useLinks(api: Api) {
  const [links, setLinks] = useState<Links | null>(null)
  useEffect(() => {
    Promise.resolve().then(() => api.getLinks()).then(setLinks).catch(() => setLinks(EMPTY))
  }, [api])
  return [links, setLinks] as const
}

export function LinksEditor({ api }: { api: Api }) {
  const [links, setLinks] = useLinks(api)
  const [status, setStatus] = useState<string | null>(null)

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!links) return
    try {
      setLinks(await api.saveLinks(links))
      setStatus('Links saved.')
    } catch (err) {
      setStatus(err instanceof ApiError ? err.message : 'Could not reach the server')
    }
  }

  if (!links) return null
  return (
    <form onSubmit={save} aria-labelledby="links-heading" className="max-w-xl space-y-3 border-t pt-4">
      <h3 id="links-heading" className="text-sm font-medium">Your links</h3>
      <p className="text-xs text-slate-500">Shown on your matches with a copy button, for pasting into applications.</p>
      {FIELDS.map((f) => (
        <div key={f.key}>
          <label htmlFor={`link-${f.key}`} className="block text-sm">{f.label}</label>
          <input id={`link-${f.key}`} type="text" inputMode="url" autoComplete="url" maxLength={200}
                 placeholder={f.placeholder} className={input} value={links[f.key] ?? ''}
                 onChange={(e) => { setLinks({ ...links, [f.key]: e.target.value }); setStatus(null) }} />
        </div>
      ))}
      <div className="flex items-center gap-3">
        <button type="submit" className="rounded-md border border-slate-300 px-3 py-1 text-sm">Save links</button>
        {status && <span role="status" className="text-sm text-slate-700">{status}</span>}
      </div>
    </form>
  )
}

export function LinksBar({ api, onEdit }: { api: Api; onEdit?: () => void }) {
  const [links] = useLinks(api)
  const [copied, setCopied] = useState<string | null>(null)
  if (!links) return null
  const filled = FIELDS.filter((f) => links[f.key])
  if (!filled.length)
    return (
      <p className="text-sm text-slate-600">
        <button onClick={onEdit} className="underline">Add your LinkedIn, GitHub and website</button> to copy them
        into applications in one click.
      </p>
    )

  async function copy(key: string, value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(key)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-slate-600">Copy your links:</span>
      {filled.map((f) => (
        <button key={f.key} type="button" title={links[f.key] ?? ''} onClick={() => copy(f.key, links[f.key] ?? '')}
                className="rounded-full bg-white px-3 py-1 shadow-sm">
          {copied === f.key ? `${f.label} copied ✓` : f.label}
        </button>
      ))}
    </div>
  )
}
