"""
Unit tests for D* Lite Real-Time Dynamic Replanning and Hazard Avoidance Simulation.
Tests both the RoutePlanningService.simulate_dynamic_replan method and the POST /api/routes/simulate-replan HTTP endpoint.
"""

import unittest
from fastapi.testclient import TestClient

from naudisha.api.main import app
from naudisha.api.services import RoutePlanningService
from naudisha.core.models import ShipProfile


class TestDynamicReplanning(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.service = RoutePlanningService()

    def test_service_simulate_dynamic_replan_cyclone(self):
        """Verify service dynamically replans around a cyclone hazard in milliseconds."""
        result = self.service.simulate_dynamic_replan(
            current_lat=18.95,
            current_lon=72.82,
            dest_lat=25.26,
            dest_lon=55.28,
            hazard_lat=21.50,
            hazard_lon=64.00,
            hazard_radius_nm=50.0,
            hazard_type="storm",
            hazard_severity=1.5,
        )

        self.assertIn("new_route", result)
        self.assertIn("replan_time_ms", result)
        self.assertIn("affected_edges_count", result)
        self.assertGreater(len(result["new_route"]), 2)
        self.assertLess(result["replan_time_ms"], 2000.0)  # Should be sub-second
        self.assertGreater(result["affected_edges_count"], 0)
        self.assertGreater(len(result["legs"]), 0)

    def test_service_simulate_dynamic_replan_current_gyre(self):
        """Verify service replanning handles opposing current gyre hazards."""
        result = self.service.simulate_dynamic_replan(
            current_lat=18.95,
            current_lon=72.82,
            dest_lat=15.00,
            dest_lon=73.50,
            hazard_lat=17.00,
            hazard_lon=73.00,
            hazard_radius_nm=30.0,
            hazard_type="current",
            hazard_severity=2.0,
        )

        self.assertIn("new_route", result)
        self.assertGreater(len(result["new_route"]), 1)
        self.assertGreater(result["total_cost"], 0.0)

    def test_api_simulate_replan_endpoint(self):
        """Verify POST /api/routes/simulate-replan returns 200 OK with correct schema."""
        payload = {
            "current_position": {"latitude": 18.95, "longitude": 72.82},
            "destination": {"latitude": 25.26, "longitude": 55.28},
            "active_route": [
                {"latitude": 18.95, "longitude": 72.82},
                {"latitude": 21.00, "longitude": 64.00},
                {"latitude": 25.26, "longitude": 55.28},
            ],
            "hazard": {
                "id": "cyclone-vortex-01",
                "name": "Tropical Cyclone Simulation",
                "type": "storm",
                "center": {"latitude": 21.00, "longitude": 64.00},
                "radius_nm": 45.0,
                "severity": 1.2,
                "description": "Simulated gale force storm vortex",
            },
            "optimization_objective": "balanced",
        }

        response = self.client.post("/api/routes/simulate-replan", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("new_route", data)
        self.assertIn("replan_time_ms", data)
        self.assertIn("affected_edges_count", data)
        self.assertIn("hazard_avoidance_score", data)
        self.assertGreater(len(data["new_route"]), 2)
        self.assertEqual(len(data["previous_route"]), 3)
        self.assertGreater(len(data["legs"]), 0)


if __name__ == "__main__":
    unittest.main()
