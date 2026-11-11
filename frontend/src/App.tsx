import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router'
import { api } from './api'
import { CheckEmail } from './CheckEmail'
import { Applied } from './Applied'
import { Login } from './Login'
import { Matches } from './Matches'
import { Preferences } from './Preferences'
import { Privacy } from './Privacy'
import { Reset } from './Reset'
import { Signup } from './Signup'
import { Upload } from './Upload'
import { Verify } from './Verify'

const PAGES = [
  { path: '/matches', label: 'Matches' },
  { path: '/applied', label: 'Applied' },
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

type Status = 'checking' | 'in' | 'unconfirmed' | 'out'

function Shell() {
  const [status, setStatus] = useState<Status>('checking')
  const [email, setEmail] = useState('')
  const [flash, setFlash] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)                 // unsaved edits on Preferences
  const navigate = useNavigate()
  const location = useLocation()

  // Logged in, but is the address confirmed? Unconfirmed accounts only see the check-your-email page.
  const refresh = () => api.me()
    .then((u) => { setEmail(u.email); setStatus(u.email_verified_at ? 'in' : 'unconfirmed') })
    .catch(() => setStatus('out'))

  useEffect(() => { api.restore().then((ok) => (ok ? refresh() : setStatus('out'))) }, [])   // survives refresh
  useEffect(() => api.onUnauthorized(() => setStatus('out')), [])                              // expired -> login

  const leaveOk = () => {
    if (dirty && !window.confirm('You have unsaved changes on Preferences. Leave without saving?')) return false
    setDirty(false)
    return true
  }
  const go = (path: string, message: string | null = null) => { setFlash(message); navigate(path) }
  const logout = async () => { await api.logout(); setStatus('out'); navigate('/', { replace: true }) }

  // Emailed links work logged in or out; the token rides after '#'.
  if (location.pathname === '/privacy') return <Privacy />
  if (location.pathname === '/verify')
    return <Verify api={api} token={location.hash.slice(1)}
                   onDone={() => { navigate('/matches', { replace: true }); refresh() }} />
  if (location.pathname === '/reset')
    return <Reset api={api} token={location.hash.slice(1)}
                  onDone={() => { setStatus('out'); navigate('/', { replace: true }) }} />

  if (status === 'checking') return <p className="p-6 text-slate-600">Loading…</p>
  if (status === 'out')
    return location.pathname === '/signup'
      ? <Signup api={api} onDone={refresh} onLogin={() => navigate('/')} />
      : <Login api={api} onDone={refresh} onSignup={() => navigate('/signup')} />
  if (status === 'unconfirmed')
    return <CheckEmail api={api} email={email} onConfirmed={refresh} onLogout={logout} />

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-white px-4 py-3 sm:px-6">
        <span className="font-semibold">JobMatch</span>
        {PAGES.map((p) => (
          <NavLink key={p.path} to={p.path} onClick={(e) => { if (!leaveOk()) { e.preventDefault(); return } setFlash(null) }}
                   className={({ isActive }) => (isActive ? 'font-medium underline' : 'text-slate-600')}>
            {p.label}
          </NavLink>
        ))}
        <button onClick={() => { if (leaveOk()) logout() }} className="ml-auto whitespace-nowrap text-sm text-slate-600">
          Log out
        </button>
      </nav>
      <main className="p-4 sm:p-6">
        {flash && <p role="status" className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">{flash}</p>}
        <Routes>
          <Route path="/matches" element={<Matches api={api} onUpload={() => go('/resume')} onPreferences={() => go('/preferences')} />} />
          <Route path="/applied" element={<Applied api={api} />} />
          <Route path="/resume" element={<Upload api={api} onDone={() => go('/matches', 'Resume uploaded. Your matches are updated.')} />} />
          <Route path="/preferences" element={<Preferences api={api} onDirty={setDirty} onSaved={() => go('/matches', 'Preferences saved. Your matches are updated.')}
                                                     onDeleted={() => setStatus('out')} />} />
          <Route path="*" element={<Navigate to="/matches" replace />} />
        </Routes>
      </main>
    </div>
  )
}
