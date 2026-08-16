/**
 * Worldwide Searchable Port / Harbour / Marine Location Selector.
 *
 * Clean, minimal design — no port anchor icon per row, just clear text.
 * Searches name, country, region, UN/LOCODE intelligently.
 */

import { useState, useRef, useEffect, useMemo } from 'react'
import { ChevronDown, Globe, Search, X } from 'lucide-react'
import { NAMED_LOCATIONS, searchLocations, type NamedLocation } from '@/lib/ports'
import type { Coordinate } from '@/types/api'
import { cn } from '@/lib/utils'

interface PortSearchInputProps {
  label: string
  placeholder?: string
  value: Coordinate | null
  onChange: (coordinate: Coordinate, locationName: string) => void
  accent?: 'origin' | 'destination'
  className?: string
}

export function PortSearchInput({
  label,
  placeholder = 'Search ports worldwide (e.g. Mumbai, Dubai, London, Rotterdam, Shanghai)…',
  value,
  onChange,
  accent = 'origin',
  className,
}: PortSearchInputProps) {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Find currently selected named location
  const selectedLocation = useMemo(() => {
    if (!value) return null
    return (
      NAMED_LOCATIONS.find(
        (loc) =>
          Math.abs(loc.coordinate.latitude - value.latitude) < 0.1 &&
          Math.abs(loc.coordinate.longitude - value.longitude) < 0.1,
      ) ?? null
    )
  }, [value])

  const results = useMemo(() => searchLocations(query), [query])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [isOpen])

  const handleSelect = (loc: NamedLocation) => {
    onChange(loc.coordinate, loc.name)
    setQuery('')
    setIsOpen(false)
  }

  const dotColor = accent === 'origin' ? 'bg-emerald-500' : 'bg-rose-500'
  const ringColor = accent === 'origin' ? 'focus-within:ring-emerald-500/30 focus-within:border-emerald-500/60' : 'focus-within:ring-rose-500/30 focus-within:border-rose-500/60'

  return (
    <div className={cn('relative', className)} ref={dropdownRef}>
      {/* Label */}
      <div className="mb-1.5 flex items-center justify-between">
        <label className="flex items-center gap-1.5 text-xs font-semibold text-foreground/80">
          <span className={cn('h-2 w-2 rounded-full', dotColor)} />
          {label}
        </label>
        {selectedLocation && (
          <span className="text-[10px] text-muted-foreground">{selectedLocation.country}</span>
        )}
      </div>

      {/* Selected Location Display or Search Input */}
      {!isOpen && selectedLocation ? (
        /* Compact selected-state chip */
        <button
          type="button"
          onClick={() => { setIsOpen(true); setQuery('') }}
          className={cn(
            'group flex w-full items-center justify-between rounded-xl border border-[var(--border)] bg-secondary/20 px-3 py-2.5 text-left transition-all hover:bg-secondary/40 hover:border-primary/30',
          )}
        >
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-foreground leading-tight">
              {selectedLocation.name}
            </div>
            <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
              {selectedLocation.country} · {selectedLocation.region}
            </div>
          </div>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors" />
        </button>
      ) : (
        /* Search input when open or no selection */
        <div className={cn('relative rounded-xl border border-[var(--border)] bg-background ring-2 ring-transparent transition-all', ringColor)}>
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIsOpen(true) }}
            onFocus={() => setIsOpen(true)}
            placeholder={placeholder}
            className="w-full rounded-xl bg-transparent py-2.5 pl-8 pr-8 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
            autoComplete="off"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : (
            <Globe className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/40" />
          )}
        </div>
      )}

      {/* Autocomplete Dropdown */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-60 overflow-auto rounded-xl border border-[var(--border)] bg-card shadow-2xl ring-1 ring-black/10 backdrop-blur-sm scrollbar-thin">
          {/* Header */}
          <div className="sticky top-0 flex items-center justify-between border-b border-[var(--border)]/50 bg-card/95 px-3 py-1.5 font-mono text-[10px] text-muted-foreground backdrop-blur-sm">
            <span>{query ? `${results.length} port${results.length !== 1 ? 's' : ''} found` : 'Top global ports'}</span>
            <span className="text-[9px] text-cyan-400/70">Worldwide</span>
          </div>

          {/* Port List */}
          <div className="p-1">
            {results.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                No ports match "{query}"
              </div>
            ) : (
              results.map((loc) => {
                const isSelected = selectedLocation?.id === loc.id
                return (
                  <button
                    key={loc.id}
                    type="button"
                    onClick={() => handleSelect(loc)}
                    className={cn(
                      'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition-colors',
                      isSelected
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-secondary/60 text-foreground',
                    )}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="truncate text-xs font-semibold leading-tight">{loc.name}</div>
                      <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
                        {loc.country} · {loc.region}
                        {loc.unLocode && <span className="ml-1 opacity-60">({loc.unLocode})</span>}
                      </div>
                    </div>
                    <span className={cn(
                      'shrink-0 rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase',
                      isSelected ? 'bg-primary/20 text-primary' : 'bg-secondary text-muted-foreground'
                    )}>
                      {loc.kind}
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
