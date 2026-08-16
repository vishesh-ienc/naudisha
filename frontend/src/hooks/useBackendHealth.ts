/**
 * Polls the backend health endpoint so the UI can state plainly whether it is
 * talking to a real server or running on demo data.
 *
 * Backs off while the backend is down. Developing the frontend ahead of the
 * backend is the normal case, and a fixed 20-second poll against a server that
 * does not exist produces a stream of pointless failures in every log. The
 * interval doubles up to a two-minute ceiling and snaps back to the base rate
 * the moment the backend answers, so recovery is still noticed promptly.
 */

import { useEffect, useRef, useState } from 'react'
import { probeBackend, useApiModeAware, type BackendHealth } from '@/services/backendStatus'

const MAX_INTERVAL_MS = 120_000

export function useBackendHealth(baseIntervalMs = 20_000): BackendHealth & { checking: boolean } {
  const [health, setHealth] = useState<BackendHealth>({ online: false, checkedAt: 0 })
  const [checking, setChecking] = useState(true)
  const mode = useApiModeAware()
  const intervalRef = useRef(baseIntervalMs)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const scheduleNext = () => {
      if (cancelled) return
      timer = setTimeout(run, intervalRef.current)
    }

    async function run() {
      // In Force Demo mode the backend is intentionally not contacted, so a
      // health probe would be noise in the console log.
      if (mode === 'mock') {
        if (!cancelled) {
          setHealth({ online: false, checkedAt: Date.now(), detail: 'Force Demo mode' })
          setChecking(false)
        }
        scheduleNext()
        return
      }

      if (!cancelled) setChecking(true)
      const result = await probeBackend()
      if (cancelled) return

      setHealth(result)
      setChecking(false)

      intervalRef.current = result.online
        ? baseIntervalMs
        : Math.min(intervalRef.current * 2, MAX_INTERVAL_MS)

      scheduleNext()
    }

    intervalRef.current = baseIntervalMs
    void run()

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [baseIntervalMs, mode])

  return { ...health, checking }
}
