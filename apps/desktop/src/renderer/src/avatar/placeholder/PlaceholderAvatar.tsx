import { useSyncExternalStore } from 'react'

import { type BrowShape, EMOTION_STYLES, type EyeShape, type MouthShape } from './emotionStyles'
import type { ObservableAvatarController } from '../ObservableAvatarController'
import { useAutoBlink } from '../useAutoBlink'

const EYE_X = { left: 78, right: 122 } as const
const EYE_Y = 112
const INK = '#2a2233'

function Eye({ cx, shape, gazeX, gazeY }: { cx: number; shape: EyeShape; gazeX: number; gazeY: number }) {
  switch (shape) {
    case 'happy':
      return <path d={`M${cx - 8} ${EYE_Y + 3} Q${cx} ${EYE_Y - 9} ${cx + 8} ${EYE_Y + 3}`} className="stroke" />
    case 'closed':
      return <path d={`M${cx - 8} ${EYE_Y} Q${cx} ${EYE_Y + 6} ${cx + 8} ${EYE_Y}`} className="stroke" />
    default: {
      const ry = shape === 'wide' ? 12 : shape === 'half' ? 5 : 10
      const rx = shape === 'wide' ? 9 : 7.5
      return (
        <g transform={`translate(${gazeX * 4} ${gazeY * 3})`}>
          <ellipse cx={cx} cy={EYE_Y} rx={rx} ry={ry} fill={INK} />
          <circle cx={cx + 2.5} cy={EYE_Y - ry / 3} r={2.4} fill="#fff" />
        </g>
      )
    }
  }
}

const BROW_PATHS: Record<BrowShape, (cx: number, side: 1 | -1) => string> = {
  neutral: (cx) => `M${cx - 9} 96 L${cx + 9} 96`,
  raised: (cx) => `M${cx - 9} 93 Q${cx} 88 ${cx + 9} 93`,
  angry: (cx, side) => `M${cx - 9} ${side === -1 ? 92 : 99} L${cx + 9} ${side === -1 ? 99 : 92}`,
  sad: (cx, side) => `M${cx - 9} ${side === -1 ? 99 : 93} L${cx + 9} ${side === -1 ? 93 : 99}`,
}

const MOUTH_PATHS: Record<Exclude<MouthShape, 'o'>, string> = {
  smile: 'M88 143 Q100 154 112 143',
  grin: 'M86 141 Q100 162 114 141 Z',
  frown: 'M90 151 Q100 142 110 151',
  flat: 'M92 147 L108 147',
  wavy: 'M88 147 Q94 142 100 147 Q106 152 112 147',
  small: 'M95 146 Q100 150 105 146',
}

function Mouth({ shape, speaking, mouthOpen }: { shape: MouthShape; speaking: boolean; mouthOpen: number }) {
  if (speaking) {
    // With real lip sync mouthOpen drives the shape; without audio, a CSS loop fakes it.
    const driven = mouthOpen > 0
    return (
      <ellipse
        cx={100}
        cy={147}
        rx={7}
        ry={driven ? 1.5 + mouthOpen * 7 : 5}
        fill="#7a2b3a"
        className={driven ? undefined : 'mouth--talking'}
      />
    )
  }
  if (shape === 'o') return <ellipse cx={100} cy={148} rx={5} ry={6} fill="#7a2b3a" />
  const filled = shape === 'grin'
  return <path d={MOUTH_PATHS[shape]} className={filled ? 'mouth-fill' : 'stroke'} />
}

interface PlaceholderAvatarProps {
  controller: ObservableAvatarController
}

export function PlaceholderAvatar({ controller }: PlaceholderAvatarProps) {
  const snapshot = useSyncExternalStore(controller.subscribe, controller.getSnapshot)
  useAutoBlink(controller)

  const { expression, motion, motionKey, gaze, blinking, speaking, mouthOpen } = snapshot
  const style = EMOTION_STYLES[expression.emotion]
  const eyes: EyeShape = blinking ? 'closed' : style.eyes

  return (
    <svg className="placeholder-avatar" viewBox="0 0 200 240" role="img" aria-label={`Avatar: ${expression.emotion}`}>
      <circle cx={100} cy={118} r={92} fill={style.accent} opacity={0.15 + expression.intensity * 0.3} className="aura" />
      <g key={motionKey} className={motion ? `head motion-${motion}` : 'head'}>
        <ellipse cx={100} cy={118} rx={72} ry={78} fill="#3b2e5a" />
        <rect x={52} y={150} width={96} height={70} rx={30} fill="#3b2e5a" />
        <circle cx={100} cy={116} r={60} fill="#ffe3d3" />
        <path d="M40 112 Q46 52 100 50 Q154 52 160 112 Q140 78 118 74 Q108 92 84 88 Q90 76 92 70 Q60 80 40 112 Z" fill="#4a3870" />
        {style.blush && (
          <g opacity={0.35 + expression.intensity * 0.5}>
            <ellipse cx={68} cy={132} rx={10} ry={5} fill="#ff8fa3" />
            <ellipse cx={132} cy={132} rx={10} ry={5} fill="#ff8fa3" />
          </g>
        )}
        <path d={BROW_PATHS[style.brows](EYE_X.left, -1)} className="stroke brow" />
        <path d={BROW_PATHS[style.brows](EYE_X.right, 1)} className="stroke brow" />
        <Eye cx={EYE_X.left} shape={eyes} gazeX={gaze.x} gazeY={gaze.y} />
        <Eye cx={EYE_X.right} shape={eyes} gazeX={gaze.x} gazeY={gaze.y} />
        <Mouth shape={style.mouth} speaking={speaking} mouthOpen={mouthOpen} />
        {style.symbol && (
          <text x={158} y={64} className="emotion-symbol" fill={style.accent}>
            {style.symbol}
          </text>
        )}
      </g>
      {motion === 'wave' && (
        <text key={`wave-${motionKey}`} x={164} y={196} className="wave-hand">
          👋
        </text>
      )}
    </svg>
  )
}
