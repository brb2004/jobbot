import type { Education as Level } from './api'

const OPTIONS: [Level | '', string][] = [
  ['', "Don't filter by degree"],
  ['none', 'No degree'],
  ['associate', "Associate's"],
  ['bachelor', "Bachelor's"],
  ['master', "Master's"],
  ['phd', 'PhD'],
]

export function Education({ value, onChange }: { value: Level | ''; onChange: (v: Level | '') => void }) {
  return (
    <div>
      <label htmlFor="education" className="block text-sm font-medium">Highest education</label>
      <select id="education" aria-describedby="education-hint" value={value}
              onChange={(e) => onChange(e.target.value as Level | '')}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none">
        {OPTIONS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
      </select>
      <p id="education-hint" className="mt-1 text-xs text-slate-500">
        Hides jobs that require a higher degree with no "or equivalent experience." A degree listed as preferred never
        hides a job.
      </p>
    </div>
  )
}
