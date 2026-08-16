/**
 * Low-level HTTP transport: timeouts, retries, and typed failure classification.
 *
 * This layer never decides whether to fall back to mock data — it only reports
 * precisely *how* a request failed. `resilientApi` owns the fallback policy.
 * Keeping those separate is what makes the policy testable and the failure
 * reporting honest.
 */

import { z } from 'zod'
import { apiErrorResponseSchema, formatSchemaError } from './schemas'
import type { ApiErrorDetail } from '@/types/api'

export const DEFAULT_TIMEOUT_MS = 8000

export type HttpFailureKind =
  | 'network' // could not reach the server at all
  | 'timeout' // exceeded the deadline
  | 'server' // 5xx
  | 'client' // 4xx — a real error the user must see, never masked by mock data
  | 'not_found' // 404 — usually "endpoint not built yet"
  | 'schema' // 2xx but off-contract

export class HttpError extends Error {
  readonly kind: HttpFailureKind
  readonly status?: number
  readonly apiError?: ApiErrorDetail
  readonly detail: string

  constructor(kind: HttpFailureKind, detail: string, status?: number, apiError?: ApiErrorDetail) {
    super(detail)
    this.name = 'HttpError'
    this.kind = kind
    this.detail = detail
    if (status !== undefined) this.status = status
    if (apiError !== undefined) this.apiError = apiError
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  timeoutMs?: number
  /** Retries apply only to transient failures (network/timeout/5xx). */
  retries?: number
  signal?: AbortSignal
}

/**
 * Performs a request and validates the response against `schema`.
 * Throws `HttpError` on any failure — including a 2xx whose body is off-contract.
 */
export async function request<T>(
  endpoint: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, timeoutMs = DEFAULT_TIMEOUT_MS, retries = 1, signal } = options

  let lastError: HttpError | undefined

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await attemptRequest(endpoint, schema, { method, body, timeoutMs, signal })
    } catch (err) {
      const httpError = err instanceof HttpError ? err : new HttpError('network', String(err))
      lastError = httpError

      // 4xx responses are deterministic — retrying produces the same answer and
      // only delays showing the user their actual problem.
      if (httpError.kind === 'client' || httpError.kind === 'not_found' || httpError.kind === 'schema') {
        throw httpError
      }
      if (attempt === retries) throw httpError

      // Exponential backoff with jitter, so parallel calls don't retry in lockstep.
      const backoff = Math.min(250 * 2 ** attempt, 2000) + Math.random() * 120
      await new Promise((resolve) => setTimeout(resolve, backoff))
    }
  }

  throw lastError ?? new HttpError('network', 'Request failed with no recorded error')
}

async function attemptRequest<T>(
  endpoint: string,
  schema: z.ZodType<T>,
  opts: { method: string; body?: unknown; timeoutMs: number; signal?: AbortSignal },
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), opts.timeoutMs)

  // Bridge an external abort (component unmount) into our controller.
  const onExternalAbort = () => controller.abort()
  opts.signal?.addEventListener('abort', onExternalAbort)

  let response: Response
  try {
    response = await fetch(endpoint, {
      method: opts.method,
      headers: opts.body !== undefined ? { 'Content-Type': 'application/json' } : {},
      ...(opts.body !== undefined && { body: JSON.stringify(opts.body) }),
      signal: controller.signal,
    })
  } catch (err) {
    if (controller.signal.aborted && (err as Error)?.name !== 'AbortError') {
      throw new HttpError('timeout', `No response within ${opts.timeoutMs}ms`)
    }
    if ((err as Error)?.name === 'AbortError' || (err as Error)?.name === 'TimeoutError') {
      throw new HttpError('timeout', `Request aborted after ${opts.timeoutMs}ms`)
    }
    throw new HttpError('network', `Cannot reach backend: ${(err as Error).message}`)
  } finally {
    clearTimeout(timer)
    opts.signal?.removeEventListener('abort', onExternalAbort)
  }

  if (!response.ok) {
    throw await buildErrorFromResponse(response)
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new HttpError('schema', 'Response body was not valid JSON', response.status)
  }

  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    throw new HttpError(
      'schema',
      `Off-contract response — ${formatSchemaError(parsed.error)}`,
      response.status,
    )
  }

  return parsed.data
}

/**
 * Extracts the contract's `{ error: { code, message } }` envelope when present.
 * FastAPI's default 422 body has a different shape, so that is handled too —
 * otherwise a validation error would surface as an unhelpful "unknown error".
 */
async function buildErrorFromResponse(response: Response): Promise<HttpError> {
  const kind: HttpFailureKind =
    response.status === 404 ? 'not_found' : response.status >= 500 ? 'server' : 'client'

  let bodyText = ''
  try {
    bodyText = await response.text()
  } catch {
    return new HttpError(kind, `HTTP ${response.status} ${response.statusText}`, response.status)
  }

  try {
    const json: unknown = JSON.parse(bodyText)

    const contractError = apiErrorResponseSchema.safeParse(json)
    if (contractError.success) {
      return new HttpError(
        kind,
        contractError.data.error.message,
        response.status,
        contractError.data.error,
      )
    }

    // FastAPI validation error: { detail: [{ loc, msg, type }, ...] }
    const fastApiDetail = (json as { detail?: unknown })?.detail
    if (Array.isArray(fastApiDetail)) {
      const messages = fastApiDetail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const loc = Array.isArray(d.loc) ? d.loc.slice(1).join('.') : ''
          return loc ? `${loc}: ${d.msg}` : d.msg
        })
        .filter(Boolean)
        .join('; ')
      return new HttpError(kind, messages || `HTTP ${response.status}`, response.status, {
        code: 'INVALID_COORDINATES',
        message: messages,
      })
    }
    if (typeof fastApiDetail === 'string') {
      return new HttpError(kind, fastApiDetail, response.status)
    }
  } catch {
    // Not JSON — fall through to the generic message.
  }

  return new HttpError(kind, `HTTP ${response.status} ${response.statusText}`, response.status)
}
