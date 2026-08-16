import { Link, NavLink } from 'react-router-dom'
import { Compass, LocateFixed, Navigation, Route as RouteIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'
import { BackendStatusPill } from './BackendStatusPill'

const NAV_ITEMS = [
  { to: '/plan', label: 'Plan Voyage', icon: RouteIcon },
  { to: '/track', label: 'Track Ship', icon: Navigation },
  { to: '/live-route', label: 'Live Routing', icon: LocateFixed },
]

export function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1700px] items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-2.5" aria-label="NauDisha home">
          <span className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500 text-black shadow-md shadow-cyan-500/20">
            <Compass className="h-5 w-5 transition-transform duration-500 group-hover:rotate-90" aria-hidden />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-bold tracking-tight text-foreground">NauDisha</span>
            <span className="mt-0.5 font-mono text-[9px] text-cyan-400 uppercase tracking-wider">
              Marine Routing
            </span>
          </span>
        </Link>

        {/* 3 Core Navigation Items */}
        <nav className="ml-6 hidden items-center gap-1.5 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
                  isActive
                    ? 'bg-secondary text-cyan-400 shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                )
              }
            >
              <item.icon className="h-3.5 w-3.5" aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2.5">
          <BackendStatusPill />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
