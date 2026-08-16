/**
 * Mock fixtures — the dummy data substituted when the backend is unavailable.
 *
 * Two hard rules:
 *   1. Every fixture matches `docs/API_CONTRACT.md` exactly. Mock data that
 *      drifts from the contract trains the UI on the wrong shape and the bug
 *      only surfaces when the real backend arrives.
 *   2. Nothing here is ever presented as real. Any value sourced from this file
 *      is tagged MOCK in the UI and logged as a fallback in the telemetry bus.
 *
 * Values are physically plausible for the Arabian Sea corridor the routing
 * engine is verified against (18–19.5°N, 71–73°E).
 */

import type {
  CurrentRouteResponse,
  Coordinate,
  HealthResponse,
  RouteAlert,
  RouteLeg,
  RoutePreviewResponse,
  ShipResponse,
  ShipStatusResponse,
  TrackingStartResponse,
} from '@/types/api'
import { SAMPLE_IMO_NUMBERS } from '@/lib/imo'

/** The demo region the backend's examples are verified against. */
export const DEMO_REGION = {
  name: 'Arabian Sea — Mumbai Approaches',
  center: { latitude: 18.75, longitude: 72.2 },
  bounds: { south: 17.6, north: 20.2, west: 70.2, east: 73.4 },
} as const

export const MOCK_VESSELS: Record<string, { name: string; type: string }> = Object.fromEntries(
  SAMPLE_IMO_NUMBERS.map((v) => [v.imo, { name: v.name, type: v.type }]),
)

const NM_PER_DEG_LAT = 60

function haversineNm(a: Coordinate, b: Coordinate): number {
  const R = 3440.065 // Earth radius in nautical miles
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b.latitude - a.latitude)
  const dLon = toRad(b.longitude - a.longitude)
  const lat1 = toRad(a.latitude)
  const lat2 = toRad(b.latitude)
  const h =
    Math.sin(dLat / 2) ** 2 + Math.sin(dLon / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2)
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function pathDistanceNm(path: Coordinate[]): number {
  let total = 0
  for (let i = 0; i < path.length - 1; i += 1) {
    total += haversineNm(path[i]!, path[i + 1]!)
  }
  return total
}

/**
 * Builds a plausible optimal route between two points.
 *
 * Rather than a straight line, this bows the path perpendicular to the track and
 * adds a small deterministic wobble, so it reads like a route that responded to
 * currents and weather. Deterministic on the inputs — the same request always
 * produces the same route, which matters for a demo you rehearse.
 */
export function generateMockRoute(
  start: Coordinate,
  destination: Coordinate,
  options: { waypoints?: number; bow?: number; seed?: number } = {},
): Coordinate[] {
  const { waypoints = 7, bow = 0.13, seed = 1 } = options

  const dLat = destination.latitude - start.latitude
  const dLon = destination.longitude - start.longitude

  // Unit normal to the great-circle track, used to offset intermediate points.
  const len = Math.hypot(dLat, dLon) || 1
  const normalLat = -dLon / len
  const normalLon = dLat / len

  const path: Coordinate[] = [start]

  for (let i = 1; i < waypoints - 1; i += 1) {
    const t = i / (waypoints - 1)
    // Sine envelope: zero deflection at both ends, maximum mid-voyage.
    const envelope = Math.sin(t * Math.PI)
    const wobble = Math.sin(t * Math.PI * 3 + seed) * 0.18
    const offset = bow * envelope * (1 + wobble)

    path.push({
      latitude: Number((start.latitude + dLat * t + normalLat * offset).toFixed(4)),
      longitude: Number((start.longitude + dLon * t + normalLon * offset).toFixed(4)),
    })
  }

  path.push(destination)
  return path
}

function buildLegs(path: Coordinate[], departure: Date, speedKn: number): RouteLeg[] {
  const legs: RouteLeg[] = []
  let elapsedHours = 0

  for (let i = 0; i < path.length - 1; i += 1) {
    const from = path[i]!
    const to = path[i + 1]!
    const distance = haversineNm(from, to)
    const hours = distance / speedKn
    elapsedHours += hours

    // Environmental values drift smoothly along the route so the UI shows
    // variation rather than a constant.
    const phase = i / Math.max(path.length - 2, 1)
    legs.push({
      from,
      to,
      distance_nm: Number(distance.toFixed(2)),
      travel_time_hours: Number(hours.toFixed(2)),
      eta: new Date(departure.getTime() + elapsedHours * 3600_000).toISOString(),
      cost: Number((2.1 + Math.sin(phase * Math.PI * 2) * 0.55).toFixed(4)),
      environment: {
        wind_speed_kn: Number((15 + Math.sin(phase * 3.1) * 5.2).toFixed(1)),
        wind_direction_deg: Number((255 + Math.sin(phase * 2) * 12).toFixed(0)),
        wave_height_m: Number((2.3 + Math.sin(phase * 2.4) * 0.6).toFixed(2)),
        wave_period_s: Number((9.4 + Math.cos(phase * 2) * 0.8).toFixed(1)),
        current_speed_kn: Number((0.3 + Math.sin(phase * 4) * 0.15).toFixed(2)),
        current_direction_deg: Number((128 + Math.cos(phase * 3) * 20).toFixed(0)),
      },
    })
  }

  return legs
}

