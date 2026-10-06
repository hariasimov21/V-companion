import type { Emotion } from '../../protocol/types'

export type EyeShape = 'open' | 'happy' | 'closed' | 'wide' | 'half'
export type MouthShape = 'smile' | 'grin' | 'frown' | 'flat' | 'o' | 'wavy' | 'small'
export type BrowShape = 'neutral' | 'raised' | 'angry' | 'sad'

export interface EmotionStyle {
  eyes: EyeShape
  mouth: MouthShape
  brows: BrowShape
  blush: boolean
  accent: string
  symbol?: string
}

/** Placeholder equivalent of a Live2D expression mapping: emotion -> visual parts. */
export const EMOTION_STYLES: Record<Emotion, EmotionStyle> = {
  neutral: { eyes: 'open', mouth: 'small', brows: 'neutral', blush: false, accent: '#7c83a6' },
  happy: { eyes: 'happy', mouth: 'smile', brows: 'raised', blush: true, accent: '#ffb547' },
  excited: { eyes: 'wide', mouth: 'grin', brows: 'raised', blush: true, accent: '#ff7a59', symbol: '✦' },
  sad: { eyes: 'half', mouth: 'frown', brows: 'sad', blush: false, accent: '#5b8def' },
  annoyed: { eyes: 'half', mouth: 'flat', brows: 'angry', blush: false, accent: '#e5484d', symbol: '💢' },
  embarrassed: { eyes: 'closed', mouth: 'wavy', brows: 'sad', blush: true, accent: '#ff8fb1' },
  curious: { eyes: 'wide', mouth: 'small', brows: 'raised', blush: false, accent: '#3dd6b5', symbol: '?' },
  thinking: { eyes: 'half', mouth: 'small', brows: 'neutral', blush: false, accent: '#a78bfa', symbol: '…' },
  sleepy: { eyes: 'closed', mouth: 'o', brows: 'sad', blush: false, accent: '#8b9bb4', symbol: 'z' },
  surprised: { eyes: 'wide', mouth: 'o', brows: 'raised', blush: false, accent: '#f5d90a', symbol: '!' },
}
