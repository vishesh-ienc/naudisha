"""
Unit & Integration Tests for Real Vessel Provider, Registry, and API Mapping.
Validates real vessel data lookup, schema mapping, caching, and failure modes.
"""

import unittest
from naudisha.data.vessel_provider import (
    CompositeVesselProvider,
    MockVesselProvider,
    RegistryVesselProvider,
    VesselRecord,
    GLOBAL_VESSEL_REGISTRY,
)


class TestVesselProvider(unittest.TestCase):
    """Test suite for vessel data providers and real maritime registry integration."""

    def setUp(self) -> None:
        self.registry = RegistryVesselProvider()
        self.composite = CompositeVesselProvider()

    def test_01_real_vessel_lookup_courage(self) -> None:
        """1. Real vessel lookup for IMO 9176187 (Courage - Vehicle Carrier)."""
        vessel = self.registry.get_vessel_by_imo("9176187")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Courage")
        self.assertEqual(vessel.ship_type, "Vehicles Carrier")
        self.assertEqual(vessel.length_m, 199.9)
        self.assertEqual(vessel.beam_m, 32.2)
        self.assertEqual(vessel.draft_m, 8.8)
        self.assertEqual(vessel.cruising_speed_kn, 18.0)
        self.assertEqual(vessel.max_speed_kn, 20.5)

    def test_02_real_vessel_lookup_ever_given(self) -> None:
        """2. Real vessel lookup for IMO 9811000 (Ever Given - Ultra Large Container Ship)."""
        vessel = self.registry.get_vessel_by_imo("9811000")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Ever Given")
        self.assertIn("Container Ship", vessel.ship_type)
        self.assertEqual(vessel.length_m, 399.9)
        self.assertEqual(vessel.beam_m, 58.8)
        self.assertEqual(vessel.draft_m, 14.5)
        self.assertEqual(vessel.cruising_speed_kn, 19.5)
        self.assertEqual(vessel.max_speed_kn, 22.8)

    def test_03_real_vessel_lookup_berge_everest(self) -> None:
        """3. Real vessel lookup for IMO 9748289 (Berge Everest - VLOC Bulk Carrier)."""
        vessel = self.registry.get_vessel_by_imo("9748289")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Berge Everest")
        self.assertIn("Bulk Carrier", vessel.ship_type)
        self.assertEqual(vessel.length_m, 361.0)
        self.assertEqual(vessel.beam_m, 65.0)
        self.assertEqual(vessel.draft_m, 23.0)

    def test_04_real_vessel_lookup_ti_europe_tanker(self) -> None:
        """4. Real vessel lookup for IMO 9235268 (TI Europe - ULCC Tanker)."""
        vessel = self.registry.get_vessel_by_imo("9235268")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "TI Europe")
        self.assertIn("Crude Carrier", vessel.ship_type)
        self.assertEqual(vessel.length_m, 380.0)
        self.assertEqual(vessel.draft_m, 24.5)

    def test_05_unknown_imo_returns_none(self) -> None:
        """5. Unrecognized valid IMO number returns None."""
        vessel = self.registry.get_vessel_by_imo("9999999")
        self.assertIsNone(vessel)

    def test_06_composite_provider_caching(self) -> None:
        """6. Composite provider caches query results in memory."""
        mock_provider = MockVesselProvider()
        test_vessel = VesselRecord(
            imo_number="9617246",
            name="Pacific Ruby",
            ship_type="Bulk Carrier",
            length_m=229.0,
            beam_m=32.2,
            draft_m=14.5,
            cruising_speed_kn=14.2,
            max_speed_kn=15.0,
        )
        mock_provider.add_vessel(test_vessel)

        composite = CompositeVesselProvider(primary_provider=mock_provider)
        # First call fetches from primary
        v1 = composite.get_vessel_by_imo("9617246")
        self.assertEqual(v1.name, "Pacific Ruby")

        # Mutate primary mock
        mock_provider.fixtures.clear()

        # Second call returns from cache
        v2 = composite.get_vessel_by_imo("9617246")
        self.assertIsNotNone(v2)
        self.assertEqual(v2.name, "Pacific Ruby")


if __name__ == "__main__":
    unittest.main()
