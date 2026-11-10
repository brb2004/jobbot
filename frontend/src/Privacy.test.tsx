// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, it } from 'vitest'
import { Privacy } from './Privacy'

afterEach(cleanup)

it('says what is stored and how to delete it', () => {
  render(<Privacy />)
  screen.getByRole('heading', { name: 'What we store' })
  screen.getByText(/never sent to an AI service/i)
  screen.getByText(/delete account removes your account/i)
})
