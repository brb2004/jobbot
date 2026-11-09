// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(cleanup)
import type { Api } from './api'
import { Upload } from './Upload'

const fakeApi = (own: number | null) => ({
  listResumes: vi.fn().mockResolvedValue([{ id: 'r1', filename: 'cv.docx', years_detected: 3 }]),
  getPreferences: vi.fn().mockResolvedValue({ years_experience: own }),
}) as unknown as Api

describe('detected experience note', () => {
  it('explains the fallback when your years field is blank', async () => {
    render(<Upload api={fakeApi(null)} onDone={() => {}} />)
    await screen.findByText(/used when "years of experience"/i)
  })

  it('drops the note when you set your own years', async () => {
    render(<Upload api={fakeApi(2)} onDone={() => {}} />)
    await screen.findByText(/detected experience: 3 years/i)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.queryByText(/used when/i)).toBeNull()
  })
})
