// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api } from './api'
import { Preferences } from './Preferences'

afterEach(cleanup)

const prefs = { include_titles: ['backend'], exclude_titles: ['sales', 'senior'], locations: [], remote_regions: [],
  extra_skills: [], years_experience: null, include_presales: false }
const fakeApi = () => ({
  getPreferences: vi.fn().mockResolvedValue(prefs),
  listResumes: vi.fn().mockResolvedValue([]),
  savePreferences: vi.fn().mockResolvedValue(prefs),
})
const value = (label: string) => (screen.getByLabelText(label) as HTMLTextAreaElement).value

describe('editing preferences', () => {
  it('marks unsaved edits, reports them, and can discard them', async () => {
    const onDirty = vi.fn()
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} onDirty={onDirty} />)
    fireEvent.change(await screen.findByLabelText('Extra skills'), { target: { value: 'Go' } })
    screen.getByText(/unsaved changes/i)
    expect(onDirty).toHaveBeenLastCalledWith(true)
    fireEvent.click(screen.getByRole('button', { name: /discard/i }))
    expect(value('Extra skills')).toBe('')
    expect(screen.queryByText(/unsaved changes/i)).toBeNull()
  })

  it('warns when the exclude list cancels the sales checkbox', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    fireEvent.click(await screen.findByLabelText(/include sales/i))
    screen.getByText(/still hide some of these: sales/i)
  })

  it('refuses letters in years instead of silently using the resume', async () => {
    const api = fakeApi()
    render(<Preferences api={api as unknown as Api} onSaved={() => {}} />)
    fireEvent.change(await screen.findByLabelText(/years of experience/i), { target: { value: 'ab' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await screen.findByText(/whole number/i)
    expect(api.savePreferences).not.toHaveBeenCalled()
  })

  it('resets job titles to the defaults', async () => {
    render(<Preferences api={fakeApi() as unknown as Api} onSaved={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: /reset job titles/i }))
    expect(value('Job titles to include')).toBe('')
    expect(value('Job titles to exclude')).toBe('')
  })
})
