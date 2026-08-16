"""
Offline Unit & Integration Tests for NauDisha Backend API & Service Layer.
Strictly validates adherence to docs/API_CONTRACT.md (v2) and Phase 8.4 contract alignment.
"""

from typing import Dict, Sequence
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from naudisha.api.main import app, create_app
from naudisha.api.routes import get_route_service
from naudisha.api.schemas import (
    DEFAULT_SHIP_PROFILE_SCHEMA,
    ShipProfileSchema,
    validate_iso_8713_imo,
)
from naudisha.api.services import RoutePlanningService, RoutePlanResult
from naudisha.api.errors import (
    EnvironmentUnavailableError,
    InvalidCoordinatesError,
    InvalidIMOError,
    RouteNotFoundError,
)
from naudisha.core.models import EnvironmentalData, ShipProfile, CostWeights
from naudisha.data.composite_provider import CompositeEnvironmentalProvider
from naudisha.data.weather_provider import WeatherProvider, BatchCapableProvider, ConditionRequest


class DummyWeatherProvider(WeatherProvider):
    """Deterministic offline single-point weather provider for test isolation."""

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


class MockBatchWeatherProvider(WeatherProvider, BatchCapableProvider):
    """Deterministic offline batch provider tracking batch call counts and midpoint requests."""

    def __init__(self) -> None:
        self.batch_call_count = 0
        self.last_requests: Sequence[ConditionRequest] = []

    def fetch_conditions(self, lat: float, lon: float, timestamp: str) -> EnvironmentalData:
        return EnvironmentalData(
            timestamp=timestamp,
            current_speed=0.5,
            current_direction=120.0,
            wave_height=1.2,
            wave_direction=240.0,
            wave_period=7.5,
            wind_speed=12.0,
            wind_direction=260.0,
        )

    def fetch_conditions_batch(
        self, requests: Sequence[ConditionRequest]
    ) -> Dict[ConditionRequest, EnvironmentalData]:
        self.batch_call_count += 1
        self.last_requests = requests
        return {
            req: EnvironmentalData(
                timestamp=req.timestamp,
                current_speed=0.4,
                current_direction=110.0,
                wave_height=1.1,
                wave_direction=230.0,
                wave_period=7.0,
                wind_speed=14.0,
                wind_direction=250.0,
            )
            for req in requests
        }


