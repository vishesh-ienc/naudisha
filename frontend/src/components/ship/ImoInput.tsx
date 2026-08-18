/**
 * IMO number entry with live ISO 8713 validation.
 *
 * Validation is deliberately *not* shown while the user is still typing the
 * first six digits — flashing "check digit failed" at someone mid-entry is
 * hostile. Errors appear once the field reaches full length or loses focus.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Ship } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { normalizeImo, validateImo } from '@/lib/imo'

interface ImoInputProps {
  value: string
  onChange: (value: string) => void
  /** Fired with the normalised 7-digit number, or null when invalid. */
  onValidChange?: (imo: string | null) => void
  label?: string
  disabled?: boolean
  autoFocus?: boolean
  className?: string
}

export function ImoInput({
  value,
  onChange,
  onValidChange,
  label = 'IMO Number',
  disabled,
  autoFocus,
  className,
}: ImoInputProps) {
  const [touched, setTouched] = useState(false)

  const result = useMemo(() => validateImo(value), [value])
  const normalized = normalizeImo(value)

  // Only complain once there is enough input for the complaint to be fair.
  const shouldValidate = touched || normalized.length >= 7

  const prevValidRef = useRef<string | null>(undefined as any)
  const currentValid = result.valid ? result.normalized : null

  useEffect(() => {
    if (prevValidRef.current !== currentValid) {
      prevValidRef.current = currentValid
      onValidChange?.(currentValid)
    }
  }, [currentValid, onValidChange])

  const error = shouldValidate && !result.valid && normalized.length > 0 ? result.message : null
  const success = result.valid ? 'Valid IMO number (ISO 8713 checksum verified)' : null

  return (
    <div className={className}>
      <Input
        label={label}
        value={value}
        onChange={(e) => {
          // Permit digits plus standard separators
          const next = e.target.value.replace(/[^\d\s\-a-zA-Z:]/g, '').slice(0, 16)
          onChange(next)
        }}
        onBlur={() => setTouched(true)}
        placeholder="e.g. 9811000"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        autoFocus={autoFocus}
        leadingIcon={<Ship className="h-4 w-4 text-muted-foreground" aria-hidden />}
        error={error}
        success={success}
        hint="7-digit IMO ship identification number with ISO 8713 check digit."
        trailing={
          normalized.length > 0 ? (
            <span className="font-mono text-[10px] text-muted-foreground">
              {normalized.length}/7
            </span>
          ) : null
        }
      />
    </div>
  )
}
