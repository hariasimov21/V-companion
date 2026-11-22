import type {
  AssistantPhase,
  CharacterSummary,
  Emotion,
  Gesture,
  HistoryEntry,
  PrivacySettings,
  ServerEvent,
} from '../protocol/types'
import type { ConnectionStatus } from '../websocket/BackendClient'

export interface SessionInfo {
  characterId: string
  characterName: string
  characters: CharacterSummary[]
  aiProvider: string
  aiIsRemote: boolean
  aiModel: string | null
  aiModels: string[]
  /** A newly selected model is loading into memory: nothing can be sent meanwhile. */
  modelLoading: boolean
  privacy: PrivacySettings
}

export type ChatEntry =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; text: string; emotion: Emotion; gesture: Gesture }

type Role = ChatEntry['role']
type NewChatEntry = { [R in Role]: Omit<Extract<ChatEntry, { role: R }>, 'id'> }[Role]

export interface AppState {
  connection: ConnectionStatus
  /** Mirrors the backend's phase; the backend is the source of truth. */
  phase: AssistantPhase
  session: SessionInfo | null
  emotion: Emotion
  messages: ChatEntry[]
  lastError: string | null
  nextId: number
}

export type AppAction =
  | { type: 'connection_changed'; status: ConnectionStatus }
  | { type: 'server_event'; event: ServerEvent }
  | { type: 'user_message_sent'; text: string }

export const initialAppState: AppState = {
  connection: 'disconnected',
  phase: 'idle',
  session: null,
  emotion: 'neutral',
  messages: [],
  lastError: null,
  nextId: 1,
}

const MAX_MESSAGES = 200

function appendMessage(state: AppState, entry: NewChatEntry): AppState {
  const message: ChatEntry = { ...entry, id: state.nextId }
  return {
    ...state,
    messages: [...state.messages, message].slice(-MAX_MESSAGES),
    nextId: state.nextId + 1,
  }
}

/** Replaces the chat with a conversation restored by the backend (its source of truth). */
function withHistory(state: AppState, history: HistoryEntry[]): AppState {
  const messages = history.slice(-MAX_MESSAGES).map(
    (entry, index): ChatEntry =>
      entry.role === 'user'
        ? { id: state.nextId + index, role: 'user', text: entry.text }
        : {
            id: state.nextId + index,
            role: 'assistant',
            text: entry.text,
            emotion: entry.emotion ?? 'neutral',
            gesture: entry.gesture ?? 'none',
          },
  )
  return { ...state, messages, nextId: state.nextId + messages.length }
}

function reduceServerEvent(state: AppState, event: ServerEvent): AppState {
  switch (event.type) {
    case 'session_ready':
      return withHistory(
        {
          ...state,
          phase: event.state,
          session: {
            characterId: event.character_id,
            characterName: event.character_name,
            characters: event.characters,
            aiProvider: event.ai_provider,
            aiIsRemote: event.ai_is_remote,
            aiModel: event.ai_model,
            aiModels: event.ai_models,
            modelLoading: event.ai_model_loading,
            privacy: event.privacy,
          },
        },
        event.history,
      )
    case 'character_changed':
      // Each character has its own conversation: show the one the backend restored.
      return withHistory(
        {
          ...state,
          session: state.session && {
            ...state.session,
            characterId: event.character_id,
            characterName: event.character_name,
          },
          emotion: 'neutral',
          lastError: null,
        },
        event.history,
      )
    case 'conversation_cleared':
      if (state.session?.characterId !== event.character_id) return state
      return { ...state, messages: [], emotion: 'neutral', lastError: null }
    case 'model_changed':
      return {
        ...state,
        session: state.session && {
          ...state.session,
          aiModel: event.model,
          modelLoading: event.loading,
        },
        lastError: null,
      }
    case 'state_changed':
      return { ...state, phase: event.state }
    case 'assistant_message':
      return appendMessage(
        { ...state, emotion: event.emotion },
        { role: 'assistant', text: event.text, emotion: event.emotion, gesture: event.gesture },
      )
    case 'error':
      return { ...state, lastError: event.message }
  }
}

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'connection_changed':
      return { ...state, connection: action.status }
    case 'server_event':
      return reduceServerEvent(state, action.event)
    case 'user_message_sent':
      return appendMessage({ ...state, lastError: null }, { role: 'user', text: action.text })
  }
}

export type DisplayStatus = AssistantPhase | 'offline' | 'loading'

/** What the UI should show: connection problems first, then a model load, then the phase. */
export function selectDisplayStatus(state: AppState): DisplayStatus {
  if (state.connection !== 'connected') return 'offline'
  return state.session?.modelLoading ? 'loading' : state.phase
}

/** Connected, not thinking and no model loading: the backend would answer "busy" otherwise. */
function isReady(state: AppState): boolean {
  return state.connection === 'connected' && state.phase !== 'thinking' && !state.session?.modelLoading
}

export function selectCanSend(state: AppState): boolean {
  return isReady(state)
}

export function selectCanSwitchModel(state: AppState): boolean {
  return isReady(state) && (state.session?.aiModels.length ?? 0) > 0
}

/** Clearing mid-answer would be rejected as busy by the backend. */
export function selectCanClearConversation(state: AppState): boolean {
  return isReady(state) && state.messages.length > 0
}

/** Switching mid-answer would be rejected as busy by the backend. */
export function selectCanSwitchCharacter(state: AppState): boolean {
  return isReady(state)
}
