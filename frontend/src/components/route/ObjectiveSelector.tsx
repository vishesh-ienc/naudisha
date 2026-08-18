import type { OptimizationObjective } from '@/types/api'
import { cn } from '@/lib/utils'

export interface ObjectiveOption {
  id: OptimizationObjective
  title: string
  subtitle: string
  description: string
  color: {
    borderActive: string
    bgActive: string
    textAccent: string
    bar: string
    hover: string
  }
}

export const OBJECTIVE_OPTIONS: ObjectiveOption[] = [
  {
    id: 'balanced',
    title: 'Balanced',
    subtitle: 'Standard commercial passage',
    description: 'Balances travel duration, bunker fuel efficiency, and sea state conditions.',
    color: {
      borderActive: 'border-slate-400 ring-1 ring-slate-400/30',
      bgActive: 'bg-slate-500/15',
      textAccent: 'text-slate-300',
      bar: 'bg-slate-400',
      hover: 'hover:border-slate-400/50 hover:bg-slate-500/10',
    },
  },
  {
    id: 'fuel_efficiency',
    title: 'Minimum Fuel',
    subtitle: 'Eco-speed / low emissions',
    description: 'Minimizes bunker fuel consumption by utilizing favorable ocean currents and low-resistance corridors.',
    color: {
      borderActive: 'border-emerald-500/70 ring-1 ring-emerald-500/30',
      bgActive: 'bg-emerald-500/15',
      textAccent: 'text-emerald-400',
      bar: 'bg-emerald-400',
      hover: 'hover:border-emerald-500/50 hover:bg-emerald-500/10',
    },
  },
  {
    id: 'fastest',
    title: 'Minimum Time',
    subtitle: 'Shortest transit duration',
    description: 'Maximizes speed over ground using high-velocity corridors to achieve earliest possible arrival.',
    color: {
      borderActive: 'border-amber-500/70 ring-1 ring-amber-500/30',
      bgActive: 'bg-amber-500/15',
      textAccent: 'text-amber-400',
      bar: 'bg-amber-400',
      hover: 'hover:border-amber-500/50 hover:bg-amber-500/10',
    },
  },
  {
    id: 'safety',
    title: 'Weather Avoidance',
    subtitle: 'Avoid rough sea states',
    description: 'Penalizes high waves (Hs) and headwinds to ensure vessel stability, cargo safety, and crew comfort.',
    color: {
      borderActive: 'border-sky-500/70 ring-1 ring-sky-500/30',
      bgActive: 'bg-sky-500/15',
      textAccent: 'text-sky-400',
      bar: 'bg-sky-400',
      hover: 'hover:border-sky-500/50 hover:bg-sky-500/10',
    },
  },
]

interface ObjectiveSelectorProps {
  value: OptimizationObjective
  onChange: (objective: OptimizationObjective) => void
  disabled?: boolean
}

export function ObjectiveSelector({
  value,
  onChange,
  disabled = false,
}: ObjectiveSelectorProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-semibold text-foreground">
          Routing Objective
        </label>
      </div>

      {/* 4 Objective Buttons without icons, each with distinct light professional color and hover tooltip */}
      <div className="grid grid-cols-2 gap-2">
        {OBJECTIVE_OPTIONS.map((opt) => {
          const isSelected = opt.id === value

          return (
            <button
              key={opt.id}
              id={`objective-btn-${opt.id}`}
              type="button"
              disabled={disabled}
              onClick={() => onChange(opt.id)}
              title={`${opt.title}: ${opt.description}`}
              className={cn(
                'relative flex flex-col justify-between rounded-lg border p-2.5 text-left transition-all duration-150',
                isSelected
                  ? cn(opt.color.borderActive, opt.color.bgActive)
                  : cn('border-[var(--border)] bg-card', opt.color.hover),
                disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
              )}
            >
              <div className="flex items-center justify-between w-full">
                <span
                  className={cn(
                    'text-xs font-bold transition-colors',
                    isSelected ? opt.color.textAccent : 'text-foreground',
                  )}
                >
                  {opt.title}
                </span>

                <span
                  className={cn(
                    'h-1.5 w-1.5 rounded-full transition-opacity',
                    isSelected ? cn(opt.color.bar, 'opacity-100') : 'opacity-0',
                  )}
                />
              </div>

              <div className="mt-1 text-[11px] text-muted-foreground">
                {opt.subtitle}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
