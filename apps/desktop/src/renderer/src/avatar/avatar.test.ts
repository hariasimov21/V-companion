import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AvatarController } from './AvatarController'
import { AvatarDirector } from './AvatarDirector'
import {
  MOTION_DURATION_MS,
  ObservableAvatarController,
} from './ObservableAvatarController'

function fakeController() {
  return {
    setExpression: vi.fn(async () => undefined),
    playMotion: vi.fn(async () => undefined),
    setMouthOpen: vi.fn(),
    lookAt: vi.fn(),
    blink: vi.fn(),
    setSpeaking: vi.fn(),
  } satisfies AvatarController
}

describe('AvatarDirector', () => {
  it('maps an assistant message to expression, motion and gaze', () => {
    const avatar = fakeController()
    new AvatarDirector(avatar).onAssistantMessage({
      type: 'assistant_message',
      text: 'Hola',
      emotion: 'happy',
      emotion_intensity: 0.8,
      gesture: 'nod',
      look_at_user: true,
    })
    expect(avatar.setExpression).toHaveBeenCalledWith({ emotion: 'happy', intensity: 0.8 })
    expect(avatar.playMotion).toHaveBeenCalledWith('nod')
    expect(avatar.lookAt).toHaveBeenCalledWith(0, 0)
  })

  it('skips the motion for gesture "none"', () => {
    const avatar = fakeController()
    new AvatarDirector(avatar).onAssistantMessage({
      type: 'assistant_message',
      text: '...',
      emotion: 'neutral',
      emotion_intensity: 0.5,
      gesture: 'none',
      look_at_user: false,
    })
    expect(avatar.playMotion).not.toHaveBeenCalled()
    expect(avatar.lookAt).not.toHaveBeenCalled()
  })

  it('shows a thinking face and toggles speaking with the phase', () => {
    const avatar = fakeController()
    const director = new AvatarDirector(avatar)
    director.onPhaseChanged('thinking')
    expect(avatar.setExpression).toHaveBeenCalledWith({ emotion: 'thinking', intensity: 0.6 })
    director.onPhaseChanged('speaking')
    expect(avatar.setSpeaking).toHaveBeenLastCalledWith(true)
    director.onPhaseChanged('idle')
    expect(avatar.setSpeaking).toHaveBeenLastCalledWith(false)
    expect(avatar.setMouthOpen).toHaveBeenLastCalledWith(0)
  })
})

describe('ObservableAvatarController', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('notifies subscribers on changes', async () => {
    const controller = new ObservableAvatarController()
    const listener = vi.fn()
    controller.subscribe(listener)
    await controller.setExpression({ emotion: 'sad', intensity: 3 })
    expect(listener).toHaveBeenCalledOnce()
    expect(controller.getSnapshot().expression).toEqual({ emotion: 'sad', intensity: 1 })
  })

  it('plays a motion and clears it after its duration', async () => {
    const controller = new ObservableAvatarController()
    const done = controller.playMotion('wave')
    expect(controller.getSnapshot().motion).toBe('wave')
    vi.advanceTimersByTime(MOTION_DURATION_MS.wave)
    await done
    expect(controller.getSnapshot().motion).toBeNull()
  })

  it('clamps mouth and gaze values', () => {
    const controller = new ObservableAvatarController()
    controller.setMouthOpen(2)
    controller.lookAt(-5, 0.5)
    expect(controller.getSnapshot().mouthOpen).toBe(1)
    expect(controller.getSnapshot().gaze).toEqual({ x: -1, y: 0.5 })
  })

  it('blinks briefly', () => {
    const controller = new ObservableAvatarController()
    controller.blink()
    expect(controller.getSnapshot().blinking).toBe(true)
    vi.advanceTimersByTime(500)
    expect(controller.getSnapshot().blinking).toBe(false)
  })
})
