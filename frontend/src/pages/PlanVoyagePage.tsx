/**
 * Flow B — plan a voyage before departure.
 *
 * `?manual=1` selects the IMO-less path, where vessel particulars are supplied
 * directly (ADDENDUM P0-3). Either way the route itself is always computed by
 * the backend, or substituted from a labelled fixture when it is unreachable.
 */

import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Navigation, Route as RouteIcon, SlidersHorizontal, Sparkles } from 'lucide-react'

import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge, DataBadge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { ImoInput } from '@/components/ship/ImoInput'
import {
  DEFAULT_PARTICULARS,
  ShipParticularsForm,
  particularsComplete,
} from '@/components/ship/ShipParticularsForm'
import { LocationPicker } from '@/components/route/LocationPicker'
import { RouteStatsPanel } from '@/components/route/RouteStatsPanel'
import { MapCanvas } from '@/map/MapCanvas'
import { SailingShip, WaveLoader } from '@/components/ui/ShipAnimation'
import { LottiePlayer } from '@/components/ui/LottiePlayer'

import { identifyShip, previewRoute, UserFacingApiError } from '@/services/resilientApi'
import type { Coordinate, RoutePreviewResponse, ShipParticulars, ShipResponse } from '@/types/api'
import type { DataSource } from '@/services/telemetry'
import { haversineNm, validateSelectionPoint } from '@/lib/geo'
import { toDatetimeLocalValue } from '@/lib/format'
import { cn } from '@/lib/utils'

type PickTarget = 'start' | 'destination' | null

