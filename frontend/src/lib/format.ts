import type { Coordinate } from '@/types/api'

/**
 * Formats a distance in nautical miles.
 */
export function formatDistance(distanceNm: number): string {
  if (!Number.isFinite(distanceNm)) return '0.0 NM'
  return `${distanceNm.toFixed(1)} NM`
}

/**
 * Formats duration in hours to a human-readable "Xh Ym" or "Ym".
 */
export function formatDuration(hours: number): string {
  if (!Number.isFinite(hours) || hours <= 0) return '0m'
  const totalMinutes = Math.round(hours * 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

/**
 * Formats an ISO 8601 UTC timestamp to a readable date/time string.
 */
export function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC'
  } catch {
    return iso
  }
}

/**
 * Formats a geographic coordinate as "18.5200°N, 72.9100°E".
 */
export function formatCoordinate(coord: Coordinate, precision: number = 2): string {
  if (!coord) return '—'
  const latDir = coord.latitude >= 0 ? 'N' : 'S'
  const lonDir = coord.longitude >= 0 ? 'E' : 'W'
  const latVal = Math.abs(coord.latitude).toFixed(precision)
  const lonVal = Math.abs(coord.longitude).toFixed(precision)
  return `${latVal}°${latDir}, ${lonVal}°${lonDir}`
}

/**
 * Converts a bearing in degrees [0, 360) to a compass point (e.g. N, NE, E, SE, etc.).
 */
export function compassPoint(bearing: number): string {
  const normalized = ((bearing % 360) + 360) % 360
  const points = [
    'N', 'NNE', 'NE', 'ENE',
    'E', 'ESE', 'SE', 'SSE',
    'S', 'SSW', 'SW', 'WSW',
    'W', 'WNW', 'NW', 'NNW',
  ]
  const index = Math.round(normalized / 22.5) % 16
  return points[index] ?? 'N'
}

/**
 * Formats a timestamp as a relative time string (e.g. "just now", "2m ago", "1h ago").
 */
export function relativeTime(timestamp: number | string | Date): string {
  const time = typeof timestamp === 'number' ? timestamp : new Date(timestamp).getTime()
  if (Number.isNaN(time)) return 'just now'
  const diffSec = Math.floor((Date.now() - time) / 1000)
  if (diffSec < 10) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}h ago`
  const diffDays = Math.floor(diffHour / 24)
  return `${diffDays}d ago`
}

/**
 * Formats a Date object as a value suitable for `<input type="datetime-local">` (YYYY-MM-DDTHH:mm).
 */
export function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0')
  const y = date.getFullYear()
  const m = pad(date.getMonth() + 1)
  const d = pad(date.getDate())
  const hh = pad(date.getHours())
  const mm = pad(date.getMinutes())
  return `${y}-${m}-${d}T${hh}:${mm}`
}