export function mockHealth(): HealthResponse {
  return { status: 'ok', service: 'naudisha-backend-mock', version: 'mock' }
}

export function mockShip(imo: string): ShipResponse {
  const vessel = MOCK_VESSELS[imo] ?? { name: 'Demo Vessel', type: 'Container Vessel (Panamax)' }

  return {
    imo_number: imo,
    name: vessel.name,
    status: 'underway',
    position: { latitude: 18.52, longitude: 72.91 },
    // ADDENDUM fields: deliberately incomplete, so the manual-entry flow that
    // reacts to `missing_fields` is exercised during mock development.
    ship: {
      ship_type: vessel.type,
      length_m: 294,
      beam_m: 32.2,
      draft_m: null,
      cruising_speed_kn: 18,
      max_speed_kn: null,
    },
    source: 'defaults',
    missing_fields: ['draft_m', 'max_speed_kn'],
  }
}

export function mockRoutePreview(
  imo: string | null | undefined,
  start: Coordinate,
  destination: Coordinate,
  departureTime?: string,
): RoutePreviewResponse {
  const path = generateMockRoute(start, destination)
  const distance = pathDistanceNm(path)
  const speed = 18
  const hours = distance / speed
  const departure = departureTime ? new Date(departureTime) : new Date()

  // Direct-route baseline, so the efficiency figure has something to compare to.
  const directDistance = haversineNm(start, destination)
  const totalCost = Number((distance * 0.1385).toFixed(2))
  const baselineCost = Number((directDistance * 0.169).toFixed(2))

  return {
    imo_number: imo ?? 'MANUAL',
    status: 'route_ready',
    route: path,
    distance_nm: Number(distance.toFixed(2)),
    estimated_time_hours: Number(hours.toFixed(2)),
    total_cost: totalCost,
    departure_time: departure.toISOString(),
    eta: new Date(departure.getTime() + hours * 3600_000).toISOString(),
    baseline_cost: baselineCost,
    efficiency_gain_percent: Number((((baselineCost - totalCost) / baselineCost) * 100).toFixed(1)),
    legs: buildLegs(path, departure, speed),
  }
}

export function mockTrackingStart(imo: string): TrackingStartResponse {
  return { imo_number: imo, tracking: true, message: 'Ship tracking started' }
}

export function mockShipStatus(imo: string, position?: Coordinate): ShipStatusResponse {
  return {
    imo_number: imo,
    status: 'underway',
    position: position ?? { latitude: 18.58, longitude: 72.94 },
    timestamp: new Date().toISOString(),
    destination: { latitude: 19.07, longitude: 72.87 },
    route_status: 'optimal',
  }
}

export function mockCurrentRoute(imo: string, from?: Coordinate): CurrentRouteResponse {
  const start = from ?? { latitude: 18.58, longitude: 72.94 }
  const destination = { latitude: 19.07, longitude: 72.87 }
  const path = generateMockRoute(start, destination, { waypoints: 6, bow: 0.1 })
  const distance = pathDistanceNm(path)
  const hours = distance / 18

  return {
    imo_number: imo,
    route_status: 'optimal',
    route: path,
    distance_nm: Number(distance.toFixed(2)),
    estimated_time_hours: Number(hours.toFixed(2)),
    total_cost: Number((distance * 0.1385).toFixed(2)),
    updated_at: new Date().toISOString(),
    destination,
    baseline_cost: Number((haversineNm(start, destination) * 0.169).toFixed(2)),
    legs: buildLegs(path, new Date(), 18),
  }
}

/**
 * Scripted hazards for the simulated storm scenario. Clearly labelled as
 * simulated wherever they reach the UI — the backend never sent these.
 */
export function mockStormAlerts(near: Coordinate): RouteAlert[] {
  return [
    {
      id: 'sim_storm_01',
      severity: 'critical',
      kind: 'storm',
      message: 'Severe storm cell ahead — 45 kn winds, 5.5 m significant wave height',
      position: {
        latitude: Number((near.latitude + 0.18).toFixed(4)),
        longitude: Number((near.longitude - 0.12).toFixed(4)),
      },
      radius_nm: 22,
      detected_at: new Date().toISOString(),
    },
    {
      id: 'sim_current_01',
      severity: 'warning',
      kind: 'strong_current',
      message: 'Opposing current 2.5 kn along the original corridor',
      position: {
        latitude: Number((near.latitude + 0.06).toFixed(4)),
        longitude: Number((near.longitude - 0.02).toFixed(4)),
      },
      radius_nm: 14,
      detected_at: new Date().toISOString(),
    },
  ]
}

/** Offsets a coordinate by a distance in nautical miles along a bearing. */
export function offsetCoordinate(origin: Coordinate, bearingDeg: number, distanceNm: number): Coordinate {
  const bearing = (bearingDeg * Math.PI) / 180
  const dLat = (distanceNm * Math.cos(bearing)) / NM_PER_DEG_LAT
  const dLon =
    (distanceNm * Math.sin(bearing)) /
    (NM_PER_DEG_LAT * Math.cos((origin.latitude * Math.PI) / 180))

  return {
    latitude: Number((origin.latitude + dLat).toFixed(5)),
    longitude: Number((origin.longitude + dLon).toFixed(5)),
  }
}
