/**
 * Standard Vessel Type Dropdown Selector.
 *
 * Allows users to choose standard ship types (ULCV, Panamax Container, VLCC Tanker,
 * Capesize Bulk, LNG Carrier, MR2 Tanker, Coastal Feeder) based on size and fuel efficiency.
 */

import { useState } from 'react'
import { Check, ChevronDown, Fuel, Ship } from 'lucide-react'
import { STANDARD_VESSEL_TYPES, type StandardVesselType } from '@/lib/vessels'
import { cn } from '@/lib/utils'

interface VesselTypeSelectProps {
  value: StandardVesselType
  onChange: (vessel: StandardVesselType) => void
  className?: string
}

export function VesselTypeSelect({ value, onChange, className }: VesselTypeSelectProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className={cn('relative space-y-1.5', className)}>
      <label className="block text-xs font-semibold text-foreground/80">
        Vessel Type &amp; Hydrodynamic Profile
      </label>

      {/* Selected Vessel Box */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between rounded-xl border border-[var(--border)] bg-secondary/30 p-3 text-left transition-colors hover:border-primary/50 hover:bg-secondary/50"
      >
        <div className="flex items-start gap-2.5 min-w-0">
          <Ship className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
          <div className="min-w-0">
            <span className="block truncate text-xs font-bold text-foreground">{value.name}</span>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px] text-muted-foreground">
              <span>LOA: {value.length_m}m</span>
              <span>·</span>
              <span>Draft: {value.draft_m}m</span>
              <span>·</span>
              <span>Speed: {value.cruising_speed_kn} kn</span>
            </div>
            <div className="mt-1 flex items-center gap-1 font-mono text-[10px] text-amber-400">
              <Fuel className="h-3 w-3 shrink-0" />
              <span>{value.fuelLabel} ({value.fuelRating})</span>
            </div>
          </div>
        </div>

        <ChevronDown
          className={cn('h-4 w-4 text-muted-foreground transition-transform duration-200 shrink-0', isOpen && 'rotate-180')}
        />
      </button>

      {/* Dropdown Options */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-auto rounded-xl border border-[var(--border)] bg-card/95 p-1.5 shadow-2xl backdrop-blur-md scrollbar-thin">
          <div className="space-y-1">
            {STANDARD_VESSEL_TYPES.map((vessel) => {
              const isSelected = value.id === vessel.id
              return (
                <button
                  key={vessel.id}
                  type="button"
                  onClick={() => {
                    onChange(vessel)
                    setIsOpen(false)
                  }}
                  className={cn(
                    'flex w-full items-start justify-between rounded-lg p-2.5 text-left transition-colors',
                    isSelected ? 'bg-primary/15 border border-primary/40' : 'hover:bg-secondary/60 text-foreground',
                  )}
                >
                  <div className="min-w-0 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-foreground">{vessel.name}</span>
                      <span className="rounded bg-secondary px-1.5 py-0.2 font-mono text-[9px] font-semibold text-cyan-400">
                        {vessel.category}
                      </span>
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-x-2 font-mono text-[10px] text-muted-foreground">
                      <span>LOA {vessel.length_m}m</span>
                      <span>Beam {vessel.beam_m}m</span>
                      <span>Draft {vessel.draft_m}m</span>
                      <span>Speed {vessel.cruising_speed_kn} kn</span>
                    </div>

                    <div className="mt-1 flex items-center gap-1.5 font-mono text-[10px] text-amber-400">
                      <Fuel className="h-3 w-3 shrink-0" />
                      <span>{vessel.fuelLabel}</span>
                    </div>
                  </div>

                  {isSelected && <Check className="h-4 w-4 text-primary shrink-0 mt-1" />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
