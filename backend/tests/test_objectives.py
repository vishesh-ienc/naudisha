"""
Unit and integration tests for Objective-Driven Route Optimization in NauDisha.
Verifies CostWeights mappings, safety invariants, schema validation, and cache signature behavior.
"""

import unittest
from datetime import datetime, timezone

from naudisha.api.planning import PlanningManager
from naudisha.api.schemas import (
    Coordinate,
    DEFAULT_SHIP_PROFILE_SCHEMA,
    RoutePreviewRequest,
    RoutePreviewResponse,
)
from naudisha.api.services import (
    RoutePlanningService,
    objective_to_weights,
    _weights_to_dict,
)
from naudisha.core.models import CostWeights, ShipProfile
from pydantic import ValidationError


class TestObjectiveWeights(unittest.TestCase):
    """Verifies that each optimization objective maps to the mathematically expected cost weights."""

    def test_fuel_efficiency_weights(self):
        w = objective_to_weights("fuel_efficiency")
        self.assertGreater(w.fuel, w.time, "Fuel weight should exceed time weight for fuel_efficiency")
        self.assertGreaterEqual(w.fuel, 2.5, "Fuel weight should be heavily weighted (>= 2.5)")
        self.assertGreaterEqual(w.safety, 1.0, "Safety weight must remain >= 1.0")
        self.assertGreater(w.current, 1.0, "Current assistance should be weighted up for fuel savings")

    def test_fastest_weights(self):
        w = objective_to_weights("fastest")
        self.assertGreater(w.time, w.fuel, "Time weight should exceed fuel weight for fastest")
        self.assertGreaterEqual(w.time, 3.0, "Time weight should be heavily weighted (>= 3.0)")
        self.assertGreaterEqual(w.safety, 1.0, "Safety weight must remain >= 1.0")
        self.assertGreater(w.current, 1.0, "Current assistance should be weighted up for speed")

    def test_safety_weights(self):
        w = objective_to_weights("safety")
        self.assertGreaterEqual(w.safety, 3.0, "Safety weight should be >= 3.0")
        self.assertGreaterEqual(w.wave, 2.5, "Wave penalty should be heavily weighted")
        self.assertGreaterEqual(w.wind, 2.0, "Wind penalty should be heavily weighted")
        self.assertLess(w.time, w.safety, "Time should be de-prioritized relative to safety")
        self.assertLess(w.fuel, w.safety, "Fuel should be de-prioritized relative to safety")

    def test_balanced_weights(self):
        w = objective_to_weights("balanced")
        self.assertGreaterEqual(w.safety, 1.0)
        # Check that no single dynamic factor dominates by > 3x the minimum
        factors = [w.time, w.fuel, w.wind, w.wave, w.current]
        self.assertLessEqual(max(factors) / min(factors), 3.0)

    def test_default_fallback(self):
        w_none = objective_to_weights(None)
        w_unknown = objective_to_weights("unknown_strategy")
        w_balanced = objective_to_weights("balanced")
        self.assertEqual(w_none, w_balanced)
        self.assertEqual(w_unknown, w_balanced)

    def test_safety_invariant_all_objectives(self):
        """CRITICAL: Safety weight must never be zero or below 1.0 for ANY objective."""
        for obj in ["fuel_efficiency", "fastest", "safety", "balanced", None, ""]:
            w = objective_to_weights(obj)
            self.assertGreaterEqual(
                w.safety,
                1.0,
                f"Safety weight was {w.safety} for objective '{obj}' — violated safety floor invariant!",
            )
            # All weights must be non-negative
            for factor in ("time", "fuel", "wind", "wave", "current", "safety"):
                val = getattr(w, factor)
                self.assertGreaterEqual(val, 0.0, f"Weight for {factor} was negative ({val})")

    def test_weights_to_dict(self):
        w = CostWeights(time=1.0, fuel=2.0, wind=1.2, wave=1.5, current=0.9, safety=2.5)
        d = _weights_to_dict(w)
        self.assertEqual(d["time"], 1.0)
        self.assertEqual(d["fuel"], 2.0)
        self.assertEqual(d["wind"], 1.2)
        self.assertEqual(d["wave"], 1.5)
        self.assertEqual(d["current"], 0.9)
        self.assertEqual(d["safety"], 2.5)


