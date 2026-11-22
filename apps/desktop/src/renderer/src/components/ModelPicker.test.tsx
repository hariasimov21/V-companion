import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ModelPicker } from './ModelPicker'

const models = ['gpt-oss:latest', 'mistral-nemo:latest', 'qwen3:14b']

afterEach(cleanup)

describe('ModelPicker', () => {
  it('shows the current model and requests a switch', () => {
    const onSelect = vi.fn()
    render(<ModelPicker models={models} currentModel="gpt-oss:latest" disabled={false} onSelect={onSelect} />)
    const select = screen.getByLabelText<HTMLSelectElement>('Modelo')
    expect(select.value).toBe('gpt-oss:latest')
    fireEvent.change(select, { target: { value: 'mistral-nemo:latest' } })
    expect(onSelect).toHaveBeenCalledWith('mistral-nemo:latest')
  })

  it('is disabled while busy or loading', () => {
    render(<ModelPicker models={models} currentModel="qwen3:14b" disabled onSelect={() => {}} />)
    expect(screen.getByLabelText<HTMLSelectElement>('Modelo').disabled).toBe(true)
  })
})
