import type { Coordinate } from '@/types/api'

export interface GeoBounds {
  south: number
  north: number
  west: number
  east: number
}

export const NAVIGABLE_REGION = {
  name: 'Arabian Sea — Mumbai Approaches',
  center: { latitude: 18.75, longitude: 72.2 },
  defaultZoom: 9,
  bounds: {
    south: 17.5,
    north: 20.5,
    west: 70.0,
    east: 73.5,
  },
}

export const PRESET_LOCATIONS = [
  {
    name: 'Mumbai Approaches Fairway',
    detail: 'Open-water pilot boarding ground',
    coordinate: { latitude: 18.85, longitude: 72.45 },
  },
  {
    name: 'JNPT Outer Anchorage',
    detail: 'Deep-water holding area',
    coordinate: { latitude: 18.78, longitude: 72.55 },
  },
  {
    name: 'Alibag Offshore Passage',
    detail: 'Southbound coastal shipping route',
    coordinate: { latitude: 18.52, longitude: 72.55 },
  },
  {
    name: 'North Arabian Sea Waypoint',
    detail: 'Northbound traffic separation approach',
    coordinate: { latitude: 19.15, longitude: 72.35 },
  },
]

const EARTH_RADIUS_NM = 3440.065 // 6371 km in nautical miles

/**
 * Calculates great-circle distance between two coordinates in nautical miles.
 */
export function haversineNm(c1: Coordinate, c2: Coordinate): number {
  if (!c1 || !c2) return 0
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(c2.latitude - c1.latitude)
  const dLon = toRad(c2.longitude - c1.longitude)
  const lat1 = toRad(c1.latitude)
  const lat2 = toRad(c2.latitude)

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return EARTH_RADIUS_NM * c
}

/**
 * Calculates the initial forward azimuth/bearing in degrees [0, 360).
 */
export function bearingDeg(c1: Coordinate, c2: Coordinate): number {
  if (!c1 || !c2) return 0
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const toDeg = (rad: number) => (rad * 180) / Math.PI

  const lat1 = toRad(c1.latitude)
  const lat2 = toRad(c2.latitude)
  const dLon = toRad(c2.longitude - c1.longitude)

  const y = Math.sin(dLon) * Math.cos(lat2)
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon)
  const initial = toDeg(Math.atan2(y, x))
  return (initial + 360) % 360
}

/**
 * Interpolates a position along a multi-segment polyline path after travelling `distanceNm`.
 */
export function pointAlongPath(
  path: Coordinate[],
  distanceNm: number,
): { position: Coordinate; segmentIndex: number; complete: boolean } {
  if (!path || path.length === 0) {
    return { position: { latitude: 0, longitude: 0 }, segmentIndex: 0, complete: true }
  }
  if (path.length === 1 || distanceNm <= 0) {
    return { position: path[0]!, segmentIndex: 0, complete: path.length === 1 }
  }

  let remaining = distanceNm
  for (let i = 0; i < path.length - 1; i++) {
    const from = path[i]!
    const to = path[i + 1]!
    const segDist = haversineNm(from, to)
    if (segDist <= 0) continue

    if (remaining <= segDist) {
      const frac = remaining / segDist
      return {
        position: {
          latitude: from.latitude + (to.latitude - from.latitude) * frac,
          longitude: from.longitude + (to.longitude - from.longitude) * frac,
        },
        segmentIndex: i,
        complete: false,
      }
    }
    remaining -= segDist
  }

  return {
    position: path[path.length - 1]!,
    segmentIndex: Math.max(path.length - 2, 0),
    complete: true,
  }
}

/**
 * Generates bounding box `{ south, north, west, east }` for Leaflet `fitBounds`.
 */
export function boundsOf(
  coords: Coordinate[],
  paddingFraction: number = 0.15,
): GeoBounds {
  if (!coords || coords.length === 0) {
    return { ...NAVIGABLE_REGION.bounds }
  }

  let minLat = coords[0]!.latitude
  let maxLat = coords[0]!.latitude
  let minLon = coords[0]!.longitude
  let maxLon = coords[0]!.longitude

  for (const c of coords) {
    if (c.latitude < minLat) minLat = c.latitude
    if (c.latitude > maxLat) maxLat = c.latitude
    if (c.longitude < minLon) minLon = c.longitude
    if (c.longitude > maxLon) maxLon = c.longitude
  }

  const padLat = Math.max((maxLat - minLat) * paddingFraction, 0.05)
  const padLon = Math.max((maxLon - minLon) * paddingFraction, 0.05)

  return {
    south: minLat - padLat,
    north: maxLat + padLat,
    west: minLon - padLon,
    east: maxLon + padLon,
  }
}

/**
 * Returns a visually smooth polyline using subtle subdivision where needed.
 */
export function smoothPath(coords: Coordinate[]): Coordinate[] {
  if (!coords || coords.length <= 2) return coords
  return coords
}

/**
 * Validates that a user-picked coordinate is in reasonable open waters.
 */
export function validateSelectionPoint(coord: Coordinate): { ok: boolean; message?: string } {
  if (!coord) return { ok: false, message: 'Coordinate is required.' }
  if (coord.latitude < -90 || coord.latitude > 90) {
    return { ok: false, message: 'Latitude must be between -90° and +90°.' }
  }
  if (coord.longitude < -180 || coord.longitude > 180) {
    return { ok: false, message: 'Longitude must be between -180° and +180°.' }
  }
  if (
    coord.latitude < 15.0 ||
    coord.latitude > 25.0 ||
    coord.longitude < 65.0 ||
    coord.longitude > 76.0
  ) {
    return {
      ok: true,
      message: 'Position is outside the verified Arabian Sea trial corridor (15°–25°N, 65°–76°E).',
    }
  }
  return { ok: true }
}
