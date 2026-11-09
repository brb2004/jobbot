import { describe, expect, it, vi } from 'vitest'
import { createApi } from './api'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('api client', () => {
  it('keeps the token in memory and sends it on later calls', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(json({ access_token: 'abc', token_type: 'bearer' }))
      .mockResolvedValueOnce(json([]))
    const api = createApi(fetchFn)
    await api.login('a@b.com', 'pw')
    await api.matches()
    const [url, init] = fetchFn.mock.calls[1]
    expect(url).toBe('/api/dashboard')
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer abc')
  })

  it('errors carry the status and the FastAPI detail message', async () => {
    const api = createApi(vi.fn().mockResolvedValue(json({ detail: 'Invalid credentials' }, 401)))
    await expect(api.login('a@b.com', 'bad')).rejects.toMatchObject({ status: 401, message: 'Invalid credentials' })
  })

  it('uploads the resume as FormData and lets the browser set the multipart boundary', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ id: 'r1' }, 201))
    await createApi(fetchFn).uploadResume(new File(['hi'], 'cv.pdf'))
    const init = fetchFn.mock.calls[0][1]
    expect(init.body).toBeInstanceOf(FormData)
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
  })

  it('logout forgets the token', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(json({ access_token: 'abc', token_type: 'bearer' }))
      .mockResolvedValueOnce(json([]))
    const api = createApi(fetchFn)
    await api.login('a@b.com', 'pw')
    api.logout()
    await api.matches()
    expect(new Headers(fetchFn.mock.calls[1][1].headers).has('Authorization')).toBe(false)
    expect(api.isLoggedIn()).toBe(false)
  })
})

describe('validation errors', () => {
  it('turns a FastAPI 422 detail list into a readable message', async () => {
    const body = { detail: [{ loc: ['body', 'password'], msg: 'String should have at least 8 characters' }] }
    const api = createApi(vi.fn().mockResolvedValue(json(body, 422)))
    await expect(api.register('a@b.com', 'short')).rejects.toMatchObject({
      status: 422, message: 'password: String should have at least 8 characters',
    })
  })
})

describe('session expiry', () => {
  it('a 401 while logged in clears the token and tells listeners', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(json({ access_token: 'abc', token_type: 'bearer' }))
      .mockResolvedValueOnce(json({ detail: 'Not authenticated' }, 401))
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
    await expect(api.login('a@b.com', 'bad')).rejects.toMatchObject({ status: 401 })
    expect(listener).not.toHaveBeenCalled()
  })
})
