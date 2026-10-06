import { describe, expect, it } from 'vitest'

import {
  type AppAction,
  type AppState,
  appReducer,
  initialAppState,
  selectCanSend,
  selectDisplayStatus,
} from './appState'

const run = (actions: AppAction[], from: AppState = initialAppState): AppState =>
  actions.reduce(appReducer, from)

const connected = run([{ type: 'connection_changed', status: 'connected' }])

describe('appReducer', () => {
  it('stores session info from session_ready', () => {
    const state = run(
      [
        {
          type: 'server_event',
          event: {
            type: 'session_ready',
            protocol_version: 1,
            character_name: 'Akari',
            ai_provider: 'mock',
            ai_is_remote: false,
            privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
            state: 'idle',
          },
        },
      ],
      connected,
    )
    expect(state.session?.characterName).toBe('Akari')
  })

  it('tracks a full turn', () => {
    const state = run(
      [
        { type: 'user_message_sent', text: 'hola' },
        { type: 'server_event', event: { type: 'state_changed', state: 'thinking' } },
        {
          type: 'server_event',
          event: {
            type: 'assistant_message',
            text: 'Hola, estoy funcionando.',
            emotion: 'happy',
            emotion_intensity: 0.8,
            gesture: 'nod',
            look_at_user: true,
          },
        },
        { type: 'server_event', event: { type: 'state_changed', state: 'speaking' } },
      ],
      connected,
    )
    expect(state.phase).toBe('speaking')
    expect(state.emotion).toBe('happy')
    expect(state.messages.map((m) => m.role)).toEqual(['user', 'assistant'])
    expect(new Set(state.messages.map((m) => m.id)).size).toBe(2)
  })

  it('stores errors and clears them on the next user message', () => {
    const withError = run(
      [{ type: 'server_event', event: { type: 'error', code: 'ai_timeout', message: 'Timeout' } }],
      connected,
    )
    expect(withError.lastError).toBe('Timeout')
    expect(run([{ type: 'user_message_sent', text: 'otra vez' }], withError).lastError).toBeNull()
  })
})

describe('selectors', () => {
  it('shows offline whenever the backend is not connected', () => {
    const thinking = run([{ type: 'server_event', event: { type: 'state_changed', state: 'thinking' } }])
    expect(selectDisplayStatus(thinking)).toBe('offline')
    expect(selectDisplayStatus({ ...thinking, connection: 'connected' })).toBe('thinking')
  })

  it('blocks sending while offline or thinking', () => {
    expect(selectCanSend(initialAppState)).toBe(false)
    expect(selectCanSend(connected)).toBe(true)
    expect(selectCanSend({ ...connected, phase: 'thinking' })).toBe(false)
  })
})
