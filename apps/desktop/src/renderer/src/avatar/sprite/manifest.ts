import { EMOTIONS, type Emotion } from '../../protocol/types'

/**
 * Describes a sprite avatar produced by tools/avatar/prepare_sprites.py. Two kinds:
 * - layered: a body image plus eye and mouth layers per source image, and which source
 *   each emotion uses (blinks, lip flaps, expressions).
 * - static: a single image (breathing and gestures only), until the face variants exist.
 */
export interface SpriteRect {
  x: number
  y: number
  width: number
  height: number
}

export type SpriteLayerName = 'eyes' | 'mouth'

interface ManifestCommon {
  version: 1
  id: string
  canvas: { width: number; height: number }
  base: string
}

export interface StaticSpriteManifest extends ManifestCommon {
  kind: 'static'
}

export interface LayeredSpriteManifest extends ManifestCommon {
  kind: 'layered'
  regions: Record<SpriteLayerName, SpriteRect>
  sources: string[]
  expressions: Partial<Record<Emotion, string>>
  blink: string
  mouthOpen: string
}

export type SpriteManifest = StaticSpriteManifest | LayeredSpriteManifest

type JsonObject = Record<string, unknown>

const isObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isPositive = (value: unknown): value is number => typeof value === 'number' && value > 0

const isRect = (value: unknown): value is SpriteRect =>
  isObject(value) &&
  typeof value['x'] === 'number' &&
  typeof value['y'] === 'number' &&
  isPositive(value['width']) &&
  isPositive(value['height'])

function isExpressionMap(
  value: unknown,
  sources: string[],
): value is LayeredSpriteManifest['expressions'] {
  if (!isObject(value)) return false
  return Object.entries(value).every(
    ([emotion, source]) =>
      (EMOTIONS as readonly string[]).includes(emotion) &&
      typeof source === 'string' &&
      sources.includes(source),
  )
}

/** Validates a manifest loaded from disk; returns null if anything is off. */
export function parseSpriteManifest(data: unknown): SpriteManifest | null {
  if (!isObject(data) || data['version'] !== 1 || typeof data['id'] !== 'string') return null
  const { canvas, regions, sources } = data
  if (!isObject(canvas) || !isPositive(canvas['width']) || !isPositive(canvas['height'])) return null
  if (typeof data['base'] !== 'string') return null
  if (data['kind'] === 'static') return data as unknown as StaticSpriteManifest
  // Manifests from before `kind` existed are layered.
  if (data['kind'] !== undefined && data['kind'] !== 'layered') return null
  if (!isObject(regions) || !isRect(regions['eyes']) || !isRect(regions['mouth'])) return null
  if (!Array.isArray(sources) || !sources.every((s) => typeof s === 'string')) return null
  const sourceNames = sources as string[]
  if (!sourceNames.includes(data['blink'] as string)) return null
  if (!sourceNames.includes(data['mouthOpen'] as string)) return null
  if (!isExpressionMap(data['expressions'], sourceNames)) return null
  return { ...(data as unknown as LayeredSpriteManifest), kind: 'layered' }
}

/** Source image for an emotion, falling back to neutral and then to the first source. */
export function resolveExpressionSource(manifest: LayeredSpriteManifest, emotion: Emotion): string {
  return manifest.expressions[emotion] ?? manifest.expressions.neutral ?? (manifest.sources[0] as string)
}

/** Unique sources used by expressions, i.e. the layers a view needs to render. */
export function expressionSources(manifest: LayeredSpriteManifest): string[] {
  return [...new Set(Object.values(manifest.expressions))]
}
