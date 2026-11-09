import { describe, expect, it, vi } from 'vitest'
import { createApi } from './api'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const noContent = () => new Response(null, { status: 204 })
const token = () => json({ access_token: 'abc', token_type: 'bearer' })

describe('session', () => {
  it('login relies on the cookie: no token in JS, same-origin credentials', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(token()).mockResolvedValueOnce(json([]))
    const api = createApi(fetchFn)
    await api.login('a@b.com', 'pw')
    await api.matches()
    const [url, init] = fetchFn.mock.calls[1]
    expect(url).toBe('/api/dashboard')
    expect(init.credentials).toBe('same-origin')
    expect(new Headers(init.headers).has('Authorization')).toBe(false)
    expect(api.isLoggedIn()).toBe(true)
  })

  it('restore asks /auth/me whether the cookie is still valid', async () => {
    expect(await createApi(vi.fn().mockResolvedValue(json({ id: '1', email: 'a@b.com' }))).restore()).toBe(true)
    expect(await createApi(vi.fn().mockResolvedValue(json({ detail: 'Not authenticated' }, 401))).restore()).toBe(false)
  })

  it('logout tells the server to clear the cookie', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(token()).mockResolvedValueOnce(noContent())
    const api = createApi(fetchFn)
    await api.login('a@b.com', 'pw')
    await api.logout()
    expect(fetchFn.mock.calls[1][0]).toBe('/api/auth/logout')
    expect(api.isLoggedIn()).toBe(false)
  })

  it('a 401 while logged in ends the session and tells listeners', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(token()).mockResolvedValueOnce(json({ detail: 'Not authenticated' }, 401))
    const api = createApi(fetchFn)
    const listener = vi.fn()
    api.onUnauthorized(listener)
    await api.login('a@b.com', 'pw')
    await expect(api.matches()).rejects.toMatchObject({ status: 401 })
    expect(listener).toHaveBeenCalledOnce()
    expect(api.isLoggedIn()).toBe(false)
  })

  it('a wrong password at login is not a session expiry', async () => {
    const api = createApi(vi.fn().mockResolvedValue(json({ detail: 'Invalid email or password' }, 401)))
    const listener = vi.fn()
    api.onUnauthorized(listener)
    await expect(api.login('a@b.com', 'bad')).rejects.toMatchObject({ status: 401, message: 'Invalid email or password' })
    expect(listener).not.toHaveBeenCalled()
  })
})

describe('requests', () => {
  it('uploads the resume as FormData and lets the browser set the multipart boundary', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ id: 'r1' }, 201))
    await createApi(fetchFn).uploadResume(new File(['hi'], 'cv.pdf'))
    const init = fetchFn.mock.calls[0][1]
    expect(init.body).toBeInstanceOf(FormData)
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
  })

  it('turns a FastAPI 422 detail list into a readable message', async () => {
    const body = { detail: [{ loc: ['body', 'password'], msg: 'String should have at least 8 characters' }] }
    const api = createApi(vi.fn().mockResolvedValue(json(body, 422)))
    await expect(api.register('a@b.com', 'short')).rejects.toMatchObject({
      status: 422, message: 'Password: String should have at least 8 characters',
    })
  })
})
