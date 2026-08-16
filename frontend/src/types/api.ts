/**
 * NauDisha API contract — TypeScript surface.
 *
 * Mirrors `docs/API_CONTRACT.md` exactly. Fields introduced by
 * `docs/API_CONTRACT_ADDENDUM_PROPOSAL.md` are marked ADDENDUM and are ALWAYS
 * optional: the v1 contract is the guaranteed baseline, and every consumer must
 * render correctly when an addendum field is absent.
 *
 * Rule: never add a field here that the backend does not actually promise.
 * Inventing fields is how a frontend quietly drifts out of contract.
 */

// ---------------------------------------------------------------------------
// §3 Conventions
// ---------------------------------------------------------------------------

export interface Coordinate {
  latitude: number
  longitude: number
}

/** ISO-8601 UTC, e.g. "2026-08-16T06:30:00Z". */
export type IsoTimestamp = string

/** Always a string — never an integer. Contract §3. */
export type ImoNumber = string

// ---------------------------------------------------------------------------
// §4 Ships
// ---------------------------------------------------------------------------

export type ShipStatus = 'underway' | 'stopped' | 'unknown'

/**
 * ADDENDUM P0-2. Vessel particulars.
 *
 * Every field is both optional and nullable, because a backend may express
 * "unknown" either way — omitting the key entirely or sending an explicit null.
 * Treating only one of those as valid would reject a legitimate response, so
 * consumers must handle both. This mirrors `shipParticularsSchema` exactly.
 */
export interface ShipParticulars {
  ship_type?: string | null
  length_m?: number | null
  beam_m?: number | null
  draft_m?: number | null
  cruising_speed_kn?: number | null
  max_speed_kn?: number | null
}

/** ADDENDUM P0-2. Provenance of the particulars above. */
export type ShipParticularsSource = 'registry' | 'ais' | 'defaults' | 'user_provided'

export interface ShipIdentifyRequest {
  imo_number: ImoNumber
}

export interface ShipResponse {
  imo_number: ImoNumber
  name: string
  status: ShipStatus
  /**
   * Null when no live AIS report is available for the vessel — the common case
   * without an AISSTREAM_API_KEY on the backend. Callers must handle it, not
   * assume a position exists.
   */
  position: Coordinate | null
  ship?: ShipParticulars
  /** Not currently sent by the backend; retained as an optional hint. */
  source?: ShipParticularsSource
  /** Not currently sent by the backend; the API always returns all six fields. */
  missing_fields?: string[]
}

// ---------------------------------------------------------------------------
// §5 Route preview
// ---------------------------------------------------------------------------

export interface RoutePreviewRequest {
  /** ADDENDUM P0-3: optional when `ship` is supplied. */
  imo_number?: ImoNumber | null
  start: Coordinate
  destination: Coordinate
  /** ADDENDUM P0-1 */
  departure_time?: IsoTimestamp
  /** ADDENDUM P0-2/P0-3 */
  ship?: Partial<ShipParticulars>
}

/**
 * ADDENDUM P2-3. Per-segment breakdown. The backend already computes all of
 * this on every GridEdge; when present it drives cost-graded route rendering
 * and along-route weather readouts.
 */
export interface RouteLeg {
  from: Coordinate
  to: Coordinate
  distance_nm: number
  travel_time_hours?: number
  eta?: IsoTimestamp
  cost?: number
  environment?: LegEnvironment
}

export interface LegEnvironment {
  wind_speed_kn?: number | null
  wind_direction_deg?: number | null
  wave_height_m?: number | null
  wave_period_s?: number | null
  current_speed_kn?: number | null
  current_direction_deg?: number | null
}

