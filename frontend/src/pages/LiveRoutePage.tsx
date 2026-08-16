/**
 * Flow 3 — Live Location + Destination Routing.
 *
 * Glitch-free interface:
 *  - Vessel IMO Number (acquires live transponder fix)
 *  - Destination Port autocomplete from worldwide port database
 *  - Calculates optimal route from live vessel position to destination
 *  - Renders Green Optimal Route, Red Direct Baseline, Animated Vectors
 *  - Full-width Calculation Console below map
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertTriangle,
  ChevronDown,
  LocateFixed,
  RefreshCw,
  Sparkles,
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
        err?.detail ?? `There are no live vessels found with IMO ${imo}. Please verify the 7-digit IMO number.`,
      )
    } finally {
      setIdentifying(false)
    }
  }, [validImo])

  // Initial lookup on mount only if URL query IMO provided
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

  // Toast + scroll-to-map on route start
  useEffect(() => {
    if (isPlanning) {
      setShowScrollToast(true)
      setTimeout(() => mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
      const t = setTimeout(() => setShowScrollToast(false), 5000)
      return () => clearTimeout(t)
    }
  }, [isPlanning])

  // Scroll to console when route is ready
  useEffect(() => {
    if (phase === 'ready' && route) {
      setTimeout(() => consoleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200)
    }
  }, [phase, route])

  return (
    <div className="mx-auto max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Header Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <LocateFixed className="h-4.5 w-4.5" aria-hidden />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
              Live Location + Destination Routing
            </h1>
          </div>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
            Enter a vessel IMO to lock onto its live transponder, choose a world destination port, and calculate an optimal route.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          Live Transponder Active
        </div>
      </div>

      {/* Scroll-down Toast */}
      <AnimatePresence>
        {showScrollToast && (
          <motion.div
            initial={{ opacity: 0, y: -20, x: 20 }}
            animate={{ opacity: 1, y: 0, x: 0 }}
            exit={{ opacity: 0, y: -20, x: 20 }}
            className="fixed right-6 top-16 z-50 flex items-center gap-2.5 rounded-2xl border border-emerald-500/30 bg-card/95 px-4 py-3 shadow-2xl shadow-black/30 backdrop-blur-md"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
              <ChevronDown className="h-4 w-4" />
            </span>
            <div>
              <div className="text-xs font-semibold text-foreground">Route Calculating…</div>
              <div className="text-[11px] text-muted-foreground">Scroll down to see optimization progress</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Controls (4 cols) */}
        <div className="space-y-5 lg:col-span-4 xl:col-span-4">
          {/* IMO Input */}
          <Card>
            <CardHeader
              title="1. Live Vessel Transponder"
              description="Enter 7-digit IMO to acquire real-time vessel position"
            />
            <CardBody className="space-y-4">
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
                  {identifying ? 'Locating…' : 'Locate'}
                </Button>
              </div>

              {identifyError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Vessel Not Found</div>
                    <div className="mt-0.5 text-[11px] text-destructive/80">{identifyError}</div>
                  </div>
                </div>
              )}

              {ship && !identifyError && (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 font-mono text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                      Vessel Located
                    </span>
                    {ship.is_live_position ? (
                      <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400">
                        AIS LIVE
                      </span>
                    ) : ship.position ? (
                      <span className="rounded bg-slate-500/20 px-1.5 py-0.5 text-[9px] font-bold text-slate-300">
                        STATIC DATA
                      </span>
                    ) : (
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-bold text-amber-300">
                        NO LIVE POSITION
                      </span>
                    )}
                  </div>
                  <div className="mt-1 font-semibold text-foreground">{ship.name}</div>
                  {ship.position ? (
                    <div className="text-muted-foreground text-[10px]">
                      {ship.position.latitude.toFixed(4)}°N, {ship.position.longitude.toFixed(4)}°E
                    </div>
                  ) : (
                    <div className="mt-1 text-[10px] text-amber-400/90">
                      Waiting for AIS transponder fix.
                    </div>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Destination */}
          <Card>
            <CardHeader
              title="2. Destination Port"
              description="Type and search any worldwide arrival port"
            />
            <CardBody className="space-y-4">
              <PortSearchInput
                label="Destination Port"
                placeholder="Search global port (e.g. Dubai, Singapore, Rotterdam, Shanghai, Goa)…"
                value={destCoord}
                onChange={(coord) => setDestCoord(coord)}
                accent="destination"
              />

              <div className="pt-2">
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full font-semibold shadow-md shadow-emerald-500/20 bg-emerald-600 hover:bg-emerald-500 text-white"
                  disabled={!canCalculate || isPlanning}
                  onClick={handleCalculateRoute}
                >
                  {isPlanning ? (
                    <span className="flex items-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Optimizing… ({Math.round(progressPercent)}%)
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Calculate Route from Live Location
                    </span>
                  )}
                </Button>
              </div>

              {planError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Route Calculation Failed
                  </div>
                  <p className="mt-1 text-[11px] text-destructive/80">{planError}</p>
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

      {/* Full-width Calculation Console below map */}
      {(isPlanning || route) && (
        <div ref={consoleRef} className="mt-6">
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
