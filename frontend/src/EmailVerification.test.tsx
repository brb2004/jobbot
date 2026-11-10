// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { CheckEmail } from './CheckEmail'
import { Verify } from './Verify'

afterEach(cleanup)

describe('confirmation link', () => {
  it('confirms the token from the link', async () => {
    const verifyEmail = vi.fn().mockResolvedValue(undefined)
    render(<Verify api={{ verifyEmail } as unknown as Api} token="tok" onDone={() => {}} />)
    await screen.findByText(/email confirmed/i)
    expect(verifyEmail).toHaveBeenCalledWith('tok')
  })

  it('explains a dead link', async () => {
    const verifyEmail = vi.fn().mockRejectedValue(new ApiError(400, 'This confirmation link is invalid or has expired.'))
    render(<Verify api={{ verifyEmail } as unknown as Api} token="old" onDone={() => {}} />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/expired/i)
  })
})

describe('check your email page', () => {
  const page = (api: Partial<Api>, onConfirmed = vi.fn().mockResolvedValue(undefined)) =>
    render(<CheckEmail api={api as Api} email="a@b.co" onConfirmed={onConfirmed} onLogout={() => {}} />)

  it('shows where the link went and re-sends it', async () => {
    const resendVerification = vi.fn().mockResolvedValue(undefined)
    page({ resendVerification })
    screen.getByText('a@b.co')
    fireEvent.click(screen.getByRole('button', { name: /send a new link/i }))
    await screen.findByText(/on its way/i)
    expect(resendVerification).toHaveBeenCalled()
  })

  it('re-checks, and says so when still unconfirmed', async () => {
    const onConfirmed = vi.fn().mockResolvedValue(undefined)
    page({}, onConfirmed)
    fireEvent.click(screen.getByRole('button', { name: /i've confirmed/i }))
    await screen.findByText(/not confirmed yet/i)
    expect(onConfirmed).toHaveBeenCalled()
  })
})
