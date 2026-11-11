// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Feedback } from './Feedback'

afterEach(cleanup)

const type = (text: string) => fireEvent.change(screen.getByRole('textbox'), { target: { value: text } })

describe('Feedback', () => {
  it('sends a report and shows its reference number', async () => {
    const sendFeedback = vi.fn().mockResolvedValue({ ref: 'AB12CD34', detail: 'ok' })
    render(<Feedback api={{ sendFeedback } as unknown as Api} />)
    fireEvent.click(screen.getByLabelText(/feature idea/i))
    type('Let me hide companies')
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    await screen.findByText(/#AB12CD34/)
    expect(sendFeedback).toHaveBeenCalledWith({ kind: 'idea', message: 'Let me hide companies' })
  })

  it('needs a real message and shows the rate-limit error', async () => {
    const sendFeedback = vi.fn().mockRejectedValue(new ApiError(429, "You've sent a lot of reports this hour. Try again later."))
    render(<Feedback api={{ sendFeedback } as unknown as Api} />)
    type('hi')
    expect(screen.getByRole('button', { name: /send/i })).toHaveProperty('disabled', true)
    type('It broke again')
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    await screen.findByText(/a lot of reports this hour/i)
  })
})
