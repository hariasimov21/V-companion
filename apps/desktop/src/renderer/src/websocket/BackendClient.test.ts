import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ServerEvent } from '../protocol/types'
import { BackendClient, type ConnectionStatus, type SocketLike } from './BackendClient'
import { computeBackoffDelay } from './backoff'

class FakeSocket implements SocketLike {
  readyState = 0
  sent: string[] = []
  onopen: ((event: never) => void) | null = null
  onclose: ((event: never) => void) | null = null
  onerror: ((event: never) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  send(data: string): void {
    this.sent.push(data)
  }
  close(): void {
    this.readyState = 3
    this.onclose?.(undefined as never)
  }
  simulateOpen(): void {
    this.readyState = 1
    this.onopen?.(undefined as never)
  }
  simulateMessage(data: unknown): void {
    this.onmessage?.(new MessageEvent('message', { data }))
  }
}

const reconnect = { initialDelayMs: 100, maxDelayMs: 1000 }

describe('computeBackoffDelay', () => {
  it('grows exponentially and is capped', () => {
    const noJitter = () => 1
    expect(computeBackoffDelay(0, reconnect, noJitter)).toBe(100)
    expect(computeBackoffDelay(2, reconnect, noJitter)).toBe(400)
    expect(computeBackoffDelay(10, reconnect, noJitter)).toBe(1000)
  })

  it('applies jitter within [capped/2, capped]', () => {
    expect(computeBackoffDelay(3, reconnect, () => 0)).toBe(400)
  })
})

describe('BackendClient', () => {
  let sockets: FakeSocket[]
  let client: BackendClient
  let statuses: ConnectionStatus[]

  beforeEach(() => {
    vi.useFakeTimers()
    sockets = []
    statuses = []
    client = new BackendClient('ws://test', reconnect, () => {
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket
    })
    client.onStatus((s) => statuses.push(s))
  })

  afterEach(() => {
    client.disconnect()
    vi.useRealTimers()
  })

  it('reports connection status', () => {
    client.connect()
    sockets[0]?.simulateOpen()
    expect(statuses).toEqual(['connecting', 'connected'])
  })

  it('delivers only valid server events', () => {
    const received: ServerEvent[] = []
    client.onEvent((e) => received.push(e))
    client.connect()
    sockets[0]?.simulateOpen()

    sockets[0]?.simulateMessage('{"type":"state_changed","state":"thinking"}')
    sockets[0]?.simulateMessage('{"type":"state_changed","state":"flying"}')
    sockets[0]?.simulateMessage('garbage')

    expect(received).toEqual([{ type: 'state_changed', state: 'thinking' }])
  })

  it('sends only while connected', () => {
    client.connect()
    expect(client.send({ type: 'speech_finished' })).toBe(false)
    sockets[0]?.simulateOpen()
    expect(client.send({ type: 'user_message', text: 'hola' })).toBe(true)
    expect(sockets[0]?.sent).toEqual(['{"type":"user_message","text":"hola"}'])
  })

  it('reconnects with backoff after the socket closes', () => {
    client.connect()
    sockets[0]?.simulateOpen()
    sockets[0]?.close()
    expect(statuses.at(-1)).toBe('disconnected')
    expect(sockets).toHaveLength(1)

    vi.advanceTimersByTime(reconnect.maxDelayMs)
    expect(sockets).toHaveLength(2)
    expect(statuses.at(-1)).toBe('connecting')
  })

  it('does not reconnect after an explicit disconnect', () => {
    client.connect()
    sockets[0]?.simulateOpen()
    client.disconnect()
    vi.advanceTimersByTime(reconnect.maxDelayMs * 5)
    expect(sockets).toHaveLength(1)
  })
})
