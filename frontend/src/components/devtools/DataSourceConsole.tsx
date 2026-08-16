/**
 * Data Source Console — the user-visible record of every backend interaction.
 *
 * Directly serves the requirement that fallbacks are never silent: for each call
 * it shows what was attempted, what the backend returned, whether the value on
 * screen is live or placeholder, and precisely why a substitution happened.
 *
 * Also the fastest way to tell whether a newly-shipped backend endpoint is
 * actually being reached, which makes it useful well beyond the demo.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Radio,
  Terminal,
  Trash2,
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  CircleDashed,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useApiMode, useClearTelemetry, useTelemetryEntries, useTelemetrySummary } from '@/hooks/useTelemetry'
import { FALLBACK_REASON_TEXT, type TelemetryEntry } from '@/services/telemetry'
import type { ApiMode } from '@/services/resilientApi'

const MODE_LABELS: Record<ApiMode, { label: string; hint: string }> = {
  auto: { label: 'Auto', hint: 'Try the backend, fall back to demo data on failure' },
  live: { label: 'Force Live', hint: 'Backend only — failures surface as errors' },
  mock: { label: 'Force Demo', hint: 'Never call the backend' },
}

export function DataSourceConsole() {
  const [open, setOpen] = useState(false)
  const entries = useTelemetryEntries()
  const summary = useTelemetrySummary()
  const clear = useClearTelemetry()
  const [mode, setMode] = useApiMode()

  return (
    <>
      {/* Launcher — badge count communicates degradation at a glance. */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full border px-4 py-2.5 text-xs font-medium shadow-lg backdrop-blur transition-all',
          'hover:scale-105 active:scale-95',
          summary.errors > 0
            ? 'border-destructive/40 bg-destructive/10 text-destructive'
            : summary.degraded
              ? 'border-[var(--warning)]/40 bg-[var(--warning)]/10 text-[var(--warning)]'
              : 'border-[var(--border)] bg-card/90 text-muted-foreground',
        )}
        aria-expanded={open}
        aria-label="Toggle data source console"
      >
        <Terminal className="h-3.5 w-3.5" aria-hidden />
        <span>Data Sources</span>
        {summary.total > 0 && (
          <span className="rounded-full bg-current/20 px-1.5 py-0.5 font-mono text-[10px]">
            {summary.live}L / {summary.mock}D
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.aside
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 260 }}
            className="fixed inset-x-0 bottom-0 z-40 h-[min(60vh,520px)] border-t border-[var(--border)] bg-card/98 shadow-2xl backdrop-blur"
          >
            <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
              <div className="flex items-center gap-2.5">
                <Radio className="h-4 w-4 text-primary" aria-hidden />
                <h2 className="text-sm font-semibold">Data Source Console</h2>
                <span className="text-xs text-muted-foreground">
                  {summary.total} call{summary.total === 1 ? '' : 's'}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <div className="flex rounded-lg border border-[var(--border)] p-0.5" role="group" aria-label="API mode">
                  {(Object.keys(MODE_LABELS) as ApiMode[]).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      title={MODE_LABELS[m].hint}
                      className={cn(
                        'rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors',
                        mode === m
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:bg-secondary',
                      )}
                    >
                      {MODE_LABELS[m].label}
                    </button>
                  ))}
                </div>

                <Button variant="ghost" size="icon" onClick={clear} title="Clear log">
                  <Trash2 className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setOpen(false)} title="Close">
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </header>

            {summary.degraded && (
              <div className="flex items-start gap-2 border-b border-[var(--warning)]/25 bg-[var(--warning)]/10 px-4 py-2.5 text-xs text-[var(--warning)]">
                <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>
                  <strong className="font-semibold">{summary.mock}</strong> of{' '}
                  <strong className="font-semibold">{summary.total}</strong> calls used placeholder data.
                  Values marked <span className="font-mono">DEMO</span> in the interface did not come from the backend.
                </span>
              </div>
            )}

            <div className="scrollbar-thin h-[calc(100%-var(--console-chrome,3.25rem))] overflow-y-auto overscroll-contain">
              {entries.length === 0 ? (
                <EmptyState />
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {entries.map((entry) => (
                    <TelemetryRow key={entry.id} entry={entry} />
                  ))}
                </ul>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 py-12 text-center">
      <CircleDashed className="h-8 w-8 text-muted-foreground/40" aria-hidden />
      <p className="text-sm text-muted-foreground">No backend calls yet</p>
      <p className="max-w-xs text-xs text-muted-foreground/70">
        Every request appears here with its outcome and data source.
      </p>
    </div>
  )
}

const OUTCOME_CONFIG = {
  success: { icon: CheckCircle2, tone: 'text-[var(--success)]', label: 'LIVE' },
  fallback: { icon: AlertTriangle, tone: 'text-[var(--warning)]', label: 'DEMO' },
  error: { icon: XCircle, tone: 'text-destructive', label: 'ERROR' },
  skipped: { icon: CircleDashed, tone: 'text-primary', label: 'DEMO' },
} as const

function TelemetryRow({ entry }: { entry: TelemetryEntry }) {
  const [expanded, setExpanded] = useState(false)
  const config = OUTCOME_CONFIG[entry.outcome]
  const Icon = config.icon

  return (
    <li>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-secondary/50"
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
        )}

        <Icon className={cn('h-4 w-4 shrink-0', config.tone)} aria-hidden />

        <span className="w-12 shrink-0 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
          {entry.method}
        </span>

        <span className="min-w-0 flex-1 truncate font-mono text-xs">{entry.endpoint}</span>

        {entry.httpStatus && (
          <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{entry.httpStatus}</span>
        )}

        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{entry.durationMs}ms</span>

        <Badge
          variant={
            entry.outcome === 'success' ? 'live' : entry.outcome === 'error' ? 'error' : 'mock'
          }
          className="shrink-0 font-mono"
        >
          {config.label}
        </Badge>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden bg-secondary/30"
          >
            <div className="space-y-3 px-4 py-3 pl-14 text-xs">
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
                <span>
                  <strong className="font-medium text-foreground">Operation:</strong> {entry.label}
                </span>
                <span>
                  <strong className="font-medium text-foreground">At:</strong>{' '}
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
              </div>

              {entry.fallbackReason && (
                <div className="rounded-md border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-3 py-2">
                  <p className="font-medium text-[var(--warning)]">
                    Fell back to placeholder data — {FALLBACK_REASON_TEXT[entry.fallbackReason]}
                  </p>
                  {entry.detail && (
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">{entry.detail}</p>
                  )}
                </div>
              )}

              {entry.outcome === 'error' && entry.detail && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                  <p className="font-medium text-destructive">Request failed</p>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground">{entry.detail}</p>
                </div>
              )}

              {entry.requestBody !== undefined && (
                <JsonBlock title="Request" value={entry.requestBody} />
              )}
              {entry.responseBody !== undefined && (
                <JsonBlock
                  title={entry.source === 'live' ? 'Response (from backend)' : 'Response (placeholder data)'}
                  value={entry.responseBody}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const json = JSON.stringify(value, null, 2)
  const truncated = json.length > 2400 ? `${json.slice(0, 2400)}\n… (truncated)` : json

  return (
    <div>
      <p className="mb-1 font-medium text-muted-foreground">{title}</p>
      <pre className="scrollbar-thin max-h-52 overflow-auto rounded-md border border-[var(--border)] bg-background px-3 py-2 font-mono text-[11px] leading-relaxed">
        {truncated}
      </pre>
    </div>
  )
}
