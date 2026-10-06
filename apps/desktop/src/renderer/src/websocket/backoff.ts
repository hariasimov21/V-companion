import type { ReconnectConfig } from '../config/appConfig'

/** Exponential backoff with "equal jitter": half fixed, half random. */
export function computeBackoffDelay(
  attempt: number,
  config: ReconnectConfig,
  random: () => number = Math.random,
): number {
  const exponential = config.initialDelayMs * 2 ** Math.max(0, attempt)
  const capped = Math.min(exponential, config.maxDelayMs)
  return Math.round(capped / 2 + (random() * capped) / 2)
}
