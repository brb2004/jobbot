// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api, Preferences as Prefs } from './api'
import { Preferences } from './Preferences'

afterEach(cleanup)
const saved: Prefs = {
  include_titles: ['engineer'], exclude_titles: ['senior'], locations: ['remote'],
  remote_regions: ['us'], years_experience: 1, extra_skills: [], include_presales: false,
}
const fakeApi = (o: Partial<Api> = {}) =>
  ({ getPreferences: vi.fn().mockResolvedValue(saved), savePreferences: vi.fn(async (p: Prefs) => p), ...o }) as unknown as Api

describe('Preferences', () => {
  it('loads saved preferences into the form', async () => {
    render(<Preferences api={fakeApi()} onSaved={vi.fn()} />)
    expect(await screen.findByText('engineer')).toBeTruthy()          // saved entries are chips now
    expect((screen.getByLabelText('Years of experience') as HTMLInputElement).value).toBe('1')
  })

  it('saves edited comma lists as arrays and blank years as null', async () => {
    const api = fakeApi()
    const onSaved = vi.fn()
    render(<Preferences api={api} onSaved={onSaved} />)
    const exclude = await screen.findByLabelText('Job titles to exclude')
    await userEvent.clear(exclude)
    await userEvent.type(exclude, 'senior,  staff , ')
    await userEvent.clear(screen.getByLabelText('Years of experience'))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(api.savePreferences).toHaveBeenCalledWith({ ...saved, exclude_titles: ['senior', 'staff'], years_experience: null })
    expect(onSaved).toHaveBeenCalled()
  })
})

describe('delete account', () => {
  it('needs a second click to confirm, then deletes and signs out', async () => {
    const deleteAccount = vi.fn().mockResolvedValue(undefined)
    const onDeleted = vi.fn()
    render(<Preferences api={fakeApi({ deleteAccount })} onSaved={vi.fn()} onDeleted={onDeleted} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete my account' }))
    expect(deleteAccount).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Yes, delete everything' }))
    expect(deleteAccount).toHaveBeenCalled()
    expect(onDeleted).toHaveBeenCalled()
  })
})

describe('presales category', () => {
  it('opting in saves include_presales: true', async () => {
    const api = fakeApi()
    render(<Preferences api={api} onSaved={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText(/Include sales & pre-sales roles/))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(api.savePreferences).toHaveBeenCalledWith({ ...saved, include_presales: true })
  })
})
