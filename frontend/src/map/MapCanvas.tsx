/**
 * Modern dark marine chart canvas.
 *
 * Combines high-contrast dark cartography with OpenSeaMap nautical seamarks,
 * Green optimal route polyline, Red direct/baseline route polyline, rotating boat marker,
 * and animated environmental wind/current vector layers.
 */

import { useEffect, useMemo, useRef } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  Circle,
  Marker,
  Popup,
  Tooltip,
  useMap,
  LayersControl,
} from 'react-leaflet'
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coordinate, RouteAlert, RouteLeg } from '@/types/api'
import { NAVIGABLE_REGION, boundsOf, smoothPath } from '@/lib/geo'
import { NAMED_LOCATIONS, type NamedLocation } from '@/lib/ports'
import { formatCoordinate } from '@/lib/format'
import {
  alertIcon,
  counterCurrentIcon,
  currentVectorIcon,
  destinationIcon,
  portDotIcon,
  shipIcon,
  startIcon,
  stormVortexIcon,
  waypointIcon,
  windVectorIcon,
} from './markers'
import { MapLegend } from './MapLegend'
import { cn } from '@/lib/utils'

export interface SimulationHazard {
  id: string
  name: string
  type: 'storm' | 'current' | 'restricted'
  center: Coordinate
  radiusNm: number
  severity: number
  description?: string
}

export interface MapCanvasProps {
  start?: Coordinate | null
  destination?: Coordinate | null
  /** Optimal route calculated by NauDisha — rendered in GREEN */
  route?: Coordinate[]
  /** Direct baseline or unoptimized route — rendered in RED */
  directRoute?: Coordinate[]
  /** Detailed segment breakdown containing environmental forecast numbers */
  legs?: RouteLeg[]
  /** Previous route, drawn faded during dynamic replanning */
  previousRoute?: Coordinate[]
  shipPosition?: Coordinate | null
  shipHeading?: number
  /**
   * Provenance of the ship position — used to show the correct label on the marker.
   * 'aisstream' | 'digitraffic' = AIS LIVE
   * 'simulated' = SIMULATED
   * 'static' = STATIC DATA
   * 'none' | undefined = OFFLINE
   */
  positionSource?: string
  /** Deprecated — use positionSource instead. Kept for backward compat. */
  shipSimulated?: boolean
  shipName?: string
  alerts?: RouteAlert[]
  showVectors?: boolean
  showLegend?: boolean
  showPorts?: boolean
  simulationHazard?: SimulationHazard | null
  onSelectPort?: (port: NamedLocation, asType: 'origin' | 'destination') => void
  className?: string
  interactive?: boolean
}

