// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Login } from './Login'

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

  it('switches to sign up and registers', async () => {
    const register = vi.fn().mockResolvedValue(undefined)
    render(<Login api={fakeApi({ register })} onDone={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    await fillAndSubmit('Sign up')
    expect(register).toHaveBeenCalledWith('a@b.com', 'pw123456')
  })
})
