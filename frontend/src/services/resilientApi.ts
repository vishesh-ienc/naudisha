/**
 * Resilient API layer — owns the live-vs-mock decision for every call.
 *
 * Policy, in order:
 *   1. In Force Mock mode, skip the network entirely.
 *   2. Attempt the real backend.
 *   3. On success, return live data (source: 'live').
 *   4. On a *transient or structural* failure — network down, timeout, 5xx,
 *      404 (endpoint not built), or an off-contract body — substitute the mock
 *      fixture and record why.
 *   5. On a 4xx client error, DO NOT fall back. A rejected IMO or invalid
 *      coordinate pair is a real answer about the user's input; masking it with
 *      plausible fake data would actively mislead them.
 *
 * Rule 5 is the one that matters most. "Fall back on everything" feels safer but
 * silently converts user errors into fabricated successes.
 *
 * Every outcome is recorded in the telemetry bus, so the Data Source Console can
 * show exactly what was tried, what came back, and which values are dummy.
 */

import * as api from './apiClient'
import { HttpError } from './http'
import * as mock from './mock/fixtures'
import { telemetry, type DataSource, type FallbackReason } from './telemetry'
import type {
  Coordinate,
  CurrentRouteResponse,
  RoutePreviewRequest,
  RoutePreviewResponse,
  ShipResponse,
  ShipStatusResponse,
  TrackingStartRequest,
  TrackingStartResponse,
} from '@/types/api'

// ---------------------------------------------------------------------------
// Mode
// ---------------------------------------------------------------------------

export type ApiMode = 'auto' | 'live' | 'mock'

const MODE_STORAGE_KEY = 'naudisha.apiMode'

let currentMode: ApiMode = readStoredMode()
const modeListeners = new Set<() => void>()

function readStoredMode(): ApiMode {
  if (typeof localStorage === 'undefined') return 'auto'
  const stored = localStorage.getItem(MODE_STORAGE_KEY)
  return stored === 'live' || stored === 'mock' || stored === 'auto' ? stored : 'auto'
}

export function getApiMode(): ApiMode {
  return currentMode
}

export function setApiMode(mode: ApiMode): void {
  currentMode = mode
  try {
    localStorage.setItem(MODE_STORAGE_KEY, mode)
  } catch {
    // Private browsing — mode simply won't persist across reloads.
  }
  telemetry.log('info', `API mode set to "${mode}"`, 'resilientApi')
  modeListeners.forEach((l) => l())
}

export function subscribeToMode(listener: () => void): () => void {
  modeListeners.add(listener)
  return () => modeListeners.delete(listener)
}

// ---------------------------------------------------------------------------
// Result envelope
// ---------------------------------------------------------------------------

export interface Resolved<T> {
  data: T
  source: DataSource
  /** Present when `source` is not 'live'. */
  fallbackReason?: FallbackReason
  detail?: string
}

/** Thrown for genuine client errors that must reach the user unmasked. */
export class UserFacingApiError extends Error {
  readonly code: string
  readonly missingFields?: string[]
  readonly status?: number

  constructor(message: string, code: string, status?: number, missingFields?: string[]) {
    super(message)
    this.name = 'UserFacingApiError'
    this.code = code
    if (status !== undefined) this.status = status
    if (missingFields !== undefined) this.missingFields = missingFields
  }
}

function classifyFallback(error: HttpError): FallbackReason {
  switch (error.kind) {
    case 'network':
      return 'network_error'
    case 'timeout':
      return 'timeout'
    case 'server':
      return 'server_error'
    case 'schema':
      return 'schema_mismatch'
    case 'not_found':
      return 'not_implemented'
    default:
      return 'network_error'
  }
}

/**
 * Runs `attempt`, falling back to `fallback()` per the policy above.
 * `label` is the human-readable operation name shown in the console UI.
 */
