import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

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
            characterName: 'Akari',
            aiProvider: 'openai',
            aiIsRemote: true,
            privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
          },
        }}
      />,
    )
    expect(screen.getByTestId('status').textContent).toBe('Thinking')
    expect(screen.getByText('AI: openai (remote)')).toBeTruthy()
  })
})
