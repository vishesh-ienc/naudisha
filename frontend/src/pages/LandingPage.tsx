import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Navigation, Route as RouteIcon, SlidersHorizontal, Waves, Wind, Gauge } from 'lucide-react'
import { LottiePlayer } from '@/components/ui/LottiePlayer'
import { SailingShip } from '@/components/ui/ShipAnimation'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

interface FlowOption {
  id: string
  title: string
  description: string
  detail: string
  icon: typeof Navigation
  to: string
  accent: string
}

const FLOWS: FlowOption[] = [
  {
    id: 'track',
    title: 'Ship Already Sailing',
    description: 'Track a vessel underway and watch its route adapt to conditions.',
    detail: 'Enter an IMO number to pick up live position, route and status.',
    icon: Navigation,
    to: '/track',
    accent: 'from-[var(--primary)]/12 to-transparent',
  },
  {
    id: 'plan',
    title: 'Plan a Voyage',
    description: 'Calculate an optimal route before the vessel departs.',
    detail: 'Set start, destination and departure time to preview the route.',
    icon: RouteIcon,
    to: '/plan',
    accent: 'from-[var(--accent)]/12 to-transparent',
  },
  {
    id: 'manual',
    title: 'Route Without an IMO',
    description: 'Optimise a route by entering vessel particulars directly.',
    detail: 'For planning, comparison, or when no IMO number is to hand.',
    icon: SlidersHorizontal,
    to: '/plan?manual=1',
    accent: 'from-[var(--ocean-deep)]/12 to-transparent',
  },
]

const CAPABILITIES = [
  { icon: Waves, label: 'Ocean currents & waves', source: 'Copernicus Marine' },
  { icon: Wind, label: 'Surface wind fields', source: 'Open-Meteo' },
  { icon: Gauge, label: 'Incremental replanning', source: 'D* Lite' },
]

export function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="relative overflow-hidden">
      {/* Ambient background — deep-water gradient with a slow drift. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--ocean)]/25 via-background to-background" />
        <div className="animate-swell absolute -left-24 top-20 h-72 w-72 rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div
          className="animate-swell absolute -right-16 top-48 h-80 w-80 rounded-full bg-[var(--primary)]/10 blur-3xl"
          style={{ animationDelay: '-4s' }}
        />
      </div>

      <div className="mx-auto max-w-[1200px] px-4 py-12 sm:px-6 sm:py-16 lg:py-20">
        {/* Hero */}
        <div className="flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          >
            <LottiePlayer
              name="sailing-ship"
              className="h-28 w-28"
              fallback={<SailingShip size={112} />}
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.1 }}
          >
            <Badge variant="accent" className="mt-2">
              Dynamic &amp; Optimal Ship Routing
            </Badge>

            <h1 className="mt-4 max-w-2xl text-balance text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
              Routes that respond to the ocean
            </h1>

            <p className="mx-auto mt-4 max-w-xl text-pretty text-sm text-muted-foreground sm:text-base">
              NauDisha fuses live oceanographic and atmospheric forecasts with vessel
              hydrodynamics to plan sea routes — and replans them incrementally as
              conditions change mid-voyage.
            </p>
          </motion.div>

          <motion.ul
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="mt-7 flex flex-wrap items-center justify-center gap-x-6 gap-y-3"
          >
            {CAPABILITIES.map((cap) => (
              <li key={cap.label} className="flex items-center gap-2 text-xs text-muted-foreground">
                <cap.icon className="h-3.5 w-3.5 text-accent" aria-hidden />
                <span>{cap.label}</span>
                <span className="text-muted-foreground/50">·</span>
                <span className="font-medium text-foreground/70">{cap.source}</span>
              </li>
            ))}
          </motion.ul>
        </div>

        {/* Flow selector */}
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FLOWS.map((flow, index) => (
            <motion.button
              key={flow.id}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 + index * 0.08, ease: 'easeOut' }}
              whileHover={{ y: -4 }}
              onClick={() => navigate(flow.to)}
              className={cn(
                'group relative flex flex-col overflow-hidden rounded-xl border border-[var(--border)]',
                'bg-card p-5 text-left shadow-sm transition-shadow hover:shadow-lg',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]',
              )}
            >
              <div
                aria-hidden
                className={cn('pointer-events-none absolute inset-0 bg-gradient-to-br opacity-0 transition-opacity duration-300 group-hover:opacity-100', flow.accent)}
              />

              <div className="relative">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                  <flow.icon className="h-5 w-5" aria-hidden />
                </span>

                <h2 className="mt-4 text-base font-semibold tracking-tight">{flow.title}</h2>
                <p className="mt-1.5 text-sm text-muted-foreground">{flow.description}</p>
                <p className="mt-3 text-xs text-muted-foreground/70">{flow.detail}</p>

                <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                  Continue
                  <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-1" aria-hidden />
                </span>
              </div>
            </motion.button>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-10 text-center text-xs text-muted-foreground/70"
        >
          Routing, cost evaluation and replanning are performed by the NauDisha backend engine.
          When the backend is unavailable this interface falls back to clearly-labelled demo data.
        </motion.p>
      </div>
    </div>
  )
}
