import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router'
import { api } from './api'
import { Login } from './Login'
import { Matches } from './Matches'
import { Preferences } from './Preferences'
import { Reset } from './Reset'
import { Verify } from './Verify'
import { VerifyBanner } from './VerifyBanner'
import { Upload } from './Upload'

const PAGES = [
  { path: '/matches', label: 'Matches' },
  { path: '/resume', label: 'Resume' },
  { path: '/preferences', label: 'Preferences' },
]

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}

function Shell() {
  const [status, setStatus] = useState<'checking' | 'in' | 'out'>('checking')
  const [flash, setFlash] = useState<string | null>(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => { api.restore().then((ok) => setStatus(ok ? 'in' : 'out')) }, [])   // survives refresh
  useEffect(() => api.onUnauthorized(() => setStatus('out')), [])                      // expired -> login

  const go = (path: string, message: string | null = null) => { setFlash(message); navigate(path) }

  if (location.pathname === '/verify')     // the emailed confirmation link: token after '#'
    return <Verify api={api} token={location.hash.slice(1)} onDone={() => navigate('/matches', { replace: true })} />
  if (location.pathname === '/reset')      // the emailed link: token after '#', works logged in or out
    return <Reset api={api} token={location.hash.slice(1)}
                  onDone={() => { setStatus('out'); navigate('/matches', { replace: true }) }} />
  if (status === 'checking') return <p className="p-6 text-slate-600">Loading…</p>
  if (status === 'out') return <Login api={api} onDone={() => setStatus('in')} />   // stays on the URL you asked for

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <span className="font-semibold">JobBot</span>
        {PAGES.map((p) => (
          <NavLink key={p.path} to={p.path} onClick={() => setFlash(null)}
                   className={({ isActive }) => (isActive ? 'font-medium underline' : 'text-slate-600')}>
            {p.label}
          </NavLink>
        ))}
        <button onClick={async () => { await api.logout(); setStatus('out') }}
                className="ml-auto whitespace-nowrap text-sm text-slate-600">
          Log out
        </button>
      </nav>
      <main className="p-6">
        <VerifyBanner api={api} />
        {flash && <p role="status" className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">{flash}</p>}
        <Routes>
          <Route path="/matches" element={<Matches api={api} onUpload={() => go('/resume')} onPreferences={() => go('/preferences')} />} />
          <Route path="/resume" element={<Upload api={api} onDone={() => go('/matches', 'Resume uploaded. Your matches are updated.')} />} />
          <Route path="/preferences" element={<Preferences api={api} onSaved={() => go('/matches', 'Preferences saved. Your matches are updated.')}
                                                     onDeleted={() => setStatus('out')} />} />
          <Route path="*" element={<Navigate to="/matches" replace />} />
        </Routes>
      </main>
    </div>
  )
}
