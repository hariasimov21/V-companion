import { useEffect } from 'react'

import type { AvatarController } from './AvatarController'

const MIN_INTERVAL_MS = 2500
const MAX_EXTRA_MS = 3500

/** Blinks at natural, irregular intervals while the component is mounted. */
export function useAutoBlink(controller: Pick<AvatarController, 'blink'>, enabled = true): void {
  useEffect(() => {
    if (!enabled) return
    let timer: ReturnType<typeof setTimeout>
    const schedule = () => {
      timer = setTimeout(() => {
        controller.blink()
        schedule()
      }, MIN_INTERVAL_MS + Math.random() * MAX_EXTRA_MS)
    }
    schedule()
    return () => clearTimeout(timer)
  }, [controller, enabled])
}