class TestNauDishaAPI(unittest.TestCase):
    """Test suite for FastAPI endpoints, schemas, and contract v2 compliance."""

    def setUp(self) -> None:
        # Default test client with offline mock provider
        self.mock_provider = MockBatchWeatherProvider()
        self.offline_service = RoutePlanningService(environment_provider=self.mock_provider)
        app.dependency_overrides[get_route_service] = lambda: self.offline_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # 1. Health Endpoint Tests
    # -------------------------------------------------------------------------

    def test_01_health_endpoint(self) -> None:
        """1. GET /health returns 200 OK and documented status JSON."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "naudisha-backend")

    # -------------------------------------------------------------------------
    # 2. Valid Route Preview Tests (with IMO, without IMO, custom ship, departure_time)
    # -------------------------------------------------------------------------

    def test_02_valid_route_preview_with_imo(self) -> None:
        """2. POST /api/routes/preview with IMO returns 200 with valid contract v2 schema."""
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
            "departure_time": "2026-08-20T06:00:00Z",
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("imo_number"), "1234567")
        self.assertEqual(data.get("status"), "route_ready")
        self.assertEqual(data.get("departure_time"), "2026-08-20T06:00:00Z")
        self.assertIn("eta", data)
        self.assertTrue(data["eta"].startswith("2026-08-20T"))
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

    def test_03_route_preview_without_imo_but_with_ship(self) -> None:
        """3. Route preview without IMO but with complete ship particulars succeeds."""
        payload = {
            "imo_number": None,
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
            "ship": {
                "ship_type": "Bulk Carrier",
                "length_m": 225.0,
                "beam_m": 32.2,
                "draft_m": 12.5,
                "cruising_speed_kn": 14.0,
                "max_speed_kn": 17.0,
            },
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data.get("imo_number"))
        self.assertEqual(data.get("status"), "route_ready")
        self.assertIn("departure_time", data)
        self.assertIn("eta", data)

    def test_04_route_preview_rejected_when_both_imo_and_ship_absent(self) -> None:
        """4. Route preview rejected with 422 when neither IMO nor ship is provided."""
        payload = {
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)

    def test_05_route_preview_without_departure_time_uses_current_utc(self) -> None:
        """5. Route preview without departure_time uses current UTC timestamp."""
        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("departure_time", data)
        self.assertIn("eta", data)
        # Verify it parses as ISO datetime
        dep = datetime.fromisoformat(data["departure_time"].replace("Z", "+00:00"))
        self.assertIsNotNone(dep)

    # -------------------------------------------------------------------------
    # 3. Invalid Coordinates & Validation Tests
    # -------------------------------------------------------------------------

    def test_06_invalid_latitude_out_of_bounds(self) -> None:
        """6. Invalid latitude (> 90) returns 422 with INVALID_COORDINATES error code."""
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

    def test_07_invalid_longitude_out_of_bounds(self) -> None:
        """7. Invalid longitude (> 180) returns 422 with INVALID_COORDINATES error code."""
        payload = {
            "imo_number": "1234567",
            "start": {
                "latitude": 18.52,
                "longitude": 185.0,  # Invalid
                "destination": {"latitude": 19.07, "longitude": 72.87},
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

    def test_08_missing_destination_field(self) -> None:
        """8. Missing required field 'destination' returns 422 validation error."""
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

    # -------------------------------------------------------------------------
    # 4. ISO 8713 IMO Validation Tests
    # -------------------------------------------------------------------------

    def test_09_invalid_imo_format_alphabetic(self) -> None:
        """9. Non-numeric IMO string returns 422 with INVALID_IMO error code."""
        payload = {
            "imo_number": "ABCDEFG",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    def test_10_invalid_imo_format_too_short(self) -> None:
        """10. IMO string with not exactly 7 digits returns 422 with INVALID_IMO code."""
        payload = {
            "imo_number": "123456",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    def test_11_invalid_imo_check_digit(self) -> None:
        """11. IMO string with invalid ISO 8713 check digit returns 422 with INVALID_IMO code."""
        # 1234560: 77 % 10 = 7, but 7th digit is 0
        payload = {
            "imo_number": "1234560",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    def test_12_direct_iso_8713_validation_helper(self) -> None:
        """12. Unit validation of ISO 8713 checksum algorithm."""
        # Valid cases
        self.assertEqual(validate_iso_8713_imo("1234567"), "1234567")
        self.assertEqual(validate_iso_8713_imo("9876543"), "9876543")
        self.assertEqual(validate_iso_8713_imo("7654329"), "7654329")

        # Invalid cases
        with self.assertRaises(ValueError):
            validate_iso_8713_imo("1234568")
        with self.assertRaises(ValueError):
            validate_iso_8713_imo("12345")
        with self.assertRaises(ValueError):
            validate_iso_8713_imo("12345678")

    # -------------------------------------------------------------------------
    # 5. Dependency Injection & Service Integration Tests
    # -------------------------------------------------------------------------

    def test_13_dependency_injection_custom_provider(self) -> None:
        """13. Injected RoutePlanningService with custom provider executes successfully."""
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

    def test_14_response_serialization_fields_match_contract_v2(self) -> None:
        """14. Verify response JSON keys exactly match docs/API_CONTRACT.md section 5."""
        payload = {
            "imo_number": "1234567",
            "start": {"latitude": 18.52, "longitude": 72.91},
            "destination": {"latitude": 19.07, "longitude": 72.87},
        }
        response = self.client.post("/api/routes/preview", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Contract Section 5 required fields:
        expected_keys = {
            "imo_number",
            "status",
            "departure_time",
            "eta",
            "route",
            "distance_nm",
            "estimated_time_hours",
            "total_cost",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    # -------------------------------------------------------------------------
    # 6. Error Mapping & Service Failures
    # -------------------------------------------------------------------------

    def test_15_environment_unavailable_error_mapped(self) -> None:
        """15. Service raising EnvironmentUnavailableError maps to 503 JSON response."""
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

    def test_16_route_not_found_error_mapped(self) -> None:
        """16. Service raising RouteNotFoundError maps to 404 JSON response."""
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

    def test_17_unhandled_exception_maps_to_500_internal_error(self) -> None:
        """17. Unhandled Python exception maps to clean 500 INTERNAL_ERROR without leaking traceback."""
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
    # 7. Ship Identify, Tracking, Status & Route Endpoints
    # -------------------------------------------------------------------------

    def test_18_ship_identify_endpoint_includes_ship_block(self) -> None:
        """18. POST /api/ships returns real ship profile block conforming to contract v2 §4."""
        payload = {"imo_number": "1234567"}
        response = self.client.post("/api/ships", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertEqual(data["name"], "Demo Vessel")
        self.assertEqual(data["status"], "underway")
        self.assertIn("position", data)
        self.assertIn("ship", data)
        self.assertEqual(data["ship"]["ship_type"], "Container Vessel (Panamax)")
        self.assertEqual(data["ship"]["length_m"], 294.0)
        self.assertEqual(data["ship"]["beam_m"], 32.2)
        self.assertEqual(data["ship"]["draft_m"], 12.0)
        self.assertEqual(data["ship"]["cruising_speed_kn"], 18.0)
        self.assertEqual(data["ship"]["max_speed_kn"], 23.0)

    def test_18b_ship_identify_real_vessels(self) -> None:
        """18b. POST /api/ships returns real vessel records for real IMO numbers."""
        # Test Shinsung Dream (General Cargo Vessel - Real IMO 9176187)
        res_shinsung = self.client.post("/api/ships", json={"imo_number": "9176187"})
        self.assertEqual(res_shinsung.status_code, 200)
        data_shinsung = res_shinsung.json()
        self.assertEqual(data_shinsung["name"], "Shinsung Dream")
        self.assertEqual(data_shinsung["ship"]["ship_type"], "General Cargo Vessel")
        self.assertEqual(data_shinsung["ship"]["length_m"], 106.0)
        self.assertEqual(data_shinsung["ship"]["draft_m"], 7.0)

        # Test Courage (Vehicles Carrier - Real IMO 8916968)
        res_courage = self.client.post("/api/ships", json={"imo_number": "8916968"})
        self.assertEqual(res_courage.status_code, 200)
        data_courage = res_courage.json()
        self.assertEqual(data_courage["name"], "Courage")
        self.assertEqual(data_courage["ship"]["ship_type"], "Vehicles Carrier")
        self.assertEqual(data_courage["ship"]["length_m"], 199.9)
        self.assertEqual(data_courage["ship"]["draft_m"], 8.8)

        # Test Ever Given (Container Ship - Real IMO 9811000)
        res_eg = self.client.post("/api/ships", json={"imo_number": "9811000"})
        self.assertEqual(res_eg.status_code, 200)
        data_eg = res_eg.json()
        self.assertEqual(data_eg["name"], "Ever Given")
        self.assertEqual(data_eg["ship"]["length_m"], 399.9)
        self.assertEqual(data_eg["ship"]["beam_m"], 58.8)

    def test_18c_ship_identify_universal_resolution_and_404_mock(self) -> None:
        """18c. POST /api/ships dynamically resolves uncataloged valid IMOs, and returns 404 if provider returns None."""
        # 1. Universal resolution for valid IMO
        res_universal = self.client.post("/api/ships", json={"imo_number": "9074729"})
        self.assertEqual(res_universal.status_code, 200)
        data = res_universal.json()
        self.assertEqual(data["imo_number"], "9074729")
        self.assertIn("ship", data)

        # 2. Injected mock provider returning None triggers 404 SHIP_NOT_FOUND
        from naudisha.api.routes import get_vessel_provider
        from naudisha.data.vessel_provider import MockVesselProvider
        empty_mock = MockVesselProvider()
        self.client.app.dependency_overrides[get_vessel_provider] = lambda: empty_mock
        try:
            res_404 = self.client.post("/api/ships", json={"imo_number": "9074729"})
            self.assertEqual(res_404.status_code, 404)
            self.assertEqual(res_404.json()["error"]["code"], "SHIP_NOT_FOUND")
        finally:
            self.client.app.dependency_overrides.pop(get_vessel_provider, None)

    def test_19_tracking_start_endpoint(self) -> None:
        """19. POST /api/ships/{imo}/tracking/start accepts destination body and returns confirmation."""
        payload = {"destination": {"latitude": 19.07, "longitude": 72.87}}
        response = self.client.post("/api/ships/1234567/tracking/start", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertTrue(data["tracking"])
        self.assertEqual(data["message"], "Ship tracking started")

    def test_20_tracking_start_invalid_imo_rejected(self) -> None:
        """20. POST /api/ships/{imo}/tracking/start rejects invalid IMO with 422."""
        payload = {"destination": {"latitude": 19.07, "longitude": 72.87}}
        response = self.client.post("/api/ships/invalid_imo/tracking/start", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["error"]["code"], "INVALID_IMO")

    def test_21_ship_status_endpoint(self) -> None:
        """21. GET /api/ships/{imo}/status returns status, position, and destination."""
        response = self.client.get("/api/ships/1234567/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertEqual(data["status"], "underway")
        self.assertIn("position", data)
        self.assertIn("destination", data)
        self.assertIn("timestamp", data)

    def test_22_ship_route_endpoint(self) -> None:
        """22. GET /api/ships/{imo}/route returns route, statistics, destination, updated_at."""
        response = self.client.get("/api/ships/1234567/route")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["imo_number"], "1234567")
        self.assertEqual(data["route_status"], "optimal")
        self.assertIn("destination", data)
        self.assertIsInstance(data["route"], list)
        self.assertIn("distance_nm", data)
        self.assertIn("estimated_time_hours", data)
        self.assertIn("total_cost", data)
        self.assertIn("updated_at", data)

    # -------------------------------------------------------------------------
    # 8. Ship Profile Schema Mapping Unit Tests
    # -------------------------------------------------------------------------

    def test_23_ship_profile_schema_mapping(self) -> None:
        """23. ShipProfileSchema maps to and from core domain ShipProfile model."""
        schema = ShipProfileSchema(
            ship_type="Bulk Carrier",
            length_m=225.0,
            beam_m=32.2,
            draft_m=12.5,
            cruising_speed_kn=14.0,
            max_speed_kn=17.0,
        )
        domain = schema.to_domain_model()
        self.assertEqual(domain.ship_type, "Bulk Carrier")
        self.assertEqual(domain.length, 225.0)
        self.assertEqual(domain.beam, 32.2)
        self.assertEqual(domain.draft, 12.5)
        self.assertEqual(domain.cruising_speed, 14.0)
        self.assertEqual(domain.maximum_speed, 17.0)

        mapped_back = ShipProfileSchema.from_domain_model(domain)
        self.assertEqual(mapped_back.length_m, 225.0)
        self.assertEqual(mapped_back.max_speed_kn, 17.0)

    # -------------------------------------------------------------------------
    # 9. Direct RoutePlanningService Unit Tests
    # -------------------------------------------------------------------------

    def test_24_service_direct_planning(self) -> None:
        """24. Direct invocation of RoutePlanningService produces valid RoutePlanResult with ETA."""
        service = RoutePlanningService(environment_provider=self.mock_provider)
        result = service.plan_preview_route(
            imo_number="1234567",
            start_lat=18.52,
            start_lon=72.91,
            dest_lat=19.07,
            dest_lon=72.87,
            timestamp="2026-08-20T08:00:00Z",
        )
        self.assertIsInstance(result, RoutePlanResult)
        self.assertEqual(result.imo_number, "1234567")
        self.assertEqual(result.status, "route_ready")
        self.assertEqual(result.departure_time, "2026-08-20T08:00:00Z")
        self.assertTrue(result.eta.startswith("2026-08-20T"))
        self.assertGreater(result.distance_nm, 0.0)
        self.assertGreater(result.estimated_time_hours, 0.0)
        self.assertGreater(result.total_cost, 0.0)

    def test_25_service_same_start_and_destination(self) -> None:
        """25. Direct invocation with identical start and destination coordinates returns 0 cost/distance."""
        service = RoutePlanningService(environment_provider=self.mock_provider)
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

    def test_26_service_uses_batch_capable_provider_pipeline(self) -> None:
        """26. Route planning service utilizes the batch environmental pipeline for graph population."""
        batch_provider = MockBatchWeatherProvider()
        service = RoutePlanningService(environment_provider=batch_provider)

        result = service.plan_preview_route(
            imo_number="7654329",
            start_lat=18.0,
            start_lon=71.0,
            dest_lat=18.8,
            dest_lon=71.8,
        )

        self.assertIsInstance(result, RoutePlanResult)
        self.assertEqual(result.imo_number, "7654329")
        self.assertEqual(result.status, "route_ready")
        self.assertGreater(len(result.route), 1)
        self.assertGreater(result.distance_nm, 0.0)
        self.assertGreater(result.total_cost, 0.0)

        # Confirm that BatchCapableProvider was used and received all edge midpoints
        self.assertEqual(batch_provider.batch_call_count, 1)
        self.assertGreater(len(batch_provider.last_requests), 0)

    def test_27_bounding_grid_covers_corridor_with_margin(self) -> None:
        """27. Dynamic grid builder wraps origin/bounds properly covering departure and destination."""
        service = RoutePlanningService(environment_provider=self.mock_provider)
        graph = service._build_bounding_grid(start_lat=18.2, start_lon=71.1, dest_lat=18.9, dest_lon=71.9)

        # Verify bounds encompass start and dest
        self.assertLessEqual(graph.config.origin_lat, 18.2)
        self.assertLessEqual(graph.config.origin_lon, 71.1)

        max_lat = graph.config.origin_lat + (graph.config.rows - 1) * graph.config.lat_spacing
        max_lon = graph.config.origin_lon + (graph.config.cols - 1) * graph.config.lon_spacing
        self.assertGreaterEqual(max_lat, 18.9)
    def test_28_websocket_endpoint_valid_imo(self) -> None:
        """28. WS /ws/ships/{imo} accepts connection for valid ISO 8713 IMO."""
        with self.client.websocket_connect("/ws/ships/1234567") as websocket:
            # Successfully connected
            self.assertIsNotNone(websocket)

    def test_29_websocket_endpoint_invalid_imo(self) -> None:
        """29. WS /ws/ships/{imo} rejects connection for invalid IMO."""
        with self.assertRaises(Exception):
            with self.client.websocket_connect("/ws/ships/invalid_imo"):
                pass


if __name__ == "__main__":
    unittest.main()
