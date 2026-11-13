// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
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
    await userEvent.upload(await screen.findByLabelText('Resume (PDF, Word .docx, or plain text)'), pdf)
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(uploadResume).toHaveBeenCalledWith(pdf, {})
    expect(onDone).toHaveBeenCalled()
  })

  it('cannot upload before a file is chosen', () => {
    render(<Upload api={fakeApi({})} onDone={vi.fn()} />)
    return screen.findByRole('button', { name: 'Upload' })
      .then((b) => expect((b as HTMLButtonElement).disabled).toBe(true))
  })

  it('shows the server error', async () => {
    const uploadResume = vi.fn().mockRejectedValue(new ApiError(415, 'Only PDF or DOCX files'))
    render(<Upload api={fakeApi({ uploadResume })} onDone={vi.fn()} />)
    await userEvent.upload(await screen.findByLabelText('Resume (PDF, Word .docx, or plain text)'), pdf)
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
    expect(await screen.findByText(/Relevant experience detected: 3 years/)).toBeTruthy()
  })
})

describe('two resumes', () => {
  const two = [
    { id: 'r1aaaaaaaa', name: 'Backend', filename: 'be.pdf', own: { include_titles: null, exclude_titles: null, years_experience: null } },
    { id: 'r2bbbbbbbb', name: 'DevOps', filename: 'ops.pdf', own: { include_titles: ['devops'], exclude_titles: null, years_experience: 2 } },
  ]

  it('adds a second one under a name', async () => {
    const uploadResume = vi.fn().mockResolvedValue({ id: 'r2' })
    const listResumes = vi.fn().mockResolvedValue([two[0]])
    render(<Upload api={fakeApi({ uploadResume, listResumes })} onDone={vi.fn()} />)
    expect(await screen.findByText('Add a second resume')).toBeTruthy()
    await userEvent.upload(screen.getByLabelText('Resume (PDF, Word .docx, or plain text)'), pdf)
    await userEvent.type(screen.getByLabelText('Name (optional)'), 'DevOps')
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(uploadResume).toHaveBeenCalledWith(pdf, { name: 'DevOps' })
  })

  it('has no add form at two, and saves one resume\'s own titles', async () => {
    const updateResume = vi.fn().mockResolvedValue(two[1])
    render(<Upload api={fakeApi({ listResumes: vi.fn().mockResolvedValue(two), updateResume })} onDone={vi.fn()} />)
    const ops = await screen.findByRole('region', { name: 'DevOps' })
    expect(screen.queryByText('Add a second resume')).toBeNull()
    expect(within(ops).getByText('devops')).toBeTruthy()
    await userEvent.type(within(ops).getByLabelText('Job titles for this resume'), 'platform,')
    await userEvent.click(within(ops).getByRole('button', { name: 'Save' }))
    expect(updateResume).toHaveBeenCalledWith('r2bbbbbbbb', {
      name: 'DevOps', own: { include_titles: ['devops', 'platform'], exclude_titles: null, years_experience: 2 } })
    expect(await within(ops).findByText(/Saved/)).toBeTruthy()
  })

  it('replaces one file in place', async () => {
    const uploadResume = vi.fn().mockResolvedValue({ id: 'r3' })
    const onDone = vi.fn()
    render(<Upload api={fakeApi({ listResumes: vi.fn().mockResolvedValue(two), uploadResume })} onDone={onDone} />)
    const be = await screen.findByRole('region', { name: 'Backend' })
    await userEvent.upload(within(be).getByLabelText(/Replace the file/), pdf)
    await userEvent.click(within(be).getByRole('button', { name: 'Replace' }))
    expect(uploadResume).toHaveBeenCalledWith(pdf, { replace: 'r1aaaaaaaa' })
    expect(onDone).toHaveBeenCalled()
  })
})
