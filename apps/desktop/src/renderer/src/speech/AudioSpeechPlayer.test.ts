import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AudioSpeechPlayer, decodePcm16, mouthLevel } from './AudioSpeechPlayer'

/** base64 of little-endian int16 samples. */
const pcm = (...samples: number[]) => {
  const bytes = new Uint8Array(new Int16Array(samples).buffer)
  return btoa(String.fromCharCode(...bytes))
}

class FakeSource {
  onended: (() => void) | null = null
  buffer: { duration: number } | null = null
  startedAt = -1
  stopped = false
  connect() {}
  start(when: number) {
    this.startedAt = when
  }
  stop() {
    this.stopped = true
  }
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = []
  currentTime = 0
  state = 'running'
  destination = {}
  sources: FakeSource[] = []
  constructor() {
    FakeAudioContext.instances.push(this)
  }
  createBuffer(_channels: number, length: number, sampleRate: number) {
    return { duration: length / sampleRate, copyToChannel() {} }
  }
  createBufferSource() {
    const source = new FakeSource()
    this.sources.push(source)
    return source
  }
  gains: { gain: { value: number } }[] = []
  createAnalyser() {
    return { fftSize: 0, connect() {}, getFloatTimeDomainData() {} }
  }
  createGain() {
    const node = { gain: { value: 1 }, connect() {} }
    this.gains.push(node)
    return node
  }
  resume() {
    return Promise.resolve()
  }
  close() {
    return Promise.resolve()
  }
}

describe('PCM helpers', () => {
  it('decodes 16-bit little-endian PCM', () => {
    expect(Array.from(decodePcm16(pcm(0, 16384, -32768)))).toEqual([0, 0.5, -1])
  })

  it('turns loudness into a 0..1 mouth level', () => {
    expect(mouthLevel(new Float32Array(10))).toBe(0)
    expect(mouthLevel(new Float32Array(10).fill(0.1))).toBeCloseTo(0.4)
    expect(mouthLevel(new Float32Array(10).fill(0.9))).toBe(1)
  })
})

describe('AudioSpeechPlayer', () => {
  beforeEach(() => {
    FakeAudioContext.instances = []
    vi.stubGlobal('AudioContext', FakeAudioContext)
    vi.stubGlobal('requestAnimationFrame', () => 1)
    vi.stubGlobal('cancelAnimationFrame', () => undefined)
  })
  afterEach(() => vi.unstubAllGlobals())

  const source = (index: number): FakeSource => {
    const found = FakeAudioContext.instances[0]?.sources[index]
    if (!found) throw new Error(`no audio source #${index}`)
    return found
  }

  it('plays chunks back to back and finishes after the last one ends', async () => {
    const levels: number[] = []
    const player = new AudioSpeechPlayer((level) => levels.push(level))
    const done = vi.fn()
    void player.play(1, new AbortController().signal).then(done)

    player.push(1, 4, pcm(1, 2, 3, 4)) // 1 s of audio at 4 Hz
    player.push(1, 4, pcm(5, 6)) // 0.5 s
    const [first, second] = [source(0), source(1)]
    expect(first.startedAt).toBeCloseTo(0.05)
    expect(second.startedAt).toBeCloseTo(1.05) // gapless, right after the first

    player.end(1)
    first.onended?.()
    await Promise.resolve()
    expect(done).not.toHaveBeenCalled() // the second chunk is still playing
    second.onended?.()
    await Promise.resolve()
    expect(done).toHaveBeenCalled()
    expect(levels.at(-1)).toBe(0) // mouth closed at the end
  })

  it('waits for a cushion after running dry instead of stuttering', () => {
    const player = new AudioSpeechPlayer(() => undefined)
    void player.play(6, new AbortController().signal)
    player.push(6, 4, pcm(1, 2, 3, 4)) // plays 0.05 → 1.05
    const ctx = FakeAudioContext.instances[0]
    if (!ctx) throw new Error('no context')
    ctx.currentTime = 2 // the next chunk arrives late: the audio ran dry at 1.05
    player.push(6, 4, pcm(5, 6))
    expect(source(1).startedAt).toBeCloseTo(2.6) // 0.6 s of cushion, not 2.05
  })

  it('finishes at once when the audio failed before any chunk', async () => {
    const player = new AudioSpeechPlayer(() => undefined)
    const playing = player.play(2, new AbortController().signal)
    player.end(2)
    await expect(playing).resolves.toBeUndefined()
  })

  it('ignores chunks from an older, interrupted reply', () => {
    const player = new AudioSpeechPlayer(() => undefined)
    void player.play(3, new AbortController().signal)
    player.push(2, 24000, pcm(1, 2))
    expect(FakeAudioContext.instances).toHaveLength(0)
  })

  it('applies the volume before and after the audio starts', () => {
    const player = new AudioSpeechPlayer(() => undefined)
    player.setVolume(0.4)
    void player.play(5, new AbortController().signal)
    player.push(5, 24000, pcm(1, 2))
    const gain = FakeAudioContext.instances[0]?.gains[0]
    expect(gain?.gain.value).toBe(0.4)
    player.setVolume(1.3)
    expect(gain?.gain.value).toBe(1.3)
  })

  it('stops the audio when aborted', async () => {
    const player = new AudioSpeechPlayer(() => undefined)
    const abort = new AbortController()
    const playing = player.play(4, abort.signal)
    player.push(4, 24000, pcm(1, 2, 3))
    abort.abort()
    await expect(playing).rejects.toThrow('Speech aborted')
    expect(source(0).stopped).toBe(true)
  })
})
