// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api } from './api'
import { Preferences } from './Preferences'

afterEach(cleanup)

const prefs = { include_titles: [], exclude_titles: [], locations: [], remote_regions: [], extra_skills: [],
  years_experience: null, include_presales: false }
const fakeApi = () => ({
  getPreferences: vi.fn().mockResolvedValue(prefs),
  listResumes: vi.fn().mockResolvedValue([]),
  listPlaces: vi.fn().mockResolvedValue([]),
  listSkills: vi.fn().mockResolvedValue([{ name: 'Kubernetes', aliases: ['k8s'] }]),
  savePreferences: vi.fn().mockResolvedValue(prefs),
})
const tick = () => new Promise((r) => setTimeout(r, 0))

describe('chip lists', () => {
  it('a comma turns typing into chips, and leftovers still save', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    const box = await screen.findByLabelText('Job titles to include')
    fireEvent.change(box, { target: { value: 'backend, plat' } })
    screen.getByText('backend')
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0].include_titles).toEqual(['backend', 'plat'])
  })

  it('removes a chip', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    fireEvent.change(await screen.findByLabelText('Job titles to exclude'), { target: { value: 'senior,' } })
    fireEvent.click(screen.getByRole('button', { name: 'Remove senior' }))
    expect(screen.queryByRole('button', { name: 'Remove senior' })).toBeNull()
  })

  it('names skills properly and flags unknown ones', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    const box = await screen.findByLabelText('Extra skills')
    await tick()
    fireEvent.change(box, { target: { value: 'k8s' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    screen.getByText('Kubernetes')
    fireEvent.change(box, { target: { value: 'Kubernetis' } })
    fireEvent.keyDown(box, { key: 'Enter' })
    screen.getByText(/not a known skill/i)
  })
})
