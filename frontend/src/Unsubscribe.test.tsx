// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Unsubscribe } from './Unsubscribe'

afterEach(cleanup)

describe('Unsubscribe', () => {
  it('does nothing until clicked, then can undo', async () => {
    const unsubscribe = vi.fn().mockResolvedValue(undefined)
    const resubscribe = vi.fn().mockResolvedValue(undefined)
    render(<Unsubscribe api={{ unsubscribe, resubscribe } as unknown as Api} token="tok" />)
    expect(unsubscribe).not.toHaveBeenCalled()                     // opening the link isn't enough
    await userEvent.click(screen.getByRole('button', { name: 'Unsubscribe' }))
    expect(unsubscribe).toHaveBeenCalledWith('tok')
    await screen.findByText(/won't get the weekly email/i)
    await userEvent.click(screen.getByRole('button', { name: /resubscribe/i }))
    expect(resubscribe).toHaveBeenCalledWith('tok')
    await screen.findByText(/subscribed again/i)
  })

  it('explains a bad link', async () => {
    const unsubscribe = vi.fn().mockRejectedValue(new ApiError(400, "This unsubscribe link isn't valid."))
    render(<Unsubscribe api={{ unsubscribe } as unknown as Api} token="bad" />)
    await userEvent.click(screen.getByRole('button', { name: 'Unsubscribe' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/isn't valid/)
  })
})
