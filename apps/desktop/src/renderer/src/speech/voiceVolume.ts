/**
 * The voice volume is a per-device preference (like a media player's), so it lives in
 * localStorage rather than in the backend. Storage can be unavailable or cleared: every
 * access is guarded and falls back to the default.
 */

const STORAGE_KEY = 'malfoid.voiceVolume'
export const DEFAULT_VOICE_VOLUME = 1
/** Up to 150 %: some voices are recorded quieter than others. */
export const MAX_VOICE_VOLUME = 1.5

export function clampVolume(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_VOICE_VOLUME
  return Math.min(MAX_VOICE_VOLUME, Math.max(0, value))
}

export function loadVoiceVolume(): number {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved === null ? DEFAULT_VOICE_VOLUME : clampVolume(Number(saved))
  } catch {
    return DEFAULT_VOICE_VOLUME
  }
}

export function saveVoiceVolume(value: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(clampVolume(value)))
  } catch {
    // Not persisted this time; the volume still applies until the app closes.
  }
}