export function PlanVoyagePage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const manualMode = searchParams.get('manual') === '1'

  const [imoText, setImoText] = useState('')
  const [validImo, setValidImo] = useState<string | null>(null)

  const [ship, setShip] = useState<ShipResponse | null>(null)
  const [shipSource, setShipSource] = useState<DataSource>('mock')
  const [identifying, setIdentifying] = useState(false)

  const [particulars, setParticulars] = useState<ShipParticulars>(DEFAULT_PARTICULARS)

  const [start, setStart] = useState<Coordinate | null>(null)
  const [destination, setDestination] = useState<Coordinate | null>(null)
  const [pickTarget, setPickTarget] = useState<PickTarget>(null)
  const [pickError, setPickError] = useState<string | null>(null)

  const [departure, setDeparture] = useState(() => toDatetimeLocalValue(new Date(Date.now() + 3600_000)))

  const [route, setRoute] = useState<RoutePreviewResponse | null>(null)
  const [routeSource, setRouteSource] = useState<DataSource>('mock')
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setManual = (manual: boolean) => {
    const next = new URLSearchParams(searchParams)
    if (manual) next.set('manual', '1')
    else next.delete('manual')
    setSearchParams(next, { replace: true })
  }

  const handleIdentify = useCallback(async () => {
    if (!validImo) return
    setIdentifying(true)
    setError(null)
    try {
      const result = await identifyShip(validImo)
      setShip(result.data)
      setShipSource(result.source)

      // Seed the particulars form from whatever the lookup resolved, keeping
      // sensible defaults for anything it could not.
      if (result.data.ship) {
        setParticulars((prev) => ({
          ship_type: result.data.ship?.ship_type ?? prev.ship_type,
          length_m: result.data.ship?.length_m ?? prev.length_m,
          beam_m: result.data.ship?.beam_m ?? prev.beam_m,
          draft_m: result.data.ship?.draft_m ?? prev.draft_m,
          cruising_speed_kn: result.data.ship?.cruising_speed_kn ?? prev.cruising_speed_kn,
          max_speed_kn: result.data.ship?.max_speed_kn ?? prev.max_speed_kn,
        }))
      }

      // A vessel underway is a sensible default origin.
      if (!start) setStart(result.data.position)
    } catch (err) {
      setError(err instanceof UserFacingApiError ? err.message : 'Could not identify that vessel.')
    } finally {
      setIdentifying(false)
    }
  }, [validImo, start])

  const handleMapClick = useCallback(
    (coordinate: Coordinate) => {
      if (!pickTarget) return

      const check = validateSelectionPoint(coordinate)
      if (!check.ok) {
        setPickError(check.message)
        return
      }

      setPickError(null)
      if (pickTarget === 'start') setStart(coordinate)
      else setDestination(coordinate)
      setPickTarget(null)
    },
    [pickTarget],
  )

  const canPlan = useMemo(() => {
    if (!start || !destination) return false
    if (haversineNm(start, destination) < 1) return false
    if (manualMode) return particularsComplete(particulars)
    return Boolean(validImo)
  }, [start, destination, manualMode, particulars, validImo])

  const handlePlan = useCallback(async () => {
    if (!start || !destination) return

    setPlanning(true)
    setError(null)
    setRoute(null)

    try {
      const result = await previewRoute({
        imo_number: manualMode ? null : validImo,
        start,
        destination,
        departure_time: new Date(departure).toISOString(),
        ...(manualMode || ship?.missing_fields?.length ? { ship: particulars } : {}),
      })
      setRoute(result.data)
      setRouteSource(result.source)
    } catch (err) {
      setError(
        err instanceof UserFacingApiError
          ? err.message
          : 'Route calculation failed. Check the console for details.',
      )
    } finally {
      setPlanning(false)
    }
  }, [start, destination, departure, manualMode, validImo, particulars, ship])

  // The backend snaps endpoints to grid nodes, so the drawn route can begin
  // short of the requested position. Surfacing that gap keeps the numbers honest.
  const approachDistanceNm = useMemo(() => {
    if (!route || route.route.length === 0 || !start || !destination) return 0
    return (
      haversineNm(start, route.route[0]!) +
      haversineNm(route.route[route.route.length - 1]!, destination)
    )
  }, [route, start, destination])

  const missingFields = ship?.missing_fields ?? []

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6">
      <header className="flex flex-wrap items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/15 text-accent">
          {manualMode ? <SlidersHorizontal className="h-5 w-5" /> : <RouteIcon className="h-5 w-5" />}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">
            {manualMode ? 'Route Without an IMO' : 'Plan a Voyage'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {manualMode
              ? 'Enter vessel particulars directly to optimise a route.'
              : 'Calculate an optimal route before the vessel departs.'}
          </p>
        </div>

        <div className="inline-flex rounded-lg border border-[var(--border)] p-0.5" role="group">
          {[
            { label: 'By IMO', manual: false },
            { label: 'Manual', manual: true },
          ].map((option) => (
            <button
              key={option.label}
              onClick={() => setManual(option.manual)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                manualMode === option.manual
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,380px)_1fr]">
        {/* ----------------------------- Controls ---------------------------- */}
        <div className="space-y-5">
          <Card>
            <CardHeader
              title={manualMode ? 'Vessel Particulars' : 'Vessel'}
              description={manualMode ? 'No IMO lookup performed.' : 'Resolved from the IMO number.'}
              action={manualMode ? <Badge variant="info">MANUAL</Badge> : ship ? <DataBadge source={shipSource} /> : undefined}
            />
            <CardBody className="space-y-4">
              {manualMode ? (
                <ShipParticularsForm value={particulars} onChange={setParticulars} />
              ) : (
                <>
                  <ImoInput value={imoText} onChange={setImoText} onValidChange={setValidImo} />
                  <Button
                    variant="secondary"
                    className="w-full"
                    disabled={!validImo}
                    loading={identifying}
                    onClick={handleIdentify}
                  >
                    Look up vessel
                  </Button>

                  <AnimatePresence>
                    {ship && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="rounded-lg bg-secondary/60 px-3 py-2.5">
                          <p className="text-sm font-medium">{ship.name}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {ship.ship?.ship_type ?? 'Type unknown'} · status {ship.status}
                            {ship.source ? ` · source: ${ship.source}` : ''}
                          </p>
                        </div>

                        {missingFields.length > 0 && (
                          <div className="mt-3">
                            <ShipParticularsForm
                              value={particulars}
                              onChange={setParticulars}
                              onlyFields={missingFields}
                            />
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Voyage" description="Select start, destination and departure." />
            <CardBody className="space-y-4">
              <LocationPicker
                label="Start"
                accent="start"
                value={start}
                onChange={setStart}
                picking={pickTarget === 'start'}
                onPickingChange={(p) => setPickTarget(p ? 'start' : null)}
              />
              <LocationPicker
                label="Destination"
                accent="destination"
                value={destination}
                onChange={setDestination}
                picking={pickTarget === 'destination'}
                onPickingChange={(p) => setPickTarget(p ? 'destination' : null)}
              />

              <Input
                label="Departure time"
                type="datetime-local"
                value={departure}
                onChange={(e) => setDeparture(e.target.value)}
                hint="Environmental forecasts are sampled at this time."
              />

              {pickError && (
                <p className="flex items-start gap-1.5 text-[11px] text-[var(--warning)]">
                  <AlertTriangle className="mt-px h-3 w-3 shrink-0" aria-hidden />
                  {pickError}
                </p>
              )}

              <Button size="lg" className="w-full" disabled={!canPlan} loading={planning} onClick={handlePlan}>
                <Sparkles className="h-4 w-4" aria-hidden />
                Preview Optimal Route
              </Button>

              {!canPlan && !planning && (
                <p className="text-center text-[11px] text-muted-foreground">
                  {!start || !destination
                    ? 'Set a start and destination to continue.'
                    : manualMode
                      ? 'Complete the vessel particulars to continue.'
                      : 'Enter a valid IMO number to continue.'}
                </p>
              )}

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5">
                  <AlertTriangle className="mt-px h-4 w-4 shrink-0 text-destructive" aria-hidden />
                  <p className="text-xs text-destructive">{error}</p>
                </div>
              )}
            </CardBody>
          </Card>

          <AnimatePresence>
            {route && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <RouteStatsPanel route={route} source={routeSource} approachDistanceNm={approachDistanceNm} />
                <Button
                  variant="accent"
                  className="mt-3 w-full"
                  onClick={() => navigate(`/track?imo=${route.imo_number}&autostart=1`)}
                >
                  <Navigation className="h-4 w-4" aria-hidden />
                  Start Tracking This Voyage
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ------------------------------- Chart ----------------------------- */}
        <div className="relative min-h-[520px] overflow-hidden rounded-xl border border-[var(--border)]">
          <MapCanvas
            className="h-full min-h-[520px] w-full"
            start={start}
            destination={destination}
            route={route?.route ?? []}
            onMapClick={handleMapClick}
          />

          {pickTarget && (
            <div className="pointer-events-none absolute left-1/2 top-4 z-[500] -translate-x-1/2 rounded-full border border-primary/40 bg-card/95 px-4 py-2 text-xs font-medium shadow-lg backdrop-blur">
              Click the chart to set the {pickTarget}
            </div>
          )}

          <AnimatePresence>
            {planning && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-[600] flex flex-col items-center justify-center gap-4 bg-background/80 backdrop-blur-sm"
              >
                <LottiePlayer name="loading-waves" className="h-24 w-24" fallback={<SailingShip size={96} />} />
                <div className="text-center">
                  <p className="text-sm font-medium">Computing optimal route…</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Sampling environmental forecasts and running D* Lite
                  </p>
                </div>
                <WaveLoader size={56} />
              </motion.div>
            )}
          </AnimatePresence>

          {!start && !destination && !planning && (
            <div className="pointer-events-none absolute inset-x-0 bottom-4 z-[500] flex justify-center">
              <p className="rounded-full border border-[var(--border)] bg-card/95 px-4 py-2 text-xs text-muted-foreground shadow-lg backdrop-blur">
                Pick a start and destination, or click “Pick on chart”
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
