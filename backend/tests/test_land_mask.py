"""
Unit and integration tests for Land Masking and Navigability avoidance.
Ensures ships never navigate across landmasses and properly round the Indian Peninsula.
"""

import unittest
from naudisha.routing.land_mask import (
    is_point_on_land,
    is_segment_crossing_land,
    is_cross_peninsular_voyage,
)
from naudisha.api.services import RoutePlanningService
from naudisha.data.weather_provider import MockWeatherProvider


class TestLandMaskingAndRouting(unittest.TestCase):
    """Tests land detection and maritime routing avoidance."""

    def test_land_points_identification(self):
        # Inland points
        self.assertTrue(is_point_on_land(12.97, 77.59))   # Bangalore
        self.assertTrue(is_point_on_land(17.38, 78.48))   # Hyderabad
        self.assertTrue(is_point_on_land(21.14, 79.08))   # Nagpur
        self.assertTrue(is_point_on_land(7.50, 80.70))    # Central Sri Lanka

        # Ocean points
        self.assertFalse(is_point_on_land(15.00, 70.00))  # Arabian Sea
        self.assertFalse(is_point_on_land(15.00, 85.00))  # Bay of Bengal
        self.assertFalse(is_point_on_land(6.50, 77.50))   # South of Cape Comorin
        self.assertFalse(is_point_on_land(5.20, 80.50))   # South of Sri Lanka

    def test_segment_crossing_land(self):
        # Direct line from Mumbai to Chennai cuts across peninsular India
        self.assertTrue(is_segment_crossing_land(18.85, 72.45, 13.10, 80.35))
        # Direct line between two open sea points in Arabian Sea does not cross land
        self.assertFalse(is_segment_crossing_land(18.85, 72.45, 14.00, 72.00))

    def test_cross_peninsular_voyage_detection(self):
        self.assertTrue(is_cross_peninsular_voyage(18.85, 72.45, 13.10, 80.35))  # Mumbai -> Chennai
        self.assertTrue(is_cross_peninsular_voyage(13.10, 80.35, 18.85, 72.45))  # Chennai -> Mumbai
        self.assertFalse(is_cross_peninsular_voyage(18.85, 72.45, 9.96, 76.22))   # Mumbai -> Kochi (same coast)

    def test_cross_peninsular_route_avoids_land(self):
        service = RoutePlanningService(environment_provider=MockWeatherProvider())
        result = service.plan_preview_route(
            imo_number="TEST_AVOID_LAND",
            start_lat=18.85,
            start_lon=72.45,
            dest_lat=13.10,
            dest_lon=80.35,
            optimization_objective="balanced",
        )

        self.assertIsNotNone(result)
        self.assertGreater(len(result.route), 10)
        self.assertGreater(result.distance_nm, 1200.0)  # Must be > direct Euclidean line since it routes around south cape

        # Verify all waypoints are in the ocean
        for lat, lon in result.route:
            self.assertFalse(
                is_point_on_land(lat, lon),
                f"Waypoint ({lat}, {lon}) falls on land!",
            )


if __name__ == "__main__":
    unittest.main()
