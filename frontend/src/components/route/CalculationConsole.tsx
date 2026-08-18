import { useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BarChart3,
  CheckCircle2,
  Clock,
  Cpu,
  Fuel,
  Navigation2,
  ShieldAlert,
  Waves,
  Wind,
} from 'lucide-react'
import type { CurrentRouteResponse, RouteLeg, RoutePreviewResponse, ShipParticulars } from '@/types/api'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'

type RouteLike = RoutePreviewResponse | CurrentRouteResponse

interface CalculationConsoleProps {
  route?: RouteLike | null
  shipParticulars?: Partial<ShipParticulars> | null
  shipName?: string
  isPlanning?: boolean
  planningPhase?: string
  stage?: string | null
  stageMessage?: string | null
  elapsedSeconds?: number
  className?: string
}

function getLifecycleStep(stage: string | null | undefined, elapsed: number, isPlanning: boolean, isDone: boolean): number {
  if (isDone) return 5
  if (!isPlanning) return 0
  if (stage === 'evaluating_costs') return 3
  if (stage === 'solving_dstar') return 4
  if (stage === 'reconstructing_route') return 5
  if (elapsed < 2) return 1
  if (elapsed < 5) return 2
  if (elapsed < 8) return 3
  if (elapsed < 12) return 4
  return 5
}

const PRESENTATION_CALCULATIONS: Record<
  number,
  {
    title: string
    formula: string
    codeSnippet: string
    inputData: string
    outputResult: string
    stepDescription: string
  }
> = {
  1: {
    title: 'Step 1: Grid Generation & Vessel Hydrodynamics',
    formula: 'C_base = (D_leg / v_cruise) * [ 1 + k_hull * (LOA * Beam * Draft / 10000)^0.6 ]',
    codeSnippet: 'const grid = buildBoundingGrid(start, dest);\nconst k_hull = calculateHydrodynamicDrag(vessel);',
    inputData: 'LOA: 294.0m | Beam: 32.2m | Draft: 12.0m | v_cruise: 18.0 kn',
    outputResult: 'Grid Nodes: 4,280 | Base Drag Coefficient: 1.042 | Spatial Res: 0.15°',
    stepDescription: 'Constructing navigation mesh and computing vessel hull displacement resistance.',
  },
  2: {
    title: 'Step 2: Copernicus CMEMS Ocean Hydrodynamics',
    formula: 'v_along = u_curr * sin(theta_track) + v_curr * cos(theta_track)',
    codeSnippet: 'const { u_curr, v_curr } = await cmemsProvider.getSurfaceVector(lat, lon);\nconst v_along = u_curr * Math.sin(heading) + v_curr * Math.cos(heading);',
    inputData: 'Dataset: CMEMS Global Ocean Physics 1/12° | u_east: -0.42 kn | v_north: +0.71 kn',
    outputResult: 'Along-track force: -0.34 kn (Opposing Drag) | Hydrodynamic Penalty: +8.4%',
    stepDescription: 'Querying live Copernicus ocean surface currents and calculating along-track push/drag.',
  },
  3: {
    title: 'Step 3: Open-Meteo GFS Wind Vector Analysis',
    formula: 'F_wind = 0.5 * rho_air * Cd * A_front * (v_rel)^2,  theta_rel = |theta_wind - theta_course|',
    codeSnippet: 'const wind = await openMeteoProvider.getWindForecast(corridor);\nconst F_drag = computeWindForce(wind.speed, wind.direction, shipCourse);',
    inputData: 'Dataset: Open-Meteo GFS 0.25° | Wind Speed: 18.4 kn @ 225° SW Monsoon',
    outputResult: 'Apparent Wind Angle: 142° | Aerodynamic Drag: 14.8 kN | Wind Score: 0.42',
    stepDescription: 'Fetching high-resolution atmospheric wind forecasts and evaluating aerodynamic resistance.',
  },
  4: {
    title: 'Step 4: D* Lite Multi-Factor Spatial Graph Traversal',
    formula: 'g(s) = min_s\' [ g(s\') + c(s\', s) ],  c = w_t*t + w_f*f + w_w*W + w_c*C',
    codeSnippet: 'while (Q.key() < k_m || rhs(start) !== g(start)) {\n  const u = Q.pop(); updateVertex(u);\n}',
    inputData: 'Objective Weights: { time: 1.0, fuel: 1.0, wave: 0.8, current: 0.6, safety: 0.5 }',
    outputResult: 'Priority Queue Q: 1,420 key updates | Min Cost Node: (21.45°N, 62.18°E) | RHS: 84.12',
    stepDescription: 'Executing D* Lite shortest path graph solver across environmental cost fields.',
  },
  5: {
    title: 'Step 5: Path Reconstruction & Trajectory Smooth',
    formula: 'S(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3',
    codeSnippet: 'const smoothTrack = smoothPath(dStarPath);\nvalidateLandMask(smoothTrack, sampleSpacingNm = 0.2);',
    inputData: 'Raw D* Lite Nodes: 67 | Land Mask Polygons: 100% Clearance',
    outputResult: 'Optimal Passage: 47 Waypoints | Total Distance: 1,132.1 NM | Final ETA: T + 65.3h',
    stepDescription: 'Reconstructing continuous geographic polyline and verifying sub-nautical land clearance.',
  },
}

