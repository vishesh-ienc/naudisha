/**
 * Live voyage tracking.
 *
 * Transport preference, in order:
 *   1. WebSocket `/ws/ships/{imo}` — the contract's live channel (§9).
 *   2. REST polling of §7/§8 — when the socket cannot be established or keeps
 *      dropping. Also used to re-sync after a reconnect, as §9 prescribes.
 *   3. Local simulation — only when the backend is unreachable entirely.
 *
 * The three are deliberately distinguishable in the UI: a viewer should always
 * be able to tell whether a moving vessel is coming from the backend or from
 * this file. Anything produced locally is flagged `simulated`.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getCurrentRoute,
  getShipStatus,
  identifyShip,
  startTracking,
  stopTracking,
  UserFacingApiError,
} from '@/services/resilientApi'
import { LiveSocket, type SocketState } from '@/services/liveSocket'
import { telemetry, type DataSource } from '@/services/telemetry'
import { generateMockRoute, mockStormAlerts, pathDistanceNm } from '@/services/mock/fixtures'
import { haversineNm, pointAlongPath, bearingDeg } from '@/lib/geo'
import { uid } from '@/lib/utils'
import type { Coordinate, CurrentRouteResponse, RouteAlert, RouteLeg, RouteStatus, ShipResponse } from '@/types/api'

export type ConnectionState = 'idle' | 'connecting' | 'live' | 'polling' | 'demo' | 'error'

export interface VoyageEvent {
  id: string
  at: number
  kind: 'started' | 'position' | 'route_update' | 'alert' | 'cleared' | 'arrived' | 'error'
  message: string
  reason?: string
  simulated: boolean
}

export interface TrackingOptions {
  destination?: Coordinate | null
  origin?: Coordinate | null
  departureTime?: string
}

export interface LiveTrackingState {
  ship: ShipResponse | null
  shipSource: DataSource
  route: Coordinate[]
  previousRoute: Coordinate[]
  legs: RouteLeg[]
  currentRoute: CurrentRouteResponse | null
  destination: Coordinate | null
  position: Coordinate | null
  positionSource: string
  isLivePosition: boolean
  heading: number
  speedKn: number
  alerts: RouteAlert[]
  events: VoyageEvent[]
  connection: ConnectionState
  routeStatus: RouteStatus
  routeSource: DataSource
  simulated: boolean
  progressPercent: number
  distanceRemainingNm: number
  hoursRemaining: number
  totalCost: number
  replanCount: number
  arrived: boolean
  planning: boolean
}

const SIM_TICK_MS = 1000
const SIM_MINUTES_PER_TICK = 4
const CRUISE_SPEED_KN = 18
const STORM_TRIGGER_PROGRESS = 0.32
const STORM_CLEAR_PROGRESS = 0.68

/** How often to poll §8 while the backend reports `route_status: "updating"`. */
const PLANNING_POLL_MS = 4000
/** Fallback polling cadence when the WebSocket is unavailable. */
const FALLBACK_POLL_MS = 5000

/**
 * Tracking sessions live in backend memory, so restarting the API drops them
 * while this hook keeps polling a session that no longer exists. These bound the
 * automatic recovery: enough attempts to ride out a dev-server restart, spaced
 * far enough apart that a genuinely absent ship cannot become a request loop.
 */
const MAX_REACQUIRE_ATTEMPTS = 3
const REACQUIRE_COOLDOWN_MS = 10_000

