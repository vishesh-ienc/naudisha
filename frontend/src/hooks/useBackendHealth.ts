/**
 * Polls the backend health endpoint so the UI can state plainly whether it is
 * talking to a real server or running on placeholder data.
 *
 * Polls slowly (20s) because this is ambient status, not a data dependency —
 * individual calls already handle their own failures. Its job is to let the user
 * know *before* they act that the backend is down.
 */

import { useEffect, useState } from 'react'
import { probeBackend, useApiModeAware, type BackendHealth } from '@/services/backendStatus'

export function useBackendHealth(intervalMs = 20_000): BackendHealth & { checking: boolean } {
  const [health, setHealth] = useState<BackendHealth>({ online: false, checkedAt: 0 })
  const [checking, setChecking] = useState(true)
  const mode = useApiModeAware()

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function check() {
      // In Force Demo mode the backend is intentionally not contacted, so a
      // health probe would be noise in the console log.
      if (mode === 'mock') {
        if (!cancelled) {
          setHealth({ online: false, checkedAt: Date.now(), detail: 'Force Demo mode' })
          setChecking(false)
        }
        return
      }

      if (!cancelled) setChecking(true)
      const result = await probeBackend()
      if (!cancelled) {
        setHealth(result)
        setChecking(false)
      }
    }

    void check()
    timer = setInterval(() => void check(), intervalMs)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [intervalMs, mode])

  return { ...health, checking }
}
