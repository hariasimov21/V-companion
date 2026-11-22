/** Single place where the renderer reads build-time environment. */

export interface ReconnectConfig {
  initialDelayMs: number
  maxDelayMs: number
}

export interface SpeechConfig {
  /** Text-only speech: how long a reply "takes" to say, until real TTS exists. */
  msPerCharacter: number
  minDurationMs: number
  maxDurationMs: number
}

export type AvatarRenderer = 'sprite' | 'placeholder'

export interface AvatarConfig {
  /** The sprite set is chosen per character (sprite id = character id). */
  renderer: AvatarRenderer
}

export interface AppConfig {
  backendWsUrl: string
  reconnect: ReconnectConfig
  speech: SpeechConfig
  avatar: AvatarConfig
}

const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/ws'

export function createAppConfig(env: Readonly<Record<string, unknown>>): AppConfig {
  const wsUrl = env['VITE_BACKEND_WS_URL']
  const renderer = env['VITE_AVATAR_RENDERER']
  return {
    backendWsUrl: typeof wsUrl === 'string' && wsUrl ? wsUrl : DEFAULT_WS_URL,
    reconnect: { initialDelayMs: 500, maxDelayMs: 10_000 },
    speech: { msPerCharacter: 55, minDurationMs: 1200, maxDurationMs: 12_000 },
    avatar: {
      renderer: renderer === 'placeholder' ? 'placeholder' : 'sprite',
    },
  }
}

export const appConfig: AppConfig = createAppConfig(import.meta.env)
