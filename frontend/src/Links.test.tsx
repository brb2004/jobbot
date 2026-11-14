// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Api, Links } from './api'
import { LinksBar, LinksEditor } from './Links'

afterEach(cleanup)
const mine: Links = { linkedin: 'https://linkedin.com/in/me', github: 'https://github.com/me', website: null }
const fakeApi = (links: Links = mine) =>
  ({ getLinks: vi.fn().mockResolvedValue(links), saveLinks: vi.fn(async (l: Links) => l) }) as unknown as Api

describe('links', () => {
  it('copies a saved link in one click', async () => {
    const user = userEvent.setup()
    render(<LinksBar api={fakeApi()} />)
    await user.click(await screen.findByRole('button', { name: 'GitHub' }))
    expect(await navigator.clipboard.readText()).toBe('https://github.com/me')
    expect(screen.getByRole('button', { name: 'GitHub copied ✓' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Website' })).toBeNull()
  })

  it('offers to add links when there are none', async () => {
    const onEdit = vi.fn()
    render(<LinksBar api={fakeApi({ linkedin: null, github: null, website: null })} onEdit={onEdit} />)
    await userEvent.click(await screen.findByRole('button', { name: /Add your LinkedIn/ }))
    expect(onEdit).toHaveBeenCalled()
  })

  it('saves edited links', async () => {
    const api = fakeApi()
    render(<LinksEditor api={api} />)
    await userEvent.type(await screen.findByLabelText('Website'), 'me.dev')
    await userEvent.click(screen.getByRole('button', { name: 'Save links' }))
    expect(api.saveLinks).toHaveBeenCalledWith({ ...mine, website: 'me.dev' })
    expect(await screen.findByText('Links saved.')).toBeTruthy()
  })
})
