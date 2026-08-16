"""
Offline tests for the AISStream global AIS provider.

No network is used: frames identical in shape to AISStream's are fed directly
into the parser via `ingest_message`, so the message handling, IMO resolution,
staleness and chaining behaviour are all exercised deterministically.
"""

from __future__ import annotations

import json
import time
import unittest

from naudisha.data.aisstream_provider import (
    AISStreamProvider,
    ChainedAISProvider,
    build_default_ais_provider,
)
from naudisha.data.vessel_provider import AISDataRecord, AISProvider


def position_frame(mmsi: int, lat: float, lon: float, **overrides) -> dict:
    report = {
        "Latitude": lat,
        "Longitude": lon,
        "Sog": 12.4,
        "Cog": 187.2,
        "TrueHeading": 185,
        "NavigationalStatus": 0,
    }
    report.update(overrides)
    return {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "ShipName": "TEST VESSEL", "time_utc": "2026-08-16 12:00:00 +0000 UTC"},
        "Message": {"PositionReport": report},
    }


def static_frame(mmsi: int, imo: int) -> dict:
    return {
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": mmsi, "ShipName": "TEST VESSEL"},
        "Message": {"ShipStaticData": {"ImoNumber": imo, "Name": "TEST VESSEL"}},
    }


class AISStreamParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = AISStreamProvider(api_key="test-key", autostart=False)

    def test_disabled_without_api_key(self) -> None:
        provider = AISStreamProvider(api_key="", autostart=False)
        self.assertFalse(provider.enabled)
        self.assertIsNone(provider.get_live_position("9321483"))

    def test_reads_api_key_from_environment(self) -> None:
        import os

        os.environ["AISSTREAM_API_KEY"] = "env-key"
        try:
            self.assertEqual(AISStreamProvider(autostart=False).api_key, "env-key")
        finally:
            os.environ.pop("AISSTREAM_API_KEY", None)

    def test_position_alone_is_not_resolvable_by_imo(self) -> None:
        # Position reports carry MMSI only, so until ShipStaticData arrives there
        # is no way to answer an IMO query.
        self.provider.ingest_message(position_frame(211331640, 56.0, 16.4))
        self.assertIsNone(self.provider.get_live_position("9321483"))

    def test_static_data_enables_imo_lookup(self) -> None:
        self.provider.ingest_message(static_frame(211331640, 9321483))
        self.provider.ingest_message(position_frame(211331640, 56.0, 16.4))

        record = self.provider.get_live_position("9321483")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertAlmostEqual(record.latitude, 56.0)
        self.assertAlmostEqual(record.longitude, 16.4)
        self.assertEqual(record.mmsi, "211331640")
        self.assertEqual(record.imo_number, "9321483")
        self.assertEqual(record.source, "aisstream")

    def test_static_data_backfills_earlier_position(self) -> None:
        # Order matters in a real stream: a position often arrives before the
        # vessel's static broadcast, and must become resolvable retroactively.
        self.provider.ingest_message(position_frame(211331640, 55.5, 15.5))
        self.provider.ingest_message(static_frame(211331640, 9321483))

        record = self.provider.get_live_position("9321483")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.imo_number, "9321483")
        self.assertAlmostEqual(record.latitude, 55.5)

    def test_navigational_status_mapping(self) -> None:
        cases = {0: "underway", 1: "at_anchor", 5: "moored", 8: "underway"}
        for code, expected in cases.items():
            provider = AISStreamProvider(api_key="k", autostart=False)
            provider.ingest_message(static_frame(1, 9321483))
            provider.ingest_message(position_frame(1, 10.0, 20.0, NavigationalStatus=code))
            record = provider.get_live_position("9321483")
            assert record is not None
            self.assertEqual(record.nav_status, expected, f"code {code}")

    def test_heading_sentinel_is_discarded(self) -> None:
        # 511 is the AIS "heading unavailable" sentinel and must not be reported
        # as a real bearing.
        self.provider.ingest_message(static_frame(1, 9321483))
        self.provider.ingest_message(position_frame(1, 10.0, 20.0, TrueHeading=511))
        record = self.provider.get_live_position("9321483")
        assert record is not None
        self.assertIsNone(record.heading_deg)

    def test_out_of_range_coordinates_rejected(self) -> None:
        self.provider.ingest_message(static_frame(1, 9321483))
        self.provider.ingest_message(position_frame(1, 91.0, 181.0))
        self.assertIsNone(self.provider.get_live_position("9321483"))

    def test_zero_imo_is_ignored(self) -> None:
        # Vessels without an IMO transmit 0; mapping that would collide.
        self.provider.ingest_message(static_frame(1, 0))
        self.provider.ingest_message(position_frame(1, 10.0, 20.0))
        self.assertEqual(self.provider.mapping_size(), 0)

    def test_malformed_frames_do_not_raise(self) -> None:
        for bad in ["not json", b"\x00\x01", "{}", json.dumps({"MessageType": "PositionReport"})]:
            self.provider.ingest_raw(bad)
        self.assertIsNone(self.provider.get_live_position("9321483"))

    def test_stale_positions_are_not_returned(self) -> None:
        provider = AISStreamProvider(api_key="k", autostart=False, stale_threshold_seconds=0.01)
        provider.ingest_message(static_frame(1, 9321483))
        provider.ingest_message(position_frame(1, 10.0, 20.0))
        self.assertIsNotNone(provider.get_live_position("9321483"))
        time.sleep(0.05)
        self.assertIsNone(provider.get_live_position("9321483"))

    def test_stats_reports_state(self) -> None:
        self.provider.ingest_message(static_frame(1, 9321483))
        self.provider.ingest_message(position_frame(1, 10.0, 20.0))
        stats = self.provider.stats()
        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["vessels_with_position"], 1)
        self.assertEqual(stats["imo_mappings"], 1)
        self.assertEqual(stats["messages_seen"], 2)