export function useLiveTracking(
  imo: string | null,
  enabled: boolean,
  options: TrackingOptions | null,
): LiveTrackingState & { triggerStorm: () => void; reset: () => void } {
  const [ship, setShip] = useState<ShipResponse | null>(null)
  const [shipSource, setShipSource] = useState<DataSource>('mock')
  const [route, setRoute] = useState<Coordinate[]>([])
  const [previousRoute, setPreviousRoute] = useState<Coordinate[]>([])
  const [destination, setDestination] = useState<Coordinate | null>(null)
  const [position, setPosition] = useState<Coordinate | null>(null)
  const [positionSource, setPositionSource] = useState<string>('none')
  const [isLivePosition, setIsLivePosition] = useState<boolean>(false)
  const [heading, setHeading] = useState(0)
  const [speedKn, setSpeedKn] = useState(18.0)
  const [legs, setLegs] = useState<RouteLeg[]>([])
  const [alerts, setAlerts] = useState<RouteAlert[]>([])
  const [events, setEvents] = useState<VoyageEvent[]>([])
  const [connection, setConnection] = useState<ConnectionState>('idle')
  const [routeStatus, setRouteStatus] = useState<RouteStatus>('updating')
  const [routeSource, setRouteSource] = useState<DataSource>('mock')
  const [simulated, setSimulated] = useState(true)
  const [replanCount, setReplanCount] = useState(0)
  const [arrived, setArrived] = useState(false)
  const [planning, setPlanning] = useState(false)
  const [totalCost, setTotalCost] = useState(0)
  const [distanceRemainingNm, setDistanceRemainingNm] = useState(0)
  const [hoursRemaining, setHoursRemaining] = useState(0)
  const [initialDistanceNm, setInitialDistanceNm] = useState(0)

  const socketRef = useRef<LiveSocket | null>(null)
  const travelledRef = useRef(0)
  // Bumping this re-runs acquisition, which re-creates a lost backend session.
  const [reacquireNonce, setReacquireNonce] = useState(0)
  const reacquireAttemptsRef = useRef(0)
  const lastReacquireRef = useRef(0)
  const stormFiredRef = useRef(false)
  const stormClearedRef = useRef(false)
  const routeRef = useRef<Coordinate[]>([])
  const simulatedRef = useRef(true)

  const pushEvent = useCallback((event: Omit<VoyageEvent, 'id' | 'at'>) => {
    setEvents((prev) => [{ ...event, id: uid('ev'), at: Date.now() }, ...prev].slice(0, 60))
  }, [])

  const reset = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
    travelledRef.current = 0
    stormFiredRef.current = false
    stormClearedRef.current = false
    routeRef.current = []
    simulatedRef.current = true
    reacquireAttemptsRef.current = 0
    lastReacquireRef.current = 0

    setShip(null)
    setRoute([])
    setPreviousRoute([])
    setLegs([])
    setDestination(null)
    setPosition(null)
    setSpeedKn(18.0)
    setAlerts([])
    setEvents([])
    setReplanCount(0)
    setArrived(false)
    setPlanning(false)
    setConnection('idle')
    setRouteStatus('updating')
    setTotalCost(0)
    setDistanceRemainingNm(0)
    setHoursRemaining(0)
    setInitialDistanceNm(0)
  }, [])

  /** Applies a route payload from either the WebSocket or a REST poll. */
  const applyRoute = useCallback(
    (
      next: Coordinate[],
      stats: { distance_nm: number; estimated_time_hours: number; total_cost: number },
      opts: { reason?: string; announce?: boolean; legs?: RouteLeg[] } = {},
    ) => {
      if (next.length === 0) return

      const previous = routeRef.current
      const changed =
        previous.length !== next.length ||
        previous.some((p, i) => p.latitude !== next[i]?.latitude || p.longitude !== next[i]?.longitude)

      if (!changed) return

      if (previous.length > 1) setPreviousRoute(previous)
      routeRef.current = next
      setRoute(next)
      if (opts.legs) setLegs(opts.legs)
      setDistanceRemainingNm(stats.distance_nm)
      setHoursRemaining(stats.estimated_time_hours)
      setTotalCost(stats.total_cost)

      if (initialDistanceNm === 0 && stats.distance_nm > 0) {
        setInitialDistanceNm(stats.distance_nm)
      }

      if (next.length > 1) {
        setHeading(bearingDeg(next[0]!, next[1]!))
      }

      if (opts.announce) {
        setReplanCount((n) => n + 1)
        pushEvent({
          kind: 'route_update',
          message: `Route updated — ${next.length} waypoints, ${stats.distance_nm.toFixed(1)} NM remaining`,
          ...(opts.reason !== undefined && { reason: opts.reason }),
          simulated: simulatedRef.current,
        })
      }
    },
    [initialDistanceNm, pushEvent],
  )

  // ---------------------------------------------------------------------
  // Acquisition
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!enabled || !imo || !options) return

    let cancelled = false
    setConnection('connecting')
    setPlanning(true)

    async function acquire() {
      if (!imo || !options) return

      try {
        const shipResult = await identifyShip(imo)
        if (cancelled) return
        setShip(shipResult.data)
        setShipSource(shipResult.source)

        // The backend returns a null position when no AIS fix exists, so the
        // caller-supplied origin is the reliable starting point.
        const origin = options.origin ?? shipResult.data.position ?? null

        const dest = options?.destination ?? { latitude: 15.42, longitude: 73.75 }

        const trackResult = await startTracking(imo, {
          destination: dest,
          ...(origin && { origin }),
          ...(options?.departureTime && { departure_time: options.departureTime }),
        })
        if (cancelled) return

        const isLive = shipResult.source === 'live' && trackResult.source === 'live'
        simulatedRef.current = !isLive
        setSimulated(!isLive)
        setDestination(dest)
        if (origin) setPosition(origin)
        setPositionSource(shipResult.data.position_source ?? (shipResult.data.is_live_position ? 'ais' : 'simulation'))
        setIsLivePosition(shipResult.data.is_live_position ?? false)

        pushEvent({
          kind: 'started',
          message: isLive
            ? `Tracking ${shipResult.data.name} — live backend session`
            : `Tracking ${shipResult.data.name} — simulated voyage (backend unavailable)`,
          simulated: !isLive,
        })

        if (isLive) {
          // A session exists again, so the recovery budget is spent and reset —
          // a restart an hour from now gets its own full set of attempts.
          reacquireAttemptsRef.current = 0
          setConnection('polling')
          openSocket(imo)
        } else {
          // Backend unreachable: build a local route so the demo still works.
          const localRoute = generateMockRoute(origin ?? dest, dest)
          routeRef.current = localRoute
          setRoute(localRoute)
          setPosition(localRoute[0] ?? null)
          const dist = pathDistanceNm(localRoute)
          setInitialDistanceNm(dist)
          setDistanceRemainingNm(dist)
          setHoursRemaining(dist / CRUISE_SPEED_KN)
          setRouteStatus('optimal')
          setRouteSource('mock')
          setConnection('demo')
          setPlanning(false)
        }
      } catch (err) {
        if (cancelled) return
        setConnection('error')
        setPlanning(false)
        pushEvent({ kind: 'error', message: `Could not start tracking: ${String(err)}`, simulated: false })
      }
    }

    function openSocket(imoNumber: string) {
      const socket = new LiveSocket(imoNumber, {
        onMessage: (message) => {
          if (cancelled) return

          if (message.type === 'position_update') {
            setPosition(message.position)
            if (message.position_source !== undefined) setPositionSource(message.position_source)
            if (message.is_live_position !== undefined) setIsLivePosition(message.is_live_position)
            if (message.speed_kn !== undefined && message.speed_kn !== null) setSpeedKn(message.speed_kn)
            if (message.heading_deg !== undefined && message.heading_deg !== null) setHeading(message.heading_deg)
            return
          }

          setPosition(message.position)
          if (message.position_source !== undefined) setPositionSource(message.position_source)
          if (message.is_live_position !== undefined) setIsLivePosition(message.is_live_position)
          setRouteStatus('optimal')
          setRouteSource('live')
          setPlanning(false)
          applyRoute(
            message.route,
            {
              distance_nm: message.distance_nm,
              estimated_time_hours: message.estimated_time_hours,
              total_cost: message.total_cost,
            },
            { reason: message.reason, announce: routeRef.current.length > 0, legs: message.legs },
          )
          if (message.alerts?.length) setAlerts(message.alerts)
        },
        onStateChange: (state: SocketState) => {
          if (cancelled) return
          if (state === 'open') setConnection('live')
          else if (state === 'failed') setConnection('polling')
          else if (state === 'reconnecting') setConnection('polling')
        },
        onReconnected: () => {
          // §9: after a reconnect, re-sync state over REST.
          void syncOnce(imoNumber)
        },
      })
      socketRef.current = socket
      socket.connect()
    }

    void acquire()

    return () => {
      cancelled = true
      socketRef.current?.close()
      socketRef.current = null
    }
    // `options` is intentionally compared by value below via the deps on its
    // fields, so a new object identity each render does not restart tracking.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    imo,
    enabled,
    options?.destination?.latitude,
    options?.destination?.longitude,
    options?.origin?.latitude,
    options?.origin?.longitude,
    options?.departureTime,
    // Re-runs acquisition after the backend loses its tracking session.
    reacquireNonce,
  ])

  /** One-shot REST sync of position and route (§7 + §8). */
  const syncOnce = useCallback(
    async (imoNumber: string) => {
      try {
        const [statusResult, routeResult] = await Promise.all([
          getShipStatus(imoNumber),
          getCurrentRoute(imoNumber),
        ])

        if (statusResult.source === 'live') {
          setPosition(statusResult.data.position)
          if (statusResult.data.position_source !== undefined) setPositionSource(statusResult.data.position_source)
          if (statusResult.data.is_live_position !== undefined) setIsLivePosition(statusResult.data.is_live_position)
          if (statusResult.data.destination) setDestination(statusResult.data.destination)
          if (statusResult.data.status === 'stopped') setArrived(true)
        }

        if (routeResult.source === 'live') {
          setRouteSource('live')
          setRouteStatus(routeResult.data.route_status)
          if (routeResult.data.route_status === 'optimal' && routeResult.data.route.length > 0) {
            setPlanning(false)
            applyRoute(
              routeResult.data.route,
              {
                distance_nm: routeResult.data.distance_nm,
                estimated_time_hours: routeResult.data.estimated_time_hours,
                total_cost: routeResult.data.total_cost,
              },
              { announce: routeRef.current.length > 0, reason: 'forecast_refresh' },
            )
          }
        }
      } catch (err) {
        // A ROUTE_NOT_FOUND here means the backend is healthy but has no session
        // for this ship — almost always because the API restarted and dropped
        // its in-memory sessions. Polling on would 404 forever, so re-run
        // acquisition to re-establish the voyage.
        if (err instanceof UserFacingApiError && err.code === 'ROUTE_NOT_FOUND') {
          const now = Date.now()
          const canRetry =
            reacquireAttemptsRef.current < MAX_REACQUIRE_ATTEMPTS &&
            now - lastReacquireRef.current > REACQUIRE_COOLDOWN_MS

          if (canRetry) {
            reacquireAttemptsRef.current += 1
            lastReacquireRef.current = now
            telemetry.log(
              'warn',
              `Tracking session missing for IMO ${imoNumber} — re-establishing ` +
                `(attempt ${reacquireAttemptsRef.current}/${MAX_REACQUIRE_ATTEMPTS})`,
              'useLiveTracking',
            )
            pushEvent({
              kind: 'error',
              message: 'Tracking session was lost on the backend — reconnecting',
              reason: 'session_expired',
              simulated: false,
            })
            setReacquireNonce((n) => n + 1)
          } else if (reacquireAttemptsRef.current >= MAX_REACQUIRE_ATTEMPTS) {
            setConnection('error')
          }
          return
        }
        // Everything else is already recorded by the resilient layer.
      }
    },
    [applyRoute, pushEvent],
  )

  // ---------------------------------------------------------------------
  // REST polling — while the plan is pending, and as a socket fallback.
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!enabled || !imo || simulated || connection === 'idle' || connection === 'error') return
    if (arrived) return

    const interval = planning || routeStatus === 'updating' ? PLANNING_POLL_MS : FALLBACK_POLL_MS

    // With a healthy socket, position arrives by push; polling then exists only
    // to notice the plan landing and to correct any drift.
    const timer = setInterval(() => void syncOnce(imo), interval)
    return () => clearInterval(timer)
  }, [enabled, imo, simulated, connection, planning, routeStatus, arrived, syncOnce])

  // ---------------------------------------------------------------------
  // Local simulation — only when the backend is unreachable.
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!enabled || !simulated || connection !== 'demo' || arrived) return
    if (routeRef.current.length < 2) return

    const timer = setInterval(() => {
      const path = routeRef.current
      if (path.length < 2) return

      const totalNm = pathDistanceNm(path)
      const stepNm = (CRUISE_SPEED_KN * SIM_MINUTES_PER_TICK) / 60
      travelledRef.current = Math.min(travelledRef.current + stepNm, totalNm)

      const { position: next, segmentIndex, complete } = pointAlongPath(path, travelledRef.current)
      setPosition(next)
      setDistanceRemainingNm(Math.max(totalNm - travelledRef.current, 0))
      setHoursRemaining(Math.max(totalNm - travelledRef.current, 0) / CRUISE_SPEED_KN)

      const ahead = path[Math.min(segmentIndex + 1, path.length - 1)]!
      if (haversineNm(next, ahead) > 0.01) setHeading(bearingDeg(next, ahead))

      const progress = totalNm > 0 ? travelledRef.current / totalNm : 1

      if (!stormFiredRef.current && progress >= STORM_TRIGGER_PROGRESS && destination) {
        stormFiredRef.current = true
        setAlerts(mockStormAlerts(next))
        pushEvent({
          kind: 'alert',
          message: 'Severe storm cell detected ahead — 45 kn winds, 5.5 m seas',
          reason: 'hazard_detected',
          simulated: true,
        })
        const detour = generateMockRoute(next, destination, { waypoints: 7, bow: -0.26 })
        setPreviousRoute(path)
        routeRef.current = detour
        setRoute(detour)
        travelledRef.current = 0
        setReplanCount((n) => n + 1)
        return
      }

      if (stormFiredRef.current && !stormClearedRef.current && progress >= STORM_CLEAR_PROGRESS && destination) {
        stormClearedRef.current = true
        setAlerts([])
        pushEvent({
          kind: 'cleared',
          message: 'Storm cell cleared — conditions improving, optimising route',
          reason: 'environment_changed',
          simulated: true,
        })
        const relaxed = generateMockRoute(next, destination, { waypoints: 6, bow: 0.08 })
        setPreviousRoute(path)
        routeRef.current = relaxed
        setRoute(relaxed)
        travelledRef.current = 0
        setReplanCount((n) => n + 1)
        return
      }

      if (complete) {
        setArrived(true)
        setAlerts([])
        pushEvent({ kind: 'arrived', message: 'Vessel arrived at destination', simulated: true })
      }
    }, SIM_TICK_MS)

    return () => clearInterval(timer)
  }, [enabled, simulated, connection, arrived, destination, pushEvent])

  // Arrival detection for the live path.
  useEffect(() => {
    if (simulated || arrived || !position || !destination) return
    if (routeStatus !== 'optimal') return
    if (haversineNm(position, destination) < 0.5 && distanceRemainingNm < 0.5) {
      setArrived(true)
      setAlerts([])
      pushEvent({ kind: 'arrived', message: 'Vessel arrived at destination', simulated: false })
    }
  }, [simulated, arrived, position, destination, distanceRemainingNm, routeStatus, pushEvent])

  const triggerStorm = useCallback(() => {
    if (!position || !destination) return

    if (simulatedRef.current) {
      stormFiredRef.current = true
      setAlerts(mockStormAlerts(position))
      pushEvent({
        kind: 'alert',
        message: 'Severe storm cell detected ahead — recomputing route',
        reason: 'hazard_detected',
        simulated: true,
      })
      const detour = generateMockRoute(position, destination, { waypoints: 7, bow: -0.26 })
      setPreviousRoute(routeRef.current)
      routeRef.current = detour
      setRoute(detour)
      travelledRef.current = 0
      setReplanCount((n) => n + 1)
      return
    }

    // Against a live backend the hazard is annotated locally — the API has no
    // endpoint for injecting weather, and inventing a backend route here would
    // misrepresent the engine's output.
    setAlerts(mockStormAlerts(position))
    pushEvent({
      kind: 'alert',
      message: 'Simulated hazard overlaid — the live route is unaffected',
      reason: 'hazard_detected',
      simulated: true,
    })
    telemetry.log('info', 'Hazard overlay is local; backend route unchanged', 'useLiveTracking')
  }, [position, destination, pushEvent])

  // Release the backend session when tracking ends.
  useEffect(() => {
    if (!enabled || !imo || simulated) return
    return () => {
      void stopTracking(imo)
    }
  }, [enabled, imo, simulated])

  const currentRoute: CurrentRouteResponse | null = useMemo(() => {
    if (!imo || route.length === 0) return null
    return {
      imo_number: imo,
      route_status: routeStatus,
      route,
      distance_nm: distanceRemainingNm,
      estimated_time_hours: hoursRemaining,
      total_cost: totalCost,
      updated_at: new Date().toISOString(),
      destination: destination ?? { latitude: 0, longitude: 0 },
      legs,
    }
  }, [imo, routeStatus, route, distanceRemainingNm, hoursRemaining, totalCost, destination, legs])

  const progressPercent = useMemo(() => {
    if (arrived) return 100
    if (initialDistanceNm <= 0) return 0
    const done = initialDistanceNm - distanceRemainingNm
    return Math.min(Math.max((done / initialDistanceNm) * 100, 0), 100)
  }, [arrived, initialDistanceNm, distanceRemainingNm])

  return {
    ship,
    shipSource,
    route,
    previousRoute,
    legs,
    currentRoute,
    destination,
    position,
    positionSource,
    isLivePosition,
    heading,
    speedKn,
    alerts,
    events,
    connection,
    routeStatus,
    routeSource,
    simulated,
    progressPercent,
    distanceRemainingNm,
    hoursRemaining,
    totalCost,
    replanCount,
    arrived,
    planning,
    triggerStorm,
    reset,
  }
}
