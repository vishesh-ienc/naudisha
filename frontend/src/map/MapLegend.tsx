import { useState } from 'react'
import { ChevronDown, Layers, Navigation } from 'lucide-react'
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
  className,
}: MapLegendProps) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <div
      className={cn(
        'absolute bottom-4 right-4 z-[400] max-w-[240px] rounded border border-[var(--border)] bg-card/95 p-2.5 shadow-md backdrop-blur-xs text-xs',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between text-left font-semibold text-foreground"
      >
        <span className="flex items-center gap-1.5 text-xs">
          <Layers className="h-3.5 w-3.5 text-muted-foreground" />
          Map Layers
        </span>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 text-muted-foreground transition-transform',
            isOpen && 'rotate-180',
          )}
        />
      </button>

      {isOpen && (
        <div className="mt-2 space-y-1.5 border-t border-[var(--border)] pt-2 text-[11px]">
          {/* Optimal Route */}
          <div className="flex items-center gap-2">
            <span className="h-1 w-4 rounded-full bg-emerald-500" />
            <span className="text-foreground">Optimal Route</span>
          </div>

          {/* Ports */}
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full border border-sky-400 bg-sky-400/30" />
            <span className="text-muted-foreground">Ports</span>
          </div>

          {/* Ship Marker */}
          <div className="flex items-center gap-2">
            <Navigation className="h-3 w-3 text-primary rotate-45" />
            <span className="text-muted-foreground">Vessel Position (AIS)</span>
          </div>

          {/* Wind Vector */}
          {hasWindData && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-sky-400 font-bold">→</span>
              <span className="text-muted-foreground">Wind Vectors (kn)</span>
            </div>
          )}

          {/* Current Vector */}
          {hasCurrentData && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-emerald-400 font-bold">⇶</span>
              <span className="text-muted-foreground">Current Vectors (kn)</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
