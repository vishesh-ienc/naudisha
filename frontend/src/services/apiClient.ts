/**
 * Typed backend calls — one function per contract endpoint, and nothing else.
 *
 * This module is a faithful transcription of `docs/API_CONTRACT.md`. It performs
 * no fallback logic and no error interpretation; it either returns a validated
 * response or throws `HttpError`. All policy lives in `resilientApi`.
 *
 * Endpoints not yet built on the backend are marked NOT YET IMPLEMENTED — they
 * are written against the contract so that switching to live requires no change
 * here, only the backend shipping them.
 */

import { request, type RequestOptions } from './http'
import {
  currentRouteResponseSchema,
  healthResponseSchema,
  routePreviewResponseSchema,
  shipResponseSchema,
  shipStatusResponseSchema,
  trackingStartResponseSchema,
} from './schemas'
import type {
  CurrentRouteResponse,
  HealthResponse,
  RoutePreviewRequest,
  RoutePreviewResponse,
  ShipResponse,
  ShipStatusResponse,
  TrackingStartRequest,
  TrackingStartResponse,
} from '@/types/api'

/** Relative paths — the Vite dev proxy forwards these to the backend origin. */
export const ENDPOINTS = {
  health: '/health',
  ships: '/api/ships',
  routePreview: '/api/routes/preview',
  trackingStart: (imo: string) => `/api/ships/${encodeURIComponent(imo)}/tracking/start`,
  shipStatus: (imo: string) => `/api/ships/${encodeURIComponent(imo)}/status`,
  shipRoute: (imo: string) => `/api/ships/${encodeURIComponent(imo)}/route`,
  liveSocket: (imo: string) => `/ws/ships/${encodeURIComponent(imo)}`,
} as const

/** ADDENDUM P2-1. Availability probe — short timeout, no retry. */
export function getHealth(opts?: RequestOptions): Promise<HealthResponse> {
  return request(ENDPOINTS.health, healthResponseSchema, {
    method: 'GET',
    timeoutMs: 2500,
    retries: 0,
    ...opts,
  })
}

/** Contract §4. */
export function identifyShip(imoNumber: string, opts?: RequestOptions): Promise<ShipResponse> {
  return request(ENDPOINTS.ships, shipResponseSchema, {
    method: 'POST',
    body: { imo_number: imoNumber },
    ...opts,
  })
}

/** Contract §5. */
export function previewRoute(
  payload: RoutePreviewRequest,
  opts?: RequestOptions,
): Promise<RoutePreviewResponse> {
  // Omit undefined/null keys so a v1 backend never receives unexpected fields.
  const body: Record<string, unknown> = {
    start: payload.start,
    destination: payload.destination,
  }
  if (payload.imo_number) body.imo_number = payload.imo_number
  if (payload.departure_time) body.departure_time = payload.departure_time
  if (payload.ship) body.ship = payload.ship

  return request(ENDPOINTS.routePreview, routePreviewResponseSchema, {
    method: 'POST',
    body,
    timeoutMs: 20000, // Route computation may fetch live environmental data.
    ...opts,
  })
}

/** Contract §6. NOT YET IMPLEMENTED on the backend. */
export function startTracking(
  imoNumber: string,
  payload: TrackingStartRequest = {},
  opts?: RequestOptions,
): Promise<TrackingStartResponse> {
  return request(ENDPOINTS.trackingStart(imoNumber), trackingStartResponseSchema, {
    method: 'POST',
    body: payload,
    ...opts,
  })
}

/** Contract §7. NOT YET IMPLEMENTED on the backend. */
export function getShipStatus(imoNumber: string, opts?: RequestOptions): Promise<ShipStatusResponse> {
  return request(ENDPOINTS.shipStatus(imoNumber), shipStatusResponseSchema, {
    method: 'GET',
    ...opts,
  })
}

/** Contract §8. NOT YET IMPLEMENTED on the backend. */
export function getCurrentRoute(
  imoNumber: string,
  opts?: RequestOptions,
): Promise<CurrentRouteResponse> {
  return request(ENDPOINTS.shipRoute(imoNumber), currentRouteResponseSchema, {
    method: 'GET',
    ...opts,
  })
}

/** Absolute ws:// URL for the live socket, derived from the page origin. */
export function liveSocketUrl(imoNumber: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${ENDPOINTS.liveSocket(imoNumber)}`
}
