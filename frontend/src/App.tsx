import { useState } from 'react'
import { api } from './api'
import { Login } from './Login'
import { Matches } from './Matches'
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
  if (!loggedIn) return <Login api={api} onDone={() => setLoggedIn(true)} />

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <span className="font-semibold">JobBot</span>
        {PAGES.map((p) => (
          <button key={p.id} onClick={() => setPage(p.id)}
                  className={page === p.id ? 'font-medium underline' : 'text-slate-600'}>
            {p.label}
          </button>
        ))}
        <button onClick={() => { api.logout(); setLoggedIn(false) }} className="ml-auto text-sm text-slate-600">
          Log out
        </button>
      </nav>
      <main className="p-6">
        {page === 'resume' && <Upload api={api} onDone={() => setPage('matches')} />}
        {page === 'matches' && <Matches api={api} />}
        {page === 'preferences' && <p className="text-slate-600">Coming next.</p>}
      </main>
    </div>
  )
}
