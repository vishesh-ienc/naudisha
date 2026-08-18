import { Link, NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

import { ThemeToggle } from './ThemeToggle'
import { BackendStatusPill } from './BackendStatusPill'

const NAV_ITEMS = [
  { to: '/plan', label: 'Plan Voyage' },
  { to: '/live-route', label: 'Live Tracking' },
]

export function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-background/95 backdrop-blur-xs">
      <div className="mx-auto flex h-12 max-w-[1700px] items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-baseline gap-2" aria-label="NauDisha home">
            <span className="text-sm font-bold tracking-tight text-foreground">NauDisha</span>
            <span className="text-[10px] text-muted-foreground font-mono">v1.0</span>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded px-2.5 py-1 text-xs font-medium transition-colors',
                    isActive
                      ? 'bg-secondary text-foreground font-semibold'
                      : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <BackendStatusPill />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
