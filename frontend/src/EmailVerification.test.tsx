// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { CheckEmail } from './CheckEmail'
import { Verify } from './Verify'

afterEach(() => { cleanup(); vi.useRealTimers() })

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
    expect(screen.queryByRole('button', { name: /i've confirmed/i })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /send a new link/i }))
    await screen.findByText(/on its way/i)
    expect(resendVerification).toHaveBeenCalled()
  })

  it('checks again on its own every few seconds', () => {
    vi.useFakeTimers()
    const onConfirmed = vi.fn().mockResolvedValue(undefined)
    page({}, onConfirmed)
    expect(onConfirmed).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(5000) })
    expect(onConfirmed).toHaveBeenCalledTimes(1)
  })

  it('checks right away when you come back to the tab', () => {
    const onConfirmed = vi.fn().mockResolvedValue(undefined)
    page({}, onConfirmed)
    fireEvent.focus(window)
    expect(onConfirmed).toHaveBeenCalled()
  })
})
