/**
 * Hook for streaming and polling the genuine AIS observation track.
 *
 * Polls GET /api/ships/{imo}/track while live tracking is active.
 * Only real AIS fixes are returned — never simulation points.
 * Points are rendered as the RED historical track on the world chart.
 */

import { useEffect, useRef, useState } from 'react'
import { getAisTrack } from '@/services/apiClient'
import type { AISTrackPoint, Coordinate } from '@/types/api'

const POLL_INTERVAL_MS = 6000

export interface AisTrackState {
  track: Coordinate[]
  points: AISTrackPoint[]
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useAisTrack(imo: string | null, enabled: boolean): AisTrackState {
  const [points, setPoints] = useState<AISTrackPoint[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeImoRef = useRef<string | null>(imo)
  activeImoRef.current = imo

  const fetchTrack = async () => {
    if (!imo || !enabled) return
    try {
      const res = await getAisTrack(imo)
      if (activeImoRef.current === imo) {
        setPoints(res.track ?? [])
        setError(null)
      }
    } catch (err: any) {
      if (activeImoRef.current === imo) {
        // Do not fail aggressively; track endpoint is additive
        setError(err?.message ?? 'Failed to load AIS track')
      }
    }
  }

  // Initial fetch on enable / IMO change
  useEffect(() => {
    if (!imo || !enabled) {
      setPoints([])
      setError(null)
      return
    }

    let isMounted = true
    setIsLoading(true)

    fetchTrack().finally(() => {
      if (isMounted) setIsLoading(false)
    })

    // Poll periodically while tracking is active
    const timer = setInterval(() => {
      void fetchTrack()
    }, POLL_INTERVAL_MS)

    return () => {
      isMounted = false
      clearInterval(timer)
    }
  }, [imo, enabled])

  const track: Coordinate[] = points.map((p) => ({
    latitude: p.latitude,
    longitude: p.longitude,
  }))

  return {
    track,
    points,
    isLoading,
    error,
    refetch: fetchTrack,
  }
}
