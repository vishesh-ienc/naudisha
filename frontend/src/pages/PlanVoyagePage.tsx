import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Route as RouteIcon, SlidersHorizontal } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ImoInput } from '@/components/ship/ImoInput'
import { SailingShip } from '@/components/ui/ShipAnimation'
import { cn } from '@/lib/utils'

/**
 * Flow B — plan a voyage before departure.
 *
 * `?manual=1` selects the IMO-less path, where vessel particulars are entered
 * directly. Map selection, departure time and the route preview call land in the
 * next phase.
 */
export function PlanVoyagePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const manualMode = searchParams.get('manual') === '1'

  const [imoText, setImoText] = useState('')
  const [validImo, setValidImo] = useState<string | null>(null)

  const setManual = (manual: boolean) => {
    const next = new URLSearchParams(searchParams)
    if (manual) next.set('manual', '1')
    else next.delete('manual')
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/15 text-accent">
          {manualMode ? (
            <SlidersHorizontal className="h-5 w-5" aria-hidden />
          ) : (
            <RouteIcon className="h-5 w-5" aria-hidden />
          )}
        </span>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            {manualMode ? 'Route Without an IMO' : 'Plan a Voyage'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {manualMode
              ? 'Enter vessel particulars directly to optimise a route.'
              : 'Calculate an optimal route before the vessel departs.'}
          </p>
        </div>
      </div>

      {/* Mode switch between IMO lookup and manual particulars. */}
      <div className="mt-6 inline-flex rounded-lg border border-[var(--border)] p-0.5" role="group">
        {[
          { label: 'Identify by IMO', manual: false },
          { label: 'Enter particulars', manual: true },
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

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,400px)_1fr]">
        <Card>
          <CardHeader
            title={manualMode ? 'Vessel Particulars' : 'Vessel Identification'}
            description={
              manualMode
                ? 'Supplied directly — no IMO lookup performed.'
                : 'Particulars are resolved from the IMO number.'
            }
            action={manualMode ? <Badge variant="info">MANUAL</Badge> : undefined}
          />
          <CardBody className="space-y-5">
            {manualMode ? (
              <p className="text-sm text-muted-foreground">
                The particulars form arrives with the next phase. It will request only the fields
                the backend could not resolve.
              </p>
            ) : (
              <ImoInput value={imoText} onChange={setImoText} onValidChange={setValidImo} autoFocus />
            )}

            <Button className="w-full" size="lg" disabled={!manualMode && !validImo}>
              Continue to Route Setup
            </Button>
          </CardBody>
        </Card>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[var(--border)] bg-card/40 p-8 text-center"
        >
          <SailingShip size={88} />
          <p className="text-sm font-medium">Chart and route preview</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            Select start and destination on the chart, set a departure time, and the optimal route
            will be drawn here with distance, ETA and cost.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
