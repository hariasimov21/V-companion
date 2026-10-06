import type { Emotion, Gesture } from '../protocol/types'

export interface AvatarExpression {
  emotion: Emotion
  /** 0..1 */
  intensity: number
}

export type AvatarMotion = Exclude<Gesture, 'none'>

/**
 * Rendering-agnostic avatar API. Implementations (placeholder, Live2D, VRM...) translate
 * these semantic commands to their own engine. Nothing outside src/avatar/ should know
 * which implementation is in use.
 */
export interface AvatarController {
  setExpression(expression: AvatarExpression): Promise<void>
  playMotion(motion: AvatarMotion): Promise<void>
  /** 0 (closed) .. 1 (fully open). Driven by lip sync. */
  setMouthOpen(value: number): void
  /** Normalized gaze target, -1..1 on each axis; (0, 0) looks at the user. */
  lookAt(x: number, y: number): void
  blink(): void
  setSpeaking(speaking: boolean): void
}
