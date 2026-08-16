import { useState } from 'react'
import { motion } from 'framer-motion'
import { Navigation } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ImoInput } from '@/components/ship/ImoInput'
import { RadarSweep } from '@/components/ui/ShipAnimation'

/**
 * Flow A — track a vessel already underway.
 * Map, live position and dynamic replanning arrive in the next phase.
 */
export function TrackShipPage() {
  const [imoText, setImoText] = useState('')
  const [validImo, setValidImo] = useState<string | null>(null)

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Navigation className="h-5 w-5" aria-hidden />
        </span>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Track a Sailing Vessel</h1>
          <p className="text-sm text-muted-foreground">
            Follow a ship underway and watch its route adapt to changing conditions.
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,400px)_1fr]">
        <Card>
          <CardHeader title="Vessel Identification" description="Enter the IMO number of the vessel to track." />
          <CardBody className="space-y-5">
            <ImoInput value={imoText} onChange={setImoText} onValidChange={setValidImo} autoFocus />
            <Button className="w-full" size="lg" disabled={!validImo}>
              Track Ship
            </Button>
          </CardBody>
        </Card>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[var(--border)] bg-card/40 p-8 text-center"
        >
          <RadarSweep size={72} />
          <p className="text-sm font-medium">Awaiting vessel selection</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            Once a vessel is identified, its live position, current route and status will appear
            here alongside the chart.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
