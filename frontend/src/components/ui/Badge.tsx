import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight tracking-wide',
  {
    variants: {
      variant: {
        neutral: 'bg-secondary text-secondary-foreground',
        live: 'bg-[var(--success)]/15 text-[var(--success)] ring-1 ring-inset ring-[var(--success)]/30',
        mock: 'bg-[var(--warning)]/15 text-[var(--warning)] ring-1 ring-inset ring-[var(--warning)]/30',
        error: 'bg-destructive/15 text-destructive ring-1 ring-inset ring-destructive/30',
        info: 'bg-primary/15 text-primary ring-1 ring-inset ring-primary/30',
        accent: 'bg-accent/15 text-accent ring-1 ring-inset ring-accent/30',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

/**
 * Marks a value's provenance inline in the UI.
 *
 * This is the visible half of the fallback requirement: telemetry records the
 * substitution, and this badge makes it impossible to mistake dummy data for a
 * real backend value while looking at the screen.
 */
export function DataBadge({ source, className }: { source: 'live' | 'mock' | 'simulated'; className?: string }) {
  const config = {
    live: { variant: 'live' as const, label: 'LIVE', title: 'Value returned by the backend' },
    mock: { variant: 'mock' as const, label: 'DEMO', title: 'Backend unavailable — placeholder data' },
    simulated: { variant: 'info' as const, label: 'SIM', title: 'Simulated for demonstration' },
  }[source]

  return (
    <Badge variant={config.variant} className={cn('font-mono', className)} title={config.title}>
      {config.label}
    </Badge>
  )
}
