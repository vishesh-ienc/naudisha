/**
 * Telemetry bus — the record of every data-access decision the app makes.
 *
 * Requirement this serves: when the backend is unavailable and we substitute
 * dummy data, that substitution must be visible and explained, not silent. Every
 * call records what was attempted, what came back, whether the value shown to the
 * user is LIVE or MOCK, and why it fell back.
 *
 * Deliberately dependency-free (no React, no store) so it can be imported by the
 * service layer without creating a cycle. Components subscribe via `useTelemetry`.
 */

import { uid } from '@/lib/utils'

export type DataSource = 'live' | 'mock' | 'simulated'

export type CallOutcome =
  | 'success' // backend answered and the response validated
  | 'fallback' // backend failed or was off-contract; mock data substituted
  | 'error' // failed with no fallback (e.g. a 4xx we must surface)
  | 'skipped' // not attempted (Force Mock mode)

export type FallbackReason =
  | 'network_error'
  | 'timeout'
  | 'server_error'
  | 'schema_mismatch'
  | 'not_implemented'
  | 'forced_mock'
  | 'backend_offline'

export interface TelemetryEntry {
  id: string
  timestamp: number
  method: string
  endpoint: string
  label: string
  outcome: CallOutcome
  source: DataSource
  httpStatus?: number
  durationMs: number
  attempts: number
  fallbackReason?: FallbackReason
  /** Human-readable detail — the schema error path, the HTTP message, etc. */
  detail?: string
  requestBody?: unknown
  responseBody?: unknown
}

export interface TelemetryLogEntry {
  id: string
  timestamp: number
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
  context?: string
}

type Listener = () => void

const MAX_ENTRIES = 200

class TelemetryBus {
  private entries: TelemetryEntry[] = []
  private logs: TelemetryLogEntry[] = []
  private listeners = new Set<Listener>()

  /** Cached snapshots — useSyncExternalStore requires referential stability. */
  private entriesSnapshot: TelemetryEntry[] = []
  private logsSnapshot: TelemetryLogEntry[] = []

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  getEntries = (): TelemetryEntry[] => this.entriesSnapshot
  getLogs = (): TelemetryLogEntry[] => this.logsSnapshot

  record(entry: Omit<TelemetryEntry, 'id' | 'timestamp'>): TelemetryEntry {
    const full: TelemetryEntry = { ...entry, id: uid('tel'), timestamp: Date.now() }

    this.entries = [full, ...this.entries].slice(0, MAX_ENTRIES)
    this.entriesSnapshot = this.entries

    this.mirrorToConsole(full)
    this.emit()
    return full
  }

  log(level: TelemetryLogEntry['level'], message: string, context?: string): void {
    const entry: TelemetryLogEntry = {
      id: uid('log'),
      timestamp: Date.now(),
      level,
      message,
      ...(context !== undefined && { context }),
    }
    this.logs = [entry, ...this.logs].slice(0, MAX_ENTRIES)
    this.logsSnapshot = this.logs
    this.emit()
  }

  clear(): void {
    this.entries = []
    this.entriesSnapshot = []
    this.logs = []
    this.logsSnapshot = []
    this.emit()
  }

  /**
   * Mirror to the browser console so the fallback story is legible from devtools
   * during a demo without opening the in-app panel.
   */
  private mirrorToConsole(e: TelemetryEntry): void {
    const tag = `[NauDisha] ${e.method} ${e.endpoint}`
    const timing = `${e.durationMs}ms`

    switch (e.outcome) {
      case 'success':
        console.info(`%c${tag} → LIVE (${timing})`, 'color:#10b981;font-weight:600')
        break
      case 'fallback':
        console.warn(
          `%c${tag} → MOCK (${timing}) — reason: ${e.fallbackReason}${e.detail ? ` — ${e.detail}` : ''}`,
          'color:#f59e0b;font-weight:600',
        )
        break
      case 'error':
        console.error(`%c${tag} → ERROR (${timing}) — ${e.detail ?? 'unknown'}`, 'color:#ef4444;font-weight:600')
        break
      case 'skipped':
        console.info(`%c${tag} → MOCK (forced)`, 'color:#6366f1;font-weight:600')
        break
    }
  }

  private emit(): void {
    this.listeners.forEach((l) => l())
  }
}

export const telemetry = new TelemetryBus()

/** Human-readable explanation of a fallback, shown in the console UI. */
export const FALLBACK_REASON_TEXT: Record<FallbackReason, string> = {
  network_error: 'Backend unreachable — connection refused or DNS failure',
  timeout: 'Backend did not respond within the timeout window',
  server_error: 'Backend returned a 5xx server error',
  schema_mismatch: 'Response did not match the API contract',
  not_implemented: 'Endpoint not implemented on the backend yet (404)',
  forced_mock: 'Force Mock mode is enabled',
  backend_offline: 'Health probe reports the backend is offline',
}
