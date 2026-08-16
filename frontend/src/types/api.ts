/**
 * NauDisha API contract — TypeScript surface.
 *
 * Mirrors `docs/API_CONTRACT.md` v2 plus the two additive fields the backend
 * actually returns today (`legs`, and the async planning job endpoints).
 *
 * Rule: nothing is declared here that the backend does not send. Fields the
 * contract discussed but which were never implemented — `baseline_cost`,
 * `efficiency_gain_percent`, `missing_fields`, `alerts` — have been removed, so
 * the compiler now prevents the UI from depending on data that will never
 * arrive.
 */

// ---------------------------------------------------------------------------
// §2 Conventions
// ---------------------------------------------------------------------------

export interface Coordinate {
  latitude: number
  longitude: number
}

/** ISO-8601 UTC, e.g. "2026-08-16T06:30:00Z". */
export type IsoTimestamp = string

/** Always a string, exactly 7 digits with an ISO 8713 check digit. §2.3 */
export type ImoNumber = string

/** §2.4 — all six fields required when the object is present. */
export interface ShipProfile {
  ship_type: string
  length_m: number
  beam_m: number
  draft_m: number
  cruising_speed_kn: number
  max_speed_kn: number
}

// ---------------------------------------------------------------------------
// §4 Ships
// ---------------------------------------------------------------------------

export type ShipStatus = 'underway' | 'stopped' | 'unknown'

export interface ShipResponse {
  imo_number: ImoNumber
  name: string
  status: ShipStatus
  /** null when the vessel has no live AIS transponder report. */
  position: Coordinate | null
  ship?: ShipProfile
}

// ---------------------------------------------------------------------------
// §5 Route preview + per-leg breakdown
// ---------------------------------------------------------------------------

export interface RoutePreviewRequest {
  imo_number?: ImoNumber | null
  start: Coordinate
  destination: Coordinate
  departure_time?: IsoTimestamp
  ship?: ShipProfile
}

/**
 * Per-segment detail. Present on responses from this backend; treated as
 * optional so an older deployment that omits it still renders.
 *
 * Sign conventions, straight from the cost model:
 *   `relative_wind_dir`     0 deg = headwind, 180 deg = tailwind
 *   `relative_current_dir`  0 deg = following, 180 deg = opposing
 *   `along_track_current_kn` positive assists, negative opposes
 */
export interface RouteLeg {
  from: Coordinate
  to: Coordinate
  distance_nm: number
  travel_time_hours: number
  bearing: number
  cost: number

  wind_speed_kn?: number | null
  wind_direction_deg?: number | null
  wave_height_m?: number | null
  wave_period_s?: number | null
  current_speed_kn?: number | null
  current_direction_deg?: number | null

  relative_wind_dir?: number | null
  relative_current_dir?: number | null
  along_track_current_kn?: number | null
  effective_speed_kn?: number | null

  time_score?: number | null
  fuel_score?: number | null
  wind_score?: number | null
  wave_score?: number | null
  current_score?: number | null
  safety_score?: number | null
}

export interface RoutePreviewResponse {
  imo_number: ImoNumber | null
  status: string
  departure_time: IsoTimestamp
  eta: IsoTimestamp
  route: Coordinate[]
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// Async planning jobs
//
// A cold plan costs 70-85s of live Copernicus queries. The synchronous
// endpoint still exists, but the UI submits a job and polls so it can show
// real progress instead of holding a request open past every sane timeout.
// ---------------------------------------------------------------------------

export type PlanJobStatus = 'planning' | 'ready' | 'failed'

export interface PlanJobResponse {
  job_id: string
  status: PlanJobStatus
  elapsed_seconds: number
  route?: RoutePreviewResponse | null
  error?: ApiErrorDetail | null
}

// ---------------------------------------------------------------------------
// §6 Tracking
// ---------------------------------------------------------------------------

export interface TrackingStartRequest {
  destination: Coordinate
  origin?: Coordinate | null
  departure_time?: IsoTimestamp
}

export interface TrackingStartResponse {
  imo_number: ImoNumber
  tracking: boolean
  message: string
}

export interface TrackingStopResponse {
  imo_number: ImoNumber
  tracking: boolean
  message: string
}

// ---------------------------------------------------------------------------
// §7/§8 Status and current route
// ---------------------------------------------------------------------------

/** §13.2 */
export type RouteStatus = 'optimal' | 'updating' | 'unavailable'

export interface ShipStatusResponse {
  imo_number: ImoNumber
  status: ShipStatus
  position: Coordinate
  timestamp: IsoTimestamp
  destination?: Coordinate | null
}

export interface CurrentRouteResponse {
  imo_number: ImoNumber
  route_status: RouteStatus
  route: Coordinate[]
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  updated_at: IsoTimestamp
  destination?: Coordinate | null
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// §9-§11 Live updates over WebSocket
// ---------------------------------------------------------------------------

/** §13.3 — unknown values must render, not throw. */
export type RouteUpdateReason =
  | 'environment_changed'
  | 'position_deviation'
  | 'forecast_refresh'
  | (string & {})

export interface RouteUpdateMessage {
  type: 'route_update'
  timestamp: IsoTimestamp
  position: Coordinate
  route: Coordinate[]
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  reason: RouteUpdateReason
  legs?: RouteLeg[]
}

export interface PositionUpdateMessage {
  type: 'position_update'
  timestamp: IsoTimestamp
  position: Coordinate
}

export type LiveMessage = RouteUpdateMessage | PositionUpdateMessage

// ---------------------------------------------------------------------------
// §14/§15 Errors
// ---------------------------------------------------------------------------

export type ApiErrorCode =
  | 'INVALID_IMO'
  | 'SHIP_NOT_FOUND'
  | 'INVALID_COORDINATES'
  | 'ROUTE_NOT_FOUND'
  | 'TRACKING_UNAVAILABLE'
  | 'ENVIRONMENT_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  | (string & {})

export interface ApiErrorDetail {
  code: ApiErrorCode
  message: string
}

export interface ApiErrorResponse {
  error: ApiErrorDetail
}

// ---------------------------------------------------------------------------
// Health / readiness
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string
  service: string
}

export interface ReadinessResponse {
  status: string
  service: string
  providers?: Record<string, boolean>
}
