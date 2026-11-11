// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api, type Match } from './api'
import { Matches } from './Matches'

afterEach(cleanup)
const fakeApi = (matches: () => Promise<Match[]>) => ({ matches: vi.fn(matches) }) as unknown as Api
const m: Match = {
  job_id: '1', title: 'Backend Engineer', score: 0.5, tier: 'Strong match', company: 'stripe', location: 'Remote, US', years_note: 'asks for 5+ years', url: 'https://x/1',
  detail: { met: ['Python', 'Go'], partial: [], missing: ['Kafka'], soft: [], years_asked: 5 },
}

describe('Matches', () => {
  it('shows each match with tier, link, skills and years flag', async () => {
    render(<Matches api={fakeApi(async () => [m])} />)
    const link = await screen.findByRole('link', { name: 'Backend Engineer' })
    expect(link.getAttribute('href')).toBe('https://x/1')
    expect(screen.getByText('Strong match')).toBeTruthy()
    expect(screen.getByText('2 of 3 skills')).toBeTruthy()
    expect(screen.getByText('Python, Go')).toBeTruthy()
    expect(screen.getByText('Kafka')).toBeTruthy()
    expect(screen.getByText('asks for 5+ years')).toBeTruthy()
    expect(screen.getByText('Stripe · Remote, US')).toBeTruthy()
    expect(screen.getByText('#1')).toBeTruthy()
  })

  it('tells new users what to do when there are no matches', async () => {
    render(<Matches api={fakeApi(async () => [])} />)
    expect(await screen.findByRole('button', { name: /upload your resume/i })).toBeTruthy()
  })

  it('shows the server error', async () => {
    render(<Matches api={fakeApi(async () => { throw new ApiError(401, 'Not authenticated') })} />)
    expect((await screen.findByRole('alert')).textContent).toBe('Not authenticated')
  })
})
