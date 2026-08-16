import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Navigation, Compass } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MapLegendProps {
  hasWindData?: boolean
  hasCurrentData?: boolean
  hasDirectRoute?: boolean
  className?: string
}

export function MapLegend({
  hasWindData = true,
  hasCurrentData = true,
  hasDirectRoute = true,
  className,
}: MapLegendProps) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <div
      className={cn(
        'absolute bottom-4 right-4 z-[400] max-w-[280px] rounded-xl border border-[var(--border)] bg-card/90 p-3 shadow-2xl backdrop-blur-md transition-all',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between text-left font-mono text-[11px] font-bold uppercase tracking-wider text-foreground"
      >
        <span className="flex items-center gap-1.5 text-cyan-400">
          <Compass className="h-3.5 w-3.5" />
          Marine Chart Legend
        </span>
        <ChevronDown className={cn('h-3.5 w-3.5 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2.5 space-y-2 border-t border-[var(--border)] pt-2 text-[11px]"
          >
            {/* Optimal Route (Green) */}
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
              <span className="font-semibold text-emerald-400">NauDisha Optimal Route</span>
            </div>

            {/* Direct / Original Baseline Route (Red) */}
            {hasDirectRoute && (
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-5 rounded-full border border-dashed border-rose-500 bg-rose-500/40" />
                <span className="text-rose-400">Actual AIS Track / Baseline</span>
              </div>
            )}


            {/* Ship Marker */}
            <div className="flex items-center gap-2">
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-cyan-500/20 text-cyan-400">
                <Navigation className="h-2.5 w-2.5 rotate-45" />
              </span>
              <span className="text-muted-foreground">Live Vessel Transponder (AIS)</span>
            </div>

            {/* Wind Vector */}
            {hasWindData && (
              <div className="flex items-center gap-2">
                <span className="flex h-3 w-4 items-center justify-center rounded bg-sky-500/20 text-sky-400 font-mono text-[9px] font-bold">
                  →
                </span>
                <span className="text-sky-300">Wind Direction &amp; Speed (Open-Meteo)</span>
              </div>
            )}

            {/* Current Vector */}
            {hasCurrentData && (
              <div className="flex items-center gap-2">
                <span className="flex h-3 w-4 items-center justify-center rounded bg-emerald-500/20 text-emerald-400 font-mono text-[9px] font-bold">
                  ⇶
                </span>
                <span className="text-emerald-300">Ocean Current Velocity (Copernicus)</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
