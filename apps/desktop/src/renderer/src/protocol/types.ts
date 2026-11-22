/**
 * WebSocket protocol. Mirrors apps/backend/app/models/protocol.py.
 * Both sides are tested against shared/protocol-fixtures/ to catch drift.
 */

export const PROTOCOL_VERSION = 4

export const EMOTIONS = [
  'neutral',
  'happy',
  'excited',
  'sad',
  'annoyed',
  'embarrassed',
  'curious',
  'thinking',
  'sleepy',
  'surprised',
] as const
export type Emotion = (typeof EMOTIONS)[number]

export const GESTURES = [
  'none',
  'nod',
  'shake_head',
  'wave',
  'laugh',
  'sigh',
  'look_left',
  'look_right',
  'stretch',
] as const
export type Gesture = (typeof GESTURES)[number]

export const ASSISTANT_PHASES = ['idle', 'listening', 'thinking', 'speaking', 'error'] as const
export type AssistantPhase = (typeof ASSISTANT_PHASES)[number]

export const ERROR_CODES = [
  'ai_provider_error',
  'ai_timeout',
  'invalid_message',
  'busy',
  'unknown_character',
  'unknown_model',
  'internal_error',
] as const
export type ErrorCode = (typeof ERROR_CODES)[number]

export interface PrivacySettings {
  microphone_enabled: boolean
  camera_enabled: boolean
  remote_vision_enabled: boolean
}

// --- Server -> Client ---------------------------------------------------------

export interface CharacterSummary {
  id: string
  name: string
}

/** A past chat message, so a resumed conversation can be shown. */
export interface HistoryEntry {
  role: 'user' | 'assistant'
  text: string
  emotion?: Emotion | null
  gesture?: Gesture | null
}

export interface SessionReadyEvent {
  type: 'session_ready'
  protocol_version: number
  character_id: string
  character_name: string
  characters: CharacterSummary[]
  history: HistoryEntry[]
  ai_provider: string
  ai_is_remote: boolean
  /** Model in use and the installed ones the user can switch to (empty = not switchable). */
  ai_model: string | null
  ai_models: string[]
  ai_model_loading: boolean
  privacy: PrivacySettings
  state: AssistantPhase
}

/** Broadcast after a switch: show that character's own conversation and swap the avatar. */
export interface CharacterChangedEvent {
  type: 'character_changed'
  character_id: string
  character_name: string
  history: HistoryEntry[]
}

/** Broadcast after a character's conversation was forgotten: empty the chat. */
export interface ConversationClearedEvent {
  type: 'conversation_cleared'
  character_id: string
}

/** Sent while a newly selected model loads (loading: true) and once it is ready. */
export interface ModelChangedEvent {
  type: 'model_changed'
  model: string
  loading: boolean
}

export interface StateChangedEvent {
  type: 'state_changed'
  state: AssistantPhase
}

export interface AssistantMessageEvent {
  type: 'assistant_message'
  text: string
  emotion: Emotion
  emotion_intensity: number
  gesture: Gesture
  look_at_user: boolean
}

export interface ErrorEvent {
  type: 'error'
  code: ErrorCode
  message: string
}

export type ServerEvent =
  | SessionReadyEvent
  | CharacterChangedEvent
  | ConversationClearedEvent
  | ModelChangedEvent
  | StateChangedEvent
  | AssistantMessageEvent
  | ErrorEvent

// --- Client -> Server ---------------------------------------------------------

export interface UserMessageEvent {
  type: 'user_message'
  text: string
}

export interface SpeechFinishedEvent {
  type: 'speech_finished'
}

export interface SelectCharacterEvent {
  type: 'select_character'
  character_id: string
}

/** Forgets the active character's whole conversation. */
export interface ClearConversationEvent {
  type: 'clear_conversation'
}

/** Switches the AI model for every character (installed local models only). */
export interface SelectModelEvent {
  type: 'select_model'
  model: string
}

export type ClientEvent =
  | UserMessageEvent
  | SpeechFinishedEvent
  | SelectCharacterEvent
  | ClearConversationEvent
  | SelectModelEvent
