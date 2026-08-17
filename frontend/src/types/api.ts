/**
 * NauDisha API contract — TypeScript surface.
 *
 * Mirrors `docs/API_CONTRACT.md` v2 plus the additive fields the backend
 * returns (`legs`, and the async planning job endpoints).
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

/** For manual entry or partial forms where fields may be null while editing. */
export interface ShipParticulars {
  ship_type?: string | null
  length_m?: number | null
  beam_m?: number | null
  draft_m?: number | null
  cruising_speed_kn?: number | null
  max_speed_kn?: number | null
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
  /** True only when position originates from a live AIS fix (not static registry or simulation). */
  is_live_position?: boolean
  /** 'aisstream' | 'digitraffic' | 'static' | 'none' */
  position_source?: string
  source?: string
  missing_fields?: string[]
}

// ---------------------------------------------------------------------------
// §5 Route preview + per-leg breakdown
// ---------------------------------------------------------------------------

export type OptimizationObjective = 'fuel_efficiency' | 'fastest' | 'safety' | 'balanced'

export interface RoutePreviewRequest {
  imo_number?: ImoNumber | null
  start: Coordinate
  destination: Coordinate
  departure_time?: IsoTimestamp
  ship?: ShipProfile | ShipParticulars
  optimization_objective?: OptimizationObjective | string
}

/**
 * Per-segment detail. Present on responses from this backend; treated as
 * optional so an older deployment that omits it still renders.
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
  baseline_cost?: number | null
  efficiency_gain_percent?: number | null
  optimization_objective?: string | null
  cost_weights?: Record<string, number> | null
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// Async planning jobs
// ---------------------------------------------------------------------------

export type PlanJobStatus = 'planning' | 'ready' | 'failed'

export interface PlanJobResponse {
  job_id: string
  status: PlanJobStatus
  stage?: string | null
  stage_message?: string | null
  progress_percent?: number | null
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
  /** null when no AIS fix exists; never a fabricated fallback coordinate. */
  position: Coordinate | null
  timestamp: IsoTimestamp
  destination?: Coordinate | null
  route_status?: RouteStatus
  is_live_position?: boolean
  /** 'aisstream' | 'digitraffic' | 'simulated' | 'none' */
  position_source?: string
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
  baseline_cost?: number | null
  efficiency_gain_percent?: number | null
  optimization_objective?: string | null
  cost_weights?: Record<string, number> | null
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// §9-§11 Live updates over WebSocket & Alert definitions
// ---------------------------------------------------------------------------

export interface RouteAlert {
  id: string
  severity: 'warning' | 'critical' | 'info'
  kind?: string
  message: string
  position?: Coordinate
  radius_nm?: number
  detected_at?: IsoTimestamp
}

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
  alerts?: RouteAlert[]
  position_source?: string
  is_live_position?: boolean
}

export interface PositionUpdateMessage {
  type: 'position_update'
  timestamp: IsoTimestamp
  position: Coordinate
  position_source?: string
  is_live_position?: boolean
  speed_kn?: number | null
  heading_deg?: number | null
}

export type LiveMessage = RouteUpdateMessage | PositionUpdateMessage

export interface AISTrackPoint {
  latitude: number
  longitude: number
  timestamp: IsoTimestamp
}

export interface AISTrackResponse {
  imo_number: ImoNumber
  source: string
  track: AISTrackPoint[]
}


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
  missing_fields?: string[]
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
  version?: string
}

export interface ReadinessResponse {
  status: string
  service: string
  providers?: Record<string, boolean>
}

// ---------------------------------------------------------------------------
// Dynamic D* Lite Replanning Simulation
// ---------------------------------------------------------------------------

export interface HazardInjection {
  id: string
  name: string
  type: 'storm' | 'current' | 'restricted'
  center: Coordinate
  radius_nm: number
  severity: number
  description?: string
}

export interface DynamicReplanRequest {
  current_position: Coordinate
  destination: Coordinate
  active_route: Coordinate[]
  hazard: HazardInjection
  optimization_objective?: string
  departure_time?: IsoTimestamp
  imo_number?: ImoNumber
}

export interface DynamicReplanResponse {
  new_route: Coordinate[]
  previous_route: Coordinate[]
  replan_time_ms: number
  affected_edges_count: number
  hazard_avoidance_score: number
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  legs: RouteLeg[]
}

