/**
 * IMO number entry with live ISO 8713 validation.
 *
 * Validation is deliberately *not* shown while the user is still typing the
 * first six digits — flashing "check digit failed" at someone mid-entry is
 * hostile. Errors appear once the field reaches full length or loses focus.
 */

import { useEffect, useMemo, useState } from 'react'
import { Ship } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { SAMPLE_IMO_NUMBERS, normalizeImo, validateImo } from '@/lib/imo'
import { cn } from '@/lib/utils'

interface ImoInputProps {
  value: string
  onChange: (value: string) => void
  /** Fired with the normalised 7-digit number, or null when invalid. */
  onValidChange?: (imo: string | null) => void
  label?: string
  disabled?: boolean
  autoFocus?: boolean
  showSamples?: boolean
  className?: string
}

export function ImoInput({
  value,
  onChange,
  onValidChange,
  label = 'IMO Number',
  disabled,
  autoFocus,
  showSamples = true,
  className,
}: ImoInputProps) {
  const [touched, setTouched] = useState(false)

  const result = useMemo(() => validateImo(value), [value])
  const normalized = normalizeImo(value)

  // Only complain once there is enough input for the complaint to be fair.
  const shouldValidate = touched || normalized.length >= 7

  useEffect(() => {
    onValidChange?.(result.valid ? result.normalized : null)
  }, [result, onValidChange])

  const error = shouldValidate && !result.valid && normalized.length > 0 ? result.message : null
  const success = result.valid ? 'Valid IMO number (ISO 8713 checksum passes)' : null

  return (
    <div className={className}>
      <Input
        label={label}
        value={value}
        onChange={(e) => {
          // Permit digits plus the separators people paste, and cap the length
          // so the field cannot silently accumulate junk.
          const next = e.target.value.replace(/[^\d\s\-a-zA-Z:]/g, '').slice(0, 16)
          onChange(next)
        }}
        onBlur={() => setTouched(true)}
        placeholder="9074729"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        autoFocus={autoFocus}
        leadingIcon={<Ship className="h-4 w-4" aria-hidden />}
        error={error}
        success={success}
        hint="Seven digits. The final digit is a checksum."
        trailing={
          normalized.length > 0 ? (
            <span className="font-mono text-[10px] text-muted-foreground">
              {normalized.length}/7
            </span>
          ) : null
        }
      />

      {showSamples && (
        <div className="mt-3">
          <p className="mb-1.5 text-[11px] text-muted-foreground">Try a sample vessel</p>
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_IMO_NUMBERS.map((sample) => (
              <button
                key={sample.imo}
                type="button"
                disabled={disabled}
                onClick={() => {
                  onChange(sample.imo)
                  setTouched(true)
                }}
                className={cn(
                  'rounded-md border border-[var(--border)] px-2 py-1 text-[11px] transition-colors',
                  'hover:border-primary/40 hover:bg-primary/5 disabled:opacity-50',
                  normalized === sample.imo && 'border-primary/50 bg-primary/10',
                )}
                title={`${sample.name} — ${sample.type}`}
              >
                <span className="font-mono">{sample.imo}</span>
                <span className="ml-1.5 text-muted-foreground">{sample.name}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
            <Badge variant="neutral" className="px-1 py-0 text-[9px]">
              NOTE
            </Badge>
            Real IMO numbers — they exercise the checksum rather than bypassing it.
          </p>
        </div>
      )}
    </div>
  )
}
