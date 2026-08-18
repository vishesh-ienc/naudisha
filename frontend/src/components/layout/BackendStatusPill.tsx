import { Loader2 } from 'lucide-react'
import { useBackendHealth } from '@/hooks/useBackendHealth'
import { useApiModeAware } from '@/services/backendStatus'
import { cn } from '@/lib/utils'

export function BackendStatusPill({ className }: { className?: string }) {
  const health = useBackendHealth()
  const mode = useApiModeAware()

  const state =
    mode === 'mock' ? 'forced' : health.checking && health.checkedAt === 0 ? 'checking' : health.online ? 'online' : 'offline'

  const config = {
    online: {
      label: 'API Connected',
      short: 'Connected',
      dot: 'bg-emerald-500',
      tone: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
      title: health.service ? `Connected to ${health.service}` : 'Backend API connected',
    },
    offline: {
      label: 'Offline (Demo Data)',
      short: 'Offline',
      dot: 'bg-amber-500',
      tone: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
      title: health.detail ?? 'Backend unreachable; fallback data in use',
    },
    forced: {
      label: 'Demo Mode',
      short: 'Demo',
      dot: 'bg-primary',
      tone: 'border-primary/30 bg-primary/10 text-primary',
      title: 'Demo mode active',
    },
    checking: {
      label: 'Checking API…',
      short: 'Checking',
      dot: 'bg-muted-foreground',
      tone: 'border-[var(--border)] bg-secondary text-muted-foreground',
      title: 'Checking API status',
    },
  }[state]

  return (
    <div
      className={cn(
        'flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[11px]',
        config.tone,
        className,
      )}
      title={config.title}
      role="status"
    >
      {state === 'checking' ? (
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
      ) : (
        <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', config.dot)} />
      )}
      <span className="hidden sm:inline">{config.label}</span>
      <span className="sm:hidden">{config.short}</span>
    </div>
  )
}
