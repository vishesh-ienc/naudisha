import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, LocateFixed, Route as RouteIcon, Waves, Wind, Gauge, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FlowCard {
  id: string
  title: string
  tagline: string
  description: string
  icon: typeof RouteIcon
  to: string
  badge: string
}

const FLOWS: FlowCard[] = [
  {
    id: 'plan',
    title: 'Plan a Voyage',
    tagline: 'Pre-departure optimal routing',
    description: 'Calculate least-cost routes between any global ports considering Copernicus ocean currents, wave resistance and atmospheric winds.',
    icon: RouteIcon,
    to: '/plan',
    badge: 'Flow 1',
  },
  {
    id: 'live-route',
    title: 'Live Routing',
    tagline: 'Current fix to destination',
    description: 'Calculate a weather-optimized passage directly from a vessel’s current live AIS coordinates to any target destination.',
    icon: LocateFixed,
    to: '/live-route',
    badge: 'Flow 2',
  },
]

const CAPABILITIES = [
  { icon: Waves, label: 'Copernicus Marine', detail: 'Global ocean currents & wave physics' },
  { icon: Wind, label: 'Open-Meteo', detail: 'Real-time surface wind fields' },
  { icon: Gauge, label: 'D* Lite Solver', detail: 'Dynamic multi-factor graph search' },
  { icon: ShieldCheck, label: 'Vessel AIS', detail: 'Live maritime transponder ingestion' },
]

export function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Dark maritime ambient glow */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-[#0a0f1d] via-background to-background" />
        <div className="animate-swell absolute -left-20 top-16 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
        <div
          className="animate-swell absolute -right-20 top-40 h-96 w-96 rounded-full bg-blue-600/10 blur-3xl"
          style={{ animationDelay: '-4.5s' }}
        />
      </div>

      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6 sm:py-16 lg:py-20">
        {/* Hero Section */}
        <div className="flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="flex flex-col items-center"
          >
            <h1 className="text-5xl font-black tracking-tight sm:text-6xl md:text-7xl lg:text-8xl">
              <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-emerald-400 bg-clip-text text-transparent drop-shadow-[0_0_35px_rgba(6,182,212,0.35)]">
                NauDisha
              </span>
            </h1>
            <p className="mt-3 text-sm font-medium tracking-widest uppercase text-cyan-400/80 sm:text-base">
              Dynamic Maritime Route Optimization Platform
            </p>
          </motion.div>

          {/* Core Capabilities */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 font-mono text-xs text-muted-foreground"
          >
            {CAPABILITIES.map((cap) => (
              <div key={cap.label} className="flex items-center gap-2">
                <cap.icon className="h-3.5 w-3.5 text-cyan-400" aria-hidden />
                <span className="font-semibold text-foreground">{cap.label}</span>
                <span className="hidden text-muted-foreground/60 sm:inline">· {cap.detail}</span>
              </div>
            ))}
          </motion.div>
        </div>

        {/* 2 Core Product Flows */}
        <div className="mx-auto mt-14 grid max-w-4xl gap-6 sm:grid-cols-2">

          {FLOWS.map((flow, index) => (
            <motion.button
              key={flow.id}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 + index * 0.08, ease: 'easeOut' }}
              whileHover={{ y: -5 }}
              onClick={() => navigate(flow.to)}
              className={cn(
                'group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-[var(--border)]',
                'bg-card/70 p-6 text-left shadow-lg backdrop-blur-md transition-all hover:border-cyan-500/50 hover:shadow-cyan-500/10',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              )}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 transition-colors group-hover:bg-cyan-500 group-hover:text-black">
                    <flow.icon className="h-5 w-5" aria-hidden />
                  </span>
                  <span className="rounded-md bg-secondary/80 px-2 py-0.5 font-mono text-[10px] font-bold text-muted-foreground uppercase">
                    {flow.badge}
                  </span>
                </div>

                <h2 className="mt-5 text-lg font-bold tracking-tight text-foreground group-hover:text-cyan-400 transition-colors">
                  {flow.title}
                </h2>
                <p className="mt-1 text-xs font-medium text-cyan-400/80">{flow.tagline}</p>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{flow.description}</p>
              </div>

              <div className="mt-6 flex items-center gap-1.5 font-mono text-xs font-semibold text-cyan-400">
                Launch Flow
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" />
              </div>
            </motion.button>
          ))}
        </div>

        {/* Honest System Info */}
        <p className="mt-14 text-center font-mono text-xs text-muted-foreground/60">
          All routes, meteorological hydrodynamics and dynamic graph optimizations are computed live by the NauDisha FastAPI engine.
        </p>
      </div>
    </div>
  )
}
