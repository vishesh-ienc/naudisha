import { useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
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
    <div className={cn('relative space-y-1', className)}>
      <label className="block text-xs font-semibold text-foreground">
        Vessel Type
      </label>

      {/* Selected Vessel Box */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between rounded-lg border border-[var(--border)] bg-card p-2.5 text-left transition-colors hover:bg-secondary/40"
      >
        <div className="min-w-0 flex-1 pr-2">
          <div className="text-xs font-semibold text-foreground truncate">
            {value.name}
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
            {value.category} · {value.length_m}m LOA · {value.draft_m}m Draft · {value.cruising_speed_kn} kn
          </div>
        </div>

        <ChevronDown
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform shrink-0',
            isOpen && 'rotate-180',
          )}
        />
      </button>

      {/* Dropdown Options */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-auto rounded-lg border border-[var(--border)] bg-card p-1 shadow-lg backdrop-blur-md scrollbar-thin">
          <div className="space-y-0.5">
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
                    'flex w-full items-center justify-between rounded p-2 text-left transition-colors',
                    isSelected
                      ? 'bg-primary/10 text-foreground font-semibold'
                      : 'hover:bg-secondary text-foreground',
                  )}
                >
                  <div className="min-w-0 pr-2 flex-1">
                    <div className="text-xs font-medium text-foreground truncate">
                      {vessel.name}
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-muted-foreground truncate">
                      {vessel.category} · {vessel.length_m}m LOA · {vessel.draft_m}m Draft · {vessel.cruising_speed_kn} kn
                    </div>
                  </div>

                  {isSelected && <Check className="h-4 w-4 text-primary shrink-0 ml-2" />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