export interface RoutePreviewResponse {
  imo_number: ImoNumber
  status: string
  route: Coordinate[]
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  /** ADDENDUM P0-1 */
  departure_time?: IsoTimestamp
  /** ADDENDUM P0-1 */
  eta?: IsoTimestamp
  /** ADDENDUM P2-2 — cost of the naive direct route, for an efficiency figure. */
  baseline_cost?: number
  /** ADDENDUM P2-2 */
  efficiency_gain_percent?: number
  /** ADDENDUM P2-3 */
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// §6 Tracking
// ---------------------------------------------------------------------------

/** Contract §6. `destination` is required; the rest are optional. */
export interface TrackingStartRequest {
  destination: Coordinate
  /** Falls back to the vessel's AIS position, then a backend default. */
  origin?: Coordinate
  departure_time?: IsoTimestamp
}

/** Contract §6.1. */
export interface TrackingStopResponse {
  imo_number: ImoNumber
  tracking: boolean
  message: string
}

export interface TrackingStartResponse {
  imo_number: ImoNumber
  tracking: boolean
  message: string
}

// ---------------------------------------------------------------------------
// §7/§8 Status and current route
// ---------------------------------------------------------------------------

/** §12 */
export type RouteStatus = 'optimal' | 'updating' | 'unavailable'

export interface ShipStatusResponse {
  imo_number: ImoNumber
  status: ShipStatus
  position: Coordinate
  timestamp: IsoTimestamp
  /** ADDENDUM P1-2 */
  destination?: Coordinate | null
  /** ADDENDUM P1-2 */
  route_status?: RouteStatus
}

export interface CurrentRouteResponse {
  imo_number: ImoNumber
  route_status: RouteStatus
  route: Coordinate[]
  distance_nm: number
  estimated_time_hours: number
  total_cost: number
  updated_at: IsoTimestamp
  /** ADDENDUM P1-2 */
  destination?: Coordinate | null
  /** ADDENDUM P2-2 */
  baseline_cost?: number
  /** ADDENDUM P2-3 */
  legs?: RouteLeg[]
}

// ---------------------------------------------------------------------------
// §9–§11 Live updates over WebSocket
// ---------------------------------------------------------------------------

/**
 * ADDENDUM P1-1. Hazard descriptor. `kind` is intentionally widened with
 * `(string & {})` so an unrecognised kind from a newer backend renders with a
 * neutral icon instead of breaking the union.
 */
export type AlertSeverity = 'critical' | 'warning' | 'info'

export type AlertKind =
  | 'storm'
  | 'high_waves'
  | 'strong_current'
  | 'headwind'
  | 'non_navigable'
  | 'draft_limit'
  | 'forecast_gap'
  | (string & {})

export interface RouteAlert {
  id: string
  severity: AlertSeverity
  kind: AlertKind
  message: string
  position?: Coordinate | null
  radius_nm?: number | null
  detected_at?: IsoTimestamp
}

export type RouteUpdateReason =
  | 'environment_changed'
  | 'hazard_detected'
  | 'position_deviation'
  | 'manual_replan'
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
  /** ADDENDUM P1-1 */
  alerts?: RouteAlert[]
  /** ADDENDUM P2-3 */
  legs?: RouteLeg[]
}

export interface PositionUpdateMessage {
  type: 'position_update'
  timestamp: IsoTimestamp
  position: Coordinate
}

export type LiveMessage = RouteUpdateMessage | PositionUpdateMessage

// ---------------------------------------------------------------------------
// §13/§14 Errors
// ---------------------------------------------------------------------------

export type ApiErrorCode =
  | 'INVALID_IMO'
  | 'SHIP_NOT_FOUND'
  | 'INVALID_COORDINATES'
  | 'ROUTE_NOT_FOUND'
  | 'TRACKING_UNAVAILABLE'
  | 'ENVIRONMENT_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  // ADDENDUM §8
  | 'DEPARTURE_TIME_OUT_OF_RANGE'
  | 'SHIP_PARTICULARS_REQUIRED'
  | 'HAZARD_BLOCKING'
  | (string & {})

export interface ApiErrorDetail {
  code: ApiErrorCode
  message: string
  /** ADDENDUM §8 — accompanies SHIP_PARTICULARS_REQUIRED. */
  missing_fields?: string[]
}

export interface ApiErrorResponse {
  error: ApiErrorDetail
}

// ---------------------------------------------------------------------------
// ADDENDUM P2-1 — /health, used as the backend availability probe.
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string
  service: string
  version?: string
  providers?: Record<string, boolean>
}
