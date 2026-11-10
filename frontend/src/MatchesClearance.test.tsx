// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, it, vi } from 'vitest'
import type { Api, Match } from './api'
import { Matches } from './Matches'

afterEach(cleanup)

it('flags roles that may need a clearance', async () => {
  const match: Match = { job_id: 'j1', title: 'Platform Engineer', score: 0.5, tier: 'Strong match', company: 'acme',
    location: 'Remote', years_note: null, url: null,
    detail: { met: ['Python'], partial: [], missing: [], soft: [], clearance: true } }
  const api = { matches: vi.fn().mockResolvedValue([match]), listResumes: vi.fn().mockResolvedValue([]) } as unknown as Api
  render(<Matches api={api} />)
  await screen.findByText(/may require clearance/i)
})
