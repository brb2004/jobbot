// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChipInput } from './ChipInput'

afterEach(cleanup)

const OPTIONS = [
  { name: 'Dallas-Fort Worth', kind: 'metro', aliases: ['dallas', 'plano', 'richardson'], detail: 'includes Plano' },
  { name: 'Canada', kind: 'country', aliases: [] },
  { name: 'Europe', kind: 'region', aliases: ['eu'] },
]
const canon = (v: string) => OPTIONS.find((o) => o.name.toLowerCase() === v.toLowerCase()
  || o.aliases.includes(v.toLowerCase()))?.name

function Harness({ start = [] as string[] }) {
  const [values, setValues] = useState(start)
  const [pending, setPending] = useState('')
  return (
    <>
      <ChipInput id="loc" label="Locations" hint="" values={values} onValues={setValues} pending={pending}
                 onPending={setPending} options={OPTIONS} canon={canon} />
      <output data-testid="saved">{JSON.stringify(values)}</output>
    </>
  )
}

describe('chip input', () => {
  it('shows one chip per place no matter how many spellings were saved', () => {
    render(<Harness start={['dallas', 'plano', 'dfw-typo']} />)
    expect(screen.getAllByText('Dallas-Fort Worth')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Remove Dallas-Fort Worth' }))
    expect(screen.getByTestId('saved').textContent).toBe('["dfw-typo"]')
  })

  it('suggests by alias, grouped, and picks with the keyboard', () => {
    render(<Harness />)
    const box = screen.getByLabelText('Locations')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'pla' } })
    screen.getByText('Cities & metros')
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(screen.getByTestId('saved').textContent).toBe('["Dallas-Fort Worth"]')
  })

  it('picks with a click', () => {
    render(<Harness />)
    const box = screen.getByLabelText('Locations')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'eu' } })
    fireEvent.mouseDown(screen.getByRole('option', { name: 'Europe' }))
    expect(screen.getByTestId('saved').textContent).toBe('["Europe"]')
  })
})
