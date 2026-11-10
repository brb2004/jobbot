// Shared helpers for list fields: split typed text, dedupe, map any alias to its canonical name.
export type Named = { name: string; aliases?: string[]; kind?: string | null; detail?: string }

export const toList = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean)

export const addAll = (list: string[], items: string[]) => {
  const seen = new Set(list.map((x) => x.toLowerCase()))
  return [...list, ...items.filter((i) => !seen.has(i.toLowerCase()) && !!seen.add(i.toLowerCase()))]
}

export const canonFrom = (items: Named[] | null) => {
  const m = new Map<string, string>()
  for (const it of items ?? []) {
    m.set(it.name.toLowerCase(), it.name)
    for (const a of it.aliases ?? []) m.set(a.toLowerCase(), it.name)
  }
  return (v: string) => m.get(v.toLowerCase())
}
