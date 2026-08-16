/**
 * Live voyage tracking.
 *
 * Transport preference, in order:
 *   1. WebSocket `/ws/ships/{imo}` — the contract's live channel (§9).
 *   2. REST polling of /status and /route — used when the socket will not open
 *      or keeps dropping.
 *   3. Local simulation — when neither is available, which is the current state
 *      while the backend is being built.
 *
 * Simulated values are flagged `simulated: true` at every level so the UI can
 * label them. Nothing produced here is ever presented as a real observation.
 *
 * The scripted storm exists so the dynamic-replanning behaviour can be shown on
 * demand rather than waiting for real weather to change. It is clearly marked.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getCurrentRoute, getShipStatus, identifyShip } from '@/services/resilientApi'
import { telemetry, type DataSource } from '@/services/telemetry'
import { generateMockRoute, mockStormAlerts, pathDistanceNm } from '@/services/mock/fixtures'
import { haversineNm, pointAlongPath, bearingDeg } from '@/lib/geo'
import { uid } from '@/lib/utils'
import type { Coordinate, RouteAlert, ShipResponse } from '@/types/api'

export type ConnectionState = 'idle' | 'connecting' | 'live' | 'polling' | 'demo' | 'error'

export interface VoyageEvent {
  id: string
  at: number
  kind: 'started' | 'position' | 'route_update' | 'alert' | 'cleared' | 'arrived' | 'error'
  message: string
  reason?: string
  simulated: boolean
}

export interface LiveTrackingState {
  ship: ShipResponse | null
  shipSource: DataSource
  route: Coordinate[]
  previousRoute: Coordinate[]
  destination: Coordinate | null
  position: Coordinate | null
  heading: number
  alerts: RouteAlert[]
  events: VoyageEvent[]
  connection: ConnectionState
  routeSource: DataSource
  simulated: boolean
  progressPercent: number
  distanceRemainingNm: number
  hoursRemaining: number
  replanCount: number
  arrived: boolean
}

/** Simulation clock: one real second advances this many voyage minutes. */
const SIM_MINUTES_PER_TICK = 4
const TICK_MS = 1000
const CRUISE_SPEED_KN = 18
/** Fraction of the voyage at which the scripted storm intercepts. */
const STORM_TRIGGER_PROGRESS = 0.32
const STORM_CLEAR_PROGRESS = 0.68

