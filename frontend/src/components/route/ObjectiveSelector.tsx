import React from 'react'
import { motion } from 'framer-motion'
import { Fuel, Gauge, ShieldCheck, Scale, Check } from 'lucide-react'
import type { OptimizationObjective } from '@/types/api'

export interface ObjectiveOption {
  id: OptimizationObjective
  title: string
  subtitle: string
  description: string
  badge: string
  icon: React.ComponentType<{ className?: string }>
  accentColor: string
  activeBorder: string
  activeBg: string
  activeBadgeBg: string
}

export const OBJECTIVE_OPTIONS: ObjectiveOption[] = [
  {
    id: 'fuel_efficiency',
    title: 'Fuel Efficiency',
    subtitle: 'Minimise Fuel & Emissions',
    description: 'Prioritises propulsion efficiency and favorable current assistance to minimise bunker fuel consumption and engine wear.',
    badge: 'Eco-Steaming',
    icon: Fuel,
    accentColor: 'text-emerald-400',
    activeBorder: 'border-emerald-500/60 ring-1 ring-emerald-500/40',
    activeBg: 'bg-emerald-500/10',
    activeBadgeBg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  },
  {
    id: 'fastest',
    title: 'Fastest Voyage',
    subtitle: 'Minimise Transit Duration',
    description: 'Maximises Speed Over Ground (SOG) using along-track current corridors and optimal velocity routes to meet strict ETAs.',
    badge: 'Express Transit',
    icon: Gauge,
    accentColor: 'text-amber-400',
    activeBorder: 'border-amber-500/60 ring-1 ring-amber-500/40',
    activeBg: 'bg-amber-500/10',
    activeBadgeBg: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  },
  {
    id: 'safety',
    title: 'Safety & Weather',
    subtitle: 'Avoid Severe Sea States',
    description: 'Heavily penalises high significant wave heights (Hs) and headwinds to ensure vessel stability, cargo safety, and crew comfort.',
    badge: 'Storm Avoidance',
    icon: ShieldCheck,
    accentColor: 'text-sky-400',
    activeBorder: 'border-sky-500/60 ring-1 ring-sky-500/40',
    activeBadgeBg: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
    activeBg: 'bg-sky-500/10',
  },
  {
    id: 'balanced',
    title: 'Balanced Route',
    subtitle: 'Harmonised Multi-Factor',
    description: 'Balances transit duration, fuel economy, ocean currents, and weather safety for standard commercial vessel operations.',
    badge: 'Standard',
    icon: Scale,
    accentColor: 'text-cyan-400',
    activeBorder: 'border-cyan-500/60 ring-1 ring-cyan-500/40',
    activeBg: 'bg-cyan-500/10',
    activeBadgeBg: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
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
  const selectedOption = OBJECTIVE_OPTIONS.find((o) => o.id === value) || OBJECTIVE_OPTIONS[3]!

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Voyage Optimization Objective
        </label>
        <span className="text-[11px] font-mono text-cyan-400/90">
          D* Lite Cost Engine
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-2 lg:grid-cols-2">
        {OBJECTIVE_OPTIONS.map((opt) => {
          const isSelected = opt.id === value
          const Icon = opt.icon

          return (
            <button
              key={opt.id}
              id={`objective-btn-${opt.id}`}
              type="button"
              disabled={disabled}
              onClick={() => onChange(opt.id)}
              className={`group relative flex flex-col justify-between rounded-xl border p-3 text-left transition-all duration-200 ${
                isSelected
                  ? `${opt.activeBorder} ${opt.activeBg} shadow-lg shadow-black/20`
                  : 'border-[var(--border)] bg-card/60 hover:border-border/80 hover:bg-card/90'
              } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
            >
              {/* Top Row: Icon + Badge + Check */}
              <div className="flex items-start justify-between gap-1.5">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${
                    isSelected
                      ? 'border-white/15 bg-background/80 shadow-inner'
                      : 'border-transparent bg-muted/40 text-muted-foreground group-hover:text-foreground'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isSelected ? opt.accentColor : ''}`} />
                </div>

                <div className="flex items-center gap-1">
                  <span
                    className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium tracking-tight ${
                      isSelected
                        ? opt.activeBadgeBg
                        : 'border-[var(--border)] bg-muted/30 text-muted-foreground'
                    }`}
                  >
                    {opt.badge}
                  </span>
                  {isSelected && (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-cyan-500 text-black">
                      <Check className="h-2.5 w-2.5 stroke-[3]" />
                    </span>
                  )}
                </div>
              </div>

              {/* Title & Subtitle */}
              <div className="mt-2.5">
                <div className="text-xs font-semibold text-foreground group-hover:text-cyan-300">
                  {opt.title}
                </div>
                <div className="text-[11px] text-muted-foreground line-clamp-1">
                  {opt.subtitle}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Selected Objective Description Callout */}
      <motion.div
        key={selectedOption.id}
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="rounded-lg border border-[var(--border)] bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground leading-relaxed"
      >
        <span className={`font-semibold ${selectedOption.accentColor}`}>
          {selectedOption.title}:{' '}
        </span>
        {selectedOption.description}
      </motion.div>
    </div>
  )
}
