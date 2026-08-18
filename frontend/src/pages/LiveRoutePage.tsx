import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  ChevronDown,
  RefreshCw,
} from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ImoInput } from '@/components/ship/ImoInput'
import { PortSearchInput } from '@/components/route/PortSearchInput'
import { CalculationConsole } from '@/components/route/CalculationConsole'
import { MapCanvas } from '@/map/MapCanvas'
import { useRoutePlan } from '@/hooks/useRoutePlan'
import { identifyShip } from '@/services/apiClient'
import { validateImo } from '@/lib/imo'
import type { Coordinate, ShipResponse } from '@/types/api'
import { haversineNm } from '@/lib/geo'

export function LiveRoutePage() {
  const [searchParams] = useSearchParams()
  const queryImo = searchParams.get('imo')
  const [imoText, setImoText] = useState(() => queryImo ?? '')
  const [validImo, setValidImo] = useState<string | null>(() =>
    queryImo && validateImo(queryImo).valid ? queryImo : null,
  )

  const [ship, setShip] = useState<ShipResponse | null>(null)
  const [identifying, setIdentifying] = useState(false)
  const [identifyError, setIdentifyError] = useState<string | null>(null)

  const [currentLocation, setCurrentLocation] = useState<Coordinate | null>(null)
  const [destCoord, setDestCoord] = useState<Coordinate | null>(null)

  const [showScrollToast, setShowScrollToast] = useState(false)
  const mapRef = useRef<HTMLDivElement>(null)
  const consoleRef = useRef<HTMLDivElement>(null)

  const { phase, route, elapsedSeconds, progressPercent, error: planError, plan } = useRoutePlan()

  const handleLookupVessel = useCallback(async (targetImo?: string) => {
    const imo = targetImo ?? validImo
    if (!imo) return
    setIdentifying(true)
    setIdentifyError(null)

    try {
      const res = await identifyShip(imo)
      setShip(res)
      setCurrentLocation(res.position ?? null)
    } catch (err: any) {
      setIdentifyError(
        err?.detail ?? `No live vessel found with IMO ${imo}. Please check the 7-digit IMO number.`,
      )
    } finally {
      setIdentifying(false)
    }
  }, [validImo])

  useEffect(() => {
    if (queryImo && validateImo(queryImo).valid) {
      handleLookupVessel(queryImo)
    }
  }, [queryImo, handleLookupVessel])

  const handleCalculateRoute = useCallback(async () => {
    if (!currentLocation || !destCoord) return
    await plan({
      imo_number: validImo,
      start: currentLocation,
      destination: destCoord,
      departure_time: new Date().toISOString(),
      ...(ship?.ship ? { ship: ship.ship } : {}),
    })
  }, [currentLocation, destCoord, validImo, ship, plan])

  const isPlanning = phase === 'submitting' || phase === 'planning'
  const canCalculate = currentLocation && destCoord && haversineNm(currentLocation, destCoord) > 1

  useEffect(() => {
    if (isPlanning) {
      setShowScrollToast(true)
      setTimeout(() => mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
      const t = setTimeout(() => setShowScrollToast(false), 5000)
      return () => clearTimeout(t)
    }
  }, [isPlanning])

  useEffect(() => {
    if (phase === 'ready' && route) {
      setTimeout(() => consoleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200)
    }
  }, [phase, route])

  return (
    <div className="mx-auto max-w-[1700px] px-4 py-5 sm:px-6 lg:px-8">
      {/* Header Bar */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Live Vessel Routing</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Fetch real-time AIS transponder coordinates for a vessel and calculate a route to destination.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
          AIS Feed Active
        </div>
      </div>

      {/* Scroll-down Toast */}
      <AnimatePresence>
        {showScrollToast && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="fixed right-6 top-16 z-50 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-card px-3.5 py-2.5 shadow-lg"
          >
            <ChevronDown className="h-4 w-4 text-primary" />
            <div>
              <div className="text-xs font-semibold text-foreground">Calculating Route…</div>
              <div className="text-[11px] text-muted-foreground">See details in console below map</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Grid */}
      <div className="grid gap-5 lg:grid-cols-12">
        {/* Left Controls (4 cols) */}
        <div className="space-y-4 lg:col-span-4 xl:col-span-4">
          {/* IMO Input */}
          <Card>
            <CardHeader
              title="Vessel Selection"
              description="Enter 7-digit IMO number to retrieve position"
            />
            <CardBody className="space-y-3.5">
              <div className="flex items-center gap-2">
                <ImoInput
                  value={imoText}
                  onChange={(val) => {
                    setImoText(val)
                    if (identifyError) setIdentifyError(null)
                  }}
                  onValidChange={(imo) => {
                    setValidImo(imo)
                    if (imo) handleLookupVessel(imo)
                  }}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={!validImo || identifying}
                  onClick={() => handleLookupVessel()}
                  className="shrink-0"
                >
                  {identifying ? 'Searching…' : 'Search'}
                </Button>
              </div>

              {identifyError && (
                <div className="rounded border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Lookup Failed</div>
                    <div className="mt-0.5 text-[11px] text-destructive/90">{identifyError}</div>
                  </div>
                </div>
              )}

              {ship && !identifyError && (
                <div className="rounded border border-[var(--border)] bg-secondary/30 p-2.5 font-mono text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-foreground">{ship.name}</span>
                    {ship.is_live_position ? (
                      <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[9px] font-bold text-emerald-400">
                        AIS LIVE
                      </span>
                    ) : ship.position ? (
                      <span className="rounded bg-slate-500/20 px-1.5 py-0.2 text-[9px] text-slate-300">
                        STATIC POS
                      </span>
                    ) : (
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.2 text-[9px] text-amber-300">
                        NO POS
                      </span>
                    )}
                  </div>
                  {ship.position ? (
                    <div className="text-muted-foreground text-[10px] mt-1">
                      Lat: {ship.position.latitude.toFixed(4)}°, Lon: {ship.position.longitude.toFixed(4)}°
                    </div>
                  ) : (
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      Awaiting transponder signal.
                    </div>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Destination */}
          <Card>
            <CardHeader
              title="Destination"
              description="Select arrival port"
            />
            <CardBody className="space-y-3.5">
              <PortSearchInput
                label="Destination Port"
                placeholder="Search port (e.g. Dubai, Singapore, Rotterdam, Goa)…"
                value={destCoord}
                onChange={(coord) => setDestCoord(coord)}
                accent="destination"
              />

              <div className="pt-1">
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full font-semibold shadow-xs"
                  disabled={!canCalculate || isPlanning}
                  onClick={handleCalculateRoute}
                >
                  {isPlanning ? (
                    <span className="flex items-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Calculating Route… ({Math.round(progressPercent)}%)
                    </span>
                  ) : (
                    'Calculate Route'
                  )}
                </Button>
              </div>

              {planError && (
                <div className="rounded border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Calculation Error</div>
                    <div className="mt-0.5 text-[11px] text-destructive/90">{planError}</div>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right Map (8 cols) */}
        <div ref={mapRef} className="lg:col-span-8 xl:col-span-8">
          <div className="h-[560px] w-full lg:h-[640px]">
            <MapCanvas
              start={currentLocation}
              destination={destCoord}
              route={route?.route ?? []}
              legs={route?.legs ?? []}
              shipPosition={currentLocation}
              shipHeading={route?.legs?.[0]?.bearing ?? 180}
              positionSource={
                ship?.is_live_position
                  ? (ship.position_source ?? 'aisstream')
                  : ship?.position
                  ? 'static'
                  : 'none'
              }
              shipName={ship?.name ?? 'Live Vessel'}
              showVectors={true}
              showLegend={true}
            />
          </div>
        </div>
      </div>

      {/* Calculation Console below map */}
      {(isPlanning || route) && (
        <div ref={consoleRef} className="mt-5">
          <CalculationConsole
            route={route}
            shipParticulars={ship?.ship}
            shipName={ship?.name ?? 'Live Vessel'}
            isPlanning={isPlanning}
            planningPhase={phase}
            elapsedSeconds={elapsedSeconds}
          />
        </div>
      )}
    </div>
  )
}
