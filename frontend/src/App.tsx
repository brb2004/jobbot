import { useState } from 'react'
import { api } from './api'
import { Login } from './Login'

export default function App() {
  const [loggedIn, setLoggedIn] = useState(api.isLoggedIn())
  if (!loggedIn) return <Login api={api} onDone={() => setLoggedIn(true)} />
  return (
    <main className="p-6">
      <p>Logged in. Pages coming next.</p>
      <button onClick={() => { api.logout(); setLoggedIn(false) }} className="mt-4 underline">Log out</button>
    </main>
  )
}
