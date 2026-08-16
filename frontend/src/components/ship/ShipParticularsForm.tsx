/**
 * Vessel particulars entry.
 *
 * Used in two situations:
 *  • No IMO supplied — the user provides everything.
 *  • IMO lookup returned `missing_fields` (ADDENDUM P0-2) — only the unresolved
 *    fields are requested, so the user is never asked to retype what the
 *    backend already knows.
 *
 * These values matter: the cost model's fuel and safety scores are computed from
 * them, so a route for a 90 m coaster should not be derived from a Panamax hull.
 */

import { useMemo } from 'react'
import type { ShipParticulars } from '@/types/api'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'

export const PARTICULAR_FIELDS = [
  { key: 'length_m', label: 'Length overall', unit: 'm', placeholder: '294', min: 1, max: 500 },
  { key: 'beam_m', label: 'Beam', unit: 'm', placeholder: '32.2', min: 1, max: 100 },
  { key: 'draft_m', label: 'Draft', unit: 'm', placeholder: '12.0', min: 0.5, max: 40 },
  { key: 'cruising_speed_kn', label: 'Cruising speed', unit: 'kn', placeholder: '18', min: 1, max: 50 },
  { key: 'max_speed_kn', label: 'Maximum speed', unit: 'kn', placeholder: '23', min: 1, max: 60 },
] as const

export type ParticularKey = (typeof PARTICULAR_FIELDS)[number]['key']

export const SHIP_TYPES = [
  'Container Vessel (Panamax)',
  'Container Vessel (Post-Panamax)',
  'Bulk Carrier',
  'Crude Oil Tanker',
  'LNG Carrier',
  'General Cargo',
  'Passenger Ship',
  'Offshore Supply Vessel',
]

interface ShipParticularsFormProps {
  value?: ShipParticulars
  particulars?: ShipParticulars
  onChange: (next: ShipParticulars) => void
  /** When provided, only these fields are shown. */
  onlyFields?: string[]
  disabled?: boolean
}

export function ShipParticularsForm({
  value,
  particulars,
  onChange,
  onlyFields,
  disabled,
}: ShipParticularsFormProps) {
  const currentVal = value ?? particulars ?? DEFAULT_PARTICULARS
  const fields = useMemo(
    () => (onlyFields?.length ? PARTICULAR_FIELDS.filter((f) => onlyFields.includes(f.key)) : PARTICULAR_FIELDS),
    [onlyFields],
  )

  const showType = !onlyFields?.length || onlyFields.includes('ship_type')

  const set = (key: ParticularKey, raw: string) => {
    const parsed = raw.trim() === '' ? null : Number(raw)
    onChange({ ...currentVal, [key]: parsed != null && Number.isNaN(parsed) ? null : parsed })
  }

  // maximum_speed >= cruising_speed is enforced by ShipProfile on the backend,
  // so catching it here avoids a round trip that can only fail.
  const speedConflict =
    currentVal.cruising_speed_kn != null &&
    currentVal.max_speed_kn != null &&
    currentVal.max_speed_kn < currentVal.cruising_speed_kn

  return (
    <div className="space-y-4">
      {onlyFields?.length ? (
        <div className="flex items-start gap-2 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-3 py-2.5">
          <Badge variant="mock" className="mt-px shrink-0">
            NEEDED
          </Badge>
          <p className="text-[11px] text-muted-foreground">
            The lookup could not resolve {onlyFields.length} field{onlyFields.length === 1 ? '' : 's'}. Supply{' '}
            {onlyFields.length === 1 ? 'it' : 'them'} to get an accurate route for this vessel.
          </p>
        </div>
      ) : null}

      {showType && (
        <div>
          <label htmlFor="ship-type" className="mb-1.5 block text-xs font-medium text-muted-foreground">
            Vessel type
          </label>
          <select
            id="ship-type"
            value={currentVal.ship_type ?? ''}
            disabled={disabled}
            onChange={(e) => onChange({ ...currentVal, ship_type: e.target.value || null })}
            className="h-11 w-full rounded-lg border border-[var(--input)] bg-background px-3 text-sm disabled:opacity-50"
          >
            <option value="">Select a type…</option>
            {SHIP_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <Input
            key={field.key}
            label={`${field.label} (${field.unit})`}
            value={currentVal[field.key] ?? ''}
            onChange={(e) => set(field.key, e.target.value)}
            placeholder={field.placeholder}
            inputMode="decimal"
            type="number"
            min={field.min}
            max={field.max}
            step="0.1"
            disabled={disabled}
          />
        ))}
      </div>

      {speedConflict && (
        <p className="text-[11px] text-destructive">
          Maximum speed cannot be lower than cruising speed — the backend rejects this combination.
        </p>
      )}
    </div>
  )
}

/** True when enough is known to compute a meaningful route. */
export function particularsComplete(p: ShipParticulars): boolean {
  return (
    p.length_m != null &&
    p.beam_m != null &&
    p.draft_m != null &&
    p.cruising_speed_kn != null &&
    p.max_speed_kn != null &&
    p.max_speed_kn >= p.cruising_speed_kn
  )
}

export const DEFAULT_PARTICULARS: ShipParticulars = {
  ship_type: 'Container Vessel (Panamax)',
  length_m: 294,
  beam_m: 32.2,
  draft_m: 12,
  cruising_speed_kn: 18,
  max_speed_kn: 23,
}
