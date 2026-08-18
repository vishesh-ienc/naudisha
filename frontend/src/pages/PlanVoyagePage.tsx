import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  ChevronDown,
  RefreshCw,
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
import { cn } from '@/lib/utils'

export function PlanVoyagePage() {
  // 0. Optimization Objective (Defaults to Balanced)
  const [objective, setObjective] = useState<OptimizationObjective>('balanced')

  // 1. Origin & Destination Locations
  const [originCoord, setOriginCoord] = useState<Coordinate | null>(null)
  const [destCoord, setDestCoord] = useState<Coordinate | null>(null)

  // 2. Standard Vessel Selection
  const [selectedVessel, setSelectedVessel] = useState<StandardVesselType>(STANDARD_VESSEL_TYPES[0]!)

  // 3. Live Simulation & Dynamic Replanning State
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
      departure_time: new Date().toISOString(),
      ship: shipParticulars,
      optimization_objective: objective,
    })
  }, [originCoord, destCoord, selectedVessel, objective, plan])

  const isPlanning = phase === 'submitting' || phase === 'planning'
  const canPlan = originCoord && destCoord && haversineNm(originCoord, destCoord) > 1

  // Show "scroll down" toast right when user clicks Calculate
  useEffect(() => {
    if (isPlanning) {
      setShowScrollToast(true)
      setTimeout(() => {
        mapRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 300)
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
    <div className="mx-auto max-w-[1700px] px-4 py-5 sm:px-6 lg:px-8">
      {/* Header Bar */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">Voyage Planning</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Configure departure, destination, vessel particulars, and departure schedule to calculate route.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
          Copernicus CMEMS &amp; Open-Meteo Active
        </div>
      </div>

      {/* Scroll-down Toast Notification */}
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

      {/* Main Grid: Controls Left (4 cols) + Map Right (8 cols) */}
      <div className="grid gap-5 lg:grid-cols-12">
        {/* Left Form Column (4 cols) */}
        <div className="space-y-4 lg:col-span-4 xl:col-span-4">
          <Card>
            <CardHeader
              title="Voyage Parameters"
              description="Enter passage requirements and vessel type"
            />
            <CardBody className="space-y-3.5">
              {/* Objective Selector */}
              <ObjectiveSelector
                value={objective}
                onChange={setObjective}
                disabled={isPlanning}
              />

              <div className="border-t border-[var(--border)] pt-1" />

              {/* Origin Port */}
              <PortSearchInput
                label="Origin Port"
                placeholder="Search departure port (e.g. Mumbai, Rotterdam, Shanghai)…"
                value={originCoord}
                onChange={(coord) => setOriginCoord(coord)}
                accent="origin"
              />

              {/* Destination Port */}
              <PortSearchInput
                label="Destination Port"
                placeholder="Search arrival port (e.g. Goa, Dubai, Singapore, Salalah)…"
                value={destCoord}
                onChange={(coord) => setDestCoord(coord)}
                accent="destination"
              />

              {/* Vessel Profile Selection */}
              <VesselTypeSelect
                value={selectedVessel}
                onChange={setSelectedVessel}
              />

              {/* Calculate Button */}
              <div className="pt-1">
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full font-semibold shadow-xs"
                  disabled={!canPlan || isPlanning}
                  onClick={handlePlan}
                >
                  {isPlanning ? (
                    <span className="flex items-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Calculating… ({Math.round(progressPercent)}%)
                    </span>
                  ) : (
                    'Calculate Route'
                  )}
                </Button>
              </div>

              {/* Simulation Button */}
              <div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className={cn(
                    'w-full font-medium',
                    isSimulationActive ? 'bg-primary/10 border-primary text-primary' : ''
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
                        departure_time: new Date().toISOString(),
                        ship: shipParticulars,
                        optimization_objective: objective,
                      })
                    }
                    setIsSimulationActive(true)
                  }}
                >
                  {isSimulationActive ? 'Close Simulation Console' : 'Simulate Dynamic Re-planning'}
                </Button>
              </div>

              {planError && (
                <div className="rounded border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Route Calculation Error
                  </div>
                  <p className="mt-1 text-[11px] text-destructive/90">{planError}</p>
                  <Button variant="outline" size="sm" onClick={handlePlan} className="mt-2 text-xs">
                    Retry
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right Map (8 cols) */}
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

            {/* Simulation Floating Console Overlay */}
            {isSimulationActive && (
              <VoyageSimulatorConsole
                originalRoute={
                  route?.route && route.route.length > 0
                    ? route.route
                    : [originCoord || { latitude: 18.95, longitude: 72.82 }, destCoord || { latitude: 25.26, longitude: 55.28 }]
                }
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

      {/* Calculation Console below map */}
      {(isPlanning || route) && (
        <div ref={consoleRef} className="mt-5">
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
