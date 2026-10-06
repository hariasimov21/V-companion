import type { ReconnectConfig } from '../config/appConfig'
import { parseServerMessage } from '../protocol/parse'
import type { ClientEvent, ServerEvent } from '../protocol/types'
import { computeBackoffDelay } from './backoff'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

type Listener<T> = (value: T) => void

/**
 * Minimal surface of the browser WebSocket we rely on; lets tests inject a fake.
 * `never` params: we ignore those event payloads, and it keeps WebSocket assignable.
 */
export interface SocketLike {
  readonly readyState: number
  onopen: ((event: never) => void) | null
  onclose: ((event: never) => void) | null
  onerror: ((event: never) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  send(data: string): void
  close(): void
}

export type SocketFactory = (url: string) => SocketLike

const OPEN = 1

export class BackendClient {
  private socket: SocketLike | null = null
  private attempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private stopped = true
  private readonly eventListeners = new Set<Listener<ServerEvent>>()
  private readonly statusListeners = new Set<Listener<ConnectionStatus>>()

  constructor(
    private readonly url: string,
    private readonly reconnect: ReconnectConfig,
    private readonly createSocket: SocketFactory = (u) => new WebSocket(u),
  ) {}

  connect(): void {
    this.stopped = false
    this.open()
  }

  disconnect(): void {
    this.stopped = true
    this.clearReconnectTimer()
    this.socket?.close()
    this.socket = null
    this.emitStatus('disconnected')
  }

  /** Returns false when the message could not be sent (not connected). */
  send(event: ClientEvent): boolean {
    if (this.socket?.readyState !== OPEN) return false
    this.socket.send(JSON.stringify(event))
    return true
  }

  onEvent(listener: Listener<ServerEvent>): () => void {
    this.eventListeners.add(listener)
    return () => this.eventListeners.delete(listener)
  }

  onStatus(listener: Listener<ConnectionStatus>): () => void {
    this.statusListeners.add(listener)
    return () => this.statusListeners.delete(listener)
  }

  private open(): void {
    this.emitStatus('connecting')
    const socket = this.createSocket(this.url)
    this.socket = socket

    socket.onopen = () => {
      this.attempt = 0
      this.emitStatus('connected')
    }
    socket.onmessage = ({ data }) => this.handleMessage(data)
    socket.onerror = () => socket.close()
    socket.onclose = () => {
      if (this.socket !== socket) return
      this.socket = null
      this.emitStatus('disconnected')
      this.scheduleReconnect()
    }
  }

  private handleMessage(data: unknown): void {
    const event = typeof data === 'string' ? parseServerMessage(data) : null
    if (!event) {
      console.warn('[WS] Ignoring off-protocol message')
      return
    }
    this.eventListeners.forEach((listener) => listener(event))
  }

  private scheduleReconnect(): void {
    if (this.stopped) return
    const delay = computeBackoffDelay(this.attempt, this.reconnect)
    this.attempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.open()
    }, delay)
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private emitStatus(status: ConnectionStatus): void {
    this.statusListeners.forEach((listener) => listener(status))
  }
}
