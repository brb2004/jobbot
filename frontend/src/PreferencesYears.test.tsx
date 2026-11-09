// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(cleanup)
import type { Api } from './api'
import { Preferences } from './Preferences'

const prefs = (years: number | null) => ({
  include_titles: [], exclude_titles: [], locations: [], remote_regions: [], extra_skills: [],
  years_experience: years, include_presales: false,
})
const fakeApi = (years: number | null, detected: number) => ({
  getPreferences: vi.fn().mockResolvedValue(prefs(years)),
  savePreferences: vi.fn().mockResolvedValue(undefined),
  listResumes: vi.fn().mockResolvedValue([{ id: 'r1', filename: 'cv.docx', years_detected: detected }]),
}) as unknown as Api

describe('years of experience vs. the resume', () => {
  it('says when your value overrides the resume, and switches back', async () => {
    render(<Preferences api={fakeApi(0, 3)} onSaved={() => {}} />)
    await screen.findByText(/your resume shows 3/i)
    fireEvent.click(screen.getByRole('button', { name: /use resume/i }))
    expect((screen.getByLabelText(/years of experience/i) as HTMLInputElement).value).toBe('')
    screen.getByText(/using 3 from your resume/i)
  })

  it('stays quiet when they agree', async () => {
    render(<Preferences api={fakeApi(3, 3)} onSaved={() => {}} />)
    await screen.findByLabelText(/years of experience/i)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText(/your resume shows/i)).toBeNull()
  })
})
