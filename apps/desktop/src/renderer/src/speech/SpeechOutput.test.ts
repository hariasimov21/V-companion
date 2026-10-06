import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { estimateSpeechDurationMs, TextOnlySpeechOutput } from './SpeechOutput'

const config = { msPerCharacter: 50, minDurationMs: 1000, maxDurationMs: 5000 }

describe('estimateSpeechDurationMs', () => {
  it('scales with length within bounds', () => {
    expect(estimateSpeechDurationMs('hola', config)).toBe(1000)
    expect(estimateSpeechDurationMs('x'.repeat(40), config)).toBe(2000)
    expect(estimateSpeechDurationMs('x'.repeat(1000), config)).toBe(5000)
  })
})

describe('TextOnlySpeechOutput', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('resolves after the estimated duration', async () => {
    const done = vi.fn()
    void new TextOnlySpeechOutput(config).speak('hola', new AbortController().signal).then(done)
    await vi.advanceTimersByTimeAsync(999)
    expect(done).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(done).toHaveBeenCalled()
  })

  it('rejects when aborted', async () => {
    const controller = new AbortController()
    const speaking = new TextOnlySpeechOutput(config).speak('hola', controller.signal)
    controller.abort()
    await expect(speaking).rejects.toThrow('Speech aborted')
  })
})
