import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  clampVolume,
  DEFAULT_VOICE_VOLUME,
  loadVoiceVolume,
  MAX_VOICE_VOLUME,
  saveVoiceVolume,
} from './voiceVolume'

describe('voice volume', () => {
  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('is remembered on this device', () => {
    expect(loadVoiceVolume()).toBe(DEFAULT_VOICE_VOLUME)
    saveVoiceVolume(0.35)
    expect(loadVoiceVolume()).toBe(0.35)
  })

  it('keeps values in range', () => {
    expect(clampVolume(-1)).toBe(0)
    expect(clampVolume(9)).toBe(MAX_VOICE_VOLUME)
    expect(clampVolume(Number.NaN)).toBe(DEFAULT_VOICE_VOLUME)
    localStorage.setItem('malfoid.voiceVolume', 'basura')
    expect(loadVoiceVolume()).toBe(DEFAULT_VOICE_VOLUME)
  })

  it('works when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(loadVoiceVolume()).toBe(DEFAULT_VOICE_VOLUME)
    expect(() => saveVoiceVolume(0.5)).not.toThrow()
  })
})
