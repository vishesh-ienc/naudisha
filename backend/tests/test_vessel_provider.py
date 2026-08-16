"""
Unit & Integration Tests for Real Vessel Provider, Registry, Live AIS, and API Mapping.
Validates real vessel data lookup, schema mapping, live AIS ingestion, caching, and failure modes.
"""

import time
import unittest
from naudisha.data.vessel_provider import (
    AISDataRecord,
    CompositeVesselProvider,
    LiveAISManager,
    MockVesselProvider,
    RegistryVesselProvider,
    VesselRecord,
    GLOBAL_VESSEL_REGISTRY,
)


class TestVesselProvider(unittest.TestCase):
    """Test suite for vessel data providers, live AIS manager, and real maritime registry."""

    def setUp(self) -> None:
        self.registry = RegistryVesselProvider()
        self.composite = CompositeVesselProvider()

    def test_01_real_vessel_lookup_shinsung_dream(self) -> None:
        """1. Real vessel lookup for IMO 9176187 (Shinsung Dream - General Cargo Vessel)."""
        vessel = self.registry.get_vessel_by_imo("9176187")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Shinsung Dream")
        self.assertEqual(vessel.ship_type, "General Cargo Vessel")
        self.assertEqual(vessel.length_m, 106.0)
        self.assertEqual(vessel.beam_m, 18.0)
        self.assertEqual(vessel.draft_m, 7.0)
        self.assertEqual(vessel.cruising_speed_kn, 12.5)
        self.assertEqual(vessel.max_speed_kn, 14.0)
        self.assertIsNone(vessel.position_lat)
        self.assertIsNone(vessel.position_lon)

    def test_02_real_vessel_lookup_courage_pcc(self) -> None:
        """2. Real vessel lookup for IMO 8916968 (Courage - Vehicle Carrier)."""
        vessel = self.registry.get_vessel_by_imo("8916968")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Courage")
        self.assertEqual(vessel.ship_type, "Vehicles Carrier")
        self.assertEqual(vessel.length_m, 199.9)
        self.assertEqual(vessel.beam_m, 32.2)
        self.assertEqual(vessel.draft_m, 8.8)
        self.assertEqual(vessel.cruising_speed_kn, 18.0)
        self.assertEqual(vessel.max_speed_kn, 20.5)

    def test_03_real_vessel_lookup_ever_given(self) -> None:
        """3. Real vessel lookup for IMO 9811000 (Ever Given - Ultra Large Container Ship)."""
        vessel = self.registry.get_vessel_by_imo("9811000")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Ever Given")
        self.assertIn("Container Ship", vessel.ship_type)
        self.assertEqual(vessel.length_m, 399.9)
        self.assertEqual(vessel.beam_m, 58.8)
        self.assertEqual(vessel.draft_m, 14.5)
        self.assertEqual(vessel.cruising_speed_kn, 19.5)
        self.assertEqual(vessel.max_speed_kn, 22.8)

    def test_04_real_vessel_lookup_berge_everest(self) -> None:
        """4. Real vessel lookup for IMO 9748289 (Berge Everest - VLOC Bulk Carrier)."""
        vessel = self.registry.get_vessel_by_imo("9748289")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Berge Everest")
        self.assertIn("Bulk Carrier", vessel.ship_type)
        self.assertEqual(vessel.length_m, 361.0)
        self.assertEqual(vessel.beam_m, 65.0)
        self.assertEqual(vessel.draft_m, 23.0)

    def test_05_real_vessel_lookup_ti_europe_tanker(self) -> None:
        """5. Real vessel lookup for IMO 9235268 (TI Europe - ULCC Tanker)."""
        vessel = self.registry.get_vessel_by_imo("9235268")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "TI Europe")
        self.assertIn("Crude Carrier", vessel.ship_type)
        self.assertEqual(vessel.length_m, 380.0)
        self.assertEqual(vessel.draft_m, 24.5)

    def test_06_live_ais_manager_ingestion_and_query(self) -> None:
        """6. LiveAISManager stores live AIS position reports and returns them."""
        ais_mgr = LiveAISManager()
        ais_report = AISDataRecord(
            mmsi="368207620",
            imo_number="9811000",
            latitude=30.0123,
            longitude=32.5678,
            speed_kn=14.2,
            course_deg=182.0,
            heading_deg=181.0,
            nav_status="underway",
            timestamp_utc="2026-08-16T12:00:00Z",
            source="aisstream",
        )
        ais_mgr.record_ais_update(ais_report)

        # Query by IMO
        retrieved = ais_mgr.get_live_position("9811000")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.latitude, 30.0123)
        self.assertEqual(retrieved.longitude, 32.5678)
        self.assertEqual(retrieved.speed_kn, 14.2)
        self.assertEqual(retrieved.source, "aisstream")

        # Query by MMSI
        retrieved_mmsi = ais_mgr.get_live_position("368207620")
        self.assertIsNotNone(retrieved_mmsi)
        self.assertEqual(retrieved_mmsi.latitude, 30.0123)

    def test_07_live_ais_staleness_eviction(self) -> None:
        """7. LiveAISManager evicts positions older than staleness threshold."""
        ais_mgr = LiveAISManager(stale_threshold_seconds=0.1)
        ais_report = AISDataRecord(
            mmsi="123456789",
            imo_number="9400980",
            latitude=18.52,
            longitude=72.91,
            nav_status="underway",
        )
        ais_mgr.record_ais_update(ais_report)

        # Immediate query succeeds
        self.assertIsNotNone(ais_mgr.get_live_position("9400980"))

        # Wait past staleness threshold
        time.sleep(0.15)
        # Query now returns None (stale data not treated as live)
        self.assertIsNone(ais_mgr.get_live_position("9400980"))

    def test_08_composite_provider_stitches_live_ais_onto_static_particulars(self) -> None:
        """8. Composite provider merges live AIS position and status onto static vessel profile."""
        ais_mgr = LiveAISManager()
        ais_report = AISDataRecord(
            mmsi="368207620",
            imo_number="9811000",
            latitude=29.9876,
            longitude=32.5432,
            nav_status="underway",
            timestamp_utc="2026-08-16T12:30:00Z",
            source="aisstream",
        )
        ais_mgr.record_ais_update(ais_report)

        composite = CompositeVesselProvider(ais_manager=ais_mgr)
        vessel = composite.get_vessel_by_imo("9811000")
        self.assertIsNotNone(vessel)
        self.assertEqual(vessel.name, "Ever Given")
        self.assertEqual(vessel.length_m, 399.9)
        self.assertEqual(vessel.position_lat, 29.9876)
        self.assertEqual(vessel.position_lon, 32.5432)
        self.assertEqual(vessel.status, "underway")
        self.assertTrue(vessel.is_live_position)
        self.assertEqual(vessel.source, "aisstream")

    def test_09_composite_provider_caching(self) -> None:
        """9. Composite provider caches query results in memory."""
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
