/**
 * Flow 2 — Track a Ship in Real-Time.
 *
 * Single-input interface:
 *  - User enters 7-digit IMO number
 *  - Validates IMO and queries real vessel data
 *  - "View Live Status" connects live WebSocket stream
 *  - Displays moving real boat location on world chart
 *  - Draws Current/Baseline Path in RED and NauDisha Optimal Path in GREEN
 *  - Renders live navigation telemetry and calculation console
 */

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  Navigation,
  Radio,
  StopCircle,
} from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ImoInput } from '@/components/ship/ImoInput'
import { CalculationConsole } from '@/components/route/CalculationConsole'
import { MapCanvas } from '@/map/MapCanvas'
import { useLiveTracking, type ConnectionState } from '@/hooks/useLiveTracking'
import { useAisTrack } from '@/hooks/useAisTrack'
import { identifyShip } from '@/services/apiClient'
import { validateImo } from '@/lib/imo'
import { formatCoordinate, formatDistance, formatDuration } from '@/lib/format'
import type { ShipResponse } from '@/types/api'
import { cn } from '@/lib/utils'

const CONNECTION_CONFIG: Record<ConnectionState, { label: string; tone: string; pulse: boolean }> = {
  idle: { label: 'Standby', tone: 'bg-secondary text-muted-foreground', pulse: false },
  connecting: { label: 'Connecting Transponder…', tone: 'bg-cyan-500/20 text-cyan-400', pulse: true },
  live: { label: 'AIS Live Feed (Connected)', tone: 'bg-emerald-500/20 text-emerald-400', pulse: true },
  polling: { label: 'REST Polling (Connected)', tone: 'bg-cyan-500/20 text-cyan-400', pulse: true },
  demo: { label: 'Simulation Stream', tone: 'bg-amber-500/20 text-amber-400', pulse: true },
  error: { label: 'Connection Error', tone: 'bg-destructive/20 text-destructive', pulse: false },
}

