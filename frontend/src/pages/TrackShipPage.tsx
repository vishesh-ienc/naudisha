/**
 * Flow A — track a vessel already underway.
 *
 * Position, route and hazards come from the backend when it is reachable, and
 * from a clearly-labelled local simulation when it is not. The simulation exists
 * so dynamic replanning can be demonstrated on demand; every simulated value
 * carries a SIMULATED marker.
 */

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CloudLightning, Navigation, RotateCcw, Radio } from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ImoInput } from '@/components/ship/ImoInput'
import { ShipInfoPanel } from '@/components/ship/ShipInfoPanel'
import { VoyageEventLog } from '@/components/route/VoyageEventLog'
import { MapCanvas } from '@/map/MapCanvas'
import { RadarSweep } from '@/components/ui/ShipAnimation'
import { useLiveTracking, type ConnectionState } from '@/hooks/useLiveTracking'
import { validateImo } from '@/lib/imo'
import { cn } from '@/lib/utils'

const CONNECTION_CONFIG: Record<ConnectionState, { label: string; tone: string; pulse: boolean }> = {
  idle: { label: 'Not tracking', tone: 'bg-secondary text-muted-foreground', pulse: false },
  connecting: { label: 'Connecting…', tone: 'bg-primary/15 text-primary', pulse: true },
  live: { label: 'Live feed', tone: 'bg-[var(--success)]/15 text-[var(--success)]', pulse: true },
  polling: { label: 'Polling backend', tone: 'bg-[var(--success)]/15 text-[var(--success)]', pulse: true },
  // Shorter than the banner below it, which carries the full explanation —
  // repeating the same phrase twice on one screen just reads as a glitch.
  demo: { label: 'Simulated', tone: 'bg-[var(--warning)]/15 text-[var(--warning)]', pulse: true },
  error: { label: 'Connection failed', tone: 'bg-destructive/15 text-destructive', pulse: false },
}

export function TrackShipPage() {
  const [searchParams] = useSearchParams()
  const [imoText, setImoText] = useState(() => searchParams.get('imo') ?? '')
  const [validImo, setValidImo] = useState<string | null>(null)
  const [trackingImo, setTrackingImo] = useState<string | null>(null)

  const tracking = useLiveTracking(trackingImo, trackingImo !== null)

  // Deep link from the planning flow: /track?imo=…&autostart=1
  useEffect(() => {
    const imo = searchParams.get('imo')
    if (imo && searchParams.get('autostart') === '1' && validateImo(imo).valid && !trackingImo) {
      setTrackingImo(validateImo(imo).valid ? imo : null)
    }
  }, [searchParams, trackingImo])

  const handleStart = useCallback(() => {
    if (validImo) setTrackingImo(validImo)
  }, [validImo])

  const handleStop = useCallback(() => {
    setTrackingImo(null)
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

      {/* Simulation banner — the demo must never be mistaken for real telemetry. */}
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
      </AnimatePresence>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,360px)_1fr]">
        {/* ----------------------------- Controls ---------------------------- */}
        <div className="space-y-5">
          {!isTracking ? (
            <Card>
              <CardHeader title="Vessel Identification" description="Enter the IMO number of the vessel to track." />
              <CardBody className="space-y-5">
                <ImoInput value={imoText} onChange={setImoText} onValidChange={setValidImo} autoFocus />
                <Button className="w-full" size="lg" disabled={!validImo} onClick={handleStart}>
                  <Radio className="h-4 w-4" aria-hidden />
                  Track Ship
                </Button>
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
                  description="Demonstrate dynamic replanning"
                  action={
                    tracking.replanCount > 0 ? (
                      <Badge variant="accent">
                        {tracking.replanCount} replan{tracking.replanCount === 1 ? '' : 's'}
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
                    Injecting a storm marks a hazard ahead of the vessel and requests a new route —
                    the same path a real forecast change would take. Clearly labelled as simulated.
                  </p>
                </CardBody>
              </Card>

              <VoyageEventLog events={tracking.events} />
            </>
          )}
        </div>

        {/* ------------------------------- Chart ----------------------------- */}
        <div className="relative min-h-[560px] overflow-hidden rounded-xl border border-[var(--border)]">
          {isTracking ? (
            <>
              <MapCanvas
                className="h-full min-h-[560px] w-full"
                route={tracking.route}
                previousRoute={tracking.previousRoute}
                destination={tracking.destination}
                shipPosition={tracking.position}
                shipHeading={tracking.heading}
                shipSimulated={tracking.simulated}
                alerts={tracking.alerts}
                showApproachLegs={false}
              />

              {/* Active hazards, overlaid on the chart. */}
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

              {tracking.arrived && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute bottom-4 left-1/2 z-[500] -translate-x-1/2 rounded-full border border-[var(--success)]/40 bg-[var(--success)]/15 px-4 py-2 text-xs font-medium text-[var(--success)] shadow-lg backdrop-blur"
                >
                  Vessel arrived at destination
                </motion.div>
              )}
            </>
          ) : (
            <div className="flex h-full min-h-[560px] flex-col items-center justify-center gap-3 bg-card/40 text-center">
              <RadarSweep size={72} />
              <p className="text-sm font-medium">Awaiting vessel selection</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Enter an IMO number to begin tracking. Position, route and hazards will appear here.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
