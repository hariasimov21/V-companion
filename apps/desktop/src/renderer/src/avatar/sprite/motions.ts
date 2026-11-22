import type { AvatarMotion } from '../AvatarController'

/** Whole-body keyframes for each gesture (a sprite has no separate limbs). */
export const SPRITE_MOTION_KEYFRAMES: Record<AvatarMotion, Keyframe[]> = {
  nod: [
    { transform: 'translateY(0)' },
    { transform: 'translateY(1.2%)', offset: 0.3 },
    { transform: 'translateY(-0.3%)', offset: 0.6 },
    { transform: 'translateY(0)' },
  ],
  shake_head: [
    { transform: 'rotate(0)' },
    { transform: 'rotate(-2deg)', offset: 0.2 },
    { transform: 'rotate(2deg)', offset: 0.4 },
    { transform: 'rotate(-2deg)', offset: 0.6 },
    { transform: 'rotate(1deg)', offset: 0.8 },
    { transform: 'rotate(0)' },
  ],
  wave: [
    { transform: 'translateY(0) rotate(0)' },
    { transform: 'translateY(-2%) rotate(-2deg)', offset: 0.25 },
    { transform: 'translateY(0) rotate(0)', offset: 0.5 },
    { transform: 'translateY(-1.5%) rotate(2deg)', offset: 0.75 },
    { transform: 'translateY(0) rotate(0)' },
  ],
  laugh: [
    { transform: 'translateY(0)' },
    { transform: 'translateY(-1.5%)', offset: 0.2 },
    { transform: 'translateY(0.3%)', offset: 0.4 },
    { transform: 'translateY(-1.2%)', offset: 0.6 },
    { transform: 'translateY(0.2%)', offset: 0.8 },
    { transform: 'translateY(0)' },
  ],
  sigh: [
    { transform: 'translateY(0) scaleY(1)' },
    { transform: 'translateY(0.8%) scaleY(0.99)', offset: 0.5 },
    { transform: 'translateY(0) scaleY(1)' },
  ],
  look_left: [
    { transform: 'rotate(0) translateX(0)' },
    { transform: 'rotate(-3deg) translateX(-1.5%)', offset: 0.3 },
    { transform: 'rotate(-3deg) translateX(-1.5%)', offset: 0.7 },
    { transform: 'rotate(0) translateX(0)' },
  ],
  look_right: [
    { transform: 'rotate(0) translateX(0)' },
    { transform: 'rotate(3deg) translateX(1.5%)', offset: 0.3 },
    { transform: 'rotate(3deg) translateX(1.5%)', offset: 0.7 },
    { transform: 'rotate(0) translateX(0)' },
  ],
  stretch: [
    { transform: 'scale(1)' },
    { transform: 'scale(0.98, 1.025) translateY(-1%)', offset: 0.4 },
    { transform: 'scale(0.98, 1.025) translateY(-1%)', offset: 0.6 },
    { transform: 'scale(1)' },
  ],
}
