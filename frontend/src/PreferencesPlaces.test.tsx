// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api } from './api'
import { Preferences } from './Preferences'

afterEach(cleanup)

const prefs = { include_titles: [], exclude_titles: [], locations: ['dallas'], remote: true, onsite: true,
  extra_skills: [], years_experience: null, include_presales: false }
const places = [
  { name: 'Dallas-Fort Worth', label: 'Dallas-Fort Worth, TX', kind: 'metro', aliases: ['dallas', 'plano'] },
  { name: 'United States', kind: 'country', aliases: ['us', 'usa'] },
]
const fakeApi = () => ({
  getPreferences: vi.fn().mockResolvedValue(prefs),
  listResumes: vi.fn().mockResolvedValue([]),
  listPlaces: vi.fn().mockResolvedValue(places),
  listSkills: vi.fn().mockResolvedValue([]),
  savePreferences: vi.fn().mockResolvedValue(prefs),
})
const save = () => fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

describe('work setup and locations', () => {
  it('shows a saved spelling as its City, State label', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    await screen.findByText('Dallas-Fort Worth, TX')
    expect((screen.getByLabelText('Remote') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('On-site or hybrid') as HTMLInputElement).checked).toBe(true)
  })

  it('saves "no remote"', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    fireEvent.click(await screen.findByLabelText('Remote'))
    save()
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0]).toMatchObject({ remote: false, onsite: true })
  })

  it('needs at least one setup checked', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    fireEvent.click(await screen.findByLabelText('Remote'))
    fireEvent.click(screen.getByLabelText('On-site or hybrid'))
    save()
    await screen.findByText(/pick on-site, remote, or both/i)
    expect(api.savePreferences).not.toHaveBeenCalled()
  })

  it('adds a place by alias and saves its canonical name', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    await screen.findByText('Dallas-Fort Worth, TX')
    fireEvent.change(screen.getByLabelText('Locations'), { target: { value: 'usa' } })
    fireEvent.keyDown(screen.getByLabelText('Locations'), { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Add to Locations' }))
    save()
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0].locations).toEqual(['dallas', 'United States'])
  })
})
