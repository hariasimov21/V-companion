import type { SpeechConfig } from '../config/appConfig'

/**
 * Presents the assistant's speech and resolves when it is done. Today it only waits for
 * a reading-time estimate; in Phase 3 a TTS implementation will play audio and feed a
 * LipSyncController. Rejects with an AbortError when interrupted.
 */
export interface SpeechOutput {
  speak(text: string, signal: AbortSignal): Promise<void>
}

export function estimateSpeechDurationMs(text: string, config: SpeechConfig): number {
  const estimate = text.trim().length * config.msPerCharacter
  return Math.min(config.maxDurationMs, Math.max(config.minDurationMs, estimate))
}

export class TextOnlySpeechOutput implements SpeechOutput {
  constructor(private readonly config: SpeechConfig) {}

  speak(text: string, signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException('Speech aborted', 'AbortError'))
        return
      }
      const timer = setTimeout(resolve, estimateSpeechDurationMs(text, this.config))
      signal.addEventListener(
        'abort',
        () => {
          clearTimeout(timer)
          reject(new DOMException('Speech aborted', 'AbortError'))
        },
        { once: true },
      )
    })
  }
}
