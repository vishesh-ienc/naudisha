/**
 * Chronological log of voyage events — route updates, hazards, arrival.
 *
 * Every entry states whether it came from the backend or was simulated, so a
 * viewer is never left guessing which parts of the demonstration are real.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Flag, Navigation, RefreshCw, XCircle } from 'lucide-react'
import type { VoyageEvent } from '@/hooks/useLiveTracking'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const EVENT_CONFIG: Record<VoyageEvent['kind'], { icon: typeof Flag; tone: string }> = {
  started: { icon: Navigation, tone: 'text-primary' },
  position: { icon: Navigation, tone: 'text-muted-foreground' },
  route_update: { icon: RefreshCw, tone: 'text-accent' },
  alert: { icon: AlertTriangle, tone: 'text-destructive' },
  cleared: { icon: CheckCircle2, tone: 'text-[var(--success)]' },
  arrived: { icon: Flag, tone: 'text-[var(--success)]' },
  error: { icon: XCircle, tone: 'text-destructive' },
}

export function VoyageEventLog({ events, className }: { events: VoyageEvent[]; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader
        title="Voyage Log"
        description="Route changes and hazards as they occur"
        action={
          events.length > 0 ? (
            <span className="text-[11px] text-muted-foreground">{events.length}</span>
          ) : undefined
        }
      />
      <CardBody className="max-h-72 space-y-1.5 overflow-y-auto scrollbar-thin p-3">
        {events.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">No events yet</p>
        ) : (
          <AnimatePresence initial={false}>
            {events.map((event) => {
              const config = EVENT_CONFIG[event.kind]
              const Icon = config.icon

              return (
                <motion.div
                  key={event.id}
                  layout
                  initial={{ opacity: 0, x: -12, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.22 }}
                  className="flex items-start gap-2.5 rounded-lg px-2 py-2 hover:bg-secondary/50"
                >
                  <Icon className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', config.tone)} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-snug">{event.message}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-muted-foreground">{relativeTime(event.at)}</span>
                      {event.reason && (
                        <span className="font-mono text-[10px] text-muted-foreground/70">{event.reason}</span>
                      )}
                      {event.simulated && (
                        <Badge variant="info" className="px-1 py-0 text-[9px]">
                          SIMULATED
                        </Badge>
                      )}
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>
        )}
      </CardBody>
    </Card>
  )
}
