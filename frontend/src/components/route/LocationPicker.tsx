/**
 * Start / destination selection.
 *
 * Three ways in, because each suits a different user: a preset offshore
 * waypoint, manual coordinate entry, or clicking the chart. Coordinates are the
 * canonical value — place names are labels only, never sent as routing input
 * (FRONTEND_DEVELOPMENT_WORKFLOW §3).
 */

import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Crosshair, MapPin, ChevronDown, AlertTriangle } from 'lucide-react'
import type { Coordinate } from '@/types/api'
import { PRESET_LOCATIONS, validateSelectionPoint } from '@/lib/geo'
import { formatCoordinate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'

interface LocationPickerProps {
  label: string
  value: Coordinate | null
  onChange: (c: Coordinate | null) => void
  /** True while this field is the target of a map click. */
  picking?: boolean
  onPickingChange?: (picking: boolean) => void
  onPickOnMap?: () => void
  accent?: 'start' | 'destination'
}

export function LocationPicker({
  label,
  value,
  onChange,
  picking = false,
  onPickingChange,
  onPickOnMap,
  accent = 'start',
}: LocationPickerProps) {
  const [showPresets, setShowPresets] = useState(false)
  const [manual, setManual] = useState({ lat: '', lon: '' })
  const [manualError, setManualError] = useState<string | null>(null)

  const validity = value ? validateSelectionPoint(value) : null
  const dotColour = accent === 'start' ? 'bg-[var(--success)]' : 'bg-destructive'

  const applyManual = () => {
    const lat = Number(manual.lat)
    const lon = Number(manual.lon)

    if (!manual.lat.trim() || !manual.lon.trim() || Number.isNaN(lat) || Number.isNaN(lon)) {
      setManualError('Enter both latitude and longitude as numbers.')
      return
    }
    if (lat < -90 || lat > 90) {
      setManualError('Latitude must be between -90 and 90.')
      return
    }
    if (lon < -180 || lon > 180) {
      setManualError('Longitude must be between -180 and 180.')
      return
    }

    const candidate = { latitude: lat, longitude: lon }
    const check = validateSelectionPoint(candidate)
    if (!check.ok) {
      setManualError(check.message ?? 'Invalid coordinate.')
      return
    }

    setManualError(null)
    onChange(candidate)
    setShowPresets(false)
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className={cn('h-2 w-2 rounded-full', dotColour)} aria-hidden />
          {label}
        </span>
        <button
          type="button"
          onClick={() => {
            if (onPickOnMap) onPickOnMap()
            else onPickingChange?.(!picking)
          }}
          className={cn(
            'flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors',
            picking ? 'bg-primary text-primary-foreground' : 'text-primary hover:bg-primary/10',
          )}
        >
          <Crosshair className="h-3 w-3" aria-hidden />
          {picking ? 'Click the chart…' : 'Pick on chart'}
        </button>
      </div>

      <div
        className={cn(
          'rounded-lg border transition-colors',
          picking ? 'border-primary ring-2 ring-primary/20' : 'border-[var(--input)]',
        )}
      >
        <button
          type="button"
          onClick={() => setShowPresets((v) => !v)}
          className="flex w-full items-center gap-2 px-3 py-2.5 text-left"
        >
          <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1">
            {value ? (
              <span className="block truncate font-mono text-xs">{formatCoordinate(value, 4)}</span>
            ) : (
              <span className="text-sm text-muted-foreground/70">Not set</span>
            )}
          </span>
          <ChevronDown
            className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', showPresets && 'rotate-180')}
            aria-hidden
          />
        </button>

        <AnimatePresence initial={false}>
          {showPresets && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden border-t border-[var(--border)]"
            >
              <div className="max-h-44 overflow-y-auto scrollbar-thin">
                {PRESET_LOCATIONS.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    onClick={() => {
                      onChange(preset.coordinate)
                      setShowPresets(false)
                      setManualError(null)
                    }}
                    className="flex w-full flex-col items-start px-3 py-2 text-left transition-colors hover:bg-secondary"
                  >
                    <span className="text-xs font-medium">{preset.name}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {preset.detail} · {formatCoordinate(preset.coordinate, 2)}
                    </span>
                  </button>
                ))}
              </div>

              <div className="border-t border-[var(--border)] p-2.5">
                <p className="mb-1.5 text-[10px] font-medium text-muted-foreground">Or enter coordinates</p>
                <div className="flex gap-1.5">
                  <input
                    value={manual.lat}
                    onChange={(e) => setManual((m) => ({ ...m, lat: e.target.value }))}
                    placeholder="Lat"
                    inputMode="decimal"
                    className="h-8 w-full min-w-0 rounded-md border border-[var(--input)] bg-background px-2 font-mono text-xs"
                  />
                  <input
                    value={manual.lon}
                    onChange={(e) => setManual((m) => ({ ...m, lon: e.target.value }))}
                    placeholder="Lon"
                    inputMode="decimal"
                    className="h-8 w-full min-w-0 rounded-md border border-[var(--input)] bg-background px-2 font-mono text-xs"
                  />
                  <Button size="sm" variant="secondary" onClick={applyManual} className="shrink-0">
                    Set
                  </Button>
                </div>
                {manualError && (
                  <p className="mt-1.5 flex items-start gap-1 text-[10px] text-destructive">
                    <AlertTriangle className="mt-px h-3 w-3 shrink-0" aria-hidden />
                    {manualError}
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {validity && !validity.ok && (
        <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[var(--warning)]">
          <AlertTriangle className="mt-px h-3 w-3 shrink-0" aria-hidden />
          {validity.message}
        </p>
      )}
    </div>
  )
}
