/**
 * Flow A — track a vessel already underway.
 *
 * Position, route and replans come from the backend over the WebSocket when it
 * is reachable, with REST polling as the fallback and a local simulation only
 * when the backend is unavailable entirely. The interface always states which
 * of the three is in play.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CloudLightning, Navigation, RotateCcw, Radio } from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ImoInput } from '@/components/ship/ImoInput'
import { ShipInfoPanel } from '@/components/ship/ShipInfoPanel'
import { VoyageEventLog } from '@/components/route/VoyageEventLog'
import { LocationPicker } from '@/components/route/LocationPicker'
import { MapCanvas } from '@/map/MapCanvas'
import { RadarSweep, WaveLoader } from '@/components/ui/ShipAnimation'
import { useLiveTracking, type ConnectionState, type TrackingOptions } from '@/hooks/useLiveTracking'
import { validateImo } from '@/lib/imo'
import { haversineNm } from '@/lib/geo'
import type { Coordinate } from '@/types/api'
import { cn } from '@/lib/utils'

const CONNECTION_CONFIG: Record<ConnectionState, { label: string; tone: string; pulse: boolean }> = {
  idle: { label: 'Not tracking', tone: 'bg-secondary text-muted-foreground', pulse: false },
  connecting: { label: 'Connecting…', tone: 'bg-primary/15 text-primary', pulse: true },
  live: { label: 'Live feed', tone: 'bg-[var(--success)]/15 text-[var(--success)]', pulse: true },
  polling: { label: 'Polling backend', tone: 'bg-primary/15 text-primary', pulse: true },
  demo: { label: 'Simulated', tone: 'bg-[var(--warning)]/15 text-[var(--warning)]', pulse: true },
  error: { label: 'Connection failed', tone: 'bg-destructive/15 text-destructive', pulse: false },
}

export function TrackShipPage() {
  const [searchParams] = useSearchParams()
  const [imoText, setImoText] = useState(() => searchParams.get('imo') ?? '')
  const [validImo, setValidImo] = useState<string | null>(null)
  const [destination, setDestination] = useState<Coordinate | null>(null)
  const [origin, setOrigin] = useState<Coordinate | null>(null)
  const [pickTarget, setPickTarget] = useState<'origin' | 'destination' | null>(null)

  const [trackingImo, setTrackingImo] = useState<string | null>(null)
  const [committed, setCommitted] = useState<TrackingOptions | null>(null)

  const tracking = useLiveTracking(trackingImo, trackingImo !== null, committed)

  // Deep link from the planning flow: /track?imo=…&lat=…&lon=…&autostart=1
  useEffect(() => {
    if (trackingImo) return
    const imo = searchParams.get('imo')
    const lat = Number(searchParams.get('lat'))
    const lon = Number(searchParams.get('lon'))

    if (imo && validateImo(imo).valid && Number.isFinite(lat) && Number.isFinite(lon)) {
      const dest = { latitude: lat, longitude: lon }
      const oLat = Number(searchParams.get('olat'))
      const oLon = Number(searchParams.get('olon'))
      const start = Number.isFinite(oLat) && Number.isFinite(oLon) ? { latitude: oLat, longitude: oLon } : null

      setDestination(dest)
      if (start) setOrigin(start)

      if (searchParams.get('autostart') === '1') {
        setTrackingImo(validateImo(imo).valid ? imo : null)
        setCommitted({ destination: dest, origin: start })
      }
    }
  }, [searchParams, trackingImo])

  const canStart = useMemo(() => {
    if (!validImo || !destination) return false
    if (origin && haversineNm(origin, destination) < 1) return false
    return true
  }, [validImo, destination, origin])

  const handleStart = useCallback(() => {
    if (!validImo || !destination) return
    setTrackingImo(validImo)
    setCommitted({ destination, origin })
  }, [validImo, destination, origin])

  const handleStop = useCallback(() => {
    setTrackingImo(null)
    setCommitted(null)
    tracking.reset()
  }, [tracking])

  const connection = CONNECTION_CONFIG[tracking.connection]
  const isTracking = trackingImo !== null

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6">
      <header className="flex flex-wrap items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Navigation className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">Track a Sailing Vessel</h1>
          <p className="text-sm text-muted-foreground">
            Follow a ship underway and watch its route adapt to changing conditions.
          </p>
        </div>

        {isTracking && (
          <div
            className={cn('flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium', connection.tone)}
            role="status"
          >
            <span className="relative flex h-2 w-2">
              {connection.pulse && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
              )}
              <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
            </span>
            {connection.label}
          </div>
        )}
      </header>

      <AnimatePresence>
        {isTracking && tracking.simulated && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 overflow-hidden"
          >
            <div className="flex items-start gap-2.5 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--warning)]" aria-hidden />
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--warning)]">Simulated voyage</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  The backend is unavailable, so vessel movement, hazards and route updates on this
                  screen are generated locally for demonstration. They are not real observations.
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {isTracking && !tracking.simulated && tracking.planning && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 overflow-hidden"
          >
            <div className="flex items-start gap-2.5 rounded-lg border border-primary/30 bg-primary/10 px-4 py-3">
              <WaveLoader size={36} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-primary">Computing the optimal route…</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  The backend is sampling live Copernicus Marine and Open-Meteo forecasts for this
                  corridor. A first request can take up to two minutes; the route appears here the
                  moment it is ready.
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,360px)_1fr]">
        <div className="space-y-5">
          {!isTracking ? (
            <Card>
              <CardHeader
                title="Start Tracking"
                description="Identify the vessel and set where it is bound."
              />
              <CardBody className="space-y-5">
                <ImoInput value={imoText} onChange={setImoText} onValidChange={setValidImo} autoFocus />

                <LocationPicker
                  label="Destination"
                  accent="destination"
                  value={destination}
                  onChange={setDestination}
                  picking={pickTarget === 'destination'}
                  onPickingChange={(p) => setPickTarget(p ? 'destination' : null)}
                />

                <LocationPicker
                  label="Current position (optional)"
                  accent="start"
                  value={origin}
                  onChange={setOrigin}
                  picking={pickTarget === 'origin'}
                  onPickingChange={(p) => setPickTarget(p ? 'origin' : null)}
                />

                <p className="text-[11px] text-muted-foreground">
                  Leave the position blank to use the vessel's live AIS fix. Most vessels report no
                  fix without an AIS key configured, in which case the backend falls back to a
                  default open-water origin.
                </p>

                <Button className="w-full" size="lg" disabled={!canStart} onClick={handleStart}>
                  <Radio className="h-4 w-4" aria-hidden />
                  Track Ship
                </Button>

                {!canStart && (
                  <p className="text-center text-[11px] text-muted-foreground">
                    {!validImo ? 'Enter a valid IMO number.' : 'Set a destination to continue.'}
                  </p>
                )}
              </CardBody>
            </Card>
          ) : (
            <>
              <ShipInfoPanel
                ship={tracking.ship}
                source={tracking.shipSource}
                position={tracking.position}
                destination={tracking.destination}
                heading={tracking.heading}
                progressPercent={tracking.progressPercent}
                distanceRemainingNm={tracking.distanceRemainingNm}
                hoursRemaining={tracking.hoursRemaining}
                arrived={tracking.arrived}
              />

              <Card>
                <CardHeader
                  title="Voyage Controls"
                  description={tracking.simulated ? 'Demonstrate dynamic replanning' : 'Live backend session'}
                  action={
                    tracking.replanCount > 0 ? (
                      <Badge variant="accent">
                        {tracking.replanCount} update{tracking.replanCount === 1 ? '' : 's'}
                      </Badge>
                    ) : undefined
                  }
                />
                <CardBody className="space-y-2.5">
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={tracking.triggerStorm}
                    disabled={tracking.arrived || !tracking.position}
                  >
                    <CloudLightning className="h-4 w-4" aria-hidden />
                    Inject Storm Ahead
                  </Button>
                  <Button variant="ghost" className="w-full" onClick={handleStop}>
                    <RotateCcw className="h-4 w-4" aria-hidden />
                    Stop Tracking
                  </Button>
                  <p className="pt-1 text-[10px] leading-relaxed text-muted-foreground">
                    {tracking.simulated
                      ? 'Injecting a storm marks a hazard ahead and requests a new route — the same path a real forecast change would take.'
                      : 'The API has no endpoint for injecting weather, so this overlays a hazard marker only. The live route is computed by the backend and is not altered.'}
                  </p>
                </CardBody>
              </Card>

              <VoyageEventLog events={tracking.events} />
            </>
          )}
        </div>

        <div className="relative min-h-[560px] overflow-hidden rounded-xl border border-[var(--border)]">
          <MapCanvas
            className="h-full min-h-[560px] w-full"
            route={tracking.route}
            previousRoute={tracking.previousRoute}
            destination={isTracking ? tracking.destination : destination}
            start={!isTracking ? origin : null}
            shipPosition={tracking.position}
            shipHeading={tracking.heading}
            shipSimulated={tracking.simulated}
            alerts={tracking.alerts}
            showApproachLegs={false}
            {...(pickTarget && {
              onMapClick: (c: Coordinate) => {
                if (pickTarget === 'destination') setDestination(c)
                else setOrigin(c)
                setPickTarget(null)
              },
            })}
          />

          {pickTarget && (
            <div className="pointer-events-none absolute left-1/2 top-4 z-[500] -translate-x-1/2 rounded-full border border-primary/40 bg-card/95 px-4 py-2 text-xs font-medium shadow-lg backdrop-blur">
              Click the chart to set the {pickTarget === 'origin' ? 'current position' : 'destination'}
            </div>
          )}

          <AnimatePresence>
            {tracking.alerts.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                className="absolute left-4 top-4 z-[500] w-[min(340px,calc(100%-2rem))] space-y-2"
              >
                {tracking.alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={cn(
                      'rounded-lg border px-3 py-2.5 shadow-lg backdrop-blur',
                      alert.severity === 'critical'
                        ? 'border-destructive/40 bg-destructive/12'
                        : 'border-[var(--warning)]/40 bg-[var(--warning)]/12',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <AlertTriangle
                        className={cn(
                          'mt-0.5 h-4 w-4 shrink-0',
                          alert.severity === 'critical' ? 'text-destructive' : 'text-[var(--warning)]',
                        )}
                        aria-hidden
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium leading-snug">{alert.message}</p>
                        <div className="mt-1 flex items-center gap-1.5">
                          <span className="font-mono text-[10px] uppercase text-muted-foreground">
                            {alert.kind}
                          </span>
                          <Badge variant="info" className="px-1 py-0 text-[9px]">
                            SIMULATED
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {!isTracking && !destination && (
            <div className="pointer-events-none absolute inset-0 z-[400] flex flex-col items-center justify-center gap-3 bg-background/60 text-center backdrop-blur-[1px]">
              <RadarSweep size={72} />
              <p className="text-sm font-medium">Awaiting vessel selection</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Enter an IMO number and a destination to begin tracking.
              </p>
            </div>
          )}

          {tracking.arrived && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="absolute bottom-4 left-1/2 z-[500] -translate-x-1/2 rounded-full border border-[var(--success)]/40 bg-[var(--success)]/15 px-4 py-2 text-xs font-medium text-[var(--success)] shadow-lg backdrop-blur"
            >
              Vessel arrived at destination
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
