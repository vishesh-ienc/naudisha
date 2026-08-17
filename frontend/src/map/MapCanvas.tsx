/**
 * Modern dark marine chart canvas.
 *
 * Combines high-contrast dark cartography with OpenSeaMap nautical seamarks,
 * Green optimal route polyline, Red direct/baseline route polyline, rotating boat marker,
 * and animated environmental wind/current vector layers.
 */

import { useEffect, useMemo } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
  LayersControl,
} from 'react-leaflet'
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coordinate, RouteAlert, RouteLeg } from '@/types/api'
import { NAVIGABLE_REGION, boundsOf, smoothPath } from '@/lib/geo'
import { formatCoordinate } from '@/lib/format'
import {
  alertIcon,
  currentVectorIcon,
  destinationIcon,
  shipIcon,
  startIcon,
  waypointIcon,
  windVectorIcon,
} from './markers'
import { MapLegend } from './MapLegend'
import { cn } from '@/lib/utils'

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


  // Extract environmental midpoints along legs
  const { windVectors, currentVectors } = useMemo(() => {
    if (!legs || legs.length === 0 || !showVectors) {
      return { windVectors: [], currentVectors: [] }
    }

    const winds: Array<{ position: Coordinate; speed: number; direction: number; legIndex: number }> = []
    const currents: Array<{
      position: Coordinate
      speed: number
      direction: number
      alongTrack: number
      isAssist: boolean
      legIndex: number
    }> = []

    legs.forEach((leg, idx) => {
      // Calculate midpoint of segment
      const midLat = (leg.from.latitude + leg.to.latitude) / 2
      const midLon = (leg.from.longitude + leg.to.longitude) / 2
      const midPos: Coordinate = { latitude: midLat, longitude: midLon }

      if (leg.wind_speed_kn != null && leg.wind_direction_deg != null) {
        winds.push({
          position: midPos,
          speed: leg.wind_speed_kn,
          direction: leg.wind_direction_deg,
          legIndex: idx + 1,
        })
      }

      if (leg.current_speed_kn != null && leg.current_direction_deg != null) {
        currents.push({
          position: midPos,
          speed: leg.current_speed_kn,
          direction: leg.current_direction_deg,
          alongTrack: leg.along_track_current_kn ?? 0,
          isAssist: (leg.along_track_current_kn ?? 0) >= 0,
          legIndex: idx + 1,
        })
      }
    })

    return { windVectors: winds, currentVectors: currents }
  }, [legs, showVectors])

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

  // Calculate auto-fit bounds
  const fitBounds: LatLngBoundsExpression | null = useMemo(() => {
    const points: Coordinate[] = []
    if (start) points.push(start)
    if (destination) points.push(destination)
    if (shipPosition) points.push(shipPosition)
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
  }, [start, destination, shipPosition, route])

  return (
    <div className={cn('relative h-full w-full overflow-hidden rounded-2xl border border-[var(--border)] shadow-2xl', className)}>
      <MapContainer
        center={center}
        zoom={9}
        minZoom={4}
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


        {/* Previous Route Trail (Faded Cyan/Gray) */}
        {previousPositions.length > 0 && (
          <Polyline
            positions={previousPositions}
            pathOptions={{
              color: '#64748b',
              weight: 3,
              opacity: 0.45,
              dashArray: '4, 8',
            }}
          />
        )}



        {/* 2. NAUDISHA OPTIMAL ROUTE — RENDERED IN VIBRANT GREEN */}
        {smoothedOptimalPositions.length > 0 && (
          <>
            {/* Green Outer Ambient Glow */}
            <Polyline
              positions={smoothedOptimalPositions}
              pathOptions={{
                color: '#10b981',
                weight: 9,
                opacity: 0.3,
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
                  <div className="font-bold text-emerald-400">NauDisha Optimal Route</div>
                  <p className="mt-1 text-muted-foreground">
                    Multi-factor $D^*$ Lite calculated route minimizing fuel, weather drag, and sea hazard exposure.
                  </p>
                </div>
              </Popup>
            </Polyline>
          </>
        )}

        {/* Start Point Marker */}
        {start && (
          <Marker position={[start.latitude, start.longitude]} icon={startIcon}>
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
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="font-bold text-emerald-400 text-[10px]">Waypoint {i + 1}</div>
                <div className="mt-0.5 font-mono text-[11px]">{formatCoordinate(pt, 4)}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* REAL-TIME ANIMATED WIND VECTORS (Open-Meteo) */}
        {showVectors && windVectors.map((vec, idx) => (
          <Marker
            key={`wind-${idx}`}
            position={[vec.position.latitude, vec.position.longitude]}
            icon={windVectorIcon(vec.direction, vec.speed)}
          >
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className="font-bold text-sky-400 uppercase tracking-wider text-[10px]">
                  Atmospheric Wind · Leg {vec.legIndex}
                </div>
                <div className="mt-1 grid grid-cols-2 gap-1 font-mono text-[11px]">
                  <div>Velocity: <span className="font-bold text-sky-300">{Math.round(vec.speed)} kn</span></div>
                  <div>Heading: <span className="font-bold text-sky-300">{Math.round(vec.direction)}°</span></div>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground">Source: Open-Meteo High-Res Marine API</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* REAL-TIME ANIMATED OCEAN CURRENT VECTORS (Copernicus) */}
        {showVectors && currentVectors.map((vec, idx) => (
          <Marker
            key={`curr-${idx}`}
            position={[vec.position.latitude, vec.position.longitude]}
            icon={currentVectorIcon(vec.direction, vec.speed, vec.isAssist)}
          >
            <Popup className="naudisha-popup">
              <div className="p-1.5 font-sans text-xs">
                <div className={cn('font-bold uppercase tracking-wider text-[10px]', vec.isAssist ? 'text-emerald-400' : 'text-amber-400')}>
                  Ocean Surface Current · Leg {vec.legIndex} ({vec.isAssist ? 'Assisting' : 'Opposing'})
                </div>
                <div className="mt-1 grid grid-cols-2 gap-1 font-mono text-[11px]">
                  <div>Speed: <span className="font-bold">{vec.speed.toFixed(1)} kn</span></div>
                  <div>Direction: <span className="font-bold">{Math.round(vec.direction)}°</span></div>
                  <div className="col-span-2">
                    Along-Track: <span className={cn('font-bold', vec.alongTrack >= 0 ? 'text-emerald-400' : 'text-amber-400')}>
                      {vec.alongTrack >= 0 ? `+${vec.alongTrack.toFixed(2)} kn (Push)` : `${vec.alongTrack.toFixed(2)} kn (Drag)`}
                    </span>
                  </div>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground">Source: Copernicus Marine Hydrodynamic Model</div>
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

/** Helper component to fit map bounds on route or single vessel position change */
function MapBoundsController({
  bounds,
  singlePoint,
}: {
  bounds: LatLngBoundsExpression | null
  singlePoint?: Coordinate | null
}) {
  const map = useMap()
  useEffect(() => {
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
  }, [bounds, singlePoint, map])
  return null
}

