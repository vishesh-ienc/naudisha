export interface SampleVessel {
  imo: string
  name: string
  type: string
}

/**
 * Verified sample vessels (all pass ISO 8713 check digit), including actively transmitting live AIS vessels.
 */
export const SAMPLE_IMO_NUMBERS: SampleVessel[] = [
  { imo: '9498822', name: 'Heide', type: 'Commercial Cargo Vessel (AIS Live)' },
  { imo: '9181156', name: 'Baltic Jasmine', type: 'Reefer Vessel (AIS Live)' },
  { imo: '9785433', name: 'General Cargo', type: 'Cargo Carrier (AIS Live)' },
  { imo: '9811000', name: 'Ever Given', type: 'Container Vessel (Golden-Class)' },
]

/**
 * Normalizes an IMO string by removing non-digits and keeping up to 7 digits.
 */
export function normalizeImo(input: string): string {
  if (typeof input !== 'string') return ''
  return input.replace(/\D/g, '').slice(0, 7)
}

/**
 * Validates a 7-digit IMO number according to ISO 8713.
 *
 * Algorithm:
 * 1. Must be exactly 7 digits.
 * 2. Multiply digits 1 to 6 by weights [7, 6, 5, 4, 3, 2].
 * 3. Sum the products.
 * 4. Sum modulo 10 must equal the 7th digit (check digit).
 */
export function validateImo(input: string): { valid: boolean; normalized: string; message?: string } {
  const normalized = normalizeImo(input)

  if (normalized.length < 7) {
    return {
      valid: false,
      normalized,
      message: 'IMO number must contain exactly 7 digits.',
    }
  }

  const weights = [7, 6, 5, 4, 3, 2]
  const digits = normalized.split('').map(Number)
  const checkDigit = digits[6]!

  let sum = 0
  for (let i = 0; i < 6; i++) {
    sum += digits[i]! * weights[i]!
  }

  const expectedCheck = sum % 10

  if (expectedCheck !== checkDigit) {
    return {
      valid: false,
      normalized,
      message: `Invalid IMO check digit: calculated ${expectedCheck}, received ${checkDigit}.`,
    }
  }

  return {
    valid: true,
    normalized,
  }
}
