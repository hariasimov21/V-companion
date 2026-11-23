import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { initialAppState } from '../state/appState'
import { StatusBar } from './StatusBar'

afterEach(cleanup)

describe('StatusBar', () => {
  it('shows Offline and privacy indicators off by default', () => {
    render(<StatusBar state={initialAppState} />)
    expect(screen.getByTestId('status').textContent).toBe('Offline')
    expect(screen.getByText('Mic OFF')).toBeTruthy()
    expect(screen.getByText('Camera OFF')).toBeTruthy()
  })

  it('shows the backend phase and flags remote AI providers', () => {
    render(
      <StatusBar
        state={{
          ...initialAppState,
          connection: 'connected',
          phase: 'thinking',
          session: {
            characterId: 'akari',
            characterName: 'Akari',
            characters: [],
            aiProvider: 'openai',
            aiIsRemote: true,
            aiModel: null,
            aiModels: [],
            modelLoading: false,
            voiceAvailable: false,
            voiceEnabled: true,
            privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
          },
        }}
      />,
    )
    expect(screen.getByTestId('status').textContent).toBe('Thinking')
    expect(screen.getByText('AI: openai (remote)')).toBeTruthy()
  })

  it('toggles the voice when available', () => {
    const onToggleVoice = vi.fn()
    const session = {
      characterId: 'akari',
      characterName: 'Akari',
      characters: [],
      aiProvider: 'ollama',
      aiIsRemote: false,
      aiModel: null,
      aiModels: [],
      modelLoading: false,
      voiceAvailable: true,
      voiceEnabled: true,
      privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
    }
    const { rerender } = render(
      <StatusBar state={{ ...initialAppState, connection: 'connected', session }} onToggleVoice={onToggleVoice} />,
    )
    fireEvent.click(screen.getByText('Voz ON'))
    expect(onToggleVoice).toHaveBeenCalledWith(false)

    const onVoiceVolume = vi.fn()
    rerender(
      <StatusBar
        state={{ ...initialAppState, connection: 'connected', session }}
        voiceVolume={0.8}
        onVoiceVolume={onVoiceVolume}
      />,
    )
    const slider = screen.getByLabelText<HTMLInputElement>('Volumen de la voz')
    expect(screen.getByText('80%')).toBeTruthy()
    fireEvent.change(slider, { target: { value: '1.2' } })
    expect(onVoiceVolume).toHaveBeenCalledWith(1.2)

    rerender(
      <StatusBar
        state={{ ...initialAppState, connection: 'connected', session: { ...session, voiceAvailable: false } }}
        onToggleVoice={onToggleVoice}
      />,
    )
    expect(screen.getByText<HTMLButtonElement>('Voz —').disabled).toBe(true)
  })
})
