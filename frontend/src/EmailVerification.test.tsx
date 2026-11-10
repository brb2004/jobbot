// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Verify } from './Verify'
import { VerifyBanner } from './VerifyBanner'

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

describe('banner', () => {
  it('shows for an unconfirmed address and re-sends', async () => {
    const resendVerification = vi.fn().mockResolvedValue(undefined)
    const me = vi.fn().mockResolvedValue({ id: 'u', email: 'a@b.co', email_verified_at: null })
    render(<VerifyBanner api={{ me, resendVerification } as unknown as Api} />)
    fireEvent.click(await screen.findByRole('button', { name: /send a new link/i }))
    await screen.findByText(/on its way/i)
    expect(resendVerification).toHaveBeenCalled()
  })

  it('stays hidden once confirmed', async () => {
    const me = vi.fn().mockResolvedValue({ id: 'u', email: 'a@b.co', email_verified_at: '2026-11-10T00:00:00Z' })
    render(<VerifyBanner api={{ me } as unknown as Api} />)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText(/confirm your email/i)).toBeNull()
  })
})
