import { appConfig } from '../config/appConfig'
import type { ObservableAvatarController } from './ObservableAvatarController'
import { PlaceholderAvatar } from './placeholder/PlaceholderAvatar'
import { SpriteAvatar } from './sprite/SpriteAvatar'
import { bundledSpriteSets } from './sprite/spriteAssets'

interface AvatarViewProps {
  controller: ObservableAvatarController
  /** Active character; its sprite set has the same id. */
  characterId: string | null
}

/** Picks the avatar renderer; characters without sprites use the placeholder. */
export function AvatarView({ controller, characterId }: AvatarViewProps) {
  const assets =
    appConfig.avatar.renderer === 'sprite' && characterId
      ? bundledSpriteSets.get(characterId)
      : undefined
  // key: a new character remounts the view, so no layer of the previous one lingers.
  return assets ? (
    <SpriteAvatar key={characterId} controller={controller} assets={assets} />
  ) : (
    <PlaceholderAvatar controller={controller} />
  )
}