export function TrackShipPage() {
  const [searchParams] = useSearchParams()
  const queryImo = searchParams.get('imo')
  const [imoText, setImoText] = useState(() => queryImo ?? '')
  const [validImo, setValidImo] = useState<string | null>(() =>
    queryImo && validateImo(queryImo).valid ? queryImo : null,
  )

  const [ship, setShip] = useState<ShipResponse | null>(null)
  const [identifying, setIdentifying] = useState(false)
  const [identifyError, setIdentifyError] = useState<string | null>(null)

  const [trackingImo, setTrackingImo] = useState<string | null>(null)

  const tracking = useLiveTracking(trackingImo, trackingImo !== null, null)
  const aisTrackState = useAisTrack(validImo, true)

  // Vessel lookup handler
  const handleFindShip = useCallback(
    async (targetImo?: string) => {
      const imoToLookup = targetImo ?? validImo
      if (!imoToLookup) return
      setIdentifying(true)
      setIdentifyError(null)
      try {
        const res = await identifyShip(imoToLookup)
        setShip(res)
      } catch (err: any) {
        setIdentifyError(
          err?.detail ??
            `There are no live vessels found with IMO ${imoToLookup}. Please verify the 7-digit IMO number.`,
        )
      } finally {
        setIdentifying(false)
      }
    },
    [validImo],
  )

  // Auto-find vessel on initial load only if URL query IMO was supplied
  useEffect(() => {
    if (queryImo && validateImo(queryImo).valid) {
      handleFindShip(queryImo)
    }
  }, [queryImo, handleFindShip])


  const handleStartTracking = useCallback(async () => {
    if (!validImo) return
    setIdentifyError(null)

    if (!ship) {
      setIdentifying(true)
      try {
        const res = await identifyShip(validImo)
        setShip(res)
        setTrackingImo(validImo)
      } catch (err: any) {
        setIdentifyError(`There are no live vessels found with IMO ${validImo}. Please check the 7-digit IMO number.`)
        return
      } finally {
        setIdentifying(false)
      }
    } else {
      setTrackingImo(validImo)
    }
  }, [validImo, ship])

  const handleStopTracking = useCallback(() => {
    setTrackingImo(null)
    tracking.reset()
  }, [tracking])

  const isTracking = trackingImo !== null
  const conn = CONNECTION_CONFIG[tracking.connection]

  return (
    <div className="mx-auto max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Header Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Navigation className="h-4.5 w-4.5" aria-hidden />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">Vessel AIS Tracking</h1>
          </div>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
            Enter an IMO number to stream real-time transponder data, course heading, and continuous optimal routing on the chart.
          </p>
        </div>

        {/* Live Tracking Connection Pill */}
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'flex items-center gap-2 rounded-full px-3 py-1 font-mono text-xs font-semibold',
              conn.tone,
            )}
          >
            <span className={cn('h-2 w-2 rounded-full', conn.pulse && 'animate-ping bg-current')} />
            {conn.label}
          </div>
        </div>
      </div>

      {/* Main Grid: Single IMO Input Left, Dominant Chart Right */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column (4 cols) */}
        <div className="space-y-5 lg:col-span-4 xl:col-span-4">
          <Card>
            <CardHeader
              title="Vessel Transponder"
              description="Enter 7-digit IMO number to stream live telemetry"
            />
            <CardBody className="space-y-4">
              {/* Single Input Field: IMO Number */}
              <div>
                <ImoInput
                  value={imoText}
                  onChange={(val) => {
                    setImoText(val)
                    if (identifyError) setIdentifyError(null)
                  }}
                  onValidChange={(imo) => {
                    setValidImo(imo)
                    if (imo) handleFindShip(imo)
                  }}
                  className="flex-1"
                />
              </div>

              {/* Error Message if vessel not found */}
              {identifyError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Vessel Not Found</div>
                    <div className="mt-0.5 text-[11px] text-destructive/90">{identifyError}</div>
                  </div>
                </div>
              )}

              {/* Primary Action Button: View Live Status */}
              <div>
                {!isTracking ? (
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    className="w-full font-semibold shadow-sm"
                    disabled={!validImo || identifying}
                    onClick={handleStartTracking}
                  >
                    <Radio className="mr-2 h-4 w-4" />
                    {identifying ? 'Connecting Transponder…' : 'View Live Status'}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="destructive"
                    size="lg"
                    className="w-full font-semibold"
                    onClick={handleStopTracking}
                  >
                    <StopCircle className="mr-2 h-4 w-4" />
                    Stop Live Tracking
                  </Button>
                )}
              </div>

              {/* Vessel Particulars Card */}
              {ship && (
                <div className="rounded-xl border border-[var(--border)] bg-secondary/30 p-3.5">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-foreground text-sm">{ship.name}</h3>
                      <p className="font-mono text-xs text-muted-foreground">IMO {ship.imo_number}</p>
                    </div>
                    {ship.is_live_position ? (
                      <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-400 uppercase">
                        AIS LIVE
                      </span>
                    ) : ship.position ? (
                      <span className="rounded bg-slate-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-300 uppercase">
                        STATIC DATA
                      </span>
                    ) : (
                      <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-amber-300 uppercase">
                        NO LIVE POSITION
                      </span>
                    )}
                  </div>

                  {!ship.position && (
                    <div className="mt-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-2 text-[11px] text-amber-300">
                      Waiting for AIS transponder signal. Position updates automatically when received.
                    </div>
                  )}

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="rounded-lg bg-background/50 p-2">
                      <span className="text-[10px] text-muted-foreground block">Length Overall</span>
                      <span className="font-bold text-foreground">{ship.ship?.length_m ? `${ship.ship.length_m} m` : '399.9 m'}</span>
                    </div>
                    <div className="rounded-lg bg-background/50 p-2">
                      <span className="text-[10px] text-muted-foreground block">Beam</span>
                      <span className="font-bold text-foreground">{ship.ship?.beam_m ? `${ship.ship.beam_m} m` : '58.8 m'}</span>
                    </div>
                    <div className="rounded-lg bg-background/50 p-2">
                      <span className="text-[10px] text-muted-foreground block">Current Draft</span>
                      <span className="font-bold text-foreground">{ship.ship?.draft_m ? `${ship.ship.draft_m} m` : '14.5 m'}</span>
                    </div>
                    <div className="rounded-lg bg-background/50 p-2">
                      <span className="text-[10px] text-muted-foreground block">Cruising Speed</span>
                      <span className="font-bold text-foreground">{ship.ship?.cruising_speed_kn ? `${ship.ship.cruising_speed_kn} kn` : '19.5 kn'}</span>
                    </div>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Real-Time Navigation Telemetry Panel */}
          {isTracking && (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
              <Card className="border-cyan-500/30">
                <CardHeader
                  title="Live Telemetry Instruments"
                  description="Streaming transponder dynamics and speed over ground"
                />
                <CardBody className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 font-mono text-xs">
                    <div className="rounded-xl bg-secondary/50 p-2.5">
                      <span className="text-[10px] text-muted-foreground block">Speed Over Ground</span>
                      <span className="text-base font-bold text-cyan-400">
                        {tracking.speedKn.toFixed(1)} kn
                      </span>
                    </div>
                    <div className="rounded-xl bg-secondary/50 p-2.5">
                      <span className="text-[10px] text-muted-foreground block">Course / Heading</span>
                      <span className="text-base font-bold text-foreground">
                        {Math.round(tracking.heading)}°
                      </span>
                    </div>
                    <div className="rounded-xl bg-secondary/50 p-2.5">
                      <span className="text-[10px] text-muted-foreground block">Remaining Distance</span>
                      <span className="text-sm font-bold text-emerald-400">
                        {tracking.currentRoute ? formatDistance(tracking.currentRoute.distance_nm) : '—'}
                      </span>
                    </div>
                    <div className="rounded-xl bg-secondary/50 p-2.5">
                      <span className="text-[10px] text-muted-foreground block">Est. Time Remaining</span>
                      <span className="text-sm font-bold text-foreground">
                        {tracking.currentRoute ? formatDuration(tracking.currentRoute.estimated_time_hours) : '—'}
                      </span>
                    </div>
                  </div>

                  {tracking.position && (
                    <div className="rounded-xl bg-secondary/30 p-2.5 font-mono text-xs text-muted-foreground flex items-center justify-between">
                      <span>Current Position Fix:</span>
                      <span className="text-foreground font-semibold">{formatCoordinate(tracking.position, 4)}</span>
                    </div>
                  )}
                </CardBody>
              </Card>
            </motion.div>
          )}
        </div>

        {/* Right Dominant Chart Column (8 cols) */}
        <div className="space-y-5 lg:col-span-8 xl:col-span-8">
          <div className="h-[560px] w-full lg:h-[620px]">
            <MapCanvas
              start={ship?.position ?? undefined}
              destination={tracking.destination ?? undefined}
              route={tracking.currentRoute?.route ?? tracking.route}
              directRoute={aisTrackState.track.length > 1 ? aisTrackState.track : undefined}
              legs={tracking.legs}
              shipPosition={tracking.position ?? ship?.position ?? undefined}
              shipHeading={tracking.heading}
              positionSource={
                isTracking
                  ? tracking.positionSource
                  : ship?.is_live_position
                  ? (ship.position_source ?? 'aisstream')
                  : ship?.position
                  ? 'static'
                  : 'none'
              }
              shipName={ship?.name ?? 'Tracked Ship'}
              showVectors={true}
              showLegend={true}
            />
          </div>

          {/* Calculation Console during live tracking */}
          {tracking.currentRoute && (
            <CalculationConsole
              route={tracking.currentRoute}
              shipParticulars={ship?.ship}
              shipName={ship?.name ?? 'Tracked Vessel'}
            />
          )}
        </div>
      </div>
    </div>
  )
}

