import { useEffect, useState } from 'react'
import { api } from './api'
import { Login } from './Login'
import { Matches } from './Matches'
import { Preferences } from './Preferences'
import { Upload } from './Upload'

type Page = 'matches' | 'resume' | 'preferences'
const PAGES: { id: Page; label: string }[] = [
  { id: 'matches', label: 'Matches' },
  { id: 'resume', label: 'Resume' },
  { id: 'preferences', label: 'Preferences' },
]

export default function App() {
  const [loggedIn, setLoggedIn] = useState(api.isLoggedIn())
  const [page, setPage] = useState<Page>('matches')
  const [flash, setFlash] = useState<string | null>(null)
  useEffect(() => api.onUnauthorized(() => setLoggedIn(false)), [])   // expired session -> login
  const go = (p: Page, message: string | null = null) => { setPage(p); setFlash(message) }
  if (!loggedIn) return <Login api={api} onDone={() => setLoggedIn(true)} />

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <span className="font-semibold">JobBot</span>
        {PAGES.map((p) => (
          <button key={p.id} onClick={() => go(p.id)}
                  className={page === p.id ? 'font-medium underline' : 'text-slate-600'}>
            {p.label}
          </button>
        ))}
        <button onClick={() => { api.logout(); setLoggedIn(false) }} className="ml-auto whitespace-nowrap text-sm text-slate-600">
          Log out
        </button>
      </nav>
      <main className="p-6">
        {flash && <p role="status" className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">{flash}</p>}
        {page === 'resume' && <Upload api={api} onDone={() => go('matches', 'Resume uploaded. Your matches are updated.')} />}
        {page === 'matches' && <Matches api={api} onUpload={() => go('resume')} />}
        {page === 'preferences' && <Preferences api={api} onSaved={() => go('matches', 'Preferences saved. Your matches are updated.')} />}
      </main>
    </div>
  )
}
