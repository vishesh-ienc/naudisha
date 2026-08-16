"""
Route Planning Service layer.
Acts as a decoupled adapter between API requests and the NauDisha routing engine
(GeographicGridGraph, CostModel, CompositeEnvironmentalProvider, DStarLite).
Strictly contains NO routing mathematics or D* Lite internals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple, Union

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


@dataclass
class RoutePlanResult:
    """Domain model output for a planned route calculation."""
    imo_number: str
    status: str
    route: List[Tuple[float, float]]  # List of (latitude, longitude) tuples
    distance_nm: float
    estimated_time_hours: float
    total_cost: float


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
        imo_number: str,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        timestamp: Optional[Union[datetime, str]] = None,
    ) -> RoutePlanResult:
        """
        Calculates an optimal route between start and destination coordinates.

        Args:
            imo_number: Ship identifier string.
            start_lat: Departure latitude [-90.0, 90.0].
            start_lon: Departure longitude [-180.0, 180.0].
            dest_lat: Destination latitude [-90.0, 90.0].
            dest_lon: Destination longitude [-180.0, 180.0].
            timestamp: Optional UTC timestamp for environmental sampling.

        Returns:
            RoutePlanResult containing waypoints, distance, time, and cost.

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

        # Zero-distance edge case
        if math_isclose_coords(start_lat, start_lon, dest_lat, dest_lon):
            return RoutePlanResult(
                imo_number=imo_number,
                status="route_ready",
                route=[(round(start_lat, 4), round(start_lon, 4))],
                distance_nm=0.0,
                estimated_time_hours=0.0,
                total_cost=0.0,
            )

        # 2. Build or retrieve graph covering voyage corridor
        if self.graph_factory:
            graph = self.graph_factory(start_lat, start_lon, dest_lat, dest_lon)
        else:
            graph = self._build_bounding_grid(start_lat, start_lon, dest_lat, dest_lon)

        # 3. Populate environment using BatchCapableProvider pipeline
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
        if self.environment_provider is not None:
            try:
                graph.populate_environment(
                    timestamp=ts,
                    provider=self.environment_provider,
                    ship=self.ship_profile,
                    weights=self.default_weights,
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
                timestamp=ts,
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
                ship=self.ship_profile,
                weights=self.default_weights,
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

        for i in range(len(path) - 1):
            edge = graph.get_edge(path[i], path[i + 1])
            if edge and edge.evaluation and edge.evaluation.metrics:
                total_nm += edge.evaluation.metrics.distance_nm
                total_hours += edge.evaluation.metrics.travel_time_hours
            else:
                n1 = graph.get_node(path[i])
                n2 = graph.get_node(path[i + 1])
                if n1 and n2:
                    d = calculate_haversine_distance(n1.lat, n1.lon, n2.lat, n2.lon)
                    total_nm += d
                    total_hours += d / max(self.ship_profile.cruising_speed, 1.0)

        return RoutePlanResult(
            imo_number=imo_number,
            status="route_ready",
            route=route_coords,
            distance_nm=round(total_nm, 2),
            estimated_time_hours=round(total_hours, 2),
            total_cost=round(cost, 2),
        )

    def _build_bounding_grid(
        self,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
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
            default_ship=self.ship_profile,
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
