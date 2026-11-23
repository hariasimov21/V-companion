import { describe, expect, it } from 'vitest'

import {
  type AppAction,
  type AppState,
  appReducer,
  initialAppState,
  selectCanClearConversation,
  selectCanSend,
  selectCanSwitchModel,
  selectDisplayStatus,
} from './appState'

const run = (actions: AppAction[], from: AppState = initialAppState): AppState =>
  actions.reduce(appReducer, from)

const connected = run([{ type: 'connection_changed', status: 'connected' }])

describe('appReducer', () => {
  it('stores session info and the restored chat from session_ready', () => {
    const state = run(
      [
        { type: 'user_message_sent', text: 'stale message from before a reconnect' },
        {
          type: 'server_event',
          event: {
            type: 'session_ready',
            protocol_version: 5,
            character_id: 'akari',
            character_name: 'Akari',
            characters: [
              { id: 'akari', name: 'Akari' },
              { id: 'mimi', name: 'Mimi' },
            ],
            history: [
              { role: 'user', text: 'hola' },
              { role: 'assistant', text: '¡Hola!', emotion: 'happy', gesture: 'wave' },
              { role: 'assistant', text: 'sin metadatos', emotion: null, gesture: null },
            ],
            ai_provider: 'mock',
            ai_is_remote: false,
            ai_model: 'gpt-oss:latest',
            ai_models: ['gpt-oss:latest', 'qwen3:14b'],
            ai_model_loading: false,
            voice_available: true,
            voice_enabled: true,
            privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
            state: 'idle',
          },
        },
      ],
      connected,
    )
    expect(state.session?.characterName).toBe('Akari')
    expect(state.session?.characters).toHaveLength(2)
    expect(state.messages.map((m) => m.text)).toEqual(['hola', '¡Hola!', 'sin metadatos'])
    expect(state.messages[1]).toMatchObject({ role: 'assistant', emotion: 'happy', gesture: 'wave' })
    expect(state.messages[2]).toMatchObject({ emotion: 'neutral', gesture: 'none' })
    expect(new Set(state.messages.map((m) => m.id)).size).toBe(3)
  })

  it("shows the new character's own conversation when the character changes", () => {
    const withSession: AppState = {
      ...connected,
      session: {
        characterId: 'akari',
        characterName: 'Akari',
        characters: [],
        aiProvider: 'mock',
        aiIsRemote: false,
        aiModel: null,
        aiModels: [],
        modelLoading: false,
        voiceAvailable: false,
        voiceEnabled: true,
        privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
      },
      emotion: 'happy',
      lastError: 'old error',
    }
    const state = run(
      [
        { type: 'user_message_sent', text: 'hola' },
        {
          type: 'server_event',
          event: {
            type: 'character_changed',
            character_id: 'mimi',
            character_name: 'Mimi',
            history: [{ role: 'user', text: 'miau' }],
          },
        },
      ],
      withSession,
    )
    expect(state.session?.characterId).toBe('mimi')
    expect(state.session?.characterName).toBe('Mimi')
    expect(state.messages.map((m) => m.text)).toEqual(['miau'])
    expect(state.emotion).toBe('neutral')
    expect(state.lastError).toBeNull()
  })

  it("empties the chat only when the active character's conversation is cleared", () => {
    const withChat: AppState = {
      ...run([{ type: 'user_message_sent', text: 'hola' }], connected),
      session: {
        characterId: 'akari',
        characterName: 'Akari',
        characters: [],
        aiProvider: 'mock',
        aiIsRemote: false,
        aiModel: null,
        aiModels: [],
        modelLoading: false,
        voiceAvailable: false,
        voiceEnabled: true,
        privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
      },
      emotion: 'happy',
    }
    expect(selectCanClearConversation(withChat)).toBe(true)

    const other = appReducer(withChat, {
      type: 'server_event',
      event: { type: 'conversation_cleared', character_id: 'mimi' },
    })
    expect(other.messages).toHaveLength(1)

    const cleared = appReducer(withChat, {
      type: 'server_event',
      event: { type: 'conversation_cleared', character_id: 'akari' },
    })
    expect(cleared.messages).toEqual([])
    expect(cleared.emotion).toBe('neutral')
    expect(selectCanClearConversation(cleared)).toBe(false)
  })

  it('blocks sending and shows loading while a model loads', () => {
    const ready: AppState = {
      ...connected,
      session: {
        characterId: 'akari',
        characterName: 'Akari',
        characters: [],
        aiProvider: 'ollama',
        aiIsRemote: false,
        aiModel: 'gpt-oss:latest',
        aiModels: ['gpt-oss:latest', 'qwen3:14b'],
        modelLoading: false,
        voiceAvailable: false,
        voiceEnabled: true,
        privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
      },
    }
    expect(selectCanSwitchModel(ready)).toBe(true)

    const loading = appReducer(ready, {
      type: 'server_event',
      event: { type: 'model_changed', model: 'qwen3:14b', loading: true },
    })
    expect(loading.session?.aiModel).toBe('qwen3:14b')
    expect(selectDisplayStatus(loading)).toBe('loading')
    expect(selectCanSend(loading)).toBe(false)
    expect(selectCanSwitchModel(loading)).toBe(false)

    const loaded = appReducer(loading, {
      type: 'server_event',
      event: { type: 'model_changed', model: 'qwen3:14b', loading: false },
    })
    expect(selectDisplayStatus(loaded)).toBe('idle')
    expect(selectCanSend(loaded)).toBe(true)
  })

  it('tracks voice availability and the toggle', () => {
    const base = run(
      [
        {
          type: 'server_event',
          event: {
            type: 'session_ready',
            protocol_version: 5,
            character_id: 'akari',
            character_name: 'Akari',
            characters: [],
            history: [],
            ai_provider: 'ollama',
            ai_is_remote: false,
            ai_model: 'qwen3:14b',
            ai_models: ['qwen3:14b'],
            ai_model_loading: false,
            voice_available: false,
            voice_enabled: true,
            privacy: { microphone_enabled: false, camera_enabled: false, remote_vision_enabled: false },
            state: 'idle',
          },
        },
      ],
      connected,
    )
    expect(base.session?.voiceAvailable).toBe(false)
    const changed = appReducer(base, {
      type: 'server_event',
      event: { type: 'voice_changed', available: true, enabled: false },
    })
    expect(changed.session?.voiceAvailable).toBe(true)
    expect(changed.session?.voiceEnabled).toBe(false)
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
            utterance_id: 1,
            voice: false,
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
