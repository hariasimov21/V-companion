import type { AssistantMessageEvent, AssistantPhase } from '../protocol/types'
import type { AvatarController } from './AvatarController'

const THINKING_EXPRESSION = { emotion: 'thinking', intensity: 0.6 } as const

/**
 * Translates protocol events into avatar commands. This is the seam between the agent
 * world (phases, assistant messages) and the rendering world (AvatarController).
 */
export class AvatarDirector {
  constructor(private readonly avatar: AvatarController) {}

  onPhaseChanged(phase: AssistantPhase): void {
    if (phase === 'thinking') void this.avatar.setExpression(THINKING_EXPRESSION)
    this.avatar.setSpeaking(phase === 'speaking')
    if (phase !== 'speaking') this.avatar.setMouthOpen(0)
  }

  onAssistantMessage(message: AssistantMessageEvent): void {
    void this.avatar.setExpression({
      emotion: message.emotion,
      intensity: message.emotion_intensity,
    })
    if (message.gesture !== 'none') void this.avatar.playMotion(message.gesture)
    if (message.look_at_user) this.avatar.lookAt(0, 0)
  }
}