class _StubAIS(AISProvider):
    def __init__(self, record=None, raises=False):
        self.record = record
        self.raises = raises
        self.calls = 0

    def get_live_position(self, imo_number: str):
        self.calls += 1
        if self.raises:
            raise RuntimeError("feed down")
        return self.record


class ChainedAISProviderTests(unittest.TestCase):
    def _record(self, source: str) -> AISDataRecord:
        return AISDataRecord(mmsi="1", imo_number="9321483", latitude=1.0, longitude=2.0, source=source)

    def test_returns_first_available(self) -> None:
        first = _StubAIS(self._record("aisstream"))
        second = _StubAIS(self._record("digitraffic"))
        chain = ChainedAISProvider([first, second])

        record = chain.get_live_position("9321483")
        assert record is not None
        self.assertEqual(record.source, "aisstream")
        self.assertEqual(second.calls, 0, "second provider should not be consulted")

    def test_falls_through_when_first_has_nothing(self) -> None:
        chain = ChainedAISProvider([_StubAIS(None), _StubAIS(self._record("digitraffic"))])
        record = chain.get_live_position("9321483")
        assert record is not None
        self.assertEqual(record.source, "digitraffic")

    def test_failing_provider_does_not_break_chain(self) -> None:
        chain = ChainedAISProvider([_StubAIS(raises=True), _StubAIS(self._record("digitraffic"))])
        record = chain.get_live_position("9321483")
        assert record is not None
        self.assertEqual(record.source, "digitraffic")

    def test_all_empty_returns_none(self) -> None:
        self.assertIsNone(ChainedAISProvider([_StubAIS(None), _StubAIS(None)]).get_live_position("9321483"))


class DefaultChainTests(unittest.TestCase):
    def test_digitraffic_only_without_key(self) -> None:
        import os

        saved = os.environ.pop("AISSTREAM_API_KEY", None)
        try:
            chain = build_default_ais_provider()
            assert isinstance(chain, ChainedAISProvider)
            self.assertEqual(len(chain.providers), 1)
        finally:
            if saved is not None:
                os.environ["AISSTREAM_API_KEY"] = saved

    def test_aisstream_takes_priority_with_key(self) -> None:
        import os

        saved = os.environ.get("AISSTREAM_API_KEY")
        os.environ["AISSTREAM_API_KEY"] = "test-key"
        try:
            chain = build_default_ais_provider()
            assert isinstance(chain, ChainedAISProvider)
            self.assertEqual(len(chain.providers), 2)
            self.assertIsInstance(chain.providers[0], AISStreamProvider)
        finally:
            if saved is None:
                os.environ.pop("AISSTREAM_API_KEY", None)
            else:
                os.environ["AISSTREAM_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main()
