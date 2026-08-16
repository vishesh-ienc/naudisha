/**
 * The chart surface.
 *
 * Base layer is OpenStreetMap with the OpenSeaMap seamark overlay — both free,
 * no API token, and the seamark layer adds real nautical markings (buoys,
 * lights, traffic separation) which makes it read as a marine chart rather than
 * a road map.
 *
 * The frontend never computes route geometry (API_CONTRACT §16). This component
 * draws what it is given.
 */

import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Circle, useMap, useMapEvents, LayersControl } from 'react-leaflet'
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coordinate, RouteAlert } from '@/types/api'
import { NAVIGABLE_REGION, boundsOf, smoothPath, bearingDeg } from '@/lib/geo'
import { useTheme } from '@/hooks/useTheme'
import { alertIcon, destinationIcon, shipIcon, startIcon, waypointIcon } from './markers'

export interface MapCanvasProps {
  start?: Coordinate | null
  destination?: Coordinate | null
  /** Waypoints exactly as returned by the backend. */
  route?: Coordinate[]
  /** Previous route, drawn faded so a replan is visible as a change. */
  previousRoute?: Coordinate[]
  shipPosition?: Coordinate | null
  shipHeading?: number
  shipSimulated?: boolean
  alerts?: RouteAlert[]
  onMapClick?: (coordinate: Coordinate) => void
  /** Draws dashed legs from the true endpoints to the route's first/last node. */
  showApproachLegs?: boolean
  className?: string
  interactive?: boolean
}

export function MapCanvas({
  start,
  destination,
  route = [],
  previousRoute = [],
  shipPosition,
  shipHeading = 0,
  shipSimulated = false,
  alerts = [],
  onMapClick,
  showApproachLegs = true,
  className,
  interactive = true,
}: MapCanvasProps) {
  const center: LatLngExpression = [NAVIGABLE_REGION.center.latitude, NAVIGABLE_REGION.center.longitude]

  return (
    <MapContainer
      center={center}
      zoom={NAVIGABLE_REGION.defaultZoom}
      className={className}
      scrollWheelZoom={interactive}
      dragging={interactive}
      zoomControl={interactive}
      attributionControl
    >
      <TileThemeSync />

      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="Standard">
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            maxZoom={18}
          />
        </LayersControl.BaseLayer>

        <LayersControl.BaseLayer name="Muted">
          <TileLayer
            url="https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; OpenStreetMap'
            maxZoom={18}
          />
        </LayersControl.BaseLayer>

        <LayersControl.Overlay checked name="Seamarks">
          <TileLayer
            url="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openseamap.org">OpenSeaMap</a>'
            maxZoom={18}
            opacity={0.9}
          />
        </LayersControl.Overlay>
      </LayersControl>

      {onMapClick && <ClickHandler onMapClick={onMapClick} />}
      <FitToContent start={start} destination={destination} route={route} shipPosition={shipPosition} />

      {/* Previous route, faded — makes a replan legible as a change rather than
          a silent swap. */}
      {previousRoute.length > 1 && (
        <Polyline
          positions={toLatLngs(smoothPath(previousRoute))}
          pathOptions={{ color: 'var(--muted-foreground)', weight: 3, opacity: 0.35, dashArray: '6 8' }}
        />
      )}

      {/* Approach legs. The backend snaps endpoints to grid nodes, so the route
          can start some distance from the requested position; drawing the gap
          dashed is honest about it instead of leaving a floating line. */}
      {showApproachLegs && start && route.length > 0 && (
        <Polyline
          positions={toLatLngs([start, route[0]!])}
          pathOptions={{ color: 'var(--muted-foreground)', weight: 2, opacity: 0.6, dashArray: '3 6' }}
        />
      )}
      {showApproachLegs && destination && route.length > 0 && (
        <Polyline
          positions={toLatLngs([route[route.length - 1]!, destination])}
          pathOptions={{ color: 'var(--muted-foreground)', weight: 2, opacity: 0.6, dashArray: '3 6' }}
        />
      )}

      {route.length > 1 && (
        <>
          {/* Halo beneath the route keeps it readable over busy tiles. */}
          <Polyline
            positions={toLatLngs(smoothPath(route))}
            pathOptions={{ color: 'var(--card)', weight: 9, opacity: 0.75 }}
          />
          <Polyline
            positions={toLatLngs(smoothPath(route))}
            pathOptions={{ color: 'var(--route)', weight: 4, opacity: 0.95, lineCap: 'round' }}
          />
        </>
      )}

      {/* True backend waypoints — the smoothed line passes through these. */}
      {route.length > 2 &&
        route.slice(1, -1).map((wp, i) => (
          <Marker key={`wp-${i}`} position={[wp.latitude, wp.longitude]} icon={waypointIcon} />
        ))}

      {alerts.map((alert) =>
        alert.position ? (
          <div key={alert.id}>
            {alert.radius_nm ? (
              <Circle
                center={[alert.position.latitude, alert.position.longitude]}
                radius={alert.radius_nm * 1852}
                pathOptions={{
                  color: alert.severity === 'critical' ? 'var(--destructive)' : 'var(--warning)',
                  fillColor: alert.severity === 'critical' ? 'var(--destructive)' : 'var(--warning)',
                  fillOpacity: 0.12,
                  weight: 1.5,
                  dashArray: '5 5',
                }}
              />
            ) : null}
            <Marker
              position={[alert.position.latitude, alert.position.longitude]}
              icon={alertIcon(alert.severity)}
              title={alert.message}
            />
          </div>
        ) : null,
      )}

      {start && <Marker position={[start.latitude, start.longitude]} icon={startIcon} title="Start" />}
      {destination && (
        <Marker position={[destination.latitude, destination.longitude]} icon={destinationIcon} title="Destination" />
      )}
      {shipPosition && (
        <Marker
          position={[shipPosition.latitude, shipPosition.longitude]}
          icon={shipIcon(shipHeading, shipSimulated)}
          title="Vessel"
          zIndexOffset={1000}
        />
      )}
    </MapContainer>
  )
}

