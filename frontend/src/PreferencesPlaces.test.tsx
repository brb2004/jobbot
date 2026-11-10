// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api } from './api'
import { Preferences } from './Preferences'

afterEach(cleanup)

const prefs = { include_titles: [], exclude_titles: [], locations: ['remote'], remote_regions: ['us'],
  extra_skills: [], years_experience: null, include_presales: false }
const places = [
  { name: 'United States', aliases: ['us', 'usa', 'america'] },
  { name: 'Dallas-Fort Worth', aliases: ['dallas', 'plano', 'richardson'] },
]
const fakeApi = () => ({
  getPreferences: vi.fn().mockResolvedValue(prefs),
  listResumes: vi.fn().mockResolvedValue([]),
  listPlaces: vi.fn().mockResolvedValue(places),
  savePreferences: vi.fn().mockResolvedValue(prefs),
})
const save = () => fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

describe('location pickers', () => {
  it('shows saved text as the right checkboxes', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    expect((await screen.findByLabelText('Remote') as HTMLInputElement).checked).toBe(true)
    expect((await screen.findByLabelText('United States') as HTMLInputElement).checked).toBe(true)   // "us"
    expect((screen.getByLabelText('Canada') as HTMLInputElement).checked).toBe(false)
  })

  it('adds a place by any alias and saves its canonical name', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    await screen.findByLabelText('United States')
    fireEvent.change(screen.getByLabelText('Locations'), { target: { value: 'plano' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to Locations' }))
    screen.getByText('Dallas-Fort Worth')
    save()
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0].locations).toEqual(['remote', 'Dallas-Fort Worth'])
  })

  it('keeps a typed place even without pressing Add', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    fireEvent.change(await screen.findByLabelText('Locations'), { target: { value: 'Austin' } })
    save()
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0].locations).toEqual(['remote', 'Austin'])
  })

  it('unchecking a region removes every spelling of it', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    fireEvent.click(await screen.findByLabelText('United States'))
    save()
    await vi.waitFor(() => expect(api.savePreferences).toHaveBeenCalled())
    expect(api.savePreferences.mock.calls[0][0].remote_regions).toEqual([])
  })
})
