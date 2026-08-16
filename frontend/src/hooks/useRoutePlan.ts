/**
 * Drives an asynchronous route plan from submit through to result.
 *
 * A cold plan takes 70-85s because the backend is fetching live Copernicus
 * currents and waves for the whole corridor. Rather than block, we submit a job
 * and poll — which also means we can show the user honest progress and a
 * realistic estimate instead of an indefinite spinner.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { pollRoutePlan, submitRoutePlan } from '@/services/apiClient'
import { HttpError } from '@/services/http'
import { telemetry } from '@/services/telemetry'
import type { RoutePreviewRequest, RoutePreviewResponse } from '@/types/api'

const POLL_INTERVAL_MS = 2500
/** Give up well past the observed worst case rather than mid-plan. */
const MAX_WAIT_MS = 240_000
/** Observed cold-plan duration, used only to render a progress estimate. */
const TYPICAL_PLAN_SECONDS = 80

export type PlanPhase = 'idle' | 'submitting' | 'planning' | 'ready' | 'failed'

export interface RoutePlanState {
  phase: PlanPhase
  route: RoutePreviewResponse | null
  elapsedSeconds: number
  /** 0-100, capped below 100 until the result actually lands. */
  progressPercent: number
  error: string | null
  errorCode: string | null
  /** True when the backend served a cached plan, i.e. it returned immediately. */
  fromCache: boolean
}

const INITIAL: RoutePlanState = {
  phase: 'idle',
  route: null,
  elapsedSeconds: 0,
  progressPercent: 0,
  error: null,
  errorCode: null,
  fromCache: false,
}

export function useRoutePlan() {
  const [state, setState] = useState<RoutePlanState>(INITIAL)
  const cancelRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  useEffect(() => {
    return () => {
      cancelRef.current = true
      clearTimer()
    }
  }, [])

  const reset = useCallback(() => {
    cancelRef.current = true
    clearTimer()
    setState(INITIAL)
  }, [])

  const plan = useCallback(async (payload: RoutePreviewRequest) => {
    cancelRef.current = false
    clearTimer()
    setState({ ...INITIAL, phase: 'submitting' })

    const startedAt = Date.now()

    // Local ticker so elapsed time advances smoothly between polls rather than
    // jumping every 2.5s.
    timerRef.current = setInterval(() => {
      if (cancelRef.current) return
      const elapsed = (Date.now() - startedAt) / 1000
      setState((prev) =>
        prev.phase === 'planning' || prev.phase === 'submitting'
          ? {
              ...prev,
              elapsedSeconds: elapsed,
              // Asymptotic: approaches but never reaches 100 while waiting, so
              // the bar never implies completion before the route exists.
              progressPercent: Math.min(95, (1 - Math.exp(-elapsed / TYPICAL_PLAN_SECONDS)) * 118),
            }
          : prev,
      )
    }, 250)

    try {
      const job = await submitRoutePlan(payload)

      if (job.status === 'ready' && job.route) {
        clearTimer()
        telemetry.log('info', `Route plan served from backend cache in ${job.elapsed_seconds}s`, 'useRoutePlan')
        setState({
          phase: 'ready',
          route: job.route,
          elapsedSeconds: job.elapsed_seconds,
          progressPercent: 100,
          error: null,
          errorCode: null,
          fromCache: true,
        })
        return job.route
      }

      if (job.status === 'failed') {
        clearTimer()
        setState({
          ...INITIAL,
          phase: 'failed',
          error: job.error?.message ?? 'Route planning failed.',
          errorCode: job.error?.code ?? 'INTERNAL_ERROR',
        })
        return null
      }

      setState((prev) => ({ ...prev, phase: 'planning' }))

      while (!cancelRef.current && Date.now() - startedAt < MAX_WAIT_MS) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
        if (cancelRef.current) return null

        let polled
        try {
          polled = await pollRoutePlan(job.job_id)
        } catch (err) {
          // A single failed poll is not fatal — the job keeps running on the
          // server, so retry rather than discarding a plan already underway.
          telemetry.log('warn', `Plan poll failed, retrying: ${String(err)}`, 'useRoutePlan')
          continue
        }

        if (polled.status === 'ready' && polled.route) {
          clearTimer()
          setState({
            phase: 'ready',
            route: polled.route,
            elapsedSeconds: polled.elapsed_seconds,
            progressPercent: 100,
            error: null,
            errorCode: null,
            fromCache: false,
          })
          return polled.route
        }

        if (polled.status === 'failed') {
          clearTimer()
          setState({
            ...INITIAL,
            phase: 'failed',
            error: polled.error?.message ?? 'Route planning failed.',
            errorCode: polled.error?.code ?? 'INTERNAL_ERROR',
          })
          return null
        }
      }

      clearTimer()
      if (!cancelRef.current) {
        setState({
          ...INITIAL,
          phase: 'failed',
          error: `Planning did not complete within ${Math.round(MAX_WAIT_MS / 1000)}s.`,
          errorCode: 'TIMEOUT',
        })
      }
      return null
    } catch (err) {
      clearTimer()
      const message =
        err instanceof HttpError
          ? err.kind === 'network' || err.kind === 'timeout'
            ? 'Cannot reach the routing backend. Check that it is running on port 8000.'
            : err.detail
          : String(err)

      setState({
        ...INITIAL,
        phase: 'failed',
        error: message,
        errorCode: err instanceof HttpError ? (err.apiError?.code ?? 'BACKEND_UNAVAILABLE') : 'UNKNOWN',
      })
      return null
    }
  }, [])

  return { ...state, plan, reset }
}
