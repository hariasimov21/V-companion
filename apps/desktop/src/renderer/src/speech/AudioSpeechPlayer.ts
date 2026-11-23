/**
 * Plays a spoken reply as its audio streams in (speech_audio chunks), and reports the
 * loudness while it plays so the avatar's mouth can follow the real voice.
 *
 * Chunks are scheduled back to back on one AudioContext timeline, so they play gaplessly
 * even though they arrive over the WebSocket at irregular intervals.
 */

/** Small lead so the first chunk is never scheduled in the past. */
const START_DELAY_S = 0.05
/**
 * When audio arrives slower than it plays (e.g. the GPU is nearly full), chunks would
 * play as they trickle in: a stutter on every chunk. Instead, after running dry, wait to
 * build this much cushion: one short pause, then fluent speech again.
 */
const REBUFFER_S = 0.6
/** RMS of normal speech is ~0.05–0.25; scale it to a 0..1 mouth opening. */
const LEVEL_GAIN = 4
/**
 * While audio plays the level never reaches exactly 0: avatars treat "speaking with a
 * mouth level of 0" as "no lip sync" and fall back to a fake talking loop.
 */
const LIVE_LEVEL_FLOOR = 0.001

/** base64 PCM 16-bit little-endian mono → Float32 samples in -1..1. */
export function decodePcm16(base64: string): Float32Array<ArrayBuffer> {
  const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const samples = new Float32Array(Math.floor(bytes.byteLength / 2))
  for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true) / 32768
  return samples
}

/** Loudness of a block of samples as a 0..1 mouth opening. */
export function mouthLevel(samples: Float32Array): number {
  if (samples.length === 0) return 0
  let sum = 0
  for (const sample of samples) sum += sample * sample
  return Math.min(1, Math.sqrt(sum / samples.length) * LEVEL_GAIN)
}

interface Utterance {
  id: number
  nextStart: number
  playing: Set<AudioBufferSourceNode>
  ended: boolean
  resolve: () => void
}

export class AudioSpeechPlayer {
  private context: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private gain: GainNode | null = null
  private volume = 1
  private current: Utterance | null = null
  private frame = 0

  constructor(private readonly onLevel: (level: number) => void) {}

  /** Resolves once `end()` was received and every chunk finished playing. */
  play(utteranceId: number, signal: AbortSignal): Promise<void> {
    this.stop()
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException('Speech aborted', 'AbortError'))
        return
      }
      const utterance: Utterance = {
        id: utteranceId,
        nextStart: 0,
        playing: new Set(),
        ended: false,
        resolve,
      }
      this.current = utterance
      signal.addEventListener(
        'abort',
        () => {
          if (this.current === utterance) this.stop()
          reject(new DOMException('Speech aborted', 'AbortError'))
        },
        { once: true },
      )
    })
  }

  push(utteranceId: number, sampleRate: number, pcm: string): void {
    const utterance = this.current
    if (utterance?.id !== utteranceId) return // a stale chunk from an interrupted reply
    const samples = decodePcm16(pcm)
    if (samples.length === 0) return
    const { context, analyser } = this.audio()
    const buffer = context.createBuffer(1, samples.length, sampleRate)
    buffer.copyToChannel(samples, 0)
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(analyser)
    const ranDry = utterance.nextStart > 0 && utterance.nextStart < context.currentTime
    const lead = ranDry ? REBUFFER_S : START_DELAY_S
    const start = Math.max(utterance.nextStart, context.currentTime + lead)
    source.start(start)
    utterance.nextStart = start + buffer.duration
    utterance.playing.add(source)
    source.onended = () => {
      utterance.playing.delete(source)
      this.finishIfDone(utterance)
    }
    this.trackLevel()
  }

  end(utteranceId: number): void {
    const utterance = this.current
    if (utterance?.id !== utteranceId) return
    utterance.ended = true
    this.finishIfDone(utterance)
  }

  /** Silences everything immediately (interrupted, character switched...). */
  stop(): void {
    const utterance = this.current
    this.current = null
    if (utterance) {
      for (const source of utterance.playing) {
        source.onended = null
        source.stop()
      }
      utterance.playing.clear()
    }
    cancelAnimationFrame(this.frame)
    this.onLevel(0)
  }

  /** 0 (silent) .. 1.5. Lip sync is measured before the volume, so the mouth does not change. */
  setVolume(volume: number): void {
    this.volume = volume
    if (this.gain) this.gain.gain.value = volume
  }

  dispose(): void {
    this.stop()
    void this.context?.close()
    this.context = null
    this.analyser = null
    this.gain = null
  }

  private finishIfDone(utterance: Utterance): void {
    if (!utterance.ended || utterance.playing.size > 0 || this.current !== utterance) return
    this.current = null
    cancelAnimationFrame(this.frame)
    this.onLevel(0)
    utterance.resolve()
  }

  private audio(): { context: AudioContext; analyser: AnalyserNode } {
    if (!this.context || !this.analyser) {
      // Default latency on purpose: latencyHint 'playback' produced no sound at all
      // through WSLg's PulseAudio.
      this.context = new AudioContext()
      // source -> analyser (lip sync, unaffected by volume) -> gain (volume) -> speakers
      this.analyser = this.context.createAnalyser()
      this.analyser.fftSize = 1024
      this.gain = this.context.createGain()
      this.gain.gain.value = this.volume
      this.analyser.connect(this.gain)
      this.gain.connect(this.context.destination)
    }
    if (this.context.state === 'suspended') void this.context.resume()
    return { context: this.context, analyser: this.analyser }
  }

  private trackLevel(): void {
    cancelAnimationFrame(this.frame)
    const analyser = this.analyser
    if (!analyser) return
    const block = new Float32Array(analyser.fftSize)
    const tick = () => {
      if (!this.current) return
      analyser.getFloatTimeDomainData(block)
      this.onLevel(Math.max(LIVE_LEVEL_FLOOR, mouthLevel(block)))
      this.frame = requestAnimationFrame(tick)
    }
    this.frame = requestAnimationFrame(tick)
  }
}
