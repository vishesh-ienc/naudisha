/**
 * WebSocket client for live position and route updates (contract §9-§11).
 *
 * Responsibilities kept here rather than in the component:
 *   • reconnect with exponential backoff and jitter
 *   • validate every frame against the contract schema before it reaches the UI
 *   • discard out-of-order messages by timestamp, as §9 instructs
 *   • report connection state so the interface can say what it is doing
 *
 * A dropped connection is expected, not exceptional — the socket reconnects
 * quietly and the caller re-syncs via REST, which is what §9 prescribes.
 */

import { liveSocketUrl } from './apiClient'
import { liveMessageSchema } from './schemas'
import { formatSchemaError } from './schemas'
import { telemetry } from './telemetry'
import type { LiveMessage } from '@/types/api'

export type SocketState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed' | 'failed'

export interface LiveSocketHandlers {
  onMessage: (message: LiveMessage) => void
  onStateChange?: (state: SocketState) => void
  /** Fired after a successful reconnect so the caller can re-sync via REST (§9). */
  onReconnected?: () => void
}

const MAX_BACKOFF_MS = 30_000
const BASE_BACKOFF_MS = 1_000
/** Give up after this many consecutive failures and let the caller fall back. */
const MAX_ATTEMPTS = 6

export class LiveSocket {
  private ws: WebSocket | null = null
  private closedByUs = false
  private attempts = 0
  private timer: ReturnType<typeof setTimeout> | null = null
  private lastTimestampMs = 0
  private hasConnectedOnce = false

  // Declared explicitly rather than as constructor parameter properties, which
  // `erasableSyntaxOnly` disallows: they emit runtime code from type syntax.
  private readonly imoNumber: string
  private readonly handlers: LiveSocketHandlers

  constructor(imoNumber: string, handlers: LiveSocketHandlers) {
    this.imoNumber = imoNumber
    this.handlers = handlers
  }

  connect(): void {
    this.closedByUs = false
    this.open()
  }

  close(): void {
    this.closedByUs = true
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    if (this.ws) {
      // Detach handlers first so the close does not schedule a reconnect.
      this.ws.onclose = null
      this.ws.onerror = null
      this.ws.onmessage = null
      this.ws.onopen = null
      try {
        this.ws.close()
      } catch {
        // Already closing — nothing to do.
      }
      this.ws = null
    }
    this.setState('closed')
  }

  private setState(state: SocketState): void {
    this.handlers.onStateChange?.(state)
  }

  private open(): void {
    this.setState(this.attempts === 0 ? 'connecting' : 'reconnecting')

    let socket: WebSocket
    try {
      socket = new WebSocket(liveSocketUrl(this.imoNumber))
    } catch (err) {
      this.scheduleReconnect(`could not open socket: ${String(err)}`)
      return
    }

    this.ws = socket

    socket.onopen = () => {
      const reconnected = this.hasConnectedOnce
      this.attempts = 0
      this.hasConnectedOnce = true
      this.setState('open')

      telemetry.record({
        method: 'WS',
        endpoint: `/ws/ships/${this.imoNumber}`,
        label: reconnected ? 'Live socket reconnected' : 'Live socket connected',
        outcome: 'success',
        source: 'live',
        durationMs: 0,
        attempts: 1,
      })

      if (reconnected) this.handlers.onReconnected?.()
    }

    socket.onmessage = (event) => {
      let payload: unknown
      try {
        payload = JSON.parse(String(event.data))
      } catch {
        telemetry.log('warn', 'Live socket sent a non-JSON frame', 'liveSocket')
        return
      }

      const parsed = liveMessageSchema.safeParse(payload)
      if (!parsed.success) {
        // An off-contract frame is dropped rather than crashing the tracking UI,
        // and named precisely so the mismatch is diagnosable.
        telemetry.log(
          'error',
          `Live socket frame off-contract — ${formatSchemaError(parsed.error)}`,
          'liveSocket',
        )
        return
      }

      const message = parsed.data
      const timestampMs = Date.parse(message.timestamp)

      // §9: messages are chronological; anything older than the newest already
      // applied is a delayed duplicate and must not move the vessel backwards.
      if (Number.isFinite(timestampMs)) {
        if (timestampMs < this.lastTimestampMs) return
        this.lastTimestampMs = timestampMs
      }

      this.handlers.onMessage(message)
    }

    socket.onerror = () => {
      // `onclose` always follows, and carries the information worth acting on.
    }

    socket.onclose = () => {
      if (this.closedByUs) return
      this.scheduleReconnect('connection closed')
    }
  }

  private scheduleReconnect(reason: string): void {
    this.ws = null
    this.attempts += 1

    if (this.attempts > MAX_ATTEMPTS) {
      this.setState('failed')
      telemetry.record({
        method: 'WS',
        endpoint: `/ws/ships/${this.imoNumber}`,
        label: 'Live socket unavailable',
        outcome: 'fallback',
        source: 'mock',
        durationMs: 0,
        attempts: this.attempts,
        fallbackReason: 'network_error',
        detail: `${reason} — giving up after ${MAX_ATTEMPTS} attempts, falling back to polling`,
      })
      return
    }

    // Exponential backoff with jitter so multiple clients do not retry in lockstep.
    const delay = Math.min(BASE_BACKOFF_MS * 2 ** (this.attempts - 1), MAX_BACKOFF_MS)
    const jittered = delay + Math.random() * 250

    this.setState('reconnecting')
    telemetry.log('warn', `Live socket ${reason}; retrying in ${Math.round(jittered)}ms`, 'liveSocket')

    this.timer = setTimeout(() => this.open(), jittered)
  }
}
