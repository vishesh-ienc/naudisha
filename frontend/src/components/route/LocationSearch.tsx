/**
 * Location entry by name, with map-click and coordinate fallbacks.
 *
 * Names are a convenience for the user; the coordinate remains the canonical
 * value sent to the backend (FRONTEND_DEVELOPMENT_WORKFLOW §3). Every named
 * location resolves to a seaward approach rather than a berth, because the
 * router has no land mask.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Anchor, Crosshair, MapPin, Search, X, AlertTriangle } from 'lucide-react'
import type { Coordinate } from '@/types/api'
import { NAMED_LOCATIONS, nearestLocationName, searchLocations, type NamedLocation } from '@/lib/ports'
import { validateSelectionPoint } from '@/lib/geo'
import { formatCoordinate } from '@/lib/format'
import { cn } from '@/lib/utils'

interface LocationSearchProps {
  label: string
  value: Coordinate | null
  /** Display name when chosen from the list, or derived from the map click. */
  displayName: string | null
  onChange: (coordinate: Coordinate | null, name: string | null) => void
  picking: boolean
  onPickingChange: (picking: boolean) => void
  accent: 'start' | 'destination'
  placeholder?: string
}

const KIND_LABEL: Record<NamedLocation['kind'], string> = {
  port: 'Port',
  anchorage: 'Anchorage',
  waypoint: 'Waypoint',
}

export function LocationSearch({
  label,
  value,
  displayName,
  onChange,
  picking,
  onPickingChange,
  accent,
  placeholder = 'Search a port or sea area…',
}: LocationSearchProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const results = useMemo(() => searchLocations(query), [query])
  const validity = value ? validateSelectionPoint(value) : null

  // Close on outside click so the dropdown never traps the page.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const select = (location: NamedLocation) => {
    onChange(location.coordinate, location.name)
    setQuery('')
    setOpen(false)
  }

  const tryCoordinates = (raw: string): boolean => {
    // Accepts "18.62, 72.35" so a user can paste a position directly.
    const m = raw.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/)
    if (!m) return false
    const lat = Number(m[1])
    const lon = Number(m[2])
    if (Number.isNaN(lat) || Number.isNaN(lon)) return false
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return false

    onChange({ latitude: lat, longitude: lon }, nearestLocationName({ latitude: lat, longitude: lon }))
    setQuery('')
    setOpen(false)
    return true
  }

  const dot = accent === 'start' ? 'bg-[var(--success)]' : 'bg-destructive'

  return (
    <div ref={containerRef} className="relative">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          <span className={cn('h-2 w-2 rounded-full', dot)} aria-hidden />
          {label}
        </span>
        <button
          type="button"
          onClick={() => onPickingChange(!picking)}
          className={cn(
            'flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors',
            picking ? 'bg-primary text-primary-foreground' : 'text-primary hover:bg-primary/10',
          )}
        >
          <Crosshair className="h-3 w-3" aria-hidden />
          {picking ? 'Click chart…' : 'Pick on chart'}
        </button>
      </div>

      {value ? (
        <div
          className={cn(
            'flex items-center gap-2.5 rounded-xl border bg-background px-3 py-2.5 transition-colors',
            picking ? 'border-primary ring-2 ring-primary/20' : 'border-[var(--input)]',
          )}
        >
          <Anchor className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{displayName ?? 'Custom position'}</p>
            <p className="truncate font-mono text-[10px] text-muted-foreground">
              {formatCoordinate(value, 4)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onChange(null, null)
              setQuery('')
            }}
            className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            aria-label={`Clear ${label}`}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpen(true)
              setHighlight(0)
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setHighlight((h) => Math.min(h + 1, results.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setHighlight((h) => Math.max(h - 1, 0))
              } else if (e.key === 'Enter') {
                e.preventDefault()
                if (tryCoordinates(query)) return
                const chosen = results[highlight]
                if (chosen) select(chosen)
              } else if (e.key === 'Escape') {
                setOpen(false)
              }
            }}
            placeholder={placeholder}
            className={cn(
              'h-11 w-full rounded-xl border bg-background pl-9 pr-3 text-sm transition-colors',
              'placeholder:text-muted-foreground/60',
              'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--ring)]',
              picking ? 'border-primary ring-2 ring-primary/20' : 'border-[var(--input)]',
            )}
          />
        </div>
      )}

      <AnimatePresence>
        {open && !value && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.14 }}
            className="absolute z-[1000] mt-1.5 w-full overflow-hidden rounded-xl border border-[var(--border)] bg-popover shadow-xl"
          >
            <div className="max-h-64 overflow-y-auto scrollbar-thin">
              {results.length === 0 ? (
                <p className="px-3 py-4 text-center text-xs text-muted-foreground">
                  No match. Try a port name, or type coordinates as “18.62, 72.35”.
                </p>
              ) : (
                results.map((location, i) => (
                  <button
                    key={location.id}
                    type="button"
                    onMouseEnter={() => setHighlight(i)}
                    onClick={() => select(location)}
                    className={cn(
                      'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors',
                      i === highlight ? 'bg-secondary' : 'hover:bg-secondary/60',
                    )}
                  >
                    <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium">{location.name}</span>
                      <span className="block truncate text-[10px] text-muted-foreground">
                        {location.country} · {formatCoordinate(location.coordinate, 2)}
                      </span>
                    </span>
                    <span className="shrink-0 rounded-md bg-secondary px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
                      {KIND_LABEL[location.kind]}
                    </span>
                  </button>
                ))
              )}
            </div>
            <p className="border-t border-[var(--border)] bg-secondary/40 px-3 py-1.5 text-[10px] text-muted-foreground">
              {NAMED_LOCATIONS.length} locations · coordinates accepted directly
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {validity && !validity.ok && (
        <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[var(--warning)]">
          <AlertTriangle className="mt-px h-3 w-3 shrink-0" aria-hidden />
          {validity.message}
        </p>
      )}
    </div>
  )
}
