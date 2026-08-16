import { motion } from 'framer-motion'
import { Anchor, Compass, Gauge, MapPin, Ship as ShipIcon } from 'lucide-react'
import type { Coordinate, ShipResponse } from '@/types/api'
import type { DataSource } from '@/services/telemetry'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { DataBadge } from '@/components/ui/Badge'
import { compassPoint, formatCoordinate, formatDistance, formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'

interface ShipInfoPanelProps {
  ship: ShipResponse | null
  source: DataSource
  position: Coordinate | null
  destination: Coordinate | null
  heading: number
  progressPercent: number
  distanceRemainingNm: number
  hoursRemaining: number
  arrived: boolean
  className?: string
}

export function ShipInfoPanel({
  ship,
  source,
  position,
  destination,
  heading,
  progressPercent,
  distanceRemainingNm,
  hoursRemaining,
  arrived,
  className,
}: ShipInfoPanelProps) {
  if (!ship) return null

  const rows = [
    { icon: MapPin, label: 'Position', value: position ? formatCoordinate(position, 4) : '—', mono: true },
    {
      icon: Compass,
      label: 'Course',
      value: `${Math.round(heading)}° (${compassPoint(heading)})`,
      mono: true,
    },
    { icon: Anchor, label: 'Destination', value: destination ? formatCoordinate(destination, 3) : '—', mono: true },
    {
      icon: Gauge,
      label: 'Remaining',
      value: arrived ? 'Arrived' : `${formatDistance(distanceRemainingNm)} · ${formatDuration(hoursRemaining)}`,
    },
  ]

  return (
    <Card className={className}>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <ShipIcon className="h-4 w-4 text-primary" aria-hidden />
            {ship.name}
          </span>
        }
        description={`IMO ${ship.imo_number}${ship.ship?.ship_type ? ` · ${ship.ship.ship_type}` : ''}`}
        action={<DataBadge source={source} />}
      />
      <CardBody className="space-y-4">
        {/* Progress */}
        <div>
          <div className="mb-1.5 flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">Voyage progress</span>
            <span className="font-mono font-medium tabular-nums">{progressPercent.toFixed(0)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-secondary">
            <motion.div
              className={cn('h-full rounded-full', arrived ? 'bg-[var(--success)]' : 'bg-primary')}
              initial={{ width: 0 }}
              animate={{ width: `${progressPercent}%` }}
              transition={{ duration: 0.9, ease: 'linear' }}
            />
          </div>
        </div>

        <dl className="grid gap-2">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center gap-2.5 rounded-lg bg-secondary/50 px-3 py-2">
              <row.icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
              <dt className="w-24 shrink-0 text-[11px] text-muted-foreground">{row.label}</dt>
              <dd className={cn('min-w-0 flex-1 truncate text-xs font-medium', row.mono && 'font-mono')}>
                {row.value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="flex items-center justify-between border-t border-[var(--border)] pt-3 text-[11px] text-muted-foreground">
          <span>Status</span>
          <span
            className={cn(
              'rounded-md px-2 py-0.5 font-medium',
              ship.status === 'underway'
                ? 'bg-[var(--success)]/15 text-[var(--success)]'
                : ship.status === 'stopped'
                  ? 'bg-[var(--warning)]/15 text-[var(--warning)]'
                  : 'bg-secondary',
            )}
          >
            {arrived ? 'arrived' : ship.status}
          </span>
        </div>
      </CardBody>
    </Card>
  )
}
