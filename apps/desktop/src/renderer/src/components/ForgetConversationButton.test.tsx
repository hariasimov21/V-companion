import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ForgetConversationButton } from './ForgetConversationButton'

afterEach(cleanup)

describe('ForgetConversationButton', () => {
  it('asks for confirmation before forgetting', () => {
    const onConfirm = vi.fn()
    render(<ForgetConversationButton characterName="Akari" disabled={false} onConfirm={onConfirm} />)

    fireEvent.click(screen.getByText('Olvidar conversación'))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.getByText(/Olvidar todo lo hablado con Akari/)).toBeTruthy()

    fireEvent.click(screen.getByText('Sí, olvidar'))
    expect(onConfirm).toHaveBeenCalledOnce()
    expect(screen.getByText('Olvidar conversación')).toBeTruthy()
  })

  it('can be cancelled', () => {
    const onConfirm = vi.fn()
    render(<ForgetConversationButton characterName="Akari" disabled={false} onConfirm={onConfirm} />)
    fireEvent.click(screen.getByText('Olvidar conversación'))
    fireEvent.click(screen.getByText('Cancelar'))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.queryByText('Sí, olvidar')).toBeNull()
  })

  it('is disabled when there is nothing to forget or the AI is busy', () => {
    render(<ForgetConversationButton characterName="Akari" disabled onConfirm={() => {}} />)
    expect(screen.getByText<HTMLButtonElement>('Olvidar conversación').disabled).toBe(true)
  })
})
