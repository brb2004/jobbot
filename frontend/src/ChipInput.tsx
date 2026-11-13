import { useEffect, useState, type ReactNode } from 'react'
import { addAll, toList, type Named } from './lists'

const box = 'w-full rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none'
const chip = 'inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-800'
const GROUPS: Record<string, [number, string]> = { metro: [0, 'Cities & metros'], country: [1, 'Countries'], region: [2, 'Regions'] }
const group = (o: Named) => GROUPS[o.kind ?? '']?.[0] ?? 9

type Props = {
  id: string
  label: string
  hint: string
  values: string[]
  onValues: (v: string[]) => void
  pending: string
  onPending: (v: string) => void
  options?: Named[]
  canon?: (v: string) => string | undefined
  unknown?: (v: string) => string | null
  placeholder?: string
  display?: (name: string) => string
  splitOnComma?: boolean
  children?: ReactNode
}

export function ChipInput({ id, label, hint, values, onValues, pending, onPending, options = [], canon,
                            unknown, placeholder, display = (n) => n, splitOnComma = true, children }: Props) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const keyOf = (v: string) => canon?.(v) ?? v
  const chips = [...new Map(values.map((v) => [keyOf(v).toLowerCase(), keyOf(v)])).values()]
  const chosen = new Set(chips.map((c) => c.toLowerCase()))

  const q = pending.trim().toLowerCase()
  const shown = (o: Named) => (o.label ?? o.name).toLowerCase()
  const available = options.filter((o) => !chosen.has(o.name.toLowerCase()))
  const matches = (q ? available.filter((o) => o.name.toLowerCase().includes(q) || shown(o).includes(q)
                                         || (o.aliases ?? []).some((a) => a.toLowerCase().startsWith(q)))
                     : available)
    .sort((a, b) => group(a) - group(b)
      || Number(!shown(a).startsWith(q)) - Number(!shown(b).startsWith(q))
      || shown(a).localeCompare(shown(b)))
  const showList = open && matches.length > 0
  useEffect(() => {
    if (active >= 0) document.getElementById(`${id}-opt-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active, id])

  const commit = (raw: string) => {
    const items = (splitOnComma ? toList(raw) : [raw.trim()].filter(Boolean)).map(keyOf)
    if (items.length) onValues(addAll(values, items))
  }
  const add = () => { commit(pending); onPending(''); setActive(-1) }
  const pick = (name: string) => { onValues(addAll(values, [name])); onPending(''); setActive(-1); setOpen(false) }
  const change = (v: string) => {
    setOpen(true)
    setActive(-1)
    if (!splitOnComma || !/[,\n]/.test(v)) {
      onPending(v)
      return
    }
    const parts = v.split(/[,\n]/)
    commit(parts.slice(0, -1).join(','))
    onPending(parts[parts.length - 1])
  }
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' && matches.length) { e.preventDefault(); setOpen(true); setActive((i) => (i + 1) % matches.length) }
    else if (e.key === 'ArrowUp' && matches.length) { e.preventDefault(); setActive((i) => (i <= 0 ? matches.length - 1 : i - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); if (showList && matches[active]) pick(matches[active].name); else add() }
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {chips.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-2">
          {chips.map((c) => {
            const note = unknown?.(c)
            return (
              <span key={c} className={chip}>
                <span>{display(c)}</span>
                {note && <span className="text-amber-700">({note})</span>}
                <button type="button" aria-label={`Remove ${display(c)}`} className="text-slate-500"
                        onClick={() => onValues(values.filter((x) => keyOf(x).toLowerCase() !== c.toLowerCase()))}>×</button>
              </span>
            )
          })}
        </div>
      )}
      <div className="relative mt-2 flex gap-2">
        <input id={id} role="combobox" aria-expanded={showList} aria-controls={`${id}-list`} aria-autocomplete="list"
               aria-activedescendant={showList && active >= 0 ? `${id}-opt-${active}` : undefined}
               aria-describedby={`${id}-hint`} placeholder={placeholder} autoComplete="off" className={box}
               value={pending} onChange={(e) => change(e.target.value)} onKeyDown={onKey}
               onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onBlur={() => setOpen(false)} />
        <button type="button" aria-label={`Add to ${label}`} onClick={add}
                className="rounded-md border border-slate-300 px-3 text-sm">Add</button>
        {showList && (
          <ul id={`${id}-list`} role="listbox"
              className="absolute left-0 right-16 top-full z-20 mt-1 max-h-72 overflow-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg">
            {matches.map((o, i) => {
              const heading = GROUPS[o.kind ?? '']?.[1]
              const first = heading && (i === 0 || matches[i - 1].kind !== o.kind)
              return [
                first && (
                  <li key={`h-${o.kind}`} role="presentation"
                      className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{heading}</li>
                ),
                <li key={o.name} id={`${id}-opt-${i}`} role="option" aria-selected={i === active}
                    onMouseDown={(e) => { e.preventDefault(); pick(o.name) }} onMouseEnter={() => setActive(i)}
                    className={`flex cursor-pointer items-baseline justify-between gap-3 px-3 py-1.5 text-sm ${i === active ? 'bg-slate-100' : ''}`}>
                  <span>{o.label ?? o.name}</span>
                  {o.detail && <span className="truncate text-xs text-slate-500">{o.detail}</span>}
                </li>,
              ]
            })}
          </ul>
        )}
      </div>
      {children}
      <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  )
}
