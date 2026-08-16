/**
 * Route statistics.
 *
 * `total_cost` is deliberately not presented as a bare number. It is a
 * dimensionless weighted sum of six normalised scores, so "16.31" means nothing
 * on its own. When the backend supplies `baseline_cost` (ADDENDUM P2-2) the
 * comparison against the direct route is shown instead, which explains itself.
 * The raw index stays available as secondary detail.
 */

import { motion } from 'framer-motion'
import { Clock, Gauge, Route as RouteIcon, TrendingDown, Flag, Anchor } from 'lucide-react'
import type { DataSource } from '@/services/telemetry'
import type { RoutePreviewResponse, CurrentRouteResponse } from '@/types/api'
import { DataBadge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { formatDistance, formatDuration, formatTimestamp } from '@/lib/format'
import { cn } from '@/lib/utils'

type RouteLike = RoutePreviewResponse | CurrentRouteResponse

interface RouteStatsPanelProps {
  route: RouteLike
  source: DataSource
  approachDistanceNm?: number
  className?: string
}

export function RouteStatsPanel({ route, source, approachDistanceNm = 0, className }: RouteStatsPanelProps) {
  const eta = 'eta' in route ? route.eta : undefined
  const departure = 'departure_time' in route ? route.departure_time : undefined
  const baseline = route.baseline_cost

  const efficiency =
    'efficiency_gain_percent' in route && route.efficiency_gain_percent != null
      ? route.efficiency_gain_percent
      : baseline != null && baseline > 0
        ? ((baseline - route.total_cost) / baseline) * 100
        : null

  const stats = [
    {
      icon: RouteIcon,
      label: 'Distance',
      value: formatDistance(route.distance_nm),
      detail:
        approachDistanceNm > 0.1
          ? `+${formatDistance(approachDistanceNm)} approach legs`
          : `${route.route.length} waypoints`,
    },
    {
      icon: Clock,
      label: 'Passage time',
      value: formatDuration(route.estimated_time_hours),
      detail: eta ? `ETA ${formatTimestamp(eta)}` : departure ? `From ${formatTimestamp(departure)}` : undefined,
    },
    {
      icon: Gauge,
      label: 'Route cost index',
      value: route.total_cost.toFixed(2),
      detail: baseline != null ? `Direct route: ${baseline.toFixed(2)}` : 'Weighted multi-factor score',
    },
  ]

  return (
    <Card className={className}>
      <CardHeader
        title="Route Summary"
        description={source === 'live' ? 'Computed by the NauDisha engine' : 'Placeholder values — backend unavailable'}
        action={<DataBadge source={source} />}
      />
      <CardBody className="space-y-4">
        {efficiency != null && Number.isFinite(efficiency) && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
              'flex items-center gap-3 rounded-lg border px-3.5 py-3',
              efficiency >= 0
                ? 'border-[var(--success)]/30 bg-[var(--success)]/10'
                : 'border-[var(--warning)]/30 bg-[var(--warning)]/10',
            )}
          >
            <TrendingDown
              className={cn('h-5 w-5 shrink-0', efficiency >= 0 ? 'text-[var(--success)]' : 'text-[var(--warning)]')}
              aria-hidden
            />
            <div className="min-w-0">
              <p className={cn('text-sm font-semibold', efficiency >= 0 ? 'text-[var(--success)]' : 'text-[var(--warning)]')}>
                {efficiency >= 0 ? `${efficiency.toFixed(1)}% more efficient` : `${Math.abs(efficiency).toFixed(1)}% costlier`}
              </p>
              <p className="text-[11px] text-muted-foreground">
                Compared with a direct route through the same conditions
              </p>
            </div>
          </motion.div>
        )}

        <div className="grid gap-2.5">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-3 rounded-lg bg-secondary/50 px-3 py-2.5"
            >
              <stat.icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-muted-foreground">{stat.label}</p>
                <p className="font-semibold tabular-nums">{stat.value}</p>
                {stat.detail && <p className="mt-0.5 text-[10px] text-muted-foreground/80">{stat.detail}</p>}
              </div>
            </motion.div>
          ))}
        </div>

        <div className="flex items-center justify-between border-t border-[var(--border)] pt-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Anchor className="h-3 w-3" aria-hidden />
            {route.imo_number === 'MANUAL' ? 'Manual particulars' : `IMO ${route.imo_number}`}
          </span>
          <span className="flex items-center gap-1.5">
            <Flag className="h-3 w-3" aria-hidden />
            {'route_status' in route ? route.route_status : route.status}
          </span>
        </div>
      </CardBody>
    </Card>
  )
}