async function resolve<T>(
  label: string,
  method: string,
  endpoint: string,
  attempt: () => Promise<T>,
  fallback: () => T,
  requestBody?: unknown,
): Promise<Resolved<T>> {
  const started = performance.now()

  if (currentMode === 'mock') {
    const data = fallback()
    telemetry.record({
      method,
      endpoint,
      label,
      outcome: 'skipped',
      source: 'mock',
      durationMs: Math.round(performance.now() - started),
      attempts: 0,
      fallbackReason: 'forced_mock',
      detail: 'Force Mock mode — no network request attempted',
      requestBody,
      responseBody: data,
    })
    return { data, source: 'mock', fallbackReason: 'forced_mock' }
  }

  try {
    const data = await attempt()
    telemetry.record({
      method,
      endpoint,
      label,
      outcome: 'success',
      source: 'live',
      durationMs: Math.round(performance.now() - started),
      attempts: 1,
      requestBody,
      responseBody: data,
    })
    return { data, source: 'live' }
  } catch (err) {
    const httpError = err instanceof HttpError ? err : new HttpError('network', String(err))
    const durationMs = Math.round(performance.now() - started)

    // Genuine client error — surface it, never fabricate a success.
    if (httpError.kind === 'client') {
      telemetry.record({
        method,
        endpoint,
        label,
        outcome: 'error',
        source: 'live',
        ...(httpError.status !== undefined && { httpStatus: httpError.status }),
        durationMs,
        attempts: 1,
        detail: `${httpError.apiError?.code ?? 'CLIENT_ERROR'} — ${httpError.detail}`,
        requestBody,
      })
      throw new UserFacingApiError(
        httpError.detail,
        httpError.apiError?.code ?? 'INVALID_REQUEST',
        httpError.status,
        httpError.apiError?.missing_fields,
      )
    }

    // Force Live mode: report the failure rather than hiding it behind mock data.
    if (currentMode === 'live') {
      telemetry.record({
        method,
        endpoint,
        label,
        outcome: 'error',
        source: 'live',
        ...(httpError.status !== undefined && { httpStatus: httpError.status }),
        durationMs,
        attempts: 1,
        detail: `Force Live mode — ${httpError.detail}`,
        requestBody,
      })
      throw new UserFacingApiError(httpError.detail, 'BACKEND_UNAVAILABLE', httpError.status)
    }

    const reason = classifyFallback(httpError)
    const data = fallback()

    telemetry.record({
      method,
      endpoint,
      label,
      outcome: 'fallback',
      source: 'mock',
      ...(httpError.status !== undefined && { httpStatus: httpError.status }),
      durationMs,
      attempts: 1,
      fallbackReason: reason,
      detail: httpError.detail,
      requestBody,
      responseBody: data,
    })

    return { data, source: 'mock', fallbackReason: reason, detail: httpError.detail }
  }
}

// ---------------------------------------------------------------------------
// Backend availability
// ---------------------------------------------------------------------------

export interface BackendHealth {
  online: boolean
  service?: string
  version?: string
  checkedAt: number
  detail?: string
}

export async function probeBackend(): Promise<BackendHealth> {
  const started = performance.now()
  try {
    const health = await api.getHealth()
    telemetry.record({
      method: 'GET',
      endpoint: '/health',
      label: 'Backend health probe',
      outcome: 'success',
      source: 'live',
      durationMs: Math.round(performance.now() - started),
      attempts: 1,
      responseBody: health,
    })
    return {
      online: true,
      service: health.service,
      ...(health.version !== undefined && { version: health.version }),
      checkedAt: Date.now(),
    }
  } catch (err) {
    const detail = err instanceof HttpError ? err.detail : String(err)
    telemetry.record({
      method: 'GET',
      endpoint: '/health',
      label: 'Backend health probe',
      outcome: 'fallback',
      source: 'mock',
      durationMs: Math.round(performance.now() - started),
      attempts: 1,
      fallbackReason: 'backend_offline',
      detail,
    })
    return { online: false, checkedAt: Date.now(), detail }
  }
}

// ---------------------------------------------------------------------------
// Contract operations
// ---------------------------------------------------------------------------

export function identifyShip(imoNumber: string): Promise<Resolved<ShipResponse>> {
  return resolve(
    'Identify ship',
    'POST',
    api.ENDPOINTS.ships,
    () => api.identifyShip(imoNumber),
    () => mock.mockShip(imoNumber),
    { imo_number: imoNumber },
  )
}

export function previewRoute(payload: RoutePreviewRequest): Promise<Resolved<RoutePreviewResponse>> {
  return resolve(
    'Preview optimal route',
    'POST',
    api.ENDPOINTS.routePreview,
    () => api.previewRoute(payload),
    () =>
      mock.mockRoutePreview(
        payload.imo_number,
        payload.start,
        payload.destination,
        payload.departure_time,
      ),
    payload,
  )
}

export function startTracking(
  imoNumber: string,
  payload: TrackingStartRequest = {},
): Promise<Resolved<TrackingStartResponse>> {
  return resolve(
    'Start tracking',
    'POST',
    api.ENDPOINTS.trackingStart(imoNumber),
    () => api.startTracking(imoNumber, payload),
    () => mock.mockTrackingStart(imoNumber),
    payload,
  )
}

export function getShipStatus(
  imoNumber: string,
  simulatedPosition?: Coordinate,
): Promise<Resolved<ShipStatusResponse>> {
  return resolve(
    'Get ship status',
    'GET',
    api.ENDPOINTS.shipStatus(imoNumber),
    () => api.getShipStatus(imoNumber),
    () => mock.mockShipStatus(imoNumber, simulatedPosition),
  )
}

export function getCurrentRoute(
  imoNumber: string,
  from?: Coordinate,
): Promise<Resolved<CurrentRouteResponse>> {
  return resolve(
    'Get current route',
    'GET',
    api.ENDPOINTS.shipRoute(imoNumber),
    () => api.getCurrentRoute(imoNumber),
    () => mock.mockCurrentRoute(imoNumber, from),
  )
}
