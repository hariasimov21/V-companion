import { describe, expect, it } from 'vitest'

import {
  expressionSources,
  parseSpriteManifest,
  resolveExpressionSource,
  type LayeredSpriteManifest,
} from './manifest'
import { buildSpriteSets } from './spriteAssets'

const validManifest = {
  version: 1,
  id: 'testy',
  canvas: { width: 800, height: 1500 },
  base: 'base.webp',
  regions: {
    eyes: { x: 280, y: 235, width: 180, height: 98 },
    mouth: { x: 280, y: 323, width: 180, height: 54 },
  },
  sources: ['normal', 'happy', 'blink', 'talk'],
  expressions: { neutral: 'normal', happy: 'happy', excited: 'happy' },
  blink: 'blink',
  mouthOpen: 'talk',
}

const manifest = parseSpriteManifest(validManifest) as LayeredSpriteManifest
const staticManifest = {
  version: 1,
  id: 'solo',
  kind: 'static',
  canvas: { width: 900, height: 1500 },
  base: 'base.webp',
}

function imagesFor(dir: string, sources: string[]): Record<string, string> {
  const images: Record<string, string> = { [`${dir}base.webp`]: `/url/${dir}base` }
  for (const layer of ['eyes', 'mouth']) {
    for (const source of sources) images[`${dir}${layer}/${source}.webp`] = `/url/${layer}/${source}`
  }
  return images
}

describe('parseSpriteManifest', () => {
  it('accepts a valid manifest (no kind = layered, for older manifests)', () => {
    expect(manifest.kind).toBe('layered')
  })

  it('accepts a static manifest without face layers', () => {
    expect(parseSpriteManifest(staticManifest)?.kind).toBe('static')
  })

  it.each([
    ['wrong version', { ...validManifest, version: 2 }],
    ['missing region', { ...validManifest, regions: { eyes: validManifest.regions.eyes } }],
    ['zero-size canvas', { ...validManifest, canvas: { width: 0, height: 10 } }],
    ['unknown blink source', { ...validManifest, blink: 'wink' }],
    ['unknown emotion', { ...validManifest, expressions: { furious: 'normal' } }],
    ['expression uses unknown source', { ...validManifest, expressions: { sad: 'crying' } }],
    ['unknown kind', { ...validManifest, kind: 'live2d' }],
    ['static without base', { ...staticManifest, base: undefined }],
  ])('rejects %s', (_, data) => {
    expect(parseSpriteManifest(data)).toBeNull()
  })
})

describe('expression resolution', () => {
  it('maps emotions to sources and falls back to neutral', () => {
    expect(resolveExpressionSource(manifest, 'excited')).toBe('happy')
    expect(resolveExpressionSource(manifest, 'sad')).toBe('normal')
  })

  it('lists each expression source once', () => {
    expect(expressionSources(manifest)).toEqual(['normal', 'happy'])
  })
})

describe('buildSpriteSets', () => {
  const dir = './assets/testy/'
  const manifests = { [`${dir}manifest.json`]: validManifest }

  it('resolves base and layer URLs', () => {
    const assets = buildSpriteSets(manifests, imagesFor(dir, validManifest.sources)).get('testy')
    expect(assets?.baseUrl).toBe('/url/./assets/testy/base')
    expect(assets && 'layers' in assets && assets.layers.eyes['blink']).toBe('/url/eyes/blink')
    expect(assets && 'layers' in assets && assets.layers.mouth['talk']).toBe('/url/mouth/talk')
  })

  it('is empty when nothing is bundled', () => {
    expect(buildSpriteSets({}, {}).size).toBe(0)
  })

  it('skips a set with a missing image', () => {
    const sourcesWithoutTalk = validManifest.sources.filter((s) => s !== 'talk')
    const images = imagesFor(dir, sourcesWithoutTalk)
    expect(buildSpriteSets(manifests, images).has('testy')).toBe(false)
  })

  it('keys sets by id, mixes static and layered, and ignores invalid manifests', () => {
    const solo = './assets/solo/'
    const all = {
      ...manifests,
      [`${solo}manifest.json`]: staticManifest,
      './assets/broken/manifest.json': { version: 99 },
    }
    const images = { ...imagesFor(dir, validManifest.sources), [`${solo}base.webp`]: '/url/solo' }
    const sets = buildSpriteSets(all, images)
    expect([...sets.keys()].sort()).toEqual(['solo', 'testy'])
    expect(sets.get('solo')).toEqual({ manifest: staticManifest, baseUrl: '/url/solo' })
  })
})
