import { type CSSProperties, useEffect, useRef, useSyncExternalStore } from 'react'

import {
  type AvatarSnapshot,
  MOTION_DURATION_MS,
  type ObservableAvatarController,
} from '../ObservableAvatarController'
import { useAutoBlink } from '../useAutoBlink'
import {
  expressionSources,
  type LayeredSpriteManifest,
  resolveExpressionSource,
  type SpriteRect,
} from './manifest'
import { SPRITE_MOTION_KEYFRAMES } from './motions'
import type { SpriteAssets, SpriteLayers } from './spriteAssets'

/** Lip-sync level above which the open-mouth layer is shown. */
const MOUTH_OPEN_THRESHOLD = 0.35

interface SpriteAvatarProps {
  controller: ObservableAvatarController
  assets: SpriteAssets
}

export function SpriteAvatar({ controller, assets }: SpriteAvatarProps) {
  const snapshot = useSyncExternalStore(controller.subscribe, controller.getSnapshot)
  const motionRef = useMotionAnimation(snapshot.motion, snapshot.motionKey)
  const layered = assets.manifest.kind === 'layered'
  useAutoBlink(controller, layered) // A static image has no closed eyes to show.

  const { canvas } = assets.manifest
  // Without a mouth layer, a gentle bob is the only cue that the character is talking.
  const bobbing = !layered && snapshot.speaking

  return (
    <div
      className="sprite-avatar"
      style={{ aspectRatio: `${canvas.width} / ${canvas.height}` }}
      role="img"
      aria-label={`Avatar: ${snapshot.expression.emotion}`}
    >
      <div ref={motionRef} className="sprite-avatar__motion">
        <div className="sprite-avatar__breath">
          <div className={`sprite-avatar__body${bobbing ? ' sprite-avatar__body--talking' : ''}`}>
            <img className="sprite-avatar__layer" src={assets.baseUrl} alt="" draggable={false} />
            {'layers' in assets && (
              <FaceLayers manifest={assets.manifest} layers={assets.layers} snapshot={snapshot} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface FaceLayersProps {
  manifest: LayeredSpriteManifest
  layers: SpriteLayers
  snapshot: AvatarSnapshot
}

function FaceLayers({ manifest, layers, snapshot }: FaceLayersProps) {
  const { canvas, regions } = manifest
  const expression = resolveExpressionSource(manifest, snapshot.expression.emotion)
  const sources = expressionSources(manifest)

  // Real lip sync drives mouthOpen; without audio levels a CSS loop fakes talking.
  const lipSyncOpen = snapshot.mouthOpen >= MOUTH_OPEN_THRESHOLD
  const fakeTalking = snapshot.speaking && snapshot.mouthOpen === 0

  return (
    <>
      <div className="sprite-avatar__region" style={regionStyle(regions.mouth, canvas)}>
        {sources.map((source) => (
          <LayerImage key={source} src={layers.mouth[source]} visible={source === expression} />
        ))}
        <LayerImage
          src={layers.mouth[manifest.mouthOpen]}
          visible={lipSyncOpen}
          instant
          className={fakeTalking ? 'sprite-avatar__talking' : undefined}
        />
      </div>
      <div className="sprite-avatar__region" style={regionStyle(regions.eyes, canvas)}>
        {sources.map((source) => (
          <LayerImage key={source} src={layers.eyes[source]} visible={source === expression} />
        ))}
        <LayerImage src={layers.eyes[manifest.blink]} visible={snapshot.blinking} instant />
      </div>
    </>
  )
}

interface LayerImageProps {
  src: string | undefined
  visible: boolean
  /** Blink and mouth flaps must not crossfade. */
  instant?: boolean
  className?: string | undefined
}

function LayerImage({ src, visible, instant = false, className }: LayerImageProps) {
  const classes = ['sprite-avatar__layer', instant ? 'sprite-avatar__layer--instant' : '', className ?? '']
  return (
    <img
      className={classes.join(' ').trim()}
      src={src}
      alt=""
      draggable={false}
      style={{ opacity: visible ? 1 : 0 }}
    />
  )
}

function regionStyle(rect: SpriteRect, canvas: { width: number; height: number }): CSSProperties {
  const percent = (value: number, total: number) => `${(value / total) * 100}%`
  return {
    left: percent(rect.x, canvas.width),
    top: percent(rect.y, canvas.height),
    width: percent(rect.width, canvas.width),
    height: percent(rect.height, canvas.height),
  }
}

/** Plays gestures with the Web Animations API, so images never remount. */
function useMotionAnimation(
  motion: keyof typeof SPRITE_MOTION_KEYFRAMES | null,
  motionKey: number,
) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = ref.current
    if (!motion || !element?.animate) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const animation = element.animate(SPRITE_MOTION_KEYFRAMES[motion], {
      duration: MOTION_DURATION_MS[motion],
      easing: 'ease-in-out',
    })
    return () => animation.cancel()
  }, [motion, motionKey])
  return ref
}
