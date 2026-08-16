/**
 * Explains why the optimiser chose this track.
 *
 * Everything shown is derived from `legs[]` returned by the backend — the same
 * numbers the cost model used. When a field is absent the row is omitted rather
 * than filled with a plausible-looking guess.
 */

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Waves, Wind, Navigation2, Gauge, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { CurrentRouteResponse, RouteLeg, RoutePreviewResponse } from '@/types/api'
import {
  describeLeg,
  legInfluence,
  summariseFactors,
  summariseRoute,
  type Influence,
  type RouteFactor,
} from '@/lib/explain'
import { compassPoint, formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'

const INFLUENCE_STYLE: Record<Influence, { chip: string; icon: typeof TrendingUp; label: string }> = {
  favourable: {
    chip: 'bg-[var(--success)]/12 text-[var(--success)] ring-[var(--success)]/25',
    icon: TrendingUp,
    label: 'Helping',
  },
  neutral: { chip: 'bg-secondary text-muted-foreground ring-[var(--border)]', icon: Minus, label: 'Neutral' },
  adverse: {
    chip: 'bg-[var(--warning)]/12 text-[var(--warning)] ring-[var(--warning)]/25',
    icon: TrendingDown,
    label: 'Hindering',
  },
}

const FACTOR_ICON = {
  current: Navigation2,
  wind: Wind,
  waves: Waves,
  speed: Gauge,
} as const

interface RouteExplanationProps {
  route: RoutePreviewResponse | CurrentRouteResponse
  className?: string
}

export function RouteExplanation({ route, className }: RouteExplanationProps) {
  const [showLegs, setShowLegs] = useState(false)
  const legs: RouteLeg[] = route.legs ?? []

  const factors = summariseFactors(legs)
  const summary = summariseRoute(route, legs)

  return (
    <div
      className={cn(
        'overflow-hidden rounded-2xl border border-[var(--border)] bg-card shadow-sm',
        className,
      )}
    >
      <div className="border-b border-[var(--border)] px-5 py-4">
        <h3 className="text-sm font-semibold tracking-tight">Why this route</h3>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{summary}</p>
      </div>

      {factors.length > 0 && (
        <div className="divide-y divide-[var(--border)]">
          {factors.map((factor: RouteFactor, i: number) => {
            const style = INFLUENCE_STYLE[factor.influence] ?? INFLUENCE_STYLE.neutral
            const Icon = FACTOR_ICON[factor.key] ?? Gauge
            const Trend = style.icon

            return (
              <motion.div
                key={factor.key}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="flex items-center gap-3 px-5 py-3"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-foreground/70">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="text-[13px] font-medium">{factor.label}</span>
                    <span className="font-mono text-sm font-semibold tabular-nums">{factor.value}</span>
                  </div>
                  <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{factor.detail}</p>
                </div>

                <span
                  className={cn(
                    'flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset',
                    style.chip,
                  )}
                >
                  <Trend className="h-3 w-3" aria-hidden />
                  {style.label}
                </span>
              </motion.div>
            )
          })}
        </div>
      )}

      {legs.length > 0 && (
        <>
          <button
            onClick={() => setShowLegs((v) => !v)}
            className="flex w-full items-center justify-between border-t border-[var(--border)] px-5 py-3 text-left transition-colors hover:bg-secondary/50"
            aria-expanded={showLegs}
          >
            <span className="text-xs font-medium">
              Segment breakdown
              <span className="ml-1.5 text-muted-foreground">({legs.length})</span>
            </span>
            <ChevronDown
              className={cn('h-4 w-4 text-muted-foreground transition-transform', showLegs && 'rotate-180')}
              aria-hidden
            />
          </button>

          <AnimatePresence initial={false}>
            {showLegs && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden border-t border-[var(--border)]"
              >
                <div className="max-h-80 overflow-auto scrollbar-thin">
                  <table className="w-full text-left text-[11px]">
                    <thead className="sticky top-0 bg-secondary/90 backdrop-blur">
                      <tr className="text-muted-foreground">
                        <th className="px-3 py-2 font-medium">#</th>
                        <th className="px-2 py-2 font-medium">Course</th>
                        <th className="px-2 py-2 text-right font-medium">Dist</th>
                        <th className="px-2 py-2 text-right font-medium">Time</th>
                        <th className="px-2 py-2 font-medium">Conditions</th>
                        <th className="px-3 py-2 text-right font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {legs.map((leg, i) => {
                        const influence = legInfluence(leg, legs)
                        return (
                          <tr key={i} className="hover:bg-secondary/40">
                            <td className="px-3 py-2 font-mono text-muted-foreground">{i + 1}</td>
                            <td className="px-2 py-2 whitespace-nowrap font-mono">
                              {Math.round(leg.bearing)}° {compassPoint(leg.bearing)}
                            </td>
                            <td className="px-2 py-2 text-right font-mono tabular-nums">
                              {leg.distance_nm.toFixed(1)}
                            </td>
                            <td className="px-2 py-2 text-right font-mono tabular-nums text-muted-foreground">
                              {formatDuration(leg.travel_time_hours)}
                            </td>
                            <td className="px-2 py-2 text-muted-foreground">{describeLeg(leg)}</td>
                            <td
                              className={cn(
                                'px-3 py-2 text-right font-mono font-medium tabular-nums',
                                influence === 'favourable' && 'text-[var(--success)]',
                                influence === 'adverse' && 'text-[var(--warning)]',
                              )}
                            >
                              {leg.cost.toFixed(2)}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}

      {legs.length === 0 && (
        <p className="px-5 py-4 text-[11px] text-muted-foreground">
          The backend did not return a segment breakdown for this route, so only the overall
          summary is available.
        </p>
      )}
    </div>
  )
}
