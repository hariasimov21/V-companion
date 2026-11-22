import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CharacterPicker } from './CharacterPicker'

const characters = [
  { id: 'akari', name: 'Akari' },
  { id: 'mimi', name: 'Mimi' },
]

afterEach(cleanup)

describe('CharacterPicker', () => {
  it('shows the current character and requests a switch', () => {
    const onSelect = vi.fn()
    render(<CharacterPicker characters={characters} currentId="akari" disabled={false} onSelect={onSelect} />)
    const select = screen.getByLabelText<HTMLSelectElement>('Character')
    expect(select.value).toBe('akari')
    fireEvent.change(select, { target: { value: 'mimi' } })
    expect(onSelect).toHaveBeenCalledWith('mimi')
  })

  it('is disabled while busy or when there is nothing to pick', () => {
    const { rerender } = render(
      <CharacterPicker characters={characters} currentId="akari" disabled onSelect={() => {}} />,
    )
    expect(screen.getByLabelText<HTMLSelectElement>('Character').disabled).toBe(true)
    rerender(
      <CharacterPicker characters={characters.slice(0, 1)} currentId="akari" disabled={false} onSelect={() => {}} />,
    )
    expect(screen.getByLabelText<HTMLSelectElement>('Character').disabled).toBe(true)
  })
})
