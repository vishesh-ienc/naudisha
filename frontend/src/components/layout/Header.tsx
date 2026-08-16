import { Link, NavLink } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'
import { BackendStatusPill } from './BackendStatusPill'

const NAV_ITEMS = [
  { to: '/plan', label: 'Plan Voyage' },
  { to: '/track', label: 'Track Ship' },
]

export function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-2.5" aria-label="NauDisha home">
          <span className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <Compass className="h-4.5 w-4.5 transition-transform duration-500 group-hover:rotate-90" aria-hidden />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight">NauDisha</span>
            <span className="mt-0.5 text-[10px] text-muted-foreground">Dynamic Ship Routing</span>
          </span>
        </Link>

        <nav className="ml-4 hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-secondary text-foreground'
                    : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <BackendStatusPill />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
