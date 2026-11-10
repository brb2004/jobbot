import type { ReactNode } from 'react'
import { addAll, toList, type Named } from './lists'

const box = 'w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
const chip = 'inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-800'

type Props = {
  id: string
  label: string
  hint: string
  values: string[]
  onValues: (v: string[]) => void
  pending: string                                     // typed but not added yet (still saved)
  onPending: (v: string) => void
  options?: Named[]                                   // suggestions while typing
  canon?: (v: string) => string | undefined           // any alias -> canonical name
  unknown?: (v: string) => string | null              // note shown on a chip, or null
  placeholder?: string
  children?: ReactNode
}

// One list field: chips you can remove, a box that turns Enter or commas into chips, and suggestions.
export function ChipInput({ id, label, hint, values, onValues, pending, onPending, options = [], canon,
                            unknown, placeholder, children }: Props) {
  const commit = (raw: string) => {
    const items = toList(raw).map((v) => canon?.(v) ?? v)
    if (items.length) onValues(addAll(values, items))
  }
  const change = (v: string) => {
    if (!/[,\n]/.test(v)) {
      onPending(v)
      return
    }
    const parts = v.split(/[,\n]/)
    commit(parts.slice(0, -1).join(','))
    onPending(parts[parts.length - 1])
  }
  const add = () => { commit(pending); onPending('') }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {values.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-2">
          {values.map((v) => {
            const note = unknown?.(v)
            return (
              <span key={v} className={chip}>
                <span>{v}</span>
                {note && <span className="text-amber-700">({note})</span>}
                <button type="button" aria-label={`Remove ${v}`} className="text-slate-500"
                        onClick={() => onValues(values.filter((x) => x !== v))}>×</button>
              </span>
            )
          })}
        </div>
      )}
      <div className="mt-2 flex gap-2">
        <input id={id} list={options.length ? `${id}-options` : undefined} aria-describedby={`${id}-hint`}
               placeholder={placeholder} autoComplete="off" className={box} value={pending}
               onChange={(e) => change(e.target.value)}
               onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
        <button type="button" aria-label={`Add to ${label}`} onClick={add}
                className="rounded-md border border-slate-300 px-3 text-sm">Add</button>
      </div>
      {options.length > 0 && (
        <datalist id={`${id}-options`}>
          {options.map((o) => <option key={o.name} value={o.name} label={o.aliases?.slice(0, 5).join(', ')} />)}
        </datalist>
      )}
      {children}
      <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  )
}
