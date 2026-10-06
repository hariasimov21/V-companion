import type { AvatarController, AvatarExpression, AvatarMotion } from '../AvatarController'

export interface PlaceholderAvatarSnapshot {
  expression: AvatarExpression
  motion: AvatarMotion | null
  /** Changes on every playMotion call so the same motion can replay. */
  motionKey: number
  mouthOpen: number
  gaze: { x: number; y: number }
  blinking: boolean
  speaking: boolean
}

export const MOTION_DURATION_MS: Record<AvatarMotion, number> = {
  nod: 700,
  shake_head: 800,
  wave: 1400,
  laugh: 1000,
  sigh: 1400,
  look_left: 1500,
  look_right: 1500,
  stretch: 1600,
}

const BLINK_DURATION_MS = 140

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

/**
 * Observable controller for the SVG placeholder avatar. It keeps an immutable snapshot
 * that React reads via useSyncExternalStore.
 */
export class PlaceholderAvatarController implements AvatarController {
  private snapshot: PlaceholderAvatarSnapshot = {
    expression: { emotion: 'neutral', intensity: 0.5 },
    motion: null,
    motionKey: 0,
    mouthOpen: 0,
    gaze: { x: 0, y: 0 },
    blinking: false,
    speaking: false,
  }
  private readonly listeners = new Set<() => void>()
  private motionTimer: ReturnType<typeof setTimeout> | null = null

  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  readonly getSnapshot = (): PlaceholderAvatarSnapshot => this.snapshot

  async setExpression(expression: AvatarExpression): Promise<void> {
    this.update({ expression: { ...expression, intensity: clamp(expression.intensity, 0, 1) } })
  }

  playMotion(motion: AvatarMotion): Promise<void> {
    if (this.motionTimer !== null) clearTimeout(this.motionTimer)
    this.update({ motion, motionKey: this.snapshot.motionKey + 1 })
    return new Promise((resolve) => {
      this.motionTimer = setTimeout(() => {
        this.motionTimer = null
        this.update({ motion: null })
        resolve()
      }, MOTION_DURATION_MS[motion])
    })
  }

  setMouthOpen(value: number): void {
    this.update({ mouthOpen: clamp(value, 0, 1) })
  }

  lookAt(x: number, y: number): void {
    this.update({ gaze: { x: clamp(x, -1, 1), y: clamp(y, -1, 1) } })
  }

  blink(): void {
    if (this.snapshot.blinking) return
    this.update({ blinking: true })
    setTimeout(() => this.update({ blinking: false }), BLINK_DURATION_MS)
  }

  setSpeaking(speaking: boolean): void {
    if (this.snapshot.speaking !== speaking) this.update({ speaking })
  }

  private update(patch: Partial<PlaceholderAvatarSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...patch }
    this.listeners.forEach((listener) => listener())
  }
}