function toLatLngs(points: Coordinate[]): LatLngExpression[] {
  return points.map((p) => [p.latitude, p.longitude] as LatLngExpression)
}

/** Dims the tile raster in dark mode so the chart doesn't glare. */
function TileThemeSync() {
  const { resolved } = useTheme()
  const map = useMap()

  useEffect(() => {
    const container = map.getContainer()
    container.classList.toggle('naudisha-map-dark', resolved === 'dark')
  }, [resolved, map])

  return null
}

function ClickHandler({ onMapClick }: { onMapClick: (c: Coordinate) => void }) {
  useMapEvents({
    click(e) {
      onMapClick({
        latitude: Number(e.latlng.lat.toFixed(4)),
        longitude: Number(e.latlng.lng.toFixed(4)),
      })
    },
  })
  return null
}

/**
 * Frames the content when the *shape* of what is displayed changes, not on every
 * position tick — otherwise the map would fight the user's pan during tracking.
 */
function FitToContent({
  start,
  destination,
  route,
  shipPosition,
}: Pick<MapCanvasProps, 'start' | 'destination' | 'route' | 'shipPosition'>) {
  const map = useMap()

  const points = useMemo(() => {
    const all: Coordinate[] = []
    if (start) all.push(start)
    if (destination) all.push(destination)
    if (shipPosition) all.push(shipPosition)
    if (route && route.length) all.push(...route)
    return all
  }, [start, destination, route, shipPosition])

  // Key on endpoints and route length only, so ship movement doesn't refit.
  const fitKey = useMemo(
    () =>
      [
        start ? `${start.latitude},${start.longitude}` : '-',
        destination ? `${destination.latitude},${destination.longitude}` : '-',
        route?.length ?? 0,
      ].join('|'),
    [start, destination, route?.length],
  )

  useEffect(() => {
    if (points.length === 0) return

    if (points.length === 1) {
      map.setView([points[0]!.latitude, points[0]!.longitude], 10, { animate: true })
      return
    }

    const b = boundsOf(points, 0.1)
    if (!b) return
    const bounds: LatLngBoundsExpression = [
      [b.south, b.west],
      [b.north, b.east],
    ]
    map.flyToBounds(bounds, { padding: [40, 40], duration: 0.8, maxZoom: 11 })
    // `points` intentionally omitted — refit only when fitKey changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, map])

  return null
}

/** Course over ground between the last two path points, for marker rotation. */
export function headingFromPath(path: Coordinate[], position: Coordinate): number {
  if (path.length < 2) return 0
  let nearest = 0
  let best = Infinity
  for (let i = 0; i < path.length; i += 1) {
    const d = (path[i]!.latitude - position.latitude) ** 2 + (path[i]!.longitude - position.longitude) ** 2
    if (d < best) {
      best = d
      nearest = i
    }
  }
  const next = Math.min(nearest + 1, path.length - 1)
  const prev = Math.max(next - 1, 0)
  return bearingDeg(path[prev]!, path[next]!)
}
