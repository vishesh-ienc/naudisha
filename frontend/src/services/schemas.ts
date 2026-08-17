/**
 * Runtime validation of every backend response.
 *
 * TypeScript types vanish at runtime; these do not. A contract violation is
 * caught where it arrives, named precisely ("route.2.latitude: expected
 * number"), logged, and turned into a clean failure rather than a crash three
 * components later.
 *
 * Unknown keys are stripped, never rejected — a backend that adds fields ahead
 * of the frontend must not break it.
 */

import { z } from 'zod'

export const coordinateSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
})

/** Only requires that JavaScript can parse it into a real instant. */
export const isoTimestampSchema = z
  .string()
  .refine((v) => !Number.isNaN(Date.parse(v)), { message: 'not a parseable ISO-8601 timestamp' })

export const shipStatusSchema = z.enum(['underway', 'stopped', 'unknown'])

/** An unrecognised route_status degrades rather than failing the payload. */
export const lenientRouteStatusSchema = z
  .string()
  .transform((v) =>
    v === 'optimal' || v === 'updating' || v === 'unavailable'
      ? (v as 'optimal' | 'updating' | 'unavailable')
      : ('unavailable' as const),
  )

export const shipProfileSchema = z.object({
  ship_type: z.string(),
  length_m: z.number().positive(),
  beam_m: z.number().positive(),
  draft_m: z.number().positive(),
  cruising_speed_kn: z.number().positive(),
  max_speed_kn: z.number().positive(),
})

export const shipResponseSchema = z.object({
  imo_number: z.string(),
  name: z.string(),
  status: shipStatusSchema,
  // Null is the honest, common case: no live AIS transponder report.
  position: coordinateSchema.nullable(),
  ship: shipProfileSchema.optional(),
  // Provenance — tells the frontend whether this is real AIS data
  is_live_position: z.boolean().optional(),
  position_source: z.string().optional(),
})

const optionalNumber = z.number().nullable().optional()

export const routeLegSchema = z.object({
  from: coordinateSchema,
  to: coordinateSchema,
  distance_nm: z.number().nonnegative(),
  travel_time_hours: z.number().nonnegative(),
  bearing: z.number(),
  cost: z.number(),

  wind_speed_kn: optionalNumber,
  wind_direction_deg: optionalNumber,
  wave_height_m: optionalNumber,
  wave_period_s: optionalNumber,
  current_speed_kn: optionalNumber,
  current_direction_deg: optionalNumber,

  relative_wind_dir: optionalNumber,
  relative_current_dir: optionalNumber,
  along_track_current_kn: optionalNumber,
  effective_speed_kn: optionalNumber,

  time_score: optionalNumber,
  fuel_score: optionalNumber,
  wind_score: optionalNumber,
  wave_score: optionalNumber,
  current_score: optionalNumber,
  safety_score: optionalNumber,
})

export const routePreviewResponseSchema = z.object({
  imo_number: z.string().nullable(),
  status: z.string(),
  departure_time: isoTimestampSchema,
  eta: isoTimestampSchema,
  route: z.array(coordinateSchema),
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  optimization_objective: z.string().nullable().optional(),
  cost_weights: z.record(z.string(), z.number()).nullable().optional(),
  legs: z.array(routeLegSchema).optional(),
})

export const apiErrorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
})

export const planJobResponseSchema = z.object({
  job_id: z.string(),
  status: z.enum(['planning', 'ready', 'failed']),
  stage: z.string().nullable().optional(),
  stage_message: z.string().nullable().optional(),
  progress_percent: z.number().nullable().optional(),
  elapsed_seconds: z.number().nonnegative(),
  route: routePreviewResponseSchema.nullable().optional(),
  error: apiErrorDetailSchema.nullable().optional(),
})

export const trackingStartResponseSchema = z.object({
  imo_number: z.string(),
  tracking: z.boolean(),
  message: z.string(),
})

export const trackingStopResponseSchema = trackingStartResponseSchema

export const shipStatusResponseSchema = z.object({
  imo_number: z.string(),
  status: shipStatusSchema,
  // Nullable — no AIS fix means null, never a fake fallback coordinate
  position: coordinateSchema.nullable(),
  timestamp: isoTimestampSchema,
  destination: coordinateSchema.nullable().optional(),
  is_live_position: z.boolean().optional(),
  position_source: z.string().optional(),
})

export const currentRouteResponseSchema = z.object({
  imo_number: z.string(),
  route_status: lenientRouteStatusSchema,
  route: z.array(coordinateSchema),
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  updated_at: isoTimestampSchema,
  destination: coordinateSchema.nullable().optional(),
  legs: z.array(routeLegSchema).optional(),
})

export const routeUpdateMessageSchema = z.object({
  type: z.literal('route_update'),
  timestamp: isoTimestampSchema,
  position: coordinateSchema,
  route: z.array(coordinateSchema),
  distance_nm: z.number().nonnegative(),
  estimated_time_hours: z.number().nonnegative(),
  total_cost: z.number(),
  reason: z.string(),
  legs: z.array(routeLegSchema).optional(),
  position_source: z.string().optional(),
  is_live_position: z.boolean().optional(),
})

export const positionUpdateMessageSchema = z.object({
  type: z.literal('position_update'),
  timestamp: isoTimestampSchema,
  position: coordinateSchema,
  position_source: z.string().optional(),
  is_live_position: z.boolean().optional(),
  speed_kn: z.number().nullable().optional(),
  heading_deg: z.number().nullable().optional(),
})

export const aisTrackPointSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  timestamp: isoTimestampSchema,
})

export const aisTrackResponseSchema = z.object({
  imo_number: z.string(),
  source: z.string(),
  track: z.array(aisTrackPointSchema),
})

export const liveMessageSchema = z.discriminatedUnion('type', [
  routeUpdateMessageSchema,
  positionUpdateMessageSchema,
])


export const apiErrorResponseSchema = z.object({ error: apiErrorDetailSchema })

export const healthResponseSchema = z.object({
  status: z.string(),
  service: z.string(),
})

export const readinessResponseSchema = z.object({
  status: z.string(),
  service: z.string(),
  providers: z.record(z.string(), z.boolean()).optional(),
})

/** Renders a ZodError as a short list of field paths for the console. */
export function formatSchemaError(error: z.ZodError): string {
  return error.issues
    .slice(0, 5)
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join('.') : '(root)'
      return `${path}: ${issue.message}`
    })
    .join('; ')
}
