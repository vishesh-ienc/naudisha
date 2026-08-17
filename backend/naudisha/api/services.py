"""
Route Planning Service layer.
Acts as a decoupled adapter between API requests and the NauDisha routing engine
(GeographicGridGraph, CostModel, CompositeEnvironmentalProvider, DStarLite).
Strictly contains NO routing mathematics or D* Lite internals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple, Union

from naudisha.core.calculations import calculate_haversine_distance
from naudisha.core.models import (
    CostWeights,
    EnvironmentalData,
    ShipProfile,
)
from naudisha.cost.model import CostModel
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.weather_provider import WeatherProvider
from naudisha.routing.dstar_lite import DStarLite
from naudisha.routing.graph import (
    GeographicGridGraph,
    GridConfig,
    GridEnvironmentUpdateError,
)
from naudisha.api.errors import (
    EnvironmentUnavailableError,
    InvalidCoordinatesError,
    RouteNotFoundError,
)

logger = logging.getLogger("naudisha.api.services")


def _opt_round(value: Optional[float], digits: int) -> Optional[float]:
    """Rounds a value that may legitimately be absent, preserving None."""
    return None if value is None else round(value, digits)


@dataclass
class RouteLegResult:
    """
    Per-segment breakdown of a planned route.

    This is what lets a client explain *why* a route was chosen rather than only
    drawing it. Every value here is already computed by the cost model while
    evaluating the graph edge — nothing is recalculated or approximated.

    Sign conventions follow `DerivedSegmentMetrics`:
      * `along_track_current_kn` is positive when the current assists.
      * `relative_wind_dir` is 0 deg for a headwind and 180 deg for a tailwind.
    """
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_nm: float
    travel_time_hours: float
    bearing: float
    cost: float

    # Environment sampled at the segment midpoint.
    wind_speed_kn: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    current_speed_kn: Optional[float] = None
    current_direction_deg: Optional[float] = None

    # Derived hydrodynamics — the basis of the human-readable explanation.
    relative_wind_dir: Optional[float] = None
    relative_current_dir: Optional[float] = None
    along_track_current_kn: Optional[float] = None
    effective_speed_kn: Optional[float] = None

    # Normalised component scores, 0.0 best to 1.0 worst.
    time_score: Optional[float] = None
    fuel_score: Optional[float] = None
    wind_score: Optional[float] = None
    wave_score: Optional[float] = None
    current_score: Optional[float] = None
    safety_score: Optional[float] = None


@dataclass
class RoutePlanResult:
    """Domain model output for a planned route calculation."""
    imo_number: Optional[str]
    status: str
    route: List[Tuple[float, float]]  # List of (latitude, longitude) tuples
    distance_nm: float
    estimated_time_hours: float
    total_cost: float
    departure_time: str  # ISO-8601 UTC timestamp string
    eta: str             # ISO-8601 UTC timestamp string
    legs: List[RouteLegResult] = field(default_factory=list)
    optimization_objective: str = "balanced"
    cost_weights: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Objective → Cost Weights mapping
# ---------------------------------------------------------------------------

_OBJECTIVE_WEIGHTS: Dict[str, CostWeights] = {
    # Balanced: equal emphasis across all dimensions with elevated safety.
    # This is the production default and the most conservative option.
    "balanced": CostWeights(
        time=1.5, fuel=1.2, wind=1.0, wave=1.0, current=0.8, safety=2.0
    ),
    # Fuel efficiency: heavily prioritises propulsion cost minimisation.
    # Current assistance weighted up (it directly reduces fuel burn).
    # Safety remains a meaningful penalty — never suppressed.
    "fuel_efficiency": CostWeights(
        time=1.0, fuel=3.0, wind=1.2, wave=1.0, current=1.2, safety=2.0
    ),
    # Fastest: travel time is the primary driver.
    # Current assistance weighted up (it increases SOG).
    # Fuel and wave de-prioritised — but safety constraint is still 2.0.
    "fastest": CostWeights(
        time=3.5, fuel=0.8, wind=1.0, wave=0.8, current=1.5, safety=2.0
    ),
    # Safety / weather routing: heavily penalises wave and wind exposure.
    # Safety weight at maximum to avoid storm-track routes.
    # Time and fuel largely sacrificed for sea-state comfort.
    "safety": CostWeights(
        time=0.8, fuel=0.8, wind=2.5, wave=3.0, current=1.0, safety=3.5
    ),
}


def objective_to_weights(objective: Optional[str]) -> CostWeights:
    """
    Resolves an optimization objective string to a CostWeights instance.

    Safety is guaranteed >= 1.0 for every objective:
    the cost model additionally enforces absolute survival constraints
    (wave/wind hard limits) independently of these weights.

    Args:
        objective: One of 'fuel_efficiency', 'fastest', 'safety', 'balanced'.
                   Defaults to 'balanced' when None or unrecognised.

    Returns:
        CostWeights instance appropriate for the D* Lite cost model.
    """
    key = (objective or "balanced").strip().lower()
    return _OBJECTIVE_WEIGHTS.get(key, _OBJECTIVE_WEIGHTS["balanced"])


def _weights_to_dict(w: CostWeights) -> Dict[str, float]:
    """Converts a CostWeights instance to a plain dict for API serialisation."""
    return {
        "time": w.time,
        "fuel": w.fuel,
        "wind": w.wind,
        "wave": w.wave,
        "current": w.current,
        "safety": w.safety,
    }


class RoutePlanningService:
    """
    Orchestration service for calculating optimal maritime routes.
    Decouples HTTP controllers from domain routing components and supports
    full dependency injection for offline testing.
    """

    def __init__(
        self,
        environment_provider: Optional[WeatherProvider] = None,
        ship_profile: Optional[ShipProfile] = None,
        cost_model: Optional[CostModel] = None,
        default_weights: Optional[CostWeights] = None,
        graph_factory: Optional[Callable[[float, float, float, float], GeographicGridGraph]] = None,
        grid_resolution_deg: float = 0.25,
    ) -> None:
        """
        Initializes the route planning service.

        Args:
            environment_provider: Optional meteorological/hydrodynamic data provider.
                Defaults to CompositeEnvironmentalProvider (live CMEMS currents/waves + Open-Meteo wind).
            ship_profile: Optional vessel parameters (defaults to Panamax container ship).
            cost_model: Optional CostModel instance.
            default_weights: Optional multi-objective cost weights.
            graph_factory: Optional custom grid factory for test injection.
            grid_resolution_deg: Default grid spatial resolution in degrees (default: 0.25 deg ~ 15 NM).
        """
        self.environment_provider = (
            environment_provider if environment_provider is not None else CompositeEnvironmentalProvider()
        )
        self.ship_profile = ship_profile or ShipProfile(
            ship_type="Container Vessel (Panamax)",
            length=294.0,
            beam=32.2,
            draft=12.0,
            cruising_speed=18.0,
            maximum_speed=23.0,
        )
        self.default_weights = default_weights or CostWeights(
            time=1.5,
            fuel=1.2,
            wind=1.0,
            wave=1.0,
            current=0.8,
            safety=2.0,
        )
        self.cost_model = cost_model or CostModel(default_weights=self.default_weights)
        self.graph_factory = graph_factory
        self.grid_resolution_deg = grid_resolution_deg

    def plan_preview_route(
        self,
        imo_number: Optional[str],
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        timestamp: Optional[Union[datetime, str]] = None,
        ship_profile: Optional[ShipProfile] = None,
        optimization_objective: Optional[str] = None,
    ) -> RoutePlanResult:
        """
        Calculates an optimal route between start and destination coordinates.

        Args:
            imo_number: Optional ship identifier string.
            start_lat: Departure latitude [-90.0, 90.0].
            start_lon: Departure longitude [-180.0, 180.0].
            dest_lat: Destination latitude [-90.0, 90.0].
            dest_lon: Destination longitude [-180.0, 180.0].
            timestamp: Optional UTC timestamp for environmental sampling.
            ship_profile: Optional vessel profile (falls back to service default).

        Returns:
            RoutePlanResult containing waypoints, distance, time, cost, departure_time, and eta.

        Raises:
            InvalidCoordinatesError: If coordinates are out of bounds.
            EnvironmentUnavailableError: If environmental data provider fails.
            RouteNotFoundError: If no navigable route exists.
        """
        # 1. Coordinate validation
        if not (-90.0 <= start_lat <= 90.0 and -90.0 <= dest_lat <= 90.0):
            raise InvalidCoordinatesError("Latitude must be between -90.0 and 90.0 degrees.")
        if not (-180.0 <= start_lon <= 180.0 and -180.0 <= dest_lon <= 180.0):
            raise InvalidCoordinatesError("Longitude must be between -180.0 and 180.0 degrees.")

        # Effective ship profile
        effective_ship = ship_profile or self.ship_profile

        # Effective optimization objective & weights
        effective_objective = (optimization_objective or "balanced").strip().lower()
        effective_weights = objective_to_weights(effective_objective)
        weights_dict = _weights_to_dict(effective_weights)

        # Effective departure time (defaults to real current UTC time)
        if timestamp is None:
            dep_dt = datetime.now(timezone.utc)
        elif isinstance(timestamp, datetime):
            dep_dt = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
        else:
            dep_dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if dep_dt.tzinfo is None:
                dep_dt = dep_dt.replace(tzinfo=timezone.utc)

        dep_iso = dep_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Zero-distance edge case
        if math_isclose_coords(start_lat, start_lon, dest_lat, dest_lon):
            return RoutePlanResult(
                imo_number=imo_number,
                status="route_ready",
                route=[(round(start_lat, 4), round(start_lon, 4))],
                distance_nm=0.0,
                estimated_time_hours=0.0,
                total_cost=0.0,
                departure_time=dep_iso,
                eta=dep_iso,
                optimization_objective=effective_objective,
                cost_weights=weights_dict,
            )

        # 2. Build or retrieve graph covering voyage corridor
        if self.graph_factory:
            graph = self.graph_factory(start_lat, start_lon, dest_lat, dest_lon)
        else:
            graph = self._build_bounding_grid(start_lat, start_lon, dest_lat, dest_lon, ship=effective_ship)

        # 3. Populate environment using BatchCapableProvider pipeline
        if self.environment_provider is not None:
            try:
                graph.populate_environment(
                    timestamp=dep_iso,
                    provider=self.environment_provider,
                    ship=effective_ship,
                    weights=effective_weights,
                )
            except GridEnvironmentUpdateError as exc:
                logger.error("Environmental update failed: %s", exc)
                raise EnvironmentUnavailableError(f"Environmental service update failed: {exc}") from exc
            except Exception as exc:
                logger.error("Unexpected error fetching environmental data: %s", exc)
                raise EnvironmentUnavailableError(f"Environmental data fetch failed: {exc}") from exc
        else:
            # Baseline calm maritime conditions if explicitly unconfigured
            baseline_env = EnvironmentalData(
                timestamp=dep_iso,
                current_speed=0.2,
                current_direction=90.0,
                wave_height=1.0,
                wave_direction=90.0,
                wave_period=6.0,
                wind_speed=10.0,
                wind_direction=90.0,
            )
            graph.populate_uniform_environment(
                env=baseline_env,
                ship=effective_ship,
                weights=effective_weights,
            )

        # 4. Map start and destination to grid nodes
        start_node_id = self._find_nearest_node_id(graph, start_lat, start_lon)
        dest_node_id = self._find_nearest_node_id(graph, dest_lat, dest_lon)

        if not start_node_id or not dest_node_id:
            raise RouteNotFoundError("Could not map start or destination to a navigable grid node.")

        if start_node_id == dest_node_id and not math_isclose_coords(start_lat, start_lon, dest_lat, dest_lon):
            # If mapped to identical node on coarse grid, select second nearest node for destination
            second_dest = self._find_second_nearest_node_id(graph, dest_lat, dest_lon, exclude_id=start_node_id)
            if second_dest:
                dest_node_id = second_dest

        # 5. Run D* Lite path planning
        dstar = DStarLite(graph=graph, start_id=start_node_id, goal_id=dest_node_id)
        reachable = dstar.compute_shortest_path()
        path = dstar.get_path()
        cost = dstar.get_path_cost()

        if not reachable or not path:
            raise RouteNotFoundError("No navigable maritime route could be found between specified coordinates.")

        # 6. Extract waypoints and calculate route metrics
        route_coords: List[Tuple[float, float]] = []
        total_nm = 0.0
        total_hours = 0.0

        for node_id in path:
            node = graph.get_node(node_id)
            if node:
                route_coords.append((round(node.lat, 4), round(node.lon, 4)))

        legs: List[RouteLegResult] = []

        for i in range(len(path) - 1):
            edge = graph.get_edge(path[i], path[i + 1])
            n1 = graph.get_node(path[i])
            n2 = graph.get_node(path[i + 1])

            if edge and edge.evaluation and edge.evaluation.metrics:
                metrics = edge.evaluation.metrics
                total_nm += metrics.distance_nm
                total_hours += metrics.travel_time_hours

                # The cost model has already derived everything below while
                # evaluating this edge; surfacing it costs nothing and is what
                # allows a client to explain the routing decision.
                env = edge.env_data
                scores = edge.evaluation.scores

                legs.append(
                    RouteLegResult(
                        from_lat=round(n1.lat, 4) if n1 else 0.0,
                        from_lon=round(n1.lon, 4) if n1 else 0.0,
                        to_lat=round(n2.lat, 4) if n2 else 0.0,
                        to_lon=round(n2.lon, 4) if n2 else 0.0,
                        distance_nm=round(metrics.distance_nm, 2),
                        travel_time_hours=round(metrics.travel_time_hours, 3),
                        bearing=round(metrics.bearing, 1),
                        cost=round(edge.cost, 4),
                        wind_speed_kn=_opt_round(getattr(env, "wind_speed", None), 1),
                        wind_direction_deg=_opt_round(getattr(env, "wind_direction", None), 0),
                        wave_height_m=_opt_round(getattr(env, "wave_height", None), 2),
                        wave_period_s=_opt_round(getattr(env, "wave_period", None), 1),
                        current_speed_kn=_opt_round(getattr(env, "current_speed", None), 2),
                        current_direction_deg=_opt_round(getattr(env, "current_direction", None), 0),
                        relative_wind_dir=round(metrics.relative_wind_dir, 1),
                        relative_current_dir=round(metrics.relative_current_dir, 1),
                        along_track_current_kn=round(metrics.along_track_current, 3),
                        effective_speed_kn=round(metrics.effective_speed, 2),
                        time_score=round(scores.time_score, 4),
                        fuel_score=round(scores.fuel_score, 4),
                        wind_score=round(scores.wind_score, 4),
                        wave_score=round(scores.wave_score, 4),
                        current_score=round(scores.current_score, 4),
                        safety_score=round(scores.safety_score, 4),
                    )
                )
            elif n1 and n2:
                d = calculate_haversine_distance(n1.lat, n1.lon, n2.lat, n2.lon)
                hours = d / max(effective_ship.cruising_speed, 1.0)
                total_nm += d
                total_hours += hours
                # No evaluation available for this edge: emit geometry only
                # rather than inventing environmental values.
                legs.append(
                    RouteLegResult(
                        from_lat=round(n1.lat, 4),
                        from_lon=round(n1.lon, 4),
                        to_lat=round(n2.lat, 4),
                        to_lon=round(n2.lon, 4),
                        distance_nm=round(d, 2),
                        travel_time_hours=round(hours, 3),
                        bearing=0.0,
                        cost=0.0,
                    )
                )

        # 6b. Anchor the route to the caller's true endpoints.
        #
        # D* Lite operates on grid nodes, so `path` begins and ends at whichever
        # nodes the requested coordinates snapped to — up to half a grid cell
        # away. Returning that raw path means the drawn route floats away from
        # the requested start/destination, and `distance_nm` silently omits both
        # approach legs (measured at ~8 NM each on a 0.25 deg grid, against a
        # 17 NM reported total).
        #
        # Prepending the true origin and appending the true destination makes the
        # geometry and the distance describe the same voyage. Contract §8 also
        # requires the tracked route to begin at the vessel's current position.
        approach_speed = max(effective_ship.cruising_speed, 1.0)

        if route_coords:
            first = route_coords[0]
            if not math_isclose_coords(start_lat, start_lon, first[0], first[1]):
                lead_nm = calculate_haversine_distance(start_lat, start_lon, first[0], first[1])
                route_coords.insert(0, (round(start_lat, 4), round(start_lon, 4)))
                total_nm += lead_nm
                total_hours += lead_nm / approach_speed

            last = route_coords[-1]
            if not math_isclose_coords(dest_lat, dest_lon, last[0], last[1]):
                tail_nm = calculate_haversine_distance(last[0], last[1], dest_lat, dest_lon)
                route_coords.append((round(dest_lat, 4), round(dest_lon, 4)))
                total_nm += tail_nm
                total_hours += tail_nm / approach_speed

        # 7. Compute ETA
        eta_dt = dep_dt + timedelta(hours=total_hours)
        eta_iso = eta_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return RoutePlanResult(
            imo_number=imo_number,
            status="route_ready",
            route=route_coords,
            distance_nm=round(total_nm, 2),
            estimated_time_hours=round(total_hours, 2),
            total_cost=round(cost, 2),
            departure_time=dep_iso,
            eta=eta_iso,
            legs=legs,
            optimization_objective=effective_objective,
            cost_weights=weights_dict,
        )

    def _build_bounding_grid(
        self,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        ship: Optional[ShipProfile] = None,
    ) -> GeographicGridGraph:
        """
        Constructs a regular navigation grid covering the bounding corridor
        of the start and destination coordinates with adequate margins.
        """
        min_lat = min(start_lat, dest_lat)
        max_lat = max(start_lat, dest_lat)
        min_lon = min(start_lon, dest_lon)
        max_lon = max(start_lon, dest_lon)

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon

        # Margins: at least 0.20 deg (~12 NM) padding, or 25% of corridor span
        margin_lat = max(0.20, lat_span * 0.25)
        margin_lon = max(0.20, lon_span * 0.25)

        origin_lat = max(-90.0, min_lat - margin_lat)
        origin_lon = max(-180.0, min_lon - margin_lon)
        top_lat = min(90.0, max_lat + margin_lat)
        right_lon = min(180.0, max_lon + margin_lon)

        total_lat = top_lat - origin_lat
        total_lon = right_lon - origin_lon

        # Calculate rows and cols (min 4x4, max 15x15)
        res = self.grid_resolution_deg
        rows = max(4, min(15, round(total_lat / res) + 1))
        cols = max(4, min(15, round(total_lon / res) + 1))

        lat_spacing = total_lat / max(rows - 1, 1)
        lon_spacing = total_lon / max(cols - 1, 1)

        config = GridConfig(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            rows=rows,
            cols=cols,
            lat_spacing=lat_spacing,
            lon_spacing=lon_spacing,
        )

        return GeographicGridGraph(
            config=config,
            cost_model=self.cost_model,
            default_ship=ship or self.ship_profile,
            default_weights=self.default_weights,
            environment_provider=self.environment_provider,
        )

    def _find_nearest_node_id(
        self,
        graph: GeographicGridGraph,
        lat: float,
        lon: float,
    ) -> Optional[str]:
        """Finds the ID of the nearest navigable node in the graph to the given coordinates."""
        best_id: Optional[str] = None
        best_dist = float("inf")

        for node in graph.get_all_nodes():
            if not node.is_navigable:
                continue
            dist = calculate_haversine_distance(lat, lon, node.lat, node.lon)
            if dist < best_dist:
                best_dist = dist
                best_id = node.node_id

        return best_id

    def _find_second_nearest_node_id(
        self,
        graph: GeographicGridGraph,
        lat: float,
        lon: float,
        exclude_id: str,
    ) -> Optional[str]:
        """Finds the second closest navigable node, excluding the specified node ID."""
        best_id: Optional[str] = None
        best_dist = float("inf")

        for node in graph.get_all_nodes():
            if not node.is_navigable or node.node_id == exclude_id:
                continue
            dist = calculate_haversine_distance(lat, lon, node.lat, node.lon)
            if dist < best_dist:
                best_dist = dist
                best_id = node.node_id

        return best_id


def math_isclose_coords(lat1: float, lon1: float, lat2: float, lon2: float, tol: float = 1e-5) -> bool:
    """Checks whether two coordinate pairs are identical within float tolerance."""
    return abs(lat1 - lat2) < tol and abs(lon1 - lon2) < tol
