"""
Offline Unit & Integration Tests for NauDisha Backend API & Service Layer.
Strictly validates adherence to docs/API_CONTRACT.md without external network calls.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from naudisha.api.main import app, create_app
from naudisha.api.routes import get_route_service
from naudisha.api.services import RoutePlanningService, RoutePlanResult
from naudisha.api.errors import (
    EnvironmentUnavailableError,
    InvalidCoordinatesError,
    InvalidIMOError,
    RouteNotFoundError,
)
from naudisha.core.models import EnvironmentalData, ShipProfile, CostWeights
from naudisha.data.weather_provider import WeatherProvider


class DummyWeatherProvider(WeatherProvider):
    """Deterministic offline weather provider for test isolation."""

    def __init__(self, current_speed: float = 0.5, wave_height: float = 1.2, wind_speed: float = 12.0) -> None:
        self.current_speed = current_speed
        self.wave_height = wave_height
        self.wind_speed = wind_speed

    def fetch_conditions(self, lat: float, lon: float, timestamp: str) -> EnvironmentalData:
        return EnvironmentalData(
            timestamp=timestamp,
            current_speed=self.current_speed,
            current_direction=120.0,
            wave_height=self.wave_height,
            wave_direction=240.0,
            wave_period=7.5,
            wind_speed=self.wind_speed,
            wind_direction=260.0,
        )


class TestNauDishaAPI(unittest.TestCase):
    """Test suite for FastAPI endpoints and error format compliance."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    # -------------------------------------------------------------------------
    # 1. Health Endpoint Tests
    # -------------------------------------------------------------------------

    def test_01_health_endpoint(self) -> None:
        """1. GET /health returns 200 OK and expected status JSON."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "naudisha-backend")

    # -------------------------------------------------------------------------
    # 2. Valid Route Preview Tests
    # -------------------------------------------------------------------------

    def test_02_valid_route_preview(self) -> None:
        """2. POST /api/routes/preview returns 200 with valid route schema."""
        payload = {
            "imo_number": "1234567",
            "start": {
                "latitude": 18.52,
                "longitude": 72.91,
            },
            "destination": {
                "latitude": 19.07,
                "longitude": 72.87,
            },
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("imo_number"), "1234567")
        self.assertEqual(data.get("status"), "route_ready")
        self.assertIsInstance(data.get("route"), list)
        self.assertGreater(len(data["route"]), 0)
        self.assertIsInstance(data.get("distance_nm"), (int, float))
        self.assertIsInstance(data.get("estimated_time_hours"), (int, float))
        self.assertIsInstance(data.get("total_cost"), (int, float))

        # Check waypoint coordinate format
        first_wp = data["route"][0]
        self.assertIn("latitude", first_wp)
        self.assertIn("longitude", first_wp)
        self.assertIsInstance(first_wp["latitude"], (int, float))
        self.assertIsInstance(first_wp["longitude"], (int, float))

    # -------------------------------------------------------------------------
    # 3. Invalid Coordinates Tests
    # -------------------------------------------------------------------------

    def test_03_invalid_latitude_out_of_bounds(self) -> None:
        """3. Invalid latitude (> 90) returns 422 with INVALID_COORDINATES error code."""
        payload = {
            "imo_number": "1234567",
            "start": {
                "latitude": 95.0,  # Invalid
                "longitude": 72.91,
            },
            "destination": {
                "latitude": 19.07,
                "longitude": 72.87,
            },
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_COORDINATES")
        self.assertIn("latitude", data["error"]["message"].lower())

    def test_04_invalid_longitude_out_of_bounds(self) -> None:
        """4. Invalid longitude (> 180) returns 422 with INVALID_COORDINATES error code."""
        payload = {
            "imo_number": "1234567",
            "start": {
                "latitude": 18.52,
                "longitude": 185.0,  # Invalid
            },
            "destination": {
                "latitude": 19.07,
                "longitude": 72.87,
            },
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_COORDINATES")

    # -------------------------------------------------------------------------
    # 4. Missing Required Fields Tests
    # -------------------------------------------------------------------------

    def test_05_missing_destination_field(self) -> None:
        """5. Missing required field 'destination' returns 422 validation error."""
        payload = {
            "imo_number": "1234567",
            "start": {
                "latitude": 18.52,
                "longitude": 72.91,
            },
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("code", data["error"])
        self.assertIn("message", data["error"])

    def test_06_missing_imo_number(self) -> None:
        """6. Missing required field 'imo_number' returns 422 validation error."""
        payload = {
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    # -------------------------------------------------------------------------
    # 5. IMO Validation Tests
    # -------------------------------------------------------------------------

    def test_07_invalid_imo_format_alphabetic(self) -> None:
        """7. Non-numeric IMO string returns 422 with INVALID_IMO error code."""
        payload = {
            "imo_number": "ABCDEF",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    def test_08_invalid_imo_format_too_short(self) -> None:
        """8. IMO string with less than 6 digits returns 422 with INVALID_IMO code."""
        payload = {
            "imo_number": "123",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    # -------------------------------------------------------------------------
    # 6. Dependency Injection & Mock Provider Tests
    # -------------------------------------------------------------------------

    def test_09_dependency_injection_custom_provider(self) -> None:
        """9. Injected RoutePlanningService with custom provider executes successfully."""
        mock_provider = DummyWeatherProvider(current_speed=1.5, wave_height=2.0, wind_speed=20.0)
        custom_service = RoutePlanningService(environment_provider=mock_provider)

        test_app = create_app()
        test_app.dependency_overrides[get_route_service] = lambda: custom_service
        custom_client = TestClient(test_app)

        payload = {
            "imo_number": "9876543",
            "start": {"latitude": 18.0, "longitude": 71.0},
            "destination": {"latitude": 18.5, "longitude": 71.5},
        }
        response = custom_client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "9876543")
        self.assertEqual(data["status"], "route_ready")
        self.assertGreater(len(data["route"]), 1)

    # -------------------------------------------------------------------------
    # 7. Serialization & API Contract Compliance
    # -------------------------------------------------------------------------

    def test_10_response_serialization_fields_match_contract(self) -> None:
        """10. Verify response JSON keys exactly match docs/API_CONTRACT.md section 5."""
        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Contract Section 5 required fields:
        expected_keys = {"imo_number", "status", "route", "distance_nm", "estimated_time_hours", "total_cost"}
        self.assertEqual(set(data.keys()), expected_keys)

    # -------------------------------------------------------------------------
    # 8. Error Mapping & Service Failures
    # -------------------------------------------------------------------------

    def test_11_environment_unavailable_error_mapped(self) -> None:
        """11. Service raising EnvironmentUnavailableError maps to 503 JSON response."""
        failing_service = MagicMock(spec=RoutePlanningService)
        failing_service.plan_preview_route.side_effect = EnvironmentUnavailableError("CMEMS provider unreachable")

        test_app = create_app()
        test_app.dependency_overrides[get_route_service] = lambda: failing_service
        custom_client = TestClient(test_app)

        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = custom_client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["error"]["code"], "ENVIRONMENT_UNAVAILABLE")
        self.assertIn("CMEMS provider unreachable", data["error"]["message"])

    def test_12_route_not_found_error_mapped(self) -> None:
        """12. Service raising RouteNotFoundError maps to 404 JSON response."""
        failing_service = MagicMock(spec=RoutePlanningService)
        failing_service.plan_preview_route.side_effect = RouteNotFoundError("No navigable path through storm")

        test_app = create_app()
        test_app.dependency_overrides[get_route_service] = lambda: failing_service
        custom_client = TestClient(test_app)

        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = custom_client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"]["code"], "ROUTE_NOT_FOUND")

    def test_13_unhandled_exception_maps_to_500_internal_error(self) -> None:
        """13. Unhandled Python exception maps to clean 500 INTERNAL_ERROR without leaking traceback."""
        failing_service = MagicMock(spec=RoutePlanningService)
        failing_service.plan_preview_route.side_effect = RuntimeError("Database pointer corrupted")

        test_app = create_app()
        test_app.dependency_overrides[get_route_service] = lambda: failing_service
        custom_client = TestClient(test_app, raise_server_exceptions=False)

        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = custom_client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertEqual(data["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("Database pointer corrupted", data["error"]["message"])

    # -------------------------------------------------------------------------
    # 9. Direct RoutePlanningService Unit Tests
    # -------------------------------------------------------------------------

    def test_14_service_direct_planning(self) -> None:
        """14. Direct invocation of RoutePlanningService produces valid RoutePlanResult."""
        service = RoutePlanningService()
        result = service.plan_preview_route(
            imo_number="1234567",
            start_lat=18.52,
            start_lon=72.91,
            dest_lat=19.07,
            dest_lon=72.87,
        )
        self.assertIsInstance(result, RoutePlanResult)
        self.assertEqual(result.imo_number, "1234567")
        self.assertEqual(result.status, "route_ready")
        self.assertGreater(result.distance_nm, 0.0)
        self.assertGreater(result.estimated_time_hours, 0.0)
        self.assertGreater(result.total_cost, 0.0)

    def test_15_service_same_start_and_destination(self) -> None:
        """15. Direct invocation with identical start and destination coordinates returns 0 cost/distance."""
        service = RoutePlanningService()
        result = service.plan_preview_route(
            imo_number="1234567",
            start_lat=18.52,
            start_lon=72.91,
            dest_lat=18.52,
            dest_lon=72.91,
        )
        self.assertEqual(result.distance_nm, 0.0)
        self.assertEqual(result.estimated_time_hours, 0.0)
        self.assertEqual(result.total_cost, 0.0)
        self.assertEqual(len(result.route), 1)

    # -------------------------------------------------------------------------
    # 10. Ship Identify Endpoint Test
    # -------------------------------------------------------------------------

    def test_16_ship_identify_endpoint(self) -> None:
        """16. POST /api/ships creates or identifies vessel matching API contract."""
        payload = {"imo_number": "1234567"}
        response = self.client.post("/api/ships", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertEqual(data["name"], "Demo Vessel")
        self.assertEqual(data["status"], "underway")
        self.assertIn("position", data)
        self.assertIn("latitude", data["position"])
        self.assertIn("longitude", data["position"])


if __name__ == "__main__":
    unittest.main()
