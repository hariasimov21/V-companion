import {
  ASSISTANT_PHASES,
  EMOTIONS,
  ERROR_CODES,
  GESTURES,
  type CharacterSummary,
  type HistoryEntry,
  type PrivacySettings,
  type ServerEvent,
} from './types'

type JsonObject = Record<string, unknown>

const isObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isString = (value: unknown): value is string => typeof value === 'string'
const isBoolean = (value: unknown): value is boolean => typeof value === 'boolean'

const isOneOf =
  <T extends string>(options: readonly T[]) =>
  (value: unknown): value is T =>
    isString(value) && (options as readonly string[]).includes(value)

const isPhase = isOneOf(ASSISTANT_PHASES)
const isEmotion = isOneOf(EMOTIONS)
const isGesture = isOneOf(GESTURES)
const isErrorCode = isOneOf(ERROR_CODES)

const isUnitInterval = (value: unknown): value is number =>
  typeof value === 'number' && value >= 0 && value <= 1

const isPrivacy = (value: unknown): value is PrivacySettings =>
  isObject(value) &&
  isBoolean(value['microphone_enabled']) &&
  isBoolean(value['camera_enabled']) &&
  isBoolean(value['remote_vision_enabled'])

const isCharacterSummary = (value: unknown): value is CharacterSummary =>
  isObject(value) && isString(value['id']) && isString(value['name'])

const isOptional =
  <T>(check: (value: unknown) => value is T) =>
  (value: unknown): value is T | null | undefined =>
    value === undefined || value === null || check(value)

const isHistoryEntry = (value: unknown): value is HistoryEntry =>
  isObject(value) &&
  (value['role'] === 'user' || value['role'] === 'assistant') &&
  isString(value['text']) &&
  isOptional(isEmotion)(value['emotion']) &&
  isOptional(isGesture)(value['gesture'])

const isHistory = (value: unknown): value is HistoryEntry[] =>
  Array.isArray(value) && value.every(isHistoryEntry)

const validators: Record<ServerEvent['type'], (data: JsonObject) => boolean> = {
  session_ready: (d) =>
    typeof d['protocol_version'] === 'number' &&
    isString(d['character_id']) &&
    isString(d['character_name']) &&
    Array.isArray(d['characters']) &&
    d['characters'].every(isCharacterSummary) &&
    isHistory(d['history']) &&
    isString(d['ai_provider']) &&
    isBoolean(d['ai_is_remote']) &&
    (d['ai_model'] === null || isString(d['ai_model'])) &&
    Array.isArray(d['ai_models']) &&
    d['ai_models'].every(isString) &&
    isBoolean(d['ai_model_loading']) &&
    isPrivacy(d['privacy']) &&
    isPhase(d['state']),
  character_changed: (d) =>
    isString(d['character_id']) && isString(d['character_name']) && isHistory(d['history']),
  conversation_cleared: (d) => isString(d['character_id']),
  model_changed: (d) => isString(d['model']) && isBoolean(d['loading']),
  state_changed: (d) => isPhase(d['state']),
  assistant_message: (d) =>
    isString(d['text']) &&
    isEmotion(d['emotion']) &&
    isUnitInterval(d['emotion_intensity']) &&
    isGesture(d['gesture']) &&
    isBoolean(d['look_at_user']),
  error: (d) => isErrorCode(d['code']) && isString(d['message']),
}

const hasValidator = (type: unknown): type is ServerEvent['type'] =>
  isString(type) && Object.hasOwn(validators, type)

/** Validates untrusted data from the socket. Returns null for anything off-protocol. */
export function parseServerEvent(data: unknown): ServerEvent | null {
  if (!isObject(data) || !hasValidator(data['type'])) return null
  return validators[data['type']](data) ? (data as unknown as ServerEvent) : null
}

export function parseServerMessage(raw: string): ServerEvent | null {
  try {
    return parseServerEvent(JSON.parse(raw))
  } catch {
    return null
  }
}
