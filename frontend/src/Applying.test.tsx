// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api, Application, Match } from './api'
import { Applied } from './Applied'
import { Matches } from './Matches'

afterEach(cleanup)

const match = (id: string, title: string): Match => ({ job_id: id, title, score: 0.5, tier: 'Strong match',
  company: 'acme', location: 'Remote', years_note: null, url: `https://x/${id}`,
  detail: { met: [], partial: [], missing: [], soft: [] } })

describe('applying from Matches', () => {
  it('asks after opening a posting, then moves it to Applied and refills the list', async () => {
    const matches = vi.fn()
      .mockResolvedValueOnce([match('a', 'Backend A'), match('b', 'Backend B')])
      .mockResolvedValueOnce([match('b', 'Backend B'), match('c', 'Backend C')])
    const markApplied = vi.fn().mockResolvedValue(undefined)
    const api = { matches, markApplied, listResumes: vi.fn().mockResolvedValue([{ id: 'r' }]) } as unknown as Api
    render(<Matches api={api} />)
    fireEvent.click((await screen.findAllByRole('link', { name: /apply/i }))[0])
    fireEvent.click(screen.getByRole('button', { name: /yes, move to applied/i }))
    await screen.findByText('Backend C')                              // next match moved up
    expect(markApplied).toHaveBeenCalledWith('a')
    expect(screen.queryByText('Backend A')).toBeNull()
    screen.getByText(/moved “backend a” to applied/i)
  })

  it('"Not yet" leaves it in place', async () => {
    const api = { matches: vi.fn().mockResolvedValue([match('a', 'Backend A')]), markApplied: vi.fn(),
      listResumes: vi.fn().mockResolvedValue([{ id: 'r' }]) } as unknown as Api
    render(<Matches api={api} />)
    fireEvent.click(await screen.findByRole('link', { name: /apply/i }))
    fireEvent.click(screen.getByRole('button', { name: /not yet/i }))
    screen.getByRole('link', { name: /apply/i })
    expect(api.markApplied).not.toHaveBeenCalled()
  })
})

describe('Applied tab', () => {
  const app = (closed: boolean): Application => ({ job_id: 'a', title: 'Backend A', company: 'acme',
    location: 'Remote', url: 'https://x/a', closed, applied_at: '2026-11-10T18:00:00Z' })

  it('lists applied jobs, flags closed postings, and moves one back', async () => {
    const unmarkApplied = vi.fn().mockResolvedValue(undefined)
    const applications = vi.fn().mockResolvedValueOnce([app(true)]).mockResolvedValueOnce([])
    render(<Applied api={{ applications, unmarkApplied } as unknown as Api} />)
    await screen.findByText('Backend A')
    screen.getByText('Closed')
    fireEvent.click(screen.getByRole('button', { name: /move back to matches/i }))
    await screen.findByText(/nothing here yet/i)
    expect(unmarkApplied).toHaveBeenCalledWith('a')
  })
})
