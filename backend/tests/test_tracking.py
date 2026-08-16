"""
Offline tests for live tracking sessions, the navigation simulator, and the
WebSocket streaming endpoint (docs/API_CONTRACT.md §6-§11).

Fully deterministic: route planning is driven by an injected fake service, and
the simulator is stepped explicitly rather than waiting on the real ticker.
"""

from __future__ import annotations

import time
import unittest
from typing import List, Optional, Tuple

from fastapi.testclient import TestClient

from naudisha.api.main import app
from naudisha.api.routes import get_route_service, get_vessel_provider
from naudisha.api.services import RoutePlanResult, RoutePlanningService
from naudisha.api.tracking import (
    TrackingSessionManager,
    path_length_nm,
    point_along_path,
    tracking_manager,
)

Coord = Tuple[float, float]

ORIGIN: Coord = (18.52, 72.55)
DESTINATION: Coord = (19.07, 72.42)


class FakeRouteService(RoutePlanningService):
    """Returns a fixed four-point route instantly, with no environmental calls."""

    def __init__(self, route: Optional[List[Coord]] = None, fail: bool = False) -> None:
        self.route = route or [(18.52, 72.55), (18.70, 72.50), (18.90, 72.46), (19.07, 72.42)]
        self.fail = fail
        self.call_count = 0

    def plan_preview_route(self, **kwargs):  # type: ignore[override]
        self.call_count += 1
        if self.fail:
            raise RuntimeError("simulated planning failure")
        distance = path_length_nm(self.route)
        return RoutePlanResult(
            imo_number=kwargs.get("imo_number"),
            status="route_ready",
            route=list(self.route),
            distance_nm=round(distance, 2),
            estimated_time_hours=round(distance / 18.0, 2),
            total_cost=7.85,
            departure_time="2026-08-20T06:00:00Z",
            eta="2026-08-20T08:00:00Z",
        )