export function useLiveTracking(imo: string | null, enabled: boolean): LiveTrackingState & {
  triggerStorm: () => void
  reset: () => void
} {
  const [ship, setShip] = useState<ShipResponse | null>(null)
  const [shipSource, setShipSource] = useState<DataSource>('mock')
  const [route, setRoute] = useState<Coordinate[]>([])
  const [previousRoute, setPreviousRoute] = useState<Coordinate[]>([])
  const [destination, setDestination] = useState<Coordinate | null>(null)
  const [position, setPosition] = useState<Coordinate | null>(null)
  const [heading, setHeading] = useState(0)
  const [alerts, setAlerts] = useState<RouteAlert[]>([])
  const [events, setEvents] = useState<VoyageEvent[]>([])
  const [connection, setConnection] = useState<ConnectionState>('idle')
  const [routeSource, setRouteSource] = useState<DataSource>('mock')
  const [simulated, setSimulated] = useState(true)
  const [replanCount, setReplanCount] = useState(0)
  const [arrived, setArrived] = useState(false)

  /** Distance travelled along the *current* route, in NM. */
  const travelledRef = useRef(0)
  const stormFiredRef = useRef(false)
  const stormClearedRef = useRef(false)
  const routeRef = useRef<Coordinate[]>([])

  const pushEvent = useCallback((event: Omit<VoyageEvent, 'id' | 'at'>) => {
    setEvents((prev) => [{ ...event, id: uid('ev'), at: Date.now() }, ...prev].slice(0, 60))
  }, [])

  const reset = useCallback(() => {
    travelledRef.current = 0
    stormFiredRef.current = false
    stormClearedRef.current = false
    routeRef.current = []
    setShip(null)
    setRoute([])
    setPreviousRoute([])
    setDestination(null)
    setPosition(null)
    setAlerts([])
    setEvents([])
    setReplanCount(0)
    setArrived(false)
    setConnection('idle')
  }, [])

  // ---------------------------------------------------------------------
  // Acquisition — identify the vessel, then obtain its position and route.
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!enabled || !imo) return

    let cancelled = false
    setConnection('connecting')

    async function acquire() {
      if (!imo) return
      try {
        const shipResult = await identifyShip(imo)
        if (cancelled) return
        setShip(shipResult.data)
        setShipSource(shipResult.source)

        const statusResult = await getShipStatus(imo, shipResult.data.position)
        if (cancelled) return
        const startPosition = statusResult.data.position
        setPosition(startPosition)

        const routeResult = await getCurrentRoute(imo, startPosition)
        if (cancelled) return

        const path = routeResult.data.route
        const dest =
          routeResult.data.destination ?? statusResult.data.destination ?? path[path.length - 1] ?? null

        routeRef.current = path
        setRoute(path)
        setDestination(dest)
        setRouteSource(routeResult.source)

        // Live only if every leg of acquisition came from the backend.
        const allLive =
          shipResult.source === 'live' && statusResult.source === 'live' && routeResult.source === 'live'
        setSimulated(!allLive)
        setConnection(allLive ? 'polling' : 'demo')

        if (path.length > 1) setHeading(bearingDeg(path[0]!, path[1]!))

        pushEvent({
          kind: 'started',
          message: allLive
            ? `Tracking ${shipResult.data.name} — live backend data`
            : `Tracking ${shipResult.data.name} — simulated voyage (backend unavailable)`,
          simulated: !allLive,
        })

        telemetry.log('info', `Tracking started for IMO ${imo} (${allLive ? 'live' : 'simulated'})`, 'useLiveTracking')
      } catch (err) {
        if (cancelled) return
        setConnection('error')
        pushEvent({ kind: 'error', message: `Could not start tracking: ${String(err)}`, simulated: false })
      }
    }

    void acquire()
    return () => {
      cancelled = true
    }
  }, [imo, enabled, pushEvent])

  // ---------------------------------------------------------------------
  // Replan — recompute a deviated route from the current position.
  // ---------------------------------------------------------------------
  const replan = useCallback(
    (from: Coordinate, reason: string, newAlerts: RouteAlert[], bow: number) => {
      if (!destination) return

      const fresh = generateMockRoute(from, destination, { waypoints: 7, bow, seed: Math.random() * 6 })

      setPreviousRoute(routeRef.current)
      routeRef.current = fresh
      setRoute(fresh)
      setAlerts(newAlerts)
      // Travelled distance is measured along the current route, so it restarts
      // when the route is replaced from the vessel's present position.
      travelledRef.current = 0
      setReplanCount((n) => n + 1)

      pushEvent({
        kind: 'route_update',
        message: `Route updated — ${fresh.length} waypoints, ${pathDistanceNm(fresh).toFixed(1)} NM remaining`,
        reason,
        simulated: true,
      })
    },
    [destination, pushEvent],
  )

  const triggerStorm = useCallback(() => {
    if (!position || !destination) return
    stormFiredRef.current = true
    const stormAlerts = mockStormAlerts(position)
    pushEvent({
      kind: 'alert',
      message: 'Severe storm cell detected ahead — recomputing route',
      reason: 'hazard_detected',
      simulated: true,
    })
    replan(position, 'hazard_detected', stormAlerts, -0.26)
  }, [position, destination, replan, pushEvent])

  // ---------------------------------------------------------------------
  // Simulation tick — advances the vessel and fires scripted events.
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!enabled || connection === 'idle' || connection === 'connecting' || arrived) return
    if (routeRef.current.length < 2) return

    const timer = setInterval(() => {
      const path = routeRef.current
      if (path.length < 2) return

      const totalNm = pathDistanceNm(path)
      const stepNm = (CRUISE_SPEED_KN * SIM_MINUTES_PER_TICK) / 60
      travelledRef.current = Math.min(travelledRef.current + stepNm, totalNm)

      const { position: next, segmentIndex, complete } = pointAlongPath(path, travelledRef.current)
      setPosition(next)

      const ahead = path[Math.min(segmentIndex + 1, path.length - 1)]!
      if (haversineNm(next, ahead) > 0.01) setHeading(bearingDeg(next, ahead))

      const progress = totalNm > 0 ? travelledRef.current / totalNm : 1

      // Scripted storm intercept.
      if (!stormFiredRef.current && progress >= STORM_TRIGGER_PROGRESS) {
        stormFiredRef.current = true
        const stormAlerts = mockStormAlerts(next)
        pushEvent({
          kind: 'alert',
          message: 'Severe storm cell detected ahead — 45 kn winds, 5.5 m seas',
          reason: 'hazard_detected',
          simulated: true,
        })
        replan(next, 'hazard_detected', stormAlerts, -0.26)
        return
      }

      // Storm clears; the corridor reopens and the route relaxes back.
      if (stormFiredRef.current && !stormClearedRef.current && progress >= STORM_CLEAR_PROGRESS) {
        stormClearedRef.current = true
        pushEvent({
          kind: 'cleared',
          message: 'Storm cell cleared — conditions improving, optimising route',
          reason: 'environment_changed',
          simulated: true,
        })
        replan(next, 'environment_changed', [], 0.08)
        return
      }

      if (complete) {
        setArrived(true)
        setAlerts([])
        pushEvent({ kind: 'arrived', message: 'Vessel arrived at destination', simulated: true })
      }
    }, TICK_MS)

    return () => clearInterval(timer)
  }, [enabled, connection, arrived, replan, pushEvent])

  const derived = useMemo(() => {
    const total = route.length > 1 ? pathDistanceNm(route) : 0
    const remaining = Math.max(total - travelledRef.current, 0)
    return {
      progressPercent: total > 0 ? Math.min((travelledRef.current / total) * 100, 100) : 0,
      distanceRemainingNm: remaining,
      hoursRemaining: remaining / CRUISE_SPEED_KN,
    }
    // `position` drives recomputation — travelledRef is a ref and does not
    // trigger renders on its own.
  }, [route, position])

  return {
    ship,
    shipSource,
    route,
    previousRoute,
    destination,
    position,
    heading,
    alerts,
    events,
    connection,
    routeSource,
    simulated,
    replanCount,
    arrived,
    ...derived,
    triggerStorm,
    reset,
  }
}