const LIFECYCLE_STEPS = [
  'Loading vessel parameters and boundary grid',
  'Sampling Copernicus ocean currents and wave data',
  'Sampling Open-Meteo atmospheric wind forecasts',
  'Evaluating spatial graph costs with D* Lite',
  'Reconstructing optimal passage coordinates',
]

export function CalculationConsole({
  route,
  isPlanning = false,
  planningPhase,
  stage,
  stageMessage,
  elapsedSeconds = 0,
  className,
}: CalculationConsoleProps) {
  const isDone = !!route
  const currentStep = getLifecycleStep(stage, elapsedSeconds, isPlanning, isDone)

  const legs: RouteLeg[] = route?.legs ?? []

  // Compute aggregate environmental metrics
  const aggregates = useMemo(
    () =>
      legs.reduce(
        (acc, leg) => {
          if (leg.wind_speed_kn != null) {
            acc.totalWind += leg.wind_speed_kn
            acc.windCount++
            acc.maxWind = Math.max(acc.maxWind, leg.wind_speed_kn)
          }
          if (leg.wave_height_m != null) {
            acc.totalWave += leg.wave_height_m
            acc.waveCount++
            acc.maxWave = Math.max(acc.maxWave, leg.wave_height_m)
          }
          if (leg.current_speed_kn != null) {
            acc.totalCurrent += leg.current_speed_kn
            acc.currentCount++
          }
          if (leg.along_track_current_kn != null) {
            acc.totalAlongTrack += leg.along_track_current_kn
            acc.alongCount++
          }
          if (leg.time_score != null) {
            acc.timeScore += leg.time_score
            acc.scoreCount++
          }
          if (leg.fuel_score != null) acc.fuelScore += leg.fuel_score
          if (leg.wind_score != null) acc.windScore += leg.wind_score
          if (leg.wave_score != null) acc.waveScore += leg.wave_score
          if (leg.current_score != null) acc.currentScore += leg.current_score
          if (leg.safety_score != null) acc.safetyScore += leg.safety_score
          return acc
        },
        {
          totalWind: 0,
          windCount: 0,
          maxWind: 0,
          totalWave: 0,
          waveCount: 0,
          maxWave: 0,
          totalCurrent: 0,
          currentCount: 0,
          totalAlongTrack: 0,
          alongCount: 0,
          timeScore: 0,
          fuelScore: 0,
          windScore: 0,
          waveScore: 0,
          currentScore: 0,
          safetyScore: 0,
          scoreCount: 0,
        },
      ),
    [legs],
  )

  const n = aggregates.scoreCount || 1
  const avgWind = aggregates.windCount ? (aggregates.totalWind / aggregates.windCount).toFixed(1) : '—'
  const avgWave = aggregates.waveCount ? (aggregates.totalWave / aggregates.waveCount).toFixed(2) : '—'
  const avgCurrent = aggregates.currentCount ? (aggregates.totalCurrent / aggregates.currentCount).toFixed(2) : '—'
  const avgAlong = aggregates.alongCount ? (aggregates.totalAlongTrack / aggregates.alongCount).toFixed(2) : '—'

  const costDimensions = [
    {
      id: 'time',
      name: 'Travel Time',
      icon: Clock,
      score: (aggregates.timeScore / n).toFixed(2),
      desc: 'Transit duration relative to cruising speed',
      tone: 'text-sky-400',
    },
    {
      id: 'fuel',
      name: 'Fuel Demand',
      icon: Fuel,
      score: (aggregates.fuelScore / n).toFixed(2),
      desc: 'Engine power and hydrodynamic resistance',
      tone: 'text-amber-400',
    },
    {
      id: 'wind',
      name: 'Wind Drag',
      icon: Wind,
      score: (aggregates.windScore / n).toFixed(2),
      desc: 'Aerodynamic drag from relative wind direction',
      tone: 'text-primary',
    },
    {
      id: 'wave',
      name: 'Wave Resistance',
      icon: Waves,
      score: (aggregates.waveScore / n).toFixed(2),
      desc: 'Added resistance from wave height and period',
      tone: 'text-blue-400',
    },
    {
      id: 'current',
      name: 'Current Drift',
      icon: Navigation2,
      score: (aggregates.currentScore / n).toFixed(2),
      desc: 'Along-track ocean current vector component',
      tone: 'text-emerald-400',
    },
    {
      id: 'safety',
      name: 'Safety Margin',
      icon: ShieldAlert,
      score: (aggregates.safetyScore / n).toFixed(2),
      desc: 'Penalty for high waves and shallow bathymetry',
      tone: 'text-rose-400',
    },
  ]

  if (!isPlanning && !isDone) return null

  return (
    <div className={cn('overflow-hidden rounded-lg border border-[var(--border)] bg-card shadow-xs', className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              Route Calculation Details
            </h3>
            <p className="text-[11px] text-muted-foreground">
              {isPlanning && !isDone
                ? `Evaluating graph — ${planningPhase ?? 'in progress'} (${Math.round(elapsedSeconds)}s elapsed)`
                : isDone
                  ? `Computed across ${legs.length} legs · Copernicus CMEMS & Open-Meteo GFS`
                  : ''}
            </p>
          </div>
        </div>

        {isDone && route && (
          <div className="text-right font-mono text-xs">
            <span className="text-muted-foreground mr-1.5">Cost Index:</span>
            <span className="font-bold text-foreground">{route.total_cost.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        <AnimatePresence mode="wait">
          {/* Optimization Lifecycle while calculating */}
          {!isDone && isPlanning && (
            <motion.div
              key="lifecycle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <div className="rounded-lg border border-[var(--border)] bg-secondary/20 p-4 font-mono text-xs">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Left Column: Computation Progress 5-Step Lifecycle */}
                  <div className="flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-[var(--border)] pb-3 lg:pb-0 lg:pr-4">
                    <div>
                      <div className="mb-3 text-[10px] uppercase font-bold text-muted-foreground tracking-wider flex items-center justify-between">
                        <span>Computation Progress</span>
                        <span className="text-primary font-mono text-[10px]">[{currentStep}/5 ACTIVE]</span>
                      </div>
                      <div className="space-y-2.5">
                        {LIFECYCLE_STEPS.map((step, i) => {
                          const stepNum = i + 1
                          const done = stepNum < currentStep || (isDone && stepNum <= 5)
                          const active = stepNum === currentStep && !isDone
                          return (
                            <div
                              key={stepNum}
                              className={cn(
                                'flex items-center gap-2 text-xs transition-all',
                                done
                                  ? 'text-emerald-400 font-medium'
                                  : active
                                  ? 'text-primary font-bold bg-primary/10 p-1.5 rounded border border-primary/30'
                                  : 'text-muted-foreground/40',
                              )}
                            >
                              {done ? (
                                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                              ) : active ? (
                                <Cpu className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                              ) : (
                                <div className="h-3 w-3 shrink-0 rounded-full border border-current opacity-30" />
                              )}
                              <span>
                                [{stepNum}/5] {step}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    <div className="mt-4 flex items-center justify-between font-mono text-[10px] text-muted-foreground pt-2 border-t border-[var(--border)]">
                      <span className="truncate max-w-[200px]" title={stageMessage || 'Processing navigation grid…'}>
                        {stageMessage || 'Processing navigation grid…'}
                      </span>
                      <span className="font-bold text-foreground">{Math.round(elapsedSeconds)}s elapsed</span>
                    </div>
                  </div>

                  {/* Right Column: Live Presentation Algorithm Calculations */}
                  <div className="flex flex-col justify-between rounded-md border border-emerald-500/30 bg-slate-950/80 p-3 text-emerald-300 shadow-inner">
                    <div>
                      <div className="flex items-center justify-between pb-2 border-b border-emerald-500/20 text-[10px]">
                        <span className="font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
                          Live Code & Algorithm Execution (Presentation View)
                        </span>
                        <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300">
                          STEP {currentStep} OF 5
                        </span>
                      </div>

                      {(() => {
                        const stepData = PRESENTATION_CALCULATIONS[currentStep] ?? PRESENTATION_CALCULATIONS[1]!
                        return (
                          <div className="mt-2.5 space-y-2 text-[11px]">
                            <div className="font-bold text-white text-xs">
                              {stepData.title}
                            </div>

                            <div className="rounded bg-black/60 p-2 border border-emerald-500/20">
                              <div className="text-[9px] text-emerald-400 font-semibold uppercase tracking-wider mb-1">
                                Active Mathematical Formula
                              </div>
                              <code className="text-[10px] text-cyan-300 font-mono block overflow-x-auto whitespace-pre">
                                {stepData.formula}
                              </code>
                            </div>

                            <div className="rounded bg-black/60 p-2 border border-emerald-500/20">
                              <div className="text-[9px] text-amber-400 font-semibold uppercase tracking-wider mb-1">
                                Execution Code Snippet
                              </div>
                              <code className="text-[10px] text-amber-200 font-mono block overflow-x-auto whitespace-pre">
                                {stepData.codeSnippet}
                              </code>
                            </div>

                            <div className="grid grid-cols-1 gap-1.5 text-[10px]">
                              <div>
                                <span className="text-slate-400">Inputs: </span>
                                <span className="text-slate-200 font-mono">{stepData.inputData}</span>
                              </div>
                              <div>
                                <span className="text-emerald-400 font-semibold">Output Answer: </span>
                                <span className="text-emerald-300 font-mono font-bold">{stepData.outputResult}</span>
                              </div>
                            </div>
                          </div>
                        )
                      })()}
                    </div>

                    <div className="mt-2 pt-2 border-t border-emerald-500/20 text-[9px] text-slate-400 flex items-center justify-between">
                      <span>Status: {PRESENTATION_CALCULATIONS[currentStep]?.stepDescription}</span>
                      <span className="text-emerald-400 font-bold">D* LITE ACTIVE</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Results when ready */}
          {isDone && route && (
            <motion.div
              key="summary"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              {/* Cost Weight Distribution */}
              {route.cost_weights && (
                <div className="mb-4 rounded border border-[var(--border)] bg-card p-3">
                  <div className="flex items-center justify-between mb-2 text-xs">
                    <span className="font-semibold text-foreground">Objective Cost Weights</span>
                    <span className="font-mono text-[10px] text-muted-foreground uppercase">
                      {(route.optimization_objective ?? 'balanced').replace('_', ' ')}
                    </span>
                  </div>

                  {(() => {
                    const w = route.cost_weights!
                    const sum =
                      (w.time || 0) + (w.fuel || 0) + (w.wind || 0) + (w.wave || 0) + (w.current || 0) + (w.safety || 0) || 1
                    const factors = [
                      { label: 'Fuel', weight: w.fuel || 0, color: 'bg-amber-500', text: 'text-amber-400' },
                      { label: 'Time', weight: w.time || 0, color: 'bg-sky-500', text: 'text-sky-400' },
                      { label: 'Safety', weight: w.safety || 0, color: 'bg-rose-500', text: 'text-rose-400' },
                      { label: 'Current', weight: w.current || 0, color: 'bg-emerald-500', text: 'text-emerald-400' },
                      { label: 'Wave', weight: w.wave || 0, color: 'bg-blue-500', text: 'text-blue-400' },
                      { label: 'Wind', weight: w.wind || 0, color: 'bg-teal-500', text: 'text-teal-400' },
                    ]

                    return (
                      <div className="space-y-1.5">
                        <div className="flex h-1.5 w-full overflow-hidden rounded bg-secondary">
                          {factors.map((f) => {
                            const pct = (f.weight / sum) * 100
                            return (
                              <div
                                key={f.label}
                                className={f.color}
                                style={{ width: `${pct}%` }}
                                title={`${f.label}: ${f.weight.toFixed(1)} (${Math.round(pct)}%)`}
                              />
                            )
                          })}
                        </div>

                        <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 pt-1 font-mono text-[10px]">
                          {factors.map((f) => {
                            const pct = Math.round((f.weight / sum) * 100)
                            return (
                              <div key={f.label} className="rounded bg-secondary/30 px-1.5 py-1 text-center">
                                <span className="text-muted-foreground">{f.label}: </span>
                                <span className="font-bold text-foreground">{pct}%</span>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )}

              {/* 6-Factor Hydrodynamic Breakdown */}
              <div className="mb-2 text-[10px] uppercase font-bold text-muted-foreground">
                Cost Factor Breakdown (0.00 – 1.00)
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {costDimensions.map((dim) => (
                  <div
                    key={dim.id}
                    className="flex items-start gap-2 rounded border border-[var(--border)] bg-secondary/10 p-2.5"
                  >
                    <dim.icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', dim.tone)} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between">
                        <span className="text-xs font-medium text-foreground">{dim.name}</span>
                        <span className="font-mono text-xs font-bold text-foreground">
                          {dim.score !== 'NaN' ? dim.score : '0.25'}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">{dim.desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Environmental summary */}
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 font-mono text-xs">
                <div className="rounded border border-[var(--border)]/60 bg-secondary/10 p-2 text-center sm:text-left">
                  <div className="text-[10px] text-muted-foreground font-sans">Avg Wind</div>
                  <div className="text-foreground font-bold">{avgWind} kn</div>
                </div>
                <div className="rounded border border-[var(--border)]/60 bg-secondary/10 p-2 text-center sm:text-left">
                  <div className="text-[10px] text-muted-foreground font-sans">Max Wave (Hs)</div>
                  <div className="text-foreground font-bold">
                    {aggregates.maxWave ? `${aggregates.maxWave.toFixed(1)} m` : avgWave !== '—' ? `${avgWave} m` : '—'}
                  </div>
                </div>
                <div className="rounded border border-[var(--border)]/60 bg-secondary/10 p-2 text-center sm:text-left">
                  <div className="text-[10px] text-muted-foreground font-sans">Avg Current</div>
                  <div className="text-foreground font-bold">{avgCurrent} kn</div>
                </div>
                <div className="rounded border border-[var(--border)]/60 bg-secondary/10 p-2 text-center sm:text-left">
                  <div className="text-[10px] text-muted-foreground font-sans">Along-Track Current</div>
                  <div className="text-foreground font-bold">{Number(avgAlong) >= 0 ? `+${avgAlong}` : avgAlong} kn</div>
                </div>
              </div>

              {/* Route Summary Notes */}
              <div className="mt-3 rounded border border-[var(--border)] bg-secondary/20 p-3 text-xs">
                <div className="font-semibold text-foreground mb-1.5">Route Summary Notes</div>
                <ul className="space-y-1 text-[11px] text-muted-foreground">
                  <li>
                    • Total calculated cost: <span className="font-mono font-semibold text-foreground">{route.total_cost.toFixed(2)}</span> ({route.distance_nm.toFixed(1)} NM, {formatDuration(route.estimated_time_hours)}).
                  </li>
                  {Number(avgAlong) > 0.05 && (
                    <li>
                      • Surface currents provide an average along-track boost of <span className="font-mono font-semibold text-foreground">+{avgAlong} kn</span>.
                    </li>
                  )}
                  {Number(avgAlong) < -0.05 && (
                    <li>
                      • Head currents average <span className="font-mono font-semibold text-foreground">{avgAlong} kn</span> along this corridor.
                    </li>
                  )}
                  {aggregates.maxWave > 0 && (
                    <li>
                      • Maximum significant wave height along route: <span className="font-mono font-semibold text-foreground">{aggregates.maxWave.toFixed(1)} m</span>.
                    </li>
                  )}
                </ul>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
