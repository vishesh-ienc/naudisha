import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merges Tailwind classes cleanly with clsx and tailwind-merge.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * Generates a unique string identifier with an optional prefix.
 */
export function uid(prefix: string = 'id'): string {
  const randomPart = Math.random().toString(36).substring(2, 9)
  const timePart = Date.now().toString(36)
  return `${prefix}_${timePart}_${randomPart}`
}
