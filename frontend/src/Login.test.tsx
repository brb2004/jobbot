// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Login } from './Login'
import { Signup } from './Signup'

afterEach(cleanup)
const fakeApi = (o: Partial<Api>) => ({ login: vi.fn(), register: vi.fn(), ...o }) as unknown as Api

async function fillAndSubmit(button: string) {
  await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
  await userEvent.type(screen.getByLabelText('Password'), 'pw123456')
  await userEvent.click(screen.getByRole('button', { name: button }))
}

describe('Login', () => {
  it('logs in and reports success', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    const onDone = vi.fn()
    render(<Login api={fakeApi({ login })} onDone={onDone} />)
    await fillAndSubmit('Log in')
    expect(login).toHaveBeenCalledWith('a@b.com', 'pw123456')
    expect(onDone).toHaveBeenCalled()
  })

  it('shows the server error and stays on the page', async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, 'Invalid credentials'))
    const onDone = vi.fn()
    render(<Login api={fakeApi({ login })} onDone={onDone} />)
    await fillAndSubmit('Log in')
    expect((await screen.findByRole('alert')).textContent).toBe('Invalid credentials')
    expect(onDone).not.toHaveBeenCalled()
  })

  it('sends you to the sign-up page', async () => {
    const onSignup = vi.fn()
    render(<Login api={fakeApi({})} onDone={vi.fn()} onSignup={onSignup} />)
    await userEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    expect(onSignup).toHaveBeenCalled()
  })
})

describe('Signup', () => {
  it('registers and reports success', async () => {
    const register = vi.fn().mockResolvedValue(undefined)
    const onDone = vi.fn()
    render(<Signup api={fakeApi({ register })} onDone={onDone} onLogin={vi.fn()} />)
    await fillAndSubmit('Sign up')
    expect(register).toHaveBeenCalledWith('a@b.com', 'pw123456')
    expect(onDone).toHaveBeenCalled()
  })

  it('links back to log in', async () => {
    const onLogin = vi.fn()
    render(<Signup api={fakeApi({})} onDone={vi.fn()} onLogin={onLogin} />)
    await userEvent.click(screen.getByRole('button', { name: 'I already have an account' }))
    expect(onLogin).toHaveBeenCalled()
  })
})
