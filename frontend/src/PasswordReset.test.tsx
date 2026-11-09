// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Login } from './Login'
import { Reset } from './Reset'

afterEach(cleanup)

describe('forgot password', () => {
  it('asks only for the email and never says whether the account exists', async () => {
    const forgotPassword = vi.fn().mockResolvedValue(undefined)
    render(<Login api={{ forgotPassword } as unknown as Api} onDone={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /forgot password/i }))
    expect(screen.queryByLabelText(/^password$/i)).toBeNull()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.co' } })
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }))
    await screen.findByText(/if an account exists for a@b.co/i)
    expect(forgotPassword).toHaveBeenCalledWith('a@b.co')
  })
})

describe('reset page', () => {
  it('sets the new password with the token from the link', async () => {
    const resetPassword = vi.fn().mockResolvedValue(undefined)
    const onDone = vi.fn()
    render(<Reset api={{ resetPassword } as unknown as Api} token="tok" onDone={onDone} />)
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'new-password-22' } })
    fireEvent.click(screen.getByRole('button', { name: /set password/i }))
    await screen.findByText(/password changed/i)
    expect(resetPassword).toHaveBeenCalledWith('tok', 'new-password-22')
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(onDone).toHaveBeenCalled()
  })

  it('shows why a dead link failed', async () => {
    const resetPassword = vi.fn().mockRejectedValue(new ApiError(400, 'This reset link is invalid or has expired. Request a new one.'))
    render(<Reset api={{ resetPassword } as unknown as Api} token="old" onDone={() => {}} />)
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'new-password-22' } })
    fireEvent.click(screen.getByRole('button', { name: /set password/i }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/expired/i)
  })
})
