// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type Api } from './api'
import { Upload } from './Upload'

afterEach(cleanup)
const fakeApi = (o: Partial<Api>) => ({ uploadResume: vi.fn(), listResumes: vi.fn().mockResolvedValue([]), ...o }) as unknown as Api
const pdf = new File(['%PDF-1.7'], 'cv.pdf', { type: 'application/pdf' })

describe('Upload', () => {
  it('uploads the chosen file', async () => {
    const uploadResume = vi.fn().mockResolvedValue({ id: 'r1' })
    const onDone = vi.fn()
    render(<Upload api={fakeApi({ uploadResume })} onDone={onDone} />)
    await userEvent.upload(screen.getByLabelText('Resume (PDF, Word .docx, or plain text)'), pdf)
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(uploadResume).toHaveBeenCalledWith(pdf)
    expect(onDone).toHaveBeenCalled()
  })

  it('cannot upload before a file is chosen', () => {
    render(<Upload api={fakeApi({})} onDone={vi.fn()} />)
    expect((screen.getByRole('button', { name: 'Upload' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the server error', async () => {
    const uploadResume = vi.fn().mockRejectedValue(new ApiError(415, 'Only PDF or DOCX files'))
    render(<Upload api={fakeApi({ uploadResume })} onDone={vi.fn()} />)
    await userEvent.upload(screen.getByLabelText('Resume (PDF, Word .docx, or plain text)'), pdf)
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Only PDF or DOCX files')
  })
})

describe('current resume', () => {
  it('shows the file you already uploaded', async () => {
    const listResumes = vi.fn().mockResolvedValue([{ id: 'r1', filename: 'cv.pdf' }])
    render(<Upload api={fakeApi({ listResumes })} onDone={vi.fn()} />)
    expect(await screen.findByText('Current: cv.pdf')).toBeTruthy()
  })
})

describe('detected experience', () => {
  it('shows the years read from the resume', async () => {
    const listResumes = vi.fn().mockResolvedValue([{ id: 'r1', filename: 'cv.pdf', years_detected: 3 }])
    render(<Upload api={fakeApi({ listResumes })} onDone={vi.fn()} />)
    expect(await screen.findByText(/Detected experience: 3 years/)).toBeTruthy()
  })
})
