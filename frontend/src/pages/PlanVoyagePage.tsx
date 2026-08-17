/**
 * Flow 1 — Plan a Voyage before departure.
 *
 * Streamlined 3-step interface:
 *  1. Source Port / Harbour (Searchable autocomplete)
 *  2. Destination Port / Anchorage (Searchable autocomplete)
 *  3. Vessel Type Dropdown (Pre-configured standard fleet profiles by size & fuel rating)
 *
 * Renders the Green Optimal Route, Red Direct Baseline Route, Animated Wind/Current Vectors,
 * and the Calculation Console (full-width below map).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertTriangle,
  Calendar,
  ChevronDown,
  Radio,
  RefreshCw,
  Route as RouteIcon,
  Sparkles,
} from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PortSearchInput } from '@/components/route/PortSearchInput'
import { VesselTypeSelect } from '@/components/ship/VesselTypeSelect'
import { ObjectiveSelector } from '@/components/route/ObjectiveSelector'
import { CalculationConsole } from '@/components/route/CalculationConsole'
import { VoyageSimulatorConsole } from '@/components/route/VoyageSimulatorConsole'
import { MapCanvas, type SimulationHazard } from '@/map/MapCanvas'
import { useRoutePlan } from '@/hooks/useRoutePlan'
import { STANDARD_VESSEL_TYPES, vesselToParticulars, type StandardVesselType } from '@/lib/vessels'
import type { Coordinate, OptimizationObjective, RouteLeg } from '@/types/api'
import type { NamedLocation } from '@/lib/ports'
import { haversineNm } from '@/lib/geo'
import { toDatetimeLocalValue } from '@/lib/format'
import { cn } from '@/lib/utils'

export function PlanVoyagePage() {
  // 0. Optimization Objective (Defaults to Balanced)
  const [objective, setObjective] = useState<OptimizationObjective>('balanced')

  // 1. Origin & Destination Locations
  const [originCoord, setOriginCoord] = useState<Coordinate | null>(null)
  const [destCoord, setDestCoord] = useState<Coordinate | null>(null)

  // 2. Standard Vessel Selection
  const [selectedVessel, setSelectedVessel] = useState<StandardVesselType>(STANDARD_VESSEL_TYPES[0]!)

  // 3. Departure Date/Time
  const [departure, setDeparture] = useState(() => toDatetimeLocalValue(new Date(Date.now() + 3600_000)))

  // 4. Live Simulation & Dynamic Replanning State
  const [isSimulationActive, setIsSimulationActive] = useState<boolean>(false)
  const [simulatedShipPos, setSimulatedShipPos] = useState<Coordinate | null>(null)
  const [simulatedShipHeading, setSimulatedShipHeading] = useState<number>(180)
  const [simulatedRoute, setSimulatedRoute] = useState<Coordinate[] | null>(null)
  const [simulatedPreviousRoute, setSimulatedPreviousRoute] = useState<Coordinate[]>([])
  const [simulatedLegs, setSimulatedLegs] = useState<RouteLeg[] | null>(null)
  const [simulatedHazard, setSimulatedHazard] = useState<SimulationHazard | null>(null)

  // Toast / scroll state
  const [showScrollToast, setShowScrollToast] = useState(false)
  const mapRef = useRef<HTMLDivElement>(null)
  const consoleRef = useRef<HTMLDivElement>(null)

  // Asynchronous planning engine hook
  const { phase, stage, stageMessage, route, elapsedSeconds, progressPercent, error: planError, plan } = useRoutePlan()

  const handlePlan = useCallback(async () => {
    if (!originCoord || !destCoord) return
    const shipParticulars = vesselToParticulars(selectedVessel)
    await plan({
      imo_number: null,
      start: originCoord,
      destination: destCoord,
      departure_time: new Date(departure).toISOString(),
      ship: shipParticulars,
      optimization_objective: objective,
    })
  }, [originCoord, destCoord, selectedVessel, departure, objective, plan])

  const isPlanning = phase === 'submitting' || phase === 'planning'
  const canPlan = originCoord && destCoord && haversineNm(originCoord, destCoord) > 1

  // Show "scroll down" toast right when user clicks Calculate
  useEffect(() => {
    if (isPlanning) {
      setShowScrollToast(true)
      // Auto-scroll to map
      setTimeout(() => {
        mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 300)
      // Hide toast after 5s
      const t = setTimeout(() => setShowScrollToast(false), 5000)
      return () => clearTimeout(t)
    }
  }, [isPlanning])

  // Scroll to console when route is ready
  useEffect(() => {
    if (phase === 'ready' && route) {
      setTimeout(() => {
        consoleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 200)
    }
  }, [phase, route])

  return (
    <div className="mx-auto max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Header Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <RouteIcon className="h-4.5 w-4.5" aria-hidden />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">Plan a Voyage</h1>
          </div>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
            Select origin port, destination harbour, and vessel profile to calculate the optimal least-cost sea route.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
          Multi-Factor Weather Engine Ready
        </div>
      </div>

      {/* Scroll-down Toast Notification */}
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
              <div className="text-[11px] text-muted-foreground">Scroll down to see progress & final route</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Grid: Controls Left (4 cols) + Map Right (8 cols) */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Form Column (4 cols) */}
        <div className="space-y-5 lg:col-span-4 xl:col-span-4">
          <Card>
            <CardHeader
              title="Voyage Parameters"
              description="Enter departure port, destination, and vessel profile"
            />
            <CardBody className="space-y-4">
              {/* Step 0: Objective Selector */}
              <ObjectiveSelector
                value={objective}
                onChange={setObjective}
                disabled={isPlanning}
              />

              <div className="border-t border-[var(--border)] pt-1" />

              {/* Step 1: Origin Port */}
              <PortSearchInput
                label="1. Origin Port"
                placeholder="Search departure port (e.g. Mumbai, Rotterdam, Shanghai)…"
                value={originCoord}
                onChange={(coord) => setOriginCoord(coord)}
                accent="origin"
              />

              {/* Step 2: Destination Port */}
              <PortSearchInput
                label="2. Destination Port"
                placeholder="Search arrival port (e.g. Goa, Dubai, Singapore, Salalah)…"
                value={destCoord}
                onChange={(coord) => setDestCoord(coord)}
                accent="destination"
              />

              {/* Step 3: Vessel Profile Selection */}
              <VesselTypeSelect
                value={selectedVessel}
                onChange={setSelectedVessel}
              />

              {/* Departure Timing */}
              <div>
                <label className="block text-xs font-semibold text-foreground/80 mb-1.5">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                    Planned Departure (UTC)
                  </span>
                </label>
                <input
                  type="datetime-local"
                  value={departure}
                  onChange={(e) => setDeparture(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-background px-3 py-1.5 font-mono text-xs text-foreground focus:outline-primary"
                />
              </div>

              {/* Calculate Button */}
              <div className="pt-2">
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full font-semibold shadow-md shadow-emerald-500/20 bg-emerald-600 hover:bg-emerald-500 text-white"
                  disabled={!canPlan || isPlanning}
                  onClick={handlePlan}
                >
                  {isPlanning ? (
                    <span className="flex items-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Optimizing… ({Math.round(progressPercent)}%)
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Calculate Optimal Route
                    </span>
                  )}
                </Button>
              </div>

              {/* Real-Time D* Lite Replanning Simulator Button */}
              <div className="pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  className={cn(
                    'w-full font-semibold border-cyan-500/50 text-cyan-300 hover:bg-cyan-500/20 shadow-md transition-all',
                    isSimulationActive ? 'bg-cyan-500/20 ring-2 ring-cyan-400' : 'bg-slate-900/60'
                  )}
                  onClick={async () => {
                    if (isSimulationActive) {
                      setIsSimulationActive(false)
                      return
                    }

                    const orig = originCoord || { latitude: 18.95, longitude: 72.82 }
                    const dest = destCoord || { latitude: 25.26, longitude: 55.28 }
                    if (!originCoord) setOriginCoord(orig)
                    if (!destCoord) setDestCoord(dest)

                    if (!route?.route || route.route.length === 0) {
                      const shipParticulars = vesselToParticulars(selectedVessel)
                      await plan({
                        imo_number: null,
                        start: orig,
                        destination: dest,
                        departure_time: new Date(departure).toISOString(),
                        ship: shipParticulars,
                        optimization_objective: objective,
                      })
                    }
                    setIsSimulationActive(true)
                  }}
                >
                  <span className="flex items-center justify-center gap-2">
                    <Radio className="h-4 w-4 text-cyan-400 animate-pulse" />
                    {isSimulationActive ? 'Hide Live Simulation' : 'Simulate Real-Time D* Lite Replanning'}
                  </span>
                </Button>
              </div>

              {planError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Route Calculation Failed
                  </div>
                  <p className="mt-1 text-[11px] text-destructive/90">{planError}</p>
                  <Button variant="outline" size="sm" onClick={handlePlan} className="mt-2 text-xs">
                    Retry Calculation
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right Dominant Map (8 cols) */}
        <div ref={mapRef} className="lg:col-span-8 xl:col-span-8">
          <div className="relative h-[560px] w-full lg:h-[640px]">
            <MapCanvas
              start={originCoord}
              destination={destCoord}
              route={simulatedRoute ?? (route?.route ?? [])}
              previousRoute={simulatedPreviousRoute}
              legs={simulatedLegs ?? (route?.legs ?? [])}
              shipPosition={simulatedShipPos ?? (originCoord || (route?.route?.[0] ?? null))}
              shipHeading={simulatedShipHeading}
              positionSource={isSimulationActive ? 'simulated' : 'static'}
              shipName={selectedVessel.name}
              showVectors={true}
              showLegend={true}
              showPorts={true}
              simulationHazard={simulatedHazard}
              onSelectPort={(port: NamedLocation, asType: 'origin' | 'destination') => {
                if (asType === 'origin') {
                  setOriginCoord(port.coordinate)
                } else {
                  setDestCoord(port.coordinate)
                }
              }}
            />

            {/* D* Lite Dynamic Simulation Floating Console Overlay */}
            {isSimulationActive && (
              <VoyageSimulatorConsole
                originalRoute={route?.route && route.route.length > 0 ? route.route : [originCoord || { latitude: 18.95, longitude: 72.82 }, destCoord || { latitude: 25.26, longitude: 55.28 }]}
                activeLegs={route?.legs ?? []}
                onShipMove={(pos, heading) => {
                  setSimulatedShipPos(pos)
                  setSimulatedShipHeading(heading)
                }}
                onRouteUpdate={(newR, prevR, newLegs) => {
                  setSimulatedRoute(newR)
                  setSimulatedPreviousRoute(prevR)
                  setSimulatedLegs(newLegs)
                }}
                onHazardUpdate={(hazard) => {
                  setSimulatedHazard(hazard)
                }}
                onClose={() => setIsSimulationActive(false)}
              />
            )}
          </div>
        </div>
      </div>

      {/* ── FULL-WIDTH SECTION BELOW MAP: Calculation Console (shown when planning or done) ── */}
      {(isPlanning || route) && (
        <div ref={consoleRef} className="mt-6">
          <CalculationConsole
            route={route}
            shipParticulars={vesselToParticulars(selectedVessel)}
            shipName={selectedVessel.name}
            isPlanning={isPlanning}
            planningPhase={phase}
            stage={stage}
            stageMessage={stageMessage}
            elapsedSeconds={elapsedSeconds}
          />
        </div>
      )}
    </div>
  )
}
