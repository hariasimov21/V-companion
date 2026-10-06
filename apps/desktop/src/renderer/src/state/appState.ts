import type {
  AssistantPhase,
  Emotion,
  Gesture,
  PrivacySettings,
  ServerEvent,
} from '../protocol/types'
import type { ConnectionStatus } from '../websocket/BackendClient'

export interface SessionInfo {
  characterName: string
  aiProvider: string
  aiIsRemote: boolean
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

function reduceServerEvent(state: AppState, event: ServerEvent): AppState {
  switch (event.type) {
    case 'session_ready':
      return {
        ...state,
        phase: event.state,
        session: {
          characterName: event.character_name,
          aiProvider: event.ai_provider,
          aiIsRemote: event.ai_is_remote,
          privacy: event.privacy,
        },
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

export type DisplayStatus = AssistantPhase | 'offline'

/** What the UI should show: connection problems take precedence over the phase. */
export function selectDisplayStatus(state: AppState): DisplayStatus {
  return state.connection === 'connected' ? state.phase : 'offline'
}

export function selectCanSend(state: AppState): boolean {
  return state.connection === 'connected' && state.phase !== 'thinking'
}
