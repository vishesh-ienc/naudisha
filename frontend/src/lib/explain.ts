import type { CurrentRouteResponse, RouteLeg, RoutePreviewResponse } from '@/types/api'
import { compassPoint } from './format'

export type Influence = 'favourable' | 'neutral' | 'adverse'

export interface RouteFactor {
  key: 'current' | 'wind' | 'waves' | 'speed'
  label: string
  value: string
  detail: string
  influence: Influence
}

/**
 * Textual summary of environmental conditions on a single leg.
 */
export function describeLeg(leg: RouteLeg): string {
  const parts: string[] = []

  if (leg.wind_speed_kn != null) {
    const dir = leg.wind_direction_deg != null ? `${compassPoint(leg.wind_direction_deg)} ` : ''
    parts.push(`${dir}${leg.wind_speed_kn.toFixed(0)} kn wind`)
  }

  if (leg.wave_height_m != null) {
    parts.push(`${leg.wave_height_m.toFixed(1)} m seas`)
  }

  if (leg.along_track_current_kn != null && Math.abs(leg.along_track_current_kn) >= 0.2) {
    if (leg.along_track_current_kn > 0) {
      parts.push(`+${leg.along_track_current_kn.toFixed(1)} kn assist`)
    } else {
      parts.push(`${leg.along_track_current_kn.toFixed(1)} kn opposing`)
    }
  }

  return parts.length > 0 ? parts.join(', ') : 'Calm conditions'
}

/**
 * Classifies a leg's overall influence compared to average route legs.
 */
export function legInfluence(leg: RouteLeg, allLegs: RouteLeg[]): Influence {
  if (!allLegs || allLegs.length === 0) return 'neutral'

  if (leg.along_track_current_kn != null) {
    if (leg.along_track_current_kn >= 0.3) return 'favourable'
    if (leg.along_track_current_kn <= -0.3) return 'adverse'
  }

  if (leg.wave_height_m != null && leg.wave_height_m >= 3.0) return 'adverse'
  if (leg.wind_speed_kn != null && leg.wind_speed_kn >= 25) return 'adverse'

  return 'neutral'
}

/**
 * Summarizes the dominant environmental factors across all route legs.
 */
export function summariseFactors(legs: RouteLeg[]): RouteFactor[] {
  if (!legs || legs.length === 0) return []

  const factors: RouteFactor[] = []

  // 1. Ocean Currents
  const currentAssists = legs.filter((l) => l.along_track_current_kn != null)
  if (currentAssists.length > 0) {
    const avgCurrent =
      currentAssists.reduce((acc, l) => acc + (l.along_track_current_kn ?? 0), 0) /
      currentAssists.length
    const maxCurrent = Math.max(...currentAssists.map((l) => Math.abs(l.current_speed_kn ?? 0)))

    factors.push({
      key: 'current',
      label: 'Ocean Currents',
      value: `${avgCurrent >= 0 ? '+' : ''}${avgCurrent.toFixed(1)} kn avg`,
      detail:
        avgCurrent >= 0.2
          ? `Following currents assist ground speed up to ${maxCurrent.toFixed(1)} kn`
          : avgCurrent <= -0.2
            ? `Opposing currents add resistance along coastal track`
            : `Neutral currents across voyage corridor`,
      influence: avgCurrent >= 0.2 ? 'favourable' : avgCurrent <= -0.2 ? 'adverse' : 'neutral',
    })
  }

  // 2. Winds
  const winds = legs.filter((l) => l.wind_speed_kn != null)
  if (winds.length > 0) {
    const avgWind = winds.reduce((acc, l) => acc + (l.wind_speed_kn ?? 0), 0) / winds.length
    const maxWind = Math.max(...winds.map((l) => l.wind_speed_kn ?? 0))

    factors.push({
      key: 'wind',
      label: 'Atmospheric Winds',
      value: `${avgWind.toFixed(0)} kn avg`,
      detail:
        maxWind >= 25
          ? `Challenging winds up to ${maxWind.toFixed(0)} kn on exposed segments`
          : `Moderate breeze along planned passage`,
      influence: maxWind >= 25 ? 'adverse' : avgWind < 15 ? 'favourable' : 'neutral',
    })
  }

  // 3. Waves & Seas
  const waves = legs.filter((l) => l.wave_height_m != null)
  if (waves.length > 0) {
    const avgWaves = waves.reduce((acc, l) => acc + (l.wave_height_m ?? 0), 0) / waves.length
    const maxWaves = Math.max(...waves.map((l) => l.wave_height_m ?? 0))

    factors.push({
      key: 'waves',
      label: 'Sea State (Hs)',
      value: `${avgWaves.toFixed(1)} m avg`,
      detail:
        maxWaves >= 3.0
          ? `Heavy swell up to ${maxWaves.toFixed(1)} m significant wave height`
          : `Navigable sea conditions with manageable swell`,
      influence: maxWaves >= 3.0 ? 'adverse' : avgWaves < 1.8 ? 'favourable' : 'neutral',
    })
  }

  return factors
}

/**
 * High-level natural language summary explaining why D* Lite picked this path.
 */
export function summariseRoute(
  route: RoutePreviewResponse | CurrentRouteResponse,
  legs: RouteLeg[],
): string {
  if (!legs || legs.length === 0) {
    return `Optimal path computed by NauDisha multi-objective cost engine across ${route.distance_nm.toFixed(1)} NM.`
  }

  const assists = legs.filter((l) => (l.along_track_current_kn ?? 0) > 0.2).length
  const total = legs.length

  if (assists > total / 2) {
    return `Selected track leverages favourable following currents across ${assists} of ${total} passage segments, balancing fuel efficiency with transit speed.`
  }

  return `Optimized track avoids heavy coastal head-seas while minimizing voyage duration and hydrodynamic fuel penalties.`
}
