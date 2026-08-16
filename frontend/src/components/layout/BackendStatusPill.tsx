import { motion } from 'framer-motion'
import { Cloud, CloudOff, Loader2, FlaskConical } from 'lucide-react'
import { useBackendHealth } from '@/hooks/useBackendHealth'
import { useApiModeAware } from '@/services/backendStatus'
import { cn } from '@/lib/utils'

/**
 * Ambient backend-connectivity indicator.
 *
 * States it must distinguish — conflating any two of these makes the demo
 * confusing to explain:
 *   • Connected      — backend reachable, values are real
 *   • Demo data      — backend unreachable, showing placeholders
 *   • Demo mode      — deliberately not calling the backend
 *   • Checking       — first probe in flight
 */
export function BackendStatusPill({ className }: { className?: string }) {
  const health = useBackendHealth()
  const mode = useApiModeAware()

  const state =
    mode === 'mock' ? 'forced' : health.checking && health.checkedAt === 0 ? 'checking' : health.online ? 'online' : 'offline'

  const config = {
    online: {
      icon: Cloud,
      label: 'Backend connected',
      short: 'Live',
      tone: 'border-[var(--success)]/35 bg-[var(--success)]/10 text-[var(--success)]',
      title: health.service ? `Connected to ${health.service}` : 'Backend reachable',
    },
    offline: {
      icon: CloudOff,
      label: 'Backend offline — using demo data',
      short: 'Demo data',
      tone: 'border-[var(--warning)]/35 bg-[var(--warning)]/10 text-[var(--warning)]',
      title: health.detail ?? 'Backend unreachable; placeholder data in use',
    },
    forced: {
      icon: FlaskConical,
      label: 'Demo mode',
      short: 'Demo mode',
      tone: 'border-primary/35 bg-primary/10 text-primary',
      title: 'Force Demo mode — the backend is not being contacted',
    },
    checking: {
      icon: Loader2,
      label: 'Checking backend…',
      short: 'Checking',
      tone: 'border-[var(--border)] bg-secondary text-muted-foreground',
      title: 'Probing backend availability',
    },
  }[state]

  const Icon = config.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium',
        config.tone,
        className,
      )}
      title={config.title}
      role="status"
    >
      <Icon className={cn('h-3 w-3', state === 'checking' && 'animate-spin')} aria-hidden />
      <span className="hidden sm:inline">{config.label}</span>
      <span className="sm:hidden">{config.short}</span>
    </motion.div>
  )
}
