import { describe, expect, it } from 'vitest'

import { createAppConfig } from './appConfig'

describe('createAppConfig', () => {
  it('uses the configured backend URL', () => {
    expect(createAppConfig({ VITE_BACKEND_WS_URL: 'ws://example:9000/ws' }).backendWsUrl).toBe(
      'ws://example:9000/ws',
    )
  })

  it('falls back to the local backend', () => {
    expect(createAppConfig({}).backendWsUrl).toBe('ws://127.0.0.1:8000/ws')
    expect(createAppConfig({ VITE_BACKEND_WS_URL: '' }).backendWsUrl).toBe('ws://127.0.0.1:8000/ws')
  })
})
