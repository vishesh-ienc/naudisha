/**
 * React bindings for the telemetry bus and API mode.
 *
 * `useSyncExternalStore` is used rather than state-in-context because the bus is
 * written to from the service layer (outside React) and must not require a
 * provider to be readable.
 */

import { useCallback, useMemo, useSyncExternalStore } from 'react'
import { telemetry, type TelemetryEntry } from '@/services/telemetry'
import { getApiMode, setApiMode, subscribeToMode, type ApiMode } from '@/services/resilientApi'

export function useTelemetryEntries(): TelemetryEntry[] {
  return useSyncExternalStore(telemetry.subscribe, telemetry.getEntries, telemetry.getEntries)
}

export interface TelemetrySummary {
  total: number
  live: number
  mock: number
  errors: number
  /** True when at least one displayed value came from a fixture. */
  degraded: boolean
  lastEntry: TelemetryEntry | undefined
}

export function useTelemetrySummary(): TelemetrySummary {
  const entries = useTelemetryEntries()

  return useMemo(() => {
    // Only count contract operations — the repeated health probe would otherwise
    // dominate the counts and make the banner misleading.
    const relevant = entries.filter((e) => e.endpoint !== '/health')
    const live = relevant.filter((e) => e.outcome === 'success').length
    const mock = relevant.filter((e) => e.outcome === 'fallback' || e.outcome === 'skipped').length
    const errors = relevant.filter((e) => e.outcome === 'error').length

    return {
      total: relevant.length,
      live,
      mock,
      errors,
      degraded: mock > 0,
      lastEntry: entries[0],
    }
  }, [entries])
}

export function useApiMode(): [ApiMode, (mode: ApiMode) => void] {
  const mode = useSyncExternalStore(subscribeToMode, getApiMode, getApiMode)
  const set = useCallback((next: ApiMode) => setApiMode(next), [])
  return [mode, set]
}

export function useClearTelemetry(): () => void {
  return useCallback(() => telemetry.clear(), [])
}
