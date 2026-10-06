import invalidServerEvents from '@protocol-fixtures/server-events.invalid.json'
import validServerEvents from '@protocol-fixtures/server-events.valid.json'
import { describe, expect, it } from 'vitest'

import { parseServerEvent, parseServerMessage } from './parse'

describe('parseServerEvent', () => {
  it.each(validServerEvents)('accepts valid fixture %#', (event) => {
    expect(parseServerEvent(event)).toEqual(event)
  })

  it.each(invalidServerEvents)('rejects invalid fixture %#', (event) => {
    expect(parseServerEvent(event)).toBeNull()
  })

  it('rejects non-objects', () => {
    expect(parseServerEvent(null)).toBeNull()
    expect(parseServerEvent([])).toBeNull()
    expect(parseServerEvent('state_changed')).toBeNull()
  })

  it('does not treat inherited properties as event types', () => {
    expect(parseServerEvent({ type: 'toString' })).toBeNull()
  })
})

describe('parseServerMessage', () => {
  it('parses JSON text', () => {
    expect(parseServerMessage('{"type":"state_changed","state":"idle"}')).toEqual({
      type: 'state_changed',
      state: 'idle',
    })
  })

  it('returns null for malformed JSON', () => {
    expect(parseServerMessage('{not json')).toBeNull()
  })
})
