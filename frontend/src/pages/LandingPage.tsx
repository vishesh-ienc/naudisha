import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Compass,
  Navigation,
  Waves,
  Wind,
  Cpu,
  Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-[calc(100vh-3.5rem)] bg-background">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        {/* Header */}
        <div className="border-b border-[var(--border)] pb-8">
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Marine Route Planner &amp; Vessel Tracker
          </h1>
          <p className="mt-2 text-sm text-muted-foreground max-w-3xl leading-relaxed">
            Weather-routing tool for commercial vessels. Calculates least-cost routes considering ocean currents (Copernicus Marine), surface winds (Open-Meteo), wave heights, and vessel hydrodynamic profiles.
          </p>
        </div>

        {/* Operational Modules */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {/* Plan Voyage */}
          <div
            onClick={() => navigate('/plan')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && navigate('/plan')}
            className={cn(
              'group flex flex-col justify-between rounded-lg border border-[var(--border)] bg-card p-5 transition-colors cursor-pointer',
              'hover:border-primary hover:bg-secondary/40',
            )}
          >
            <div>
              <div className="flex items-center gap-2 text-primary">
                <Compass className="h-5 w-5" />
                <span className="font-mono text-xs font-semibold uppercase text-muted-foreground">Module 1</span>
              </div>
              <h2 className="mt-3 text-base font-bold text-foreground group-hover:text-primary transition-colors">
                Plan a Voyage
              </h2>
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                Select departure and arrival ports, choose a vessel class, and compute an optimized sea route based on current weather forecasts and sea state data.
              </p>
            </div>

            <div className="mt-6 flex items-center gap-1 text-xs font-semibold text-primary">
              <span>Open Voyage Planner</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </div>
          </div>

          {/* Live Vessel Routing */}
          <div
            onClick={() => navigate('/live-route')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && navigate('/live-route')}
            className={cn(
              'group flex flex-col justify-between rounded-lg border border-[var(--border)] bg-card p-5 transition-colors cursor-pointer',
              'hover:border-primary hover:bg-secondary/40',
            )}
          >
            <div>
              <div className="flex items-center gap-2 text-primary">
                <Navigation className="h-5 w-5" />
                <span className="font-mono text-xs font-semibold uppercase text-muted-foreground">Module 2</span>
              </div>
              <h2 className="mt-3 text-base font-bold text-foreground group-hover:text-primary transition-colors">
                Live Vessel Routing
              </h2>
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                Enter an IMO number to fetch real-time AIS transponder coordinates and calculate a route from the ship's current position to any destination port.
              </p>
            </div>

            <div className="mt-6 flex items-center gap-1 text-xs font-semibold text-primary">
              <span>Open Vessel Tracker</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </div>
          </div>
        </div>

        {/* System Specifications / Data Sources */}
        <div className="mt-10 rounded-lg border border-[var(--border)] bg-card p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Connected Data Services
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
            <div className="rounded border border-[var(--border)]/60 bg-secondary/20 p-2.5">
              <div className="flex items-center gap-1.5 text-foreground font-semibold">
                <Waves className="h-3.5 w-3.5 text-primary" />
                <span>Ocean Currents</span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">Copernicus Marine (CMEMS)</p>
            </div>

            <div className="rounded border border-[var(--border)]/60 bg-secondary/20 p-2.5">
              <div className="flex items-center gap-1.5 text-foreground font-semibold">
                <Wind className="h-3.5 w-3.5 text-primary" />
                <span>Wind Forecasts</span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">Open-Meteo GFS Grid</p>
            </div>

            <div className="rounded border border-[var(--border)]/60 bg-secondary/20 p-2.5">
              <div className="flex items-center gap-1.5 text-foreground font-semibold">
                <Radio className="h-3.5 w-3.5 text-primary" />
                <span>AIS Position Feed</span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">AISStream Live WebSockets</p>
            </div>

            <div className="rounded border border-[var(--border)]/60 bg-secondary/20 p-2.5">
              <div className="flex items-center gap-1.5 text-foreground font-semibold">
                <Cpu className="h-3.5 w-3.5 text-primary" />
                <span>Routing Solver</span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">D* Lite Graph Engine</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
