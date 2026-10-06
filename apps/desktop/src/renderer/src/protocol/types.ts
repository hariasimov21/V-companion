/**
 * WebSocket protocol. Mirrors apps/backend/app/models/protocol.py.
 * Both sides are tested against shared/protocol-fixtures/ to catch drift.
 */

export const PROTOCOL_VERSION = 1

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
  'internal_error',
] as const
export type ErrorCode = (typeof ERROR_CODES)[number]

export interface PrivacySettings {
  microphone_enabled: boolean
  camera_enabled: boolean
  remote_vision_enabled: boolean
}

// --- Server -> Client ---------------------------------------------------------

export interface SessionReadyEvent {
  type: 'session_ready'
  protocol_version: number
  character_name: string
  ai_provider: string
  ai_is_remote: boolean
  privacy: PrivacySettings
  state: AssistantPhase
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

export type ServerEvent = SessionReadyEvent | StateChangedEvent | AssistantMessageEvent | ErrorEvent

// --- Client -> Server ---------------------------------------------------------

export interface UserMessageEvent {
  type: 'user_message'
  text: string
}

export interface SpeechFinishedEvent {
  type: 'speech_finished'
}

export type ClientEvent = UserMessageEvent | SpeechFinishedEvent
