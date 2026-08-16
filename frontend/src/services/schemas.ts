/**
 * Runtime validation of every backend response.
 *
 * Why this exists: TypeScript types vanish at runtime. If the backend returns
 * `latitude` as a string, or omits `distance_nm`, plain `fetch().json()` hands us
 * a malformed object that explodes three components later with a useless stack.
 *
 * Validating at the network boundary means a contract violation is caught at the
 * exact moment it arrives, named precisely ("route.2.latitude: expected number,
 * received string"), logged to the Data Source Console, and converted into a
 * clean fallback to mock data. That precision is the whole point — it turns
 * "the app broke" into "the backend sent the wrong shape, here is the field".
 *
 * Leniency policy: unknown keys are STRIPPED, not rejected. A backend that adds
 * fields ahead of the contract must never break the frontend.
 */

import { z } from 'zod'

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export const coordinateSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
})

/**
 * Accepts ISO-8601. Deliberately not `z.iso.datetime()` — that rejects offsets
 * like "+05:30" in some configurations, and a timestamp the backend considers
 * valid must not be treated as a contract violation. We only require that
 * JavaScript can parse it into a real instant.
 */
export const isoTimestampSchema = z
  .string()
  .refine((v) => !Number.isNaN(Date.parse(v)), { message: 'not a parseable ISO-8601 timestamp' })

export const shipStatusSchema = z.enum(['underway', 'stopped', 'unknown'])
export const routeStatusSchema = z.enum(['optimal', 'updating', 'unavailable'])

/**
 * The contract fixes three route_status values, but an unrecognised one should
 * degrade to 'unavailable' rather than fail the whole payload — a rendering
 * concern must never cost us an otherwise-valid route.
 */
export const lenientRouteStatusSchema = z
  .string()
  .transform((v) => (routeStatusSchema.safeParse(v).success ? (v as 'optimal' | 'updating' | 'unavailable') : 'unavailable' as const))

// ---------------------------------------------------------------------------
// Ship particulars (ADDENDUM P0-2)
// ---------------------------------------------------------------------------

export const shipParticularsSchema = z.object({
  ship_type: z.string().nullable().optional(),
  length_m: z.number().positive().nullable().optional(),
  beam_m: z.number().positive().nullable().optional(),
  draft_m: z.number().positive().nullable().optional(),
  cruising_speed_kn: z.number().positive().nullable().optional(),
  max_speed_kn: z.number().positive().nullable().optional(),
})

export const shipResponseSchema = z.object({
  imo_number: z.string(),
  name: z.string(),
  status: shipStatusSchema,
  position: coordinateSchema,
  // ADDENDUM — optional, absence is normal against a v1 backend.
  ship: shipParticularsSchema.optional(),
  source: z.enum(['registry', 'ais', 'defaults', 'user_provided']).optional(),
  missing_fields: z.array(z.string()).optional(),
})

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export const legEnvironmentSchema = z.object({
  wind_speed_kn: z.number().nullable().optional(),
  wind_direction_deg: z.number().nullable().optional(),
  wave_height_m: z.number().nullable().optional(),
  wave_period_s: z.number().nullable().optional(),
  current_speed_kn: z.number().nullable().optional(),
  current_direction_deg: z.number().nullable().optional(),
})

export const routeLegSchema = z.object({
  from: coordinateSchema,
  to: coordinateSchema,
  distance_nm: z.number().nonnegative(),
  travel_time_hours: z.number().nonnegative().optional(),
  eta: isoTimestampSchema.optional(),
  cost: z.number().optional(),
  environment: legEnvironmentSchema.optional(),
})

/**
 * A route of fewer than two points cannot be drawn as a line. We accept it —
 * the zero-distance case in the backend legitimately returns a single point —
 * and let the map layer decide how to present it.
 */
export const routePathSchema = z.array(coordinateSchema)

export const routePreviewResponseSchema = z.object({
  imo_number: z.string(),
  status: z.string(),
  route: routePathSchema,
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  // ADDENDUM
  departure_time: isoTimestampSchema.optional(),
  eta: isoTimestampSchema.optional(),
  baseline_cost: z.number().optional(),
  efficiency_gain_percent: z.number().optional(),
  legs: z.array(routeLegSchema).optional(),
})

export const trackingStartResponseSchema = z.object({
  imo_number: z.string(),
  tracking: z.boolean(),
  message: z.string(),
})

export const shipStatusResponseSchema = z.object({
  imo_number: z.string(),
  status: shipStatusSchema,
  position: coordinateSchema,
  timestamp: isoTimestampSchema,
  // ADDENDUM
  destination: coordinateSchema.nullable().optional(),
  route_status: lenientRouteStatusSchema.optional(),
})

export const currentRouteResponseSchema = z.object({
  imo_number: z.string(),
  route_status: lenientRouteStatusSchema,
  route: routePathSchema,
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  updated_at: isoTimestampSchema,
  // ADDENDUM
  destination: coordinateSchema.nullable().optional(),
  baseline_cost: z.number().optional(),
  legs: z.array(routeLegSchema).optional(),
})

// ---------------------------------------------------------------------------
// Live messages (§10/§11)
// ---------------------------------------------------------------------------

export const routeAlertSchema = z.object({
  id: z.string(),
  severity: z.enum(['critical', 'warning', 'info']).catch('warning'),
  kind: z.string(),
  message: z.string(),
  position: coordinateSchema.nullable().optional(),
  radius_nm: z.number().nonnegative().nullable().optional(),
  detected_at: isoTimestampSchema.optional(),
})

export const routeUpdateMessageSchema = z.object({
  type: z.literal('route_update'),
  timestamp: isoTimestampSchema,
  position: coordinateSchema,
  route: routePathSchema,
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  reason: z.string(),
  // ADDENDUM
  alerts: z.array(routeAlertSchema).optional(),
  legs: z.array(routeLegSchema).optional(),
})

export const positionUpdateMessageSchema = z.object({
  type: z.literal('position_update'),
  timestamp: isoTimestampSchema,
  position: coordinateSchema,
})

export const liveMessageSchema = z.discriminatedUnion('type', [
  routeUpdateMessageSchema,
  positionUpdateMessageSchema,
])

// ---------------------------------------------------------------------------
// Errors and health
// ---------------------------------------------------------------------------

export const apiErrorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    missing_fields: z.array(z.string()).optional(),
  }),
})

export const healthResponseSchema = z.object({
  status: z.string(),
  service: z.string(),
  version: z.string().optional(),
  providers: z.record(z.string(), z.boolean()).optional(),
})

// ---------------------------------------------------------------------------
// Error formatting
// ---------------------------------------------------------------------------

/**
 * Renders a ZodError as a short, human-readable list of field paths.
 * This string is what appears in the Data Source Console when a response fails
 * validation, so it must name the offending field precisely.
 */
export function formatSchemaError(error: z.ZodError): string {
  return error.issues
    .slice(0, 5)
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join('.') : '(root)'
      return `${path}: ${issue.message}`
    })
    .join('; ')
}