def _wait_for_plan(manager: TrackingSessionManager, imo: str, timeout: float = 5.0) -> None:
    """Blocks until the background planning thread has populated the route."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = manager.get(imo)
        if session is not None and not session.planning and session.route:
            return
        time.sleep(0.01)
    raise AssertionError(f"route for {imo} was not planned within {timeout}s")


class TestPathGeometry(unittest.TestCase):
    """Geometry helpers backing the simulator."""

    def test_01_path_length_sums_segments(self) -> None:
        length = path_length_nm([(18.0, 72.0), (18.5, 72.0), (19.0, 72.0)])
        # One degree of latitude is 60 NM by definition.
        self.assertAlmostEqual(length, 60.0, delta=0.5)

    def test_02_point_at_zero_distance_is_start(self) -> None:
        position, _, complete = point_along_path([(18.0, 72.0), (19.0, 72.0)], 0.0)
        self.assertEqual(position, (18.0, 72.0))
        self.assertFalse(complete)

    def test_03_point_midway(self) -> None:
        position, index, complete = point_along_path([(18.0, 72.0), (19.0, 72.0)], 30.0)
        self.assertAlmostEqual(position[0], 18.5, delta=0.02)
        self.assertEqual(index, 0)
        self.assertFalse(complete)

    def test_04_overshoot_clamps_to_end(self) -> None:
        position, _, complete = point_along_path([(18.0, 72.0), (19.0, 72.0)], 999.0)
        self.assertEqual(position, (19.0, 72.0))
        self.assertTrue(complete)

    def test_05_empty_path_is_safe(self) -> None:
        position, _, complete = point_along_path([], 10.0)
        self.assertEqual(position, (0.0, 0.0))
        self.assertTrue(complete)


class TestTrackingSession(unittest.TestCase):
    """Session lifecycle and simulated movement."""

    def setUp(self) -> None:
        self.service = FakeRouteService()
        self.manager = TrackingSessionManager(route_service=self.service)

    def tearDown(self) -> None:
        self.manager.clear()

    def test_06_start_creates_session_and_plans_route(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")

        session = self.manager.get("1234567")
        assert session is not None
        self.assertEqual(session.route_status, "optimal")
        self.assertEqual(len(session.route), 4)
        self.assertEqual(self.service.call_count, 1)

    def test_07_session_starts_in_updating_state(self) -> None:
        """Route planning is asynchronous, so a session exists before its route does."""
        manager = TrackingSessionManager(route_service=None)
        session = manager.start("1234567", ORIGIN, DESTINATION)
        # With no route service the session cannot plan and says so honestly.
        self.assertIn(session.route_status, {"updating", "unavailable"})

    def test_08_advance_moves_vessel_along_route(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")

        session = self.manager.get("1234567")
        assert session is not None
        before = session.position

        # 18 kn for 1800 simulated seconds = 9 NM.
        message = self.manager.advance_for_test("1234567", 1800.0)

        self.assertIsNotNone(message)
        assert message is not None
        self.assertEqual(message["type"], "position_update")
        self.assertNotEqual(session.position, before)
        self.assertAlmostEqual(session.travelled_nm, 9.0, delta=0.2)

    def test_09_vessel_arrives_and_stops(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")

        # Far more than the route length.
        self.manager.advance_for_test("1234567", 100_000.0)

        session = self.manager.get("1234567")
        assert session is not None
        self.assertTrue(session.arrived)
        self.assertEqual(session.status, "stopped")
        self.assertAlmostEqual(session.remaining_nm(), 0.0, delta=0.01)

    def test_10_arrived_session_does_not_advance_further(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")
        self.manager.advance_for_test("1234567", 100_000.0)

        session = self.manager.get("1234567")
        assert session is not None
        position = session.position

        self.assertIsNone(self.manager.advance_for_test("1234567", 1800.0))
        self.assertEqual(session.position, position)

    def test_11_remaining_route_starts_at_current_position(self) -> None:
        """Contract §8: the tracked route begins at the vessel's current position."""
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")
        self.manager.advance_for_test("1234567", 3600.0)

        session = self.manager.get("1234567")
        assert session is not None
        remaining = session.remaining_route()

        self.assertEqual(remaining[0], session.position)
        self.assertEqual(remaining[-1], session.route[-1])
        # Consumed waypoints are dropped.
        self.assertLess(len(remaining), len(session.route) + 1)

    def test_12_remaining_distance_decreases_as_vessel_advances(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")

        session = self.manager.get("1234567")
        assert session is not None
        first = session.remaining_nm()
        self.manager.advance_for_test("1234567", 3600.0)
        second = session.remaining_nm()

        self.assertLess(second, first)

    def test_13_stop_removes_session(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        self.assertTrue(self.manager.stop("1234567"))
        self.assertIsNone(self.manager.get("1234567"))
        # Idempotent.
        self.assertFalse(self.manager.stop("1234567"))

    def test_14_planning_failure_marks_session_unavailable(self) -> None:
        manager = TrackingSessionManager(route_service=FakeRouteService(fail=True))
        manager.start("1234567", ORIGIN, DESTINATION)

        deadline = time.time() + 5.0
        while time.time() < deadline:
            session = manager.get("1234567")
            if session is not None and not session.planning:
                break
            time.sleep(0.01)

        session = manager.get("1234567")
        assert session is not None
        self.assertEqual(session.route_status, "unavailable")
        self.assertIsNotNone(session.last_error)
        manager.clear()

    def test_15_starting_twice_replaces_the_session(self) -> None:
        self.manager.start("1234567", ORIGIN, DESTINATION)
        _wait_for_plan(self.manager, "1234567")
        self.manager.advance_for_test("1234567", 3600.0)

        self.manager.start("1234567", ORIGIN, (19.5, 72.0))
        session = self.manager.get("1234567")
        assert session is not None
        self.assertEqual(session.travelled_nm, 0.0)
        self.assertFalse(session.arrived)
        self.assertEqual(session.destination, (19.5, 72.0))

    def test_16_speed_comes_from_ship_profile(self) -> None:
        from naudisha.core.models import ShipProfile

        profile = ShipProfile(
            ship_type="Bulk Carrier",
            length=225.0,
            beam=32.2,
            draft=12.5,
            cruising_speed=10.0,
            maximum_speed=14.0,
        )
        self.manager.start("1234567", ORIGIN, DESTINATION, ship_profile=profile)
        _wait_for_plan(self.manager, "1234567")

        self.manager.advance_for_test("1234567", 3600.0)
        session = self.manager.get("1234567")
        assert session is not None
        # 10 kn for one hour is 10 NM, not the 18 kn default.
        self.assertAlmostEqual(session.travelled_nm, 10.0, delta=0.2)


class TestTrackingEndpoints(unittest.TestCase):
    """HTTP surface for tracking, backed by the real session manager."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.service = FakeRouteService()
        app.dependency_overrides[get_route_service] = lambda: self.service
        tracking_manager.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_route_service, None)
        tracking_manager.clear()

    def _start(self, imo: str = "1234567"):
        return self.client.post(
            f"/api/ships/{imo}/tracking/start",
            json={
                "destination": {"latitude": DESTINATION[0], "longitude": DESTINATION[1]},
                "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            },
        )

    def test_17_tracking_start_creates_a_session(self) -> None:
        response = self._start()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["tracking"])
        self.assertIsNotNone(tracking_manager.get("1234567"))

    def test_18_tracking_stop_ends_the_session(self) -> None:
        self._start()
        response = self.client.post("/api/ships/1234567/tracking/stop")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["tracking"])
        self.assertIsNone(tracking_manager.get("1234567"))

    def test_19_tracking_stop_is_idempotent(self) -> None:
        response = self.client.post("/api/ships/1234567/tracking/stop")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "No active tracking session")

    def test_20_tracking_stop_rejects_invalid_imo(self) -> None:
        response = self.client.post("/api/ships/1234560/tracking/stop")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_IMO")

    def test_21_status_reflects_the_live_session_position(self) -> None:
        self._start()
        _wait_for_plan(tracking_manager, "1234567")
        tracking_manager.advance_for_test("1234567", 3600.0)

        response = self.client.get("/api/ships/1234567/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        session = tracking_manager.get("1234567")
        assert session is not None
        self.assertAlmostEqual(data["position"]["latitude"], session.position[0], places=3)
        self.assertEqual(data["destination"]["latitude"], round(DESTINATION[0], 4))
        self.assertEqual(data["status"], "underway")

    def test_22_route_returns_the_planned_route(self) -> None:
        self._start()
        _wait_for_plan(tracking_manager, "1234567")

        response = self.client.get("/api/ships/1234567/route")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["route_status"], "optimal")
        self.assertGreater(len(data["route"]), 1)
        self.assertGreater(data["distance_nm"], 0.0)
        self.assertAlmostEqual(data["route"][-1]["latitude"], DESTINATION[0], places=2)

    def test_23_route_distance_shrinks_as_the_vessel_moves(self) -> None:
        self._start()
        _wait_for_plan(tracking_manager, "1234567")

        first = self.client.get("/api/ships/1234567/route").json()["distance_nm"]
        tracking_manager.advance_for_test("1234567", 3600.0)
        second = self.client.get("/api/ships/1234567/route").json()["distance_nm"]

        self.assertLess(second, first)

    def test_24_route_without_session_is_not_found(self) -> None:
        response = self.client.get("/api/ships/1234567/route")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "ROUTE_NOT_FOUND")

    def test_25_status_without_session_has_no_destination(self) -> None:
        response = self.client.get("/api/ships/1234567/status")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["destination"])

    def test_26_start_rejects_destination_equal_to_origin(self) -> None:
        response = self.client.post(
            "/api/ships/1234567/tracking/start",
            json={
                "destination": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
                "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_COORDINATES")


class TestWebSocketStreaming(unittest.TestCase):
    """WebSocket contract behaviour (§9-§11)."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.service = FakeRouteService()
        app.dependency_overrides[get_route_service] = lambda: self.service
        tracking_manager.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_route_service, None)
        tracking_manager.clear()

    def test_27_rejects_invalid_imo(self) -> None:
        with self.assertRaises(Exception):
            with self.client.websocket_connect("/ws/ships/1234560"):
                pass

    def test_28_pushes_current_route_on_connect(self) -> None:
        """A client connecting mid-voyage gets state immediately, not on the next tick."""
        self.client.post(
            "/api/ships/1234567/tracking/start",
            json={
                "destination": {"latitude": DESTINATION[0], "longitude": DESTINATION[1]},
                "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            },
        )
        _wait_for_plan(tracking_manager, "1234567")

        with self.client.websocket_connect("/ws/ships/1234567") as ws:
            message = ws.receive_json()

        self.assertEqual(message["type"], "route_update")
        self.assertIn("position", message)
        self.assertIn("route", message)
        self.assertIn("distance_nm", message)
        self.assertIn("reason", message)

    def test_29_connects_when_no_session_exists(self) -> None:
        """The socket must not error just because tracking has not started."""
        with self.client.websocket_connect("/ws/ships/1234567") as ws:
            self.assertIsNotNone(ws)

    def test_30_position_updates_are_broadcast_to_subscribers(self) -> None:
        self.client.post(
            "/api/ships/1234567/tracking/start",
            json={
                "destination": {"latitude": DESTINATION[0], "longitude": DESTINATION[1]},
                "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            },
        )
        _wait_for_plan(tracking_manager, "1234567")

        with self.client.websocket_connect("/ws/ships/1234567") as ws:
            first = ws.receive_json()
            self.assertEqual(first["type"], "route_update")

            # Step the simulator directly rather than waiting on the ticker.
            tracking_manager.advance_for_test("1234567", 1800.0)

            second = ws.receive_json()
            self.assertEqual(second["type"], "position_update")
            self.assertIn("latitude", second["position"])
            self.assertIn("timestamp", second)
            self.assertIn("position_source", second)
            self.assertIn("is_live_position", second)

    def test_31_ais_track_endpoint_returns_history(self) -> None:
        """GET /api/ships/{imo}/track returns empty when no session, and track points when AIS recorded."""
        # When no session
        res = self.client.get("/api/ships/1234567/track")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertEqual(data["source"], "ais")
        self.assertEqual(data["track"], [])

        # Start tracking and append an AIS track point
        self.client.post(
            "/api/ships/1234567/tracking/start",
            json={
                "destination": {"latitude": DESTINATION[0], "longitude": DESTINATION[1]},
                "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
            },
        )
        session = tracking_manager.get("1234567")
        self.assertIsNotNone(session)
        session.append_ais_track_point(18.55, 72.56, "2026-08-16T12:00:00Z")

        res = self.client.get("/api/ships/1234567/track")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["track"]), 1)
        self.assertEqual(data["track"][0]["latitude"], 18.55)
        self.assertEqual(data["track"][0]["longitude"], 72.56)

    def test_32_ais_stats_endpoint(self) -> None:
        """GET /api/ais/stats returns status schema."""
        res = self.client.get("/api/ais/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("enabled", data)
        self.assertIn("connected", data)
        self.assertIn("messages_seen", data)


if __name__ == "__main__":
    unittest.main()