class TestObjectiveSchemaValidation(unittest.TestCase):
    """Tests Pydantic request schema validation for optimization_objective."""

    def test_valid_objectives(self):
        for obj in ["fuel_efficiency", "fastest", "safety", "balanced"]:
            req = RoutePreviewRequest(
                start=Coordinate(latitude=18.52, longitude=72.55),
                destination=Coordinate(latitude=15.40, longitude=73.80),
                ship=DEFAULT_SHIP_PROFILE_SCHEMA,
                optimization_objective=obj,
            )
            self.assertEqual(req.optimization_objective, obj)

    def test_objective_case_and_whitespace_insensitivity(self):
        req = RoutePreviewRequest(
            start=Coordinate(latitude=18.52, longitude=72.55),
            destination=Coordinate(latitude=15.40, longitude=73.80),
            ship=DEFAULT_SHIP_PROFILE_SCHEMA,
            optimization_objective="  Fuel_Efficiency  ",
        )
        self.assertEqual(req.optimization_objective, "fuel_efficiency")

    def test_default_objective_is_balanced(self):
        req = RoutePreviewRequest(
            start=Coordinate(latitude=18.52, longitude=72.55),
            destination=Coordinate(latitude=15.40, longitude=73.80),
            ship=DEFAULT_SHIP_PROFILE_SCHEMA,
        )
        self.assertEqual(req.optimization_objective, "balanced")

    def test_invalid_objective_rejected(self):
        with self.assertRaises(ValidationError):
            RoutePreviewRequest(
                start=Coordinate(latitude=18.52, longitude=72.55),
                destination=Coordinate(latitude=15.40, longitude=73.80),
                ship=DEFAULT_SHIP_PROFILE_SCHEMA,
                optimization_objective="cheapest_route",
            )


class TestPlanningManagerSignature(unittest.TestCase):
    """Tests that cache keys differ when objectives differ, preventing cache collisions."""

    def test_distinct_signatures_for_different_objectives(self):
        start = (18.52, 72.55)
        dest = (15.40, 73.80)
        dep_time = "2026-08-20T06:00:00Z"

        sig_fuel = PlanningManager.signature(
            imo_number=None,
            start=start,
            destination=dest,
            departure_time=dep_time,
            optimization_objective="fuel_efficiency",
        )
        sig_fast = PlanningManager.signature(
            imo_number=None,
            start=start,
            destination=dest,
            departure_time=dep_time,
            optimization_objective="fastest",
        )
        sig_safe = PlanningManager.signature(
            imo_number=None,
            start=start,
            destination=dest,
            departure_time=dep_time,
            optimization_objective="safety",
        )
        sig_bal = PlanningManager.signature(
            imo_number=None,
            start=start,
            destination=dest,
            departure_time=dep_time,
            optimization_objective="balanced",
        )

        signatures = [sig_fuel, sig_fast, sig_safe, sig_bal]
        self.assertEqual(len(set(signatures)), 4, "All 4 objectives must produce distinct cache keys")

    def test_same_signature_for_normalized_input(self):
        start = (18.52, 72.55)
        dest = (15.40, 73.80)
        dep_time = "2026-08-20T06:00:00Z"

        sig1 = PlanningManager.signature(None, start, dest, dep_time, "fuel_efficiency")
        sig2 = PlanningManager.signature(None, start, dest, dep_time, " FUEL_EFFICIENCY ")
        self.assertEqual(sig1, sig2)


class TestRoutePlanningServiceObjectiveIntegration(unittest.TestCase):
    """Tests that RoutePlanningService populates optimization_objective and cost_weights in output."""

    def setUp(self):
        self.service = RoutePlanningService(environment_provider=None)

    def test_zero_distance_preserves_objective_and_weights(self):
        result = self.service.plan_preview_route(
            imo_number=None,
            start_lat=18.52,
            start_lon=72.55,
            dest_lat=18.52,
            dest_lon=72.55,
            optimization_objective="fuel_efficiency",
        )
        self.assertEqual(result.optimization_objective, "fuel_efficiency")
        self.assertIn("fuel", result.cost_weights)
        self.assertGreater(result.cost_weights["fuel"], result.cost_weights["time"])


if __name__ == "__main__":
    unittest.main()
