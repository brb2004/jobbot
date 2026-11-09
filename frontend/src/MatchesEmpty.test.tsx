// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api } from './api'
import { Matches } from './Matches'

afterEach(cleanup)

const fakeApi = (resumes: unknown[]) => ({
  matches: vi.fn().mockResolvedValue([]),
  listResumes: vi.fn().mockResolvedValue(resumes),
}) as unknown as Api

describe('no matches', () => {
  it('points to Preferences when a resume is already uploaded', async () => {
    const onPreferences = vi.fn()
    render(<Matches api={fakeApi([{ id: 'r1', filename: 'cv.docx' }])} onPreferences={onPreferences} />)
    fireEvent.click(await screen.findByRole('button', { name: /loosen your preferences/i }))
    expect(onPreferences).toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /upload your resume/i })).toBeNull()
  })

  it('asks for a resume when there is none', async () => {
    render(<Matches api={fakeApi([])} />)
    await screen.findByRole('button', { name: /upload your resume/i })
  })
})
