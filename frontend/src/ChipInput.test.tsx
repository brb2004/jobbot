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

describe('places with City, State labels', () => {
  const PLACES = [
    { name: 'Vancouver', label: 'Vancouver, BC', kind: 'metro', aliases: [] },
    { name: 'Vancouver WA', label: 'Vancouver, WA', kind: 'metro', aliases: ['vancouver washington'] },
  ]
  const placeCanon = (v: string) => PLACES.find((p) => [p.name, p.label].some((x) =>
    x.toLowerCase().replace(/[\s,]+/g, ' ') === v.toLowerCase().replace(/[\s,]+/g, ' ').trim()))?.name

  function Places() {
    const [values, setValues] = useState<string[]>([])
    const [pending, setPending] = useState('')
    const label = (n: string) => PLACES.find((p) => p.name === n)?.label ?? n
    return (
      <>
        <ChipInput id="p" label="Locations" hint="" values={values} onValues={setValues} pending={pending}
                   onPending={setPending} options={PLACES} canon={placeCanon} display={label} splitOnComma={false} />
        <output data-testid="saved">{JSON.stringify(values)}</output>
      </>
    )
  }

  it('lists both Vancouvers by City, State and keeps a typed comma in one entry', () => {
    render(<Places />)
    const box = screen.getByLabelText('Locations')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'vanc' } })
    screen.getByRole('option', { name: 'Vancouver, BC' })
    screen.getByRole('option', { name: /Vancouver, WA/ })
    fireEvent.change(box, { target: { value: 'Vancouver, WA' } })
    fireEvent.keyDown(box, { key: 'Escape' })
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(screen.getByTestId('saved').textContent).toBe('["Vancouver WA"]')
    screen.getByText('Vancouver, WA')
  })
})

describe('dropdown', () => {
  it('opens with the whole list on click and narrows as you type', () => {
    render(<Harness />)
    const box = screen.getByLabelText('Locations')
    fireEvent.click(box)
    fireEvent.focus(box)
    expect(screen.getAllByRole('option')).toHaveLength(3)
    screen.getByText('Countries')
    fireEvent.change(box, { target: { value: 'can' } })
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Canada'])
  })

  it('leaves out what you already picked', () => {
    render(<Harness start={['Europe']} />)
    fireEvent.focus(screen.getByLabelText('Locations'))
    expect(screen.queryByRole('option', { name: 'Europe' })).toBeNull()
  })
})