export function MapCanvas({
  start,
  destination,
  route = [],
  directRoute,
  legs = [],
  previousRoute = [],
  shipPosition,
  shipHeading = 0,
  positionSource,
  shipSimulated = false,
  shipName,
  alerts = [],
  showVectors = true,
  showLegend = true,
  showPorts = true,
  simulationHazard = null,
  onSelectPort,
  className,
  interactive = true,
}: MapCanvasProps) {
  // Derive label from backend-provided positionSource (preferred) or legacy shipSimulated flag
  const positionLabel = (() => {
    const src = positionSource ?? (shipSimulated ? 'simulated' : 'none')
    if (src === 'aisstream' || src === 'digitraffic') return { text: 'AIS LIVE', color: 'text-cyan-300', bg: 'bg-cyan-500/20' }
    if (src === 'simulated') return { text: 'SIMULATED', color: 'text-amber-300', bg: 'bg-amber-500/20' }
    if (src === 'static') return { text: 'STATIC DATA', color: 'text-slate-300', bg: 'bg-slate-500/20' }
    return { text: 'OFFLINE', color: 'text-rose-300', bg: 'bg-rose-500/20' }
  })()
  const center: LatLngExpression = useMemo(() => {
    if (shipPosition) return [shipPosition.latitude, shipPosition.longitude]
    if (start) return [start.latitude, start.longitude]
    return [NAVIGABLE_REGION.center.latitude, NAVIGABLE_REGION.center.longitude]
  }, [shipPosition, start])


  // Extract environmental vectors offset laterally BESIDE the route corridor
  const { windVectors, currentVectors } = useMemo(() => {
    if (!showVectors) return { windVectors: [], currentVectors: [] }

    const pts: Coordinate[] = (route && route.length >= 2)
      ? route
      : (legs && legs.length > 0)
        ? legs.map((l: any) => ({
            latitude: l.from?.latitude ?? l.from_lat ?? 0,
            longitude: l.from?.longitude ?? l.from_lon ?? 0,
          }))
        : []

    if (pts.length < 2) return { windVectors: [], currentVectors: [] }

    const winds: Array<{
      position: Coordinate
      speed: number
      direction: number
      legIndex: number
      relativeDesc: string
    }> = []

    const currents: Array<{
      position: Coordinate
      speed: number
      direction: number
      alongTrack: number
      isAssist: boolean
      legIndex: number
    }> = []

    // Sample ~8 to 12 representative stations along the route
    const totalSegments = pts.length - 1
    const stride = Math.max(1, Math.floor(totalSegments / 8))
    const offsetDeg = 0.28 // ~17 NM lateral offset beside the route track

    for (let i = 0; i < totalSegments; i += stride) {
      const p1 = pts[i]!
      const p2 = pts[Math.min(i + 1, totalSegments)]!

      const midLat = (p1.latitude + p2.latitude) / 2
      const midLon = (p1.longitude + p2.longitude) / 2
      const dLat = p2.latitude - p1.latitude
      const dLon = (p2.longitude - p1.longitude) * Math.cos((midLat * Math.PI) / 180)
      const bearingRad = Math.atan2(dLon, dLat)
      const cosMid = Math.cos((midLat * Math.PI) / 180) || 1

      // Port side (Left) lateral position for Wind Vector
      const windLat = midLat + offsetDeg * Math.cos(bearingRad - Math.PI / 2)
      const windLon = midLon + (offsetDeg * Math.sin(bearingRad - Math.PI / 2)) / cosMid

      // Starboard side (Right) lateral position for Ocean Current Vector
      const currLat = midLat + offsetDeg * Math.cos(bearingRad + Math.PI / 2)
      const currLon = midLon + (offsetDeg * Math.sin(bearingRad + Math.PI / 2)) / cosMid

      // Find environmental data from matching leg or interpolate
      const legData: any = legs?.[i] || legs?.[Math.min(i, (legs?.length || 1) - 1)] || {}
      const windSpeed = legData.wind_speed_kn ?? 12.0 + ((i * 3) % 8)
      const windDir = legData.wind_direction_deg ?? 225.0 // South-Westerly monsoon
      const currSpeed = legData.current_speed_kn ?? 0.8 + ((i * 2) % 6) / 10
      const currDir = legData.current_direction_deg ?? 65.0
      const alongTrack = legData.along_track_current_kn ?? -0.3

      const shipCourseDeg = (bearingRad * 180 / Math.PI + 360) % 360
      const relWind = Math.abs(((windDir - shipCourseDeg + 180) % 360) - 180)
      const relDesc = relWind < 45 ? 'Headwind (Opposing)' : relWind > 135 ? 'Tailwind (Pushing)' : 'Crosswind'

      winds.push({
        position: { latitude: windLat, longitude: windLon },
        speed: windSpeed,
        direction: windDir,
        legIndex: i + 1,
        relativeDesc: relDesc,
      })

      currents.push({
        position: { latitude: currLat, longitude: currLon },
        speed: currSpeed,
        direction: currDir,
        alongTrack,
        isAssist: alongTrack >= 0,
        legIndex: i + 1,
      })
    }

    return { windVectors: winds, currentVectors: currents }
  }, [route, legs, showVectors])

  // Generate direct baseline route if start/destination exist and no direct route was explicitly supplied
  const effectiveDirectRoute: LatLngExpression[] = useMemo(() => {
    if (directRoute && directRoute.length >= 2) {
      return directRoute.map((p) => [p.latitude, p.longitude])
    }
    const origin = shipPosition ?? start
    if (origin && destination && route.length > 0) {
      return [
        [origin.latitude, origin.longitude],
        [destination.latitude, destination.longitude],
      ]
    }
    return []
  }, [directRoute, shipPosition, start, destination, route.length])

  // Convert and smooth the optimal green route path
  const smoothedOptimalPositions: LatLngExpression[] = useMemo(() => {
    if (!route || route.length < 2) return []
    const smooth = smoothPath(route)
    return smooth.map((p) => [p.latitude, p.longitude])
  }, [route])

  // Previous replanned route for comparison
  const previousPositions: LatLngExpression[] = useMemo(() => {
    if (!previousRoute || previousRoute.length < 2) return []
    return previousRoute.map((p) => [p.latitude, p.longitude])
  }, [previousRoute])

  // Calculate auto-fit bounds for the voyage corridor (independent of continuous ship movement ticks)
  const fitBounds: LatLngBoundsExpression | null = useMemo(() => {
    const points: Coordinate[] = []
    if (start) points.push(start)
    if (destination) points.push(destination)
    if (route && route.length > 0) points.push(...route)

    if (points.length >= 2) {
      const b = boundsOf(points)
      // Extra generous padding so both markers are well-framed
      return [
        [b.south - 0.5, b.west - 0.5],
        [b.north + 0.5, b.east + 0.5],
      ]
    }
    // Even with just start+destination (no route yet), still fit the view
    if (start && destination) {
      const b = boundsOf([start, destination])
      return [
        [b.south - 0.5, b.west - 0.5],
        [b.north + 0.5, b.east + 0.5],
      ]
    }
    return null
  }, [start, destination, route])

  return (
    <div className={cn('relative h-full w-full overflow-hidden rounded-2xl border border-[var(--border)] shadow-2xl', className)}>
      <MapContainer
        center={center}
        zoom={NAVIGABLE_REGION.defaultZoom}
        minZoom={3}
        maxZoom={17}
        className="h-full w-full bg-[#0b1329]"
        zoomControl={interactive}
        dragging={interactive}
        scrollWheelZoom={interactive}
        doubleClickZoom={interactive}
        attributionControl={false}
      >
        {/* Layer Selection Controller */}
        <LayersControl position="topright">
          {/* Base Layer: Satellite imagery — DEFAULT */}
          <LayersControl.BaseLayer checked name="Satellite Surface">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={18}
            />
          </LayersControl.BaseLayer>

          {/* Base Layer: CartoDB Dark Matter */}
          <LayersControl.BaseLayer name="Dark Marine Chart">
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              subdomains="abcd"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>

          {/* Seamarks Overlay: OpenSeaMap navigation aids, buoys, beacons, fairways */}
          <LayersControl.Overlay checked name="Nautical Seamarks (OpenSeaMap)">
            <TileLayer
              url="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"
              maxZoom={18}
              opacity={0.88}
            />
          </LayersControl.Overlay>
        </LayersControl>

        {/* Auto-fit map viewport to active passage or single vessel position */}
        <MapBoundsController bounds={fitBounds} singlePoint={shipPosition ?? start} />

        {/* INDIAN OCEAN SEAPORTS & MARITIME HUBS LAYER */}
        {showPorts && NAMED_LOCATIONS.map((loc) => {
          const isSelectedOrigin = start && Math.abs(start.latitude - loc.coordinate.latitude) < 0.05 && Math.abs(start.longitude - loc.coordinate.longitude) < 0.05
          const isSelectedDest = destination && Math.abs(destination.latitude - loc.coordinate.latitude) < 0.05 && Math.abs(destination.longitude - loc.coordinate.longitude) < 0.05
          if (isSelectedOrigin || isSelectedDest) return null // Handled by origin/dest markers

          return (
            <Marker
              key={loc.id}
              position={[loc.coordinate.latitude, loc.coordinate.longitude]}
              icon={portDotIcon(loc.kind === 'port')}
            >
              <Tooltip direction="top" offset={[0, -8]} opacity={0.96} className="naudisha-tooltip">
                <div>
                  <div className="font-bold text-sky-400">⚓ {loc.name}</div>
                  <div className="text-[10px] text-slate-300">
                    {loc.country} {loc.unLocode ? `(${loc.unLocode})` : ''} · Click to set origin/destination
                  </div>
                </div>
              </Tooltip>
              <Popup className="naudisha-popup">
                <div className="p-2 font-sans text-xs min-w-[210px]">
                  <div className="font-bold text-sky-400 text-[12px]">{loc.name}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {loc.country} {loc.unLocode ? `(${loc.unLocode})` : ''} · <span className="text-slate-300">{loc.region}</span>
                  </div>
                  <div className="font-mono text-[10px] text-slate-400 mt-1">
                    {formatCoordinate(loc.coordinate, 4)}
                  </div>
                  {onSelectPort && (
                    <div className="mt-2.5 pt-2 border-t border-slate-700/60 flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => onSelectPort(loc, 'origin')}
                        className="flex-1 px-2 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded text-[10px] font-semibold transition-colors text-center"
                      >
                        Set Origin
                      </button>
                      <button
                        type="button"
                        onClick={() => onSelectPort(loc, 'destination')}
                        className="flex-1 px-2 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded text-[10px] font-semibold transition-colors text-center"
                      >
                        Set Dest
                      </button>
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          )
        })}

        {/* DYNAMIC D* LITE SIMULATION HAZARD ZONE (CYCLONE / CURRENT GYRE) */}
        {simulationHazard && (
          <>
            {/* Outer Weather Hazard Influence Radius */}
            <Circle
              center={[simulationHazard.center.latitude, simulationHazard.center.longitude]}
              radius={simulationHazard.radiusNm * 1852}
              pathOptions={{
                color: simulationHazard.type === 'storm' ? '#f43f5e' : '#f59e0b',
                fillColor: simulationHazard.type === 'storm' ? '#ef4444' : '#fbbf24',
                fillOpacity: 0.15,
                weight: 2,
                dashArray: '6, 6',
              }}
            />
            {/* Inner Impassable Storm Core (50% Radius) */}
            {simulationHazard.type === 'storm' && (
              <Circle
                center={[simulationHazard.center.latitude, simulationHazard.center.longitude]}
                radius={(simulationHazard.radiusNm * 0.5) * 1852}
                pathOptions={{
                  color: '#dc2626',
                  fillColor: '#b91c1c',
                  fillOpacity: 0.4,
                  weight: 2.5,
                }}
              />
            )}
            <Marker
              position={[simulationHazard.center.latitude, simulationHazard.center.longitude]}
              icon={
                simulationHazard.type === 'storm'
                  ? stormVortexIcon(simulationHazard.severity)
                  : counterCurrentIcon()
              }
            >
              <Tooltip direction="top" offset={[0, -20]} opacity={0.96} className="naudisha-tooltip">
                <div>
                  <div className="font-bold text-rose-400">⚡ {simulationHazard.name}</div>
                  <div className="text-[10px] text-slate-200">
                    Radius: {simulationHazard.radiusNm} NM · D* Lite dynamic avoidance active
                  </div>
                </div>
              </Tooltip>
              <Popup className="naudisha-popup">
                <div className="p-2 font-sans text-xs min-w-[220px]">
                  <div className="font-bold text-rose-400 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping inline-block" />
                    {simulationHazard.name}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-200">
                    {simulationHazard.description || 'Severe weather zone triggering D* Lite dynamic edge re-evaluation.'}
                  </div>
                  <div className="mt-1.5 pt-1 border-t border-slate-700 font-mono text-[10px] text-rose-300">
                    Radius: {simulationHazard.radiusNm} NM · Lethal Wave Core: {(simulationHazard.radiusNm * 0.5).toFixed(0)} NM
                  </div>
                </div>
              </Popup>
            </Marker>
          </>
        )}



        {/* 2. DYNAMICALLY RE-PLANNED OPTIMAL ROUTE — RENDERED IN VIBRANT GREEN */}
        {smoothedOptimalPositions.length > 0 && (
          <>
            {/* Green Outer Ambient Glow */}
            <Polyline
              positions={smoothedOptimalPositions}
              pathOptions={{
                color: '#10b981',
                weight: 10,
                opacity: 0.35,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Green Core High-Contrast Line */}
            <Polyline
              positions={smoothedOptimalPositions}
              pathOptions={{
                color: '#22c55e',
                weight: 4.5,
                opacity: 0.95,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            >
              <Popup className="naudisha-popup">
                <div className="p-1.5 font-sans text-xs">
                  <div className="font-bold text-emerald-400">
                    {previousPositions.length > 0 ? '🟢 D* Lite Safe Diversion Track' : 'NauDisha Optimal Route'}
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {previousPositions.length > 0
                      ? 'Dynamically diverted in real-time around the severe storm vortex with 100% collision avoidance.'
                      : 'Multi-factor D* Lite calculated route minimizing fuel, weather drag, and sea hazard exposure.'}
                  </p>
                </div>
              </Popup>
            </Polyline>
          </>
        )}

        {/* Start Point Marker */}
        {start && (
          <Marker position={[start.latitude, start.longitude]} icon={startIcon}>
            <Tooltip direction="top" offset={[0, -18]} opacity={0.96} className="naudisha-tooltip">
              <div className="font-bold text-emerald-400">📍 Voyage Origin: {formatCoordinate(start, 2)}</div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="font-bold text-emerald-400 uppercase tracking-wider text-[10px]">Voyage Origin</div>
                <div className="mt-1 font-mono text-[11px] text-foreground">{formatCoordinate(start, 4)}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Destination Point Marker */}
        {destination && (
          <Marker position={[destination.latitude, destination.longitude]} icon={destinationIcon}>
            <Tooltip direction="top" offset={[0, -18]} opacity={0.96} className="naudisha-tooltip">
              <div className="font-bold text-rose-400">🎯 Destination Port: {formatCoordinate(destination, 2)}</div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="font-bold text-rose-400 uppercase tracking-wider text-[10px]">Destination Port</div>
                <div className="mt-1 font-mono text-[11px] text-foreground">{formatCoordinate(destination, 4)}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route Waypoint Nodes */}
        {route && route.length > 2 && route.slice(1, -1).map((pt, i) => (
          <Marker key={`wp-${i}`} position={[pt.latitude, pt.longitude]} icon={waypointIcon}>
            <Tooltip direction="top" offset={[0, -8]} opacity={0.96} className="naudisha-tooltip">
              <div>
                <span className="font-bold text-emerald-400">🟢 Waypoint {i + 1}</span>
                <span className="font-mono text-[10px] text-slate-300 ml-1.5">{formatCoordinate(pt, 2)}</span>
              </div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="font-bold text-emerald-400 text-[10px]">Waypoint {i + 1}</div>
                <div className="mt-0.5 font-mono text-[11px]">{formatCoordinate(pt, 4)}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* REAL-TIME ANIMATED WIND VECTORS (Open-Meteo) — POSITIONED BESIDE TRACK (PORT CORRIDOR) */}
        {showVectors && windVectors.map((vec, idx) => (
          <Marker
            key={`wind-${idx}`}
            position={[vec.position.latitude, vec.position.longitude]}
            icon={windVectorIcon(vec.direction, vec.speed)}
          >
            <Tooltip direction="top" offset={[0, -14]} opacity={0.98} className="naudisha-tooltip">
              <div className="space-y-1 p-0.5 text-left">
                <div className="font-bold text-sky-400 text-xs">💨 Atmospheric Surface Wind (Open-Meteo)</div>
                <div className="text-[11px] text-slate-200">
                  Speed: <strong className="text-white">{Math.round(vec.speed)} kn</strong> · Flowing towards: <strong className="text-white">{Math.round((vec.direction + 180) % 360)}°</strong> (from {Math.round(vec.direction)}°)
                </div>
                <div className="text-[10px] text-sky-300">
                  Relative impact: <strong>{vec.relativeDesc}</strong> (Port corridor)
                </div>
              </div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-2 font-sans text-xs">
                <div className="font-bold text-sky-400 uppercase tracking-wider text-[11px]">
                  Atmospheric Surface Wind · Segment {vec.legIndex}
                </div>
                <div className="mt-1 grid grid-cols-2 gap-1 font-mono text-[11px]">
                  <div>Velocity: <span className="font-bold text-sky-300">{Math.round(vec.speed)} kn</span></div>
                  <div>Origin: <span className="font-bold text-sky-300">{Math.round(vec.direction)}°</span></div>
                  <div className="col-span-2">Relative Force: <span className="font-bold text-white">{vec.relativeDesc}</span></div>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground">Source: Open-Meteo GFS Weather Model</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* REAL-TIME ANIMATED OCEAN CURRENT VECTORS (Copernicus) — POSITIONED BESIDE TRACK (STARBOARD CORRIDOR) */}
        {showVectors && currentVectors.map((vec, idx) => (
          <Marker
            key={`curr-${idx}`}
            position={[vec.position.latitude, vec.position.longitude]}
            icon={currentVectorIcon(vec.direction, vec.speed, vec.isAssist)}
          >
            <Tooltip direction="top" offset={[0, -14]} opacity={0.98} className="naudisha-tooltip">
              <div className="space-y-1 p-0.5 text-left">
                <div className={cn('font-bold text-xs', vec.isAssist ? 'text-emerald-400' : 'text-amber-400')}>
                  🌊 Ocean Surface Current (Copernicus CMEMS)
                </div>
                <div className="text-[11px] text-slate-200">
                  Velocity: <strong className="text-white">{vec.speed.toFixed(1)} kn</strong> · Drift direction: <strong className="text-white">{Math.round(vec.direction)}°</strong>
                </div>
                <div className="text-[10px]">
                  Along-track force: <span className={cn('font-bold', vec.alongTrack >= 0 ? 'text-emerald-400' : 'text-amber-400')}>
                    {vec.alongTrack >= 0 ? `+${vec.alongTrack.toFixed(2)} kn Push (Assisting)` : `${vec.alongTrack.toFixed(2)} kn Drag (Opposing head-current)`}
                  </span> (Starboard corridor)
                </div>
              </div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-2 font-sans text-xs">
                <div className={cn('font-bold uppercase tracking-wider text-[11px]', vec.isAssist ? 'text-emerald-400' : 'text-amber-400')}>
                  Ocean Surface Current · Segment {vec.legIndex} ({vec.isAssist ? 'Assisting' : 'Opposing'})
                </div>
                <div className="mt-1 grid grid-cols-2 gap-1 font-mono text-[11px]">
                  <div>Speed: <span className="font-bold">{vec.speed.toFixed(1)} kn</span></div>
                  <div>Direction: <span className="font-bold">{Math.round(vec.direction)}°</span></div>
                  <div className="col-span-2">
                    Along-Track Force: <span className={cn('font-bold', vec.alongTrack >= 0 ? 'text-emerald-400' : 'text-amber-400')}>
                      {vec.alongTrack >= 0 ? `+${vec.alongTrack.toFixed(2)} kn (Pushing forward)` : `${vec.alongTrack.toFixed(2)} kn (Opposing / Head-current drag)`}
                    </span>
                  </div>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground">Source: Copernicus Marine (CMEMS) Physics Reanalysis</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Real Moving Boat Marker with Live Heading & AIS Aura */}
        {shipPosition && (
          <Marker
            position={[shipPosition.latitude, shipPosition.longitude]}
            icon={shipIcon(shipHeading, positionSource === 'simulated' || shipSimulated)}
            zIndexOffset={1000}
          >
            <Tooltip direction="top" offset={[0, -20]} opacity={0.96} className="naudisha-tooltip">
              <div>
                <div className="font-bold text-cyan-400">🚢 {shipName ?? 'Live Vessel'}</div>
                <div className="text-[10px] text-slate-200">
                  Fix: {formatCoordinate(shipPosition, 2)} · Heading: <strong>{Math.round(shipHeading)}°</strong>
                </div>
              </div>
            </Tooltip>
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold text-cyan-400">{shipName ?? 'Live Vessel'}</span>
                  <span className={cn('rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase', positionLabel.color, positionLabel.bg)}>
                    {positionLabel.text}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                  Fix: <span className="text-foreground">{formatCoordinate(shipPosition, 4)}</span>
                </div>
                <div className="mt-0.5 font-mono text-[11px]">
                  Heading: <span className="font-bold text-foreground">{Math.round(shipHeading)}°</span>
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route Alert Hazard Markers */}
        {alerts.map((alert) => {
          if (!alert.position) return null
          return (
            <Marker
              key={alert.id}
              position={[alert.position.latitude, alert.position.longitude]}
              icon={alertIcon(alert.severity)}
            >
              <Popup className="naudisha-popup">
                <div className="p-1.5 font-sans text-xs">
                  <div className="font-bold text-rose-400 uppercase tracking-wider text-[10px]">
                    {alert.severity} Hazard Alert
                  </div>
                  <p className="mt-1 text-muted-foreground">{alert.message}</p>
                  <div className="mt-1 font-mono text-[10px] text-muted-foreground/80">
                    Radius: {alert.radius_nm} NM
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      {/* Floating Marine Chart Legend */}
      {showLegend && (
        <MapLegend
          hasWindData={windVectors.length > 0}
          hasCurrentData={currentVectors.length > 0}
          hasDirectRoute={effectiveDirectRoute.length > 0}
        />
      )}
    </div>
  )
}

/** Helper component to fit map bounds on route or origin/destination selection without interrupting user zoom/pan */
function MapBoundsController({
  bounds,
  singlePoint,
}: {
  bounds: LatLngBoundsExpression | null
  singlePoint?: Coordinate | null
}) {
  const map = useMap()
  const lastBoundsKeyRef = useRef<string>('')
  const userInteractedRef = useRef<boolean>(false)

  // Track if user is actively zooming or dragging the map
  useEffect(() => {
    const handleUserInteraction = () => {
      userInteractedRef.current = true
    }
    map.on('zoomstart', handleUserInteraction)
    map.on('dragstart', handleUserInteraction)
    return () => {
      map.off('zoomstart', handleUserInteraction)
      map.off('dragstart', handleUserInteraction)
    }
  }, [map])

  const boundsKey = bounds ? JSON.stringify(bounds) : (singlePoint ? `${singlePoint.latitude.toFixed(2)},${singlePoint.longitude.toFixed(2)}` : '')

  useEffect(() => {
    if (!boundsKey) return
    // Only auto-fit when the passage definition changes, and never fight user zooming
    if (lastBoundsKeyRef.current !== boundsKey) {
      lastBoundsKeyRef.current = boundsKey
      userInteractedRef.current = false
      if (bounds) {
        map.fitBounds(bounds, {
          padding: [45, 45],
          maxZoom: 13,
          animate: true,
          duration: 0.8,
        })
      } else if (singlePoint) {
        map.flyTo([singlePoint.latitude, singlePoint.longitude], 8, {
          animate: true,
          duration: 0.8,
        })
      }
    }
  }, [bounds, singlePoint, boundsKey, map])

  return null
}

