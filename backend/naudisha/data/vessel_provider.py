"""
Vessel Data Providers and Real Maritime Registry Integration for NauDisha.
Provides clean abstraction for querying real vessel master particulars and live AIS data
by IMO number, with caching, live Wikidata SPARQL lookup, and real-time open AIS ingestion.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("naudisha.data.vessel")


# =============================================================================
# Domain Records & Data Models
# =============================================================================

@dataclass(frozen=True)
class AISDataRecord:
    """Live dynamic AIS position and navigational status report."""
    mmsi: Optional[str]
    imo_number: Optional[str]
    latitude: float
    longitude: float
    speed_kn: Optional[float] = None
    course_deg: Optional[float] = None
    heading_deg: Optional[float] = None
    nav_status: str = "underway"  # "underway", "stopped", "at_anchor", "moored", "unknown"
    timestamp_utc: Optional[str] = None
    source: str = "digitraffic"  # "digitraffic", "aisstream", "mock"


@dataclass(frozen=True)
class VesselRecord:
    """Standardized vessel master data and hydrodynamic particulars."""
    imo_number: str
    name: str
    ship_type: str
    length_m: float
    beam_m: float
    draft_m: float
    cruising_speed_kn: float
    max_speed_kn: float
    status: str = "unknown"  # "underway", "stopped", "at_anchor", "unknown"
    position_lat: Optional[float] = None
    position_lon: Optional[float] = None
    last_updated: Optional[str] = None
    mmsi: Optional[str] = None
    source: str = "registry"  # "wikidata", "registry", "digitraffic", "aisstream", "synthetic", "mock"
    is_live_position: bool = False


# =============================================================================
# Curated Maritime Registry Catalog (Real Global Commercial Vessels)
# Verified from public maritime registers (Clarkson's, Equasis, IMO records)
# =============================================================================

GLOBAL_VESSEL_REGISTRY: Dict[str, VesselRecord] = {
    # General Cargo Vessel (Correct mapping for IMO 9176187)
    "9176187": VesselRecord(
        imo_number="9176187",
        name="Shinsung Dream",
        ship_type="General Cargo Vessel",
        length_m=106.0,
        beam_m=18.0,
        draft_m=7.0,
        cruising_speed_kn=12.5,
        max_speed_kn=14.0,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # Vehicle Carrier / Pure Car and Truck Carrier (Real IMO for Courage)
    "8916968": VesselRecord(
        imo_number="8916968",
        name="Courage",
        ship_type="Vehicles Carrier",
        length_m=199.9,
        beam_m=32.2,
        draft_m=8.8,
        cruising_speed_kn=18.0,
        max_speed_kn=20.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # Ultra Large Container Vessels (ULCV)
    "9811000": VesselRecord(
        imo_number="9811000",
        name="Ever Given",
        ship_type="Container Ship (Golden-class)",
        length_m=399.9,
        beam_m=58.8,
        draft_m=14.5,
        cruising_speed_kn=19.5,
        max_speed_kn=22.8,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9321483": VesselRecord(
        imo_number="9321483",
        name="Emma Maersk",
        ship_type="Container Ship (E-class)",
        length_m=397.7,
        beam_m=56.4,
        draft_m=15.5,
        cruising_speed_kn=21.0,
        max_speed_kn=25.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9703291": VesselRecord(
        imo_number="9703291",
        name="MSC Oscar",
        ship_type="Container Ship (Olympic-class)",
        length_m=395.4,
        beam_m=59.0,
        draft_m=16.0,
        cruising_speed_kn=20.0,
        max_speed_kn=22.8,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9499890": VesselRecord(
        imo_number="9499890",
        name="Maersk Mc-Kinney Moller",
        ship_type="Container Ship (Triple-E)",
        length_m=399.0,
        beam_m=59.0,
        draft_m=16.0,
        cruising_speed_kn=19.0,
        max_speed_kn=23.0,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # Very Large Ore Carrier (VLOC) / Bulk Carriers
    "9748289": VesselRecord(
        imo_number="9748289",
        name="Berge Everest",
        ship_type="Bulk Carrier (Valemax VLOC)",
        length_m=361.0,
        beam_m=65.0,
        draft_m=23.0,
        cruising_speed_kn=14.0,
        max_speed_kn=15.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9617246": VesselRecord(
        imo_number="9617246",
        name="Pacific Ruby",
        ship_type="Bulk Carrier (Kamsarmax)",
        length_m=229.0,
        beam_m=32.2,
        draft_m=14.5,
        cruising_speed_kn=14.2,
        max_speed_kn=15.0,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # Crude Oil Tankers
    "9400980": VesselRecord(
        imo_number="9400980",
        name="EVALI",
        ship_type="Crude Oil Tanker (Aframax / LR2)",
        length_m=228.6,
        beam_m=42.0,
        draft_m=15.0,
        cruising_speed_kn=14.5,
        max_speed_kn=15.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9235268": VesselRecord(
        imo_number="9235268",
        name="TI Europe",
        ship_type="Ultra Large Crude Carrier (ULCC)",
        length_m=380.0,
        beam_m=68.0,
        draft_m=24.5,
        cruising_speed_kn=15.0,
        max_speed_kn=16.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    "9745902": VesselRecord(
        imo_number="9745902",
        name="Front Altair",
        ship_type="Crude Oil Tanker (LR2)",
        length_m=250.0,
        beam_m=44.0,
        draft_m=14.8,
        cruising_speed_kn=14.5,
        max_speed_kn=15.5,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # LNG Carriers
    "9443413": VesselRecord(
        imo_number="9443413",
        name="Rasheeda",
        ship_type="LNG Carrier (Q-Max)",
        length_m=345.0,
        beam_m=53.8,
        draft_m=12.0,
        cruising_speed_kn=19.5,
        max_speed_kn=21.0,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # General Cargo / Heavy Lift
    "9508419": VesselRecord(
        imo_number="9508419",
        name="BBC Everest",
        ship_type="General Cargo / Heavy Lift",
        length_m=143.0,
        beam_m=22.8,
        draft_m=7.8,
        cruising_speed_kn=13.5,
        max_speed_kn=15.0,
        status="unknown",
        position_lat=None,
        position_lon=None,
        source="registry",
    ),
    # Panamax Demo Test Fixture
    "1234567": VesselRecord(
        imo_number="1234567",
        name="Demo Vessel",
        ship_type="Container Vessel (Panamax)",
        length_m=294.0,
        beam_m=32.2,
        draft_m=12.0,
        cruising_speed_kn=18.0,
        max_speed_kn=23.0,
        status="underway",
        position_lat=18.52,
        position_lon=72.91,
        source="registry",
    ),
}


# =============================================================================
# Provider Interfaces
# =============================================================================

class VesselProvider(ABC):
    """Abstract base class for vessel particulars and AIS data providers."""

    @abstractmethod
    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        """
        Retrieves real vessel particulars and current status by IMO number.

        Args:
            imo_number: 7-digit IMO string.

        Returns:
            VesselRecord if found, None otherwise.
        """
        pass


class AISProvider(ABC):
    """Abstract base class for live satellite / terrestrial AIS data providers."""

    @abstractmethod
    def get_live_position(self, imo_number: str) -> Optional[AISDataRecord]:
        """
        Retrieves latest real-time AIS position report for an IMO or MMSI.

        Returns:
            AISDataRecord if an active transponder signal exists, None otherwise.
        """
        pass


# =============================================================================
# Real Open AIS Provider & Live Manager
# =============================================================================

class DigitrafficAISProvider(AISProvider):
    """
    Genuine open real-time maritime AIS provider querying Digitraffic Marine API.
    Fetches live satellite and terrestrial AIS transponder reports across open waterways.
    """

    def __init__(self, cache_ttl_seconds: float = 60.0) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self._last_fetch_time: float = 0.0
        self._imo_to_mmsi: Dict[str, str] = {}
        self._live_locations: Dict[str, AISDataRecord] = {}

    def _fetch_live_data(self) -> None:
        now = time.time()
        if (now - self._last_fetch_time) < self.cache_ttl_seconds:
            return

        try:
            # 1. Fetch metadata mapping (IMO -> MMSI) if not cached
            if not self._imo_to_mmsi:
                v_req = urllib.request.Request(
                    "https://meri.digitraffic.fi/api/ais/v1/vessels",
                    headers={"Digitraffic-User": "NauDisha-Maritime-API/1.0", "Accept-Encoding": "gzip"},
                )
                with urllib.request.urlopen(v_req, timeout=4) as resp:
                    content = resp.read()
                    if resp.info().get("Content-Encoding") == "gzip":
                        content = gzip.decompress(content)
                    meta_list = json.loads(content.decode("utf-8"))
                    for v in meta_list:
                        imo = v.get("imo")
                        mmsi = v.get("mmsi")
                        if imo and mmsi:
                            self._imo_to_mmsi[str(imo)] = str(mmsi)

            # 2. Fetch live locations
            l_req = urllib.request.Request(
                "https://meri.digitraffic.fi/api/ais/v1/locations",
                headers={"Digitraffic-User": "NauDisha-Maritime-API/1.0", "Accept-Encoding": "gzip"},
            )
            with urllib.request.urlopen(l_req, timeout=4) as resp:
                content = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)
                features = json.loads(content.decode("utf-8")).get("features", [])

            # Reverse map MMSI -> IMO
            mmsi_to_imo = {mmsi: imo for imo, mmsi in self._imo_to_mmsi.items()}

            new_locations: Dict[str, AISDataRecord] = {}
            for feat in features:
                mmsi_str = str(feat.get("mmsi"))
                coords = feat.get("geometry", {}).get("coordinates", [])
                props = feat.get("properties", {})
                if len(coords) >= 2:
                    lon, lat = float(coords[0]), float(coords[1])
                    sog = props.get("sog")
                    cog = props.get("cog")
                    heading = props.get("heading")
                    nav_stat_code = props.get("navStat", 0)
                    nav_status = "underway" if nav_stat_code in (0, 7, 8) else ("at_anchor" if nav_stat_code == 1 else "stopped")

                    imo_num = mmsi_to_imo.get(mmsi_str)
                    rec = AISDataRecord(
                        mmsi=mmsi_str,
                        imo_number=imo_num,
                        latitude=lat,
                        longitude=lon,
                        speed_kn=float(sog) if sog is not None else None,
                        course_deg=float(cog) if cog is not None else None,
                        heading_deg=float(heading) if heading is not None else None,
                        nav_status=nav_status,
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        source="digitraffic",
                    )
                    new_locations[mmsi_str] = rec
                    if imo_num:
                        new_locations[imo_num] = rec

            self._live_locations = new_locations
            self._last_fetch_time = now
        except Exception as exc:
            logger.debug("Digitraffic live AIS fetch skipped/failed: %s", exc)

    def get_live_position(self, imo_number: str) -> Optional[AISDataRecord]:
        self._fetch_live_data()
        return self._live_locations.get(imo_number)


class LiveAISManager(AISProvider):
    """
    In-memory live AIS store with staleness eviction and external provider fallback.
    """

    def __init__(
        self,
        external_provider: Optional[AISProvider] = None,
        stale_threshold_seconds: float = 86400.0,
    ) -> None:
        # Default to the environment-configured chain: AISStream worldwide when
        # AISSTREAM_API_KEY is set, falling back to the key-less Digitraffic
        # Baltic feed. Imported lazily to avoid a circular import, since
        # aisstream_provider depends on this module's AISProvider/AISDataRecord.
        if external_provider is not None:
            self.external_provider: Optional[AISProvider] = external_provider
        else:
            try:
                from naudisha.data.aisstream_provider import build_default_ais_provider

                self.external_provider = build_default_ais_provider()
            except Exception as exc:  # noqa: BLE001 - never fail construction
                logger.debug("Falling back to Digitraffic-only AIS: %s", exc)
                self.external_provider = DigitrafficAISProvider()

        self.stale_threshold_seconds = stale_threshold_seconds
        self._positions: Dict[str, Tuple[AISDataRecord, float]] = {}

    def record_ais_update(self, record: AISDataRecord) -> None:
        """Stores a freshly received live AIS transponder update."""
        now = time.time()
        if record.imo_number:
            self._positions[record.imo_number] = (record, now)
        if record.mmsi:
            self._positions[record.mmsi] = (record, now)

    def get_live_position(self, imo_number: str) -> Optional[AISDataRecord]:
        """Retrieves live position from local feed or queries external open AIS provider."""
        # 1. Check local in-memory stream
        if imo_number in self._positions:
            record, received_at = self._positions[imo_number]
            if (time.time() - received_at) <= self.stale_threshold_seconds:
                return record

        # 2. Check external live provider
        if self.external_provider is not None:
            try:
                live_record = self.external_provider.get_live_position(imo_number)
                if live_record is not None:
                    self.record_ais_update(live_record)
                    return live_record
            except Exception as exc:
                logger.debug("External AIS provider failed for IMO %s: %s", imo_number, exc)

        return None


# =============================================================================
# Concrete Vessel Particulars Providers
# =============================================================================

class RegistryVesselProvider(VesselProvider):
    """Authoritative maritime registry lookup provider."""

    def __init__(self, catalog: Optional[Dict[str, VesselRecord]] = None) -> None:
        self._catalog = catalog if catalog is not None else GLOBAL_VESSEL_REGISTRY

    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        return self._catalog.get(imo_number)


class WikidataVesselProvider(VesselProvider):
    """Live open online vessel provider querying Wikidata SPARQL endpoint by IMO."""

    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        sparql = f"""
        SELECT ?ship ?shipLabel ?typeLabel ?loa ?beam ?draft ?mmsi WHERE {{
          ?ship wdt:P458 "{imo_number}".
          OPTIONAL {{ ?ship wdt:P31 ?type. }}
          OPTIONAL {{ ?ship wdt:P2043 ?loa. }}
          OPTIONAL {{ ?ship wdt:P2261 ?beam. }}
          OPTIONAL {{ ?ship wdt:P2262 ?draft. }}
          OPTIONAL {{ ?ship wdt:P587 ?mmsi. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 1
        """
        url = "https://query.wikidata.org/sparql?query=" + urllib.parse.quote(sparql) + "&format=json"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "NauDisha-Maritime-API/1.0 (https://github.com/vishesh-ienc/naudisha)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                bindings = data.get("results", {}).get("bindings", [])
                if not bindings:
                    return None
                b = bindings[0]
                name = b.get("shipLabel", {}).get("value") or f"Vessel IMO-{imo_number}"
                raw_type = b.get("typeLabel", {}).get("value") or "Commercial Vessel"
                ship_type = raw_type.title() if raw_type and raw_type.lower() != "ship" else "Commercial Cargo Vessel"

                loa_val = b.get("loa", {}).get("value")
                beam_val = b.get("beam", {}).get("value")
                draft_val = b.get("draft", {}).get("value")
                mmsi_val = b.get("mmsi", {}).get("value")

                loa = float(loa_val) if loa_val else 220.0
                beam = float(beam_val) if beam_val else round(loa / 6.5, 1)
                draft = float(draft_val) if draft_val else round(beam / 2.6, 1)

                return VesselRecord(
                    imo_number=imo_number,
                    name=name,
                    ship_type=ship_type,
                    length_m=round(loa, 1),
                    beam_m=round(beam, 1),
                    draft_m=round(draft, 1),
                    cruising_speed_kn=15.0,
                    max_speed_kn=18.0,
                    status="unknown",
                    position_lat=None,
                    position_lon=None,
                    mmsi=mmsi_val,
                    source="wikidata",
                )
        except Exception as exc:
            logger.debug("Wikidata query for IMO %s skipped: %s", imo_number, exc)
            return None


class SyntheticVesselProvider(VesselProvider):
    """
    Deterministic naval architecture synthesizer for uncataloged valid IMO numbers.
    Ensures every valid 7-digit IMO number resolves to realistic commercial particulars.
    Never fabricates live AIS GPS coordinates.
    """

    SHIP_TYPES = [
        ("Container Vessel", 260.0, 32.2, 12.5, 18.5, 22.0),
        ("Bulk Carrier", 225.0, 32.2, 13.0, 14.2, 16.0),
        ("Crude Oil Tanker", 250.0, 44.0, 15.0, 14.5, 16.5),
        ("Chemical / Products Tanker", 183.0, 27.4, 11.2, 14.0, 15.5),
        ("General Cargo Vessel", 160.0, 24.0, 9.5, 13.5, 15.0),
        ("LNG Carrier", 290.0, 45.0, 11.8, 19.0, 21.0),
        ("Vehicles Carrier", 200.0, 32.2, 9.2, 17.5, 20.0),
    ]

    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        digits_sum = sum(int(d) for d in imo_number if d.isdigit())
        idx = digits_sum % len(self.SHIP_TYPES)
        stype, length, beam, draft, cruise, max_sp = self.SHIP_TYPES[idx]

        seed = int(imo_number[-3:]) if len(imo_number) >= 3 and imo_number[-3:].isdigit() else 100
        length_var = round(length + (seed % 30) - 15, 1)
        beam_var = round(beam + (seed % 6) - 3, 1)
        draft_var = round(draft + ((seed % 20) / 10.0) - 1.0, 1)

        return VesselRecord(
            imo_number=imo_number,
            name=f"Vessel IMO-{imo_number}",
            ship_type=stype,
            length_m=max(50.0, length_var),
            beam_m=max(10.0, beam_var),
            draft_m=max(4.0, draft_var),
            cruising_speed_kn=cruise,
            max_speed_kn=max_sp,
            status="unknown",
            position_lat=None,
            position_lon=None,
            source="synthetic",
        )


# =============================================================================
# Composite Orchestrator
# =============================================================================

class CompositeVesselProvider(VesselProvider):
    """
    Universal composite vessel provider managing:
    1. In-memory particulars cache (TTL: 7 days)
    2. Primary injected mock provider (for testing)
    3. Curated authoritative maritime registry
    4. Live online Wikidata SPARQL lookup
    5. Live AIS Manager for real-time satellite & terrestrial GPS
    6. Naval architecture synthesizer fallback
    """

    def __init__(
        self,
        registry_provider: Optional[VesselProvider] = None,
        online_provider: Optional[VesselProvider] = None,
        synthetic_provider: Optional[VesselProvider] = None,
        primary_provider: Optional[VesselProvider] = None,
        ais_manager: Optional[LiveAISManager] = None,
        particulars_cache_ttl: float = 604800.0,  # 7 days
    ) -> None:
        self.primary_provider = primary_provider
        self.registry_provider = registry_provider or RegistryVesselProvider()
        self.online_provider = online_provider or WikidataVesselProvider()
        self.synthetic_provider = synthetic_provider or SyntheticVesselProvider()
        self.ais_manager = ais_manager or LiveAISManager()
        self.particulars_cache_ttl = particulars_cache_ttl
        self._cache: Dict[str, Tuple[VesselRecord, float]] = {}

    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        now = time.time()

        # 1. Check in-memory query cache
        cached_entry = self._cache.get(imo_number)
        base_record: Optional[VesselRecord] = None
        if cached_entry:
            rec, cached_at = cached_entry
            if (now - cached_at) < self.particulars_cache_ttl:
                base_record = rec

        # 2. Check primary injected provider (if any)
        if base_record is None and self.primary_provider is not None:
            try:
                base_record = self.primary_provider.get_vessel_by_imo(imo_number)
            except Exception as exc:
                logger.debug("Primary provider error for IMO %s: %s", imo_number, exc)

        # 3. Check curated authoritative maritime registry
        if base_record is None:
            base_record = self.registry_provider.get_vessel_by_imo(imo_number)

        # 4. Query live open online database (Wikidata SPARQL)
        if base_record is None and self.online_provider is not None:
            try:
                base_record = self.online_provider.get_vessel_by_imo(imo_number)
            except Exception as exc:
                logger.debug("Online provider failed for IMO %s: %s", imo_number, exc)

        # 5. Synthesize realistic naval architecture particulars for valid IMO
        if base_record is None and self.synthetic_provider is not None:
            base_record = self.synthetic_provider.get_vessel_by_imo(imo_number)

        if base_record is None:
            return None

        # Cache the base static particulars
        self._cache[imo_number] = (base_record, now)

        # 6. Check for live real-time AIS position report
        live_ais = self.ais_manager.get_live_position(imo_number)
        if live_ais is not None:
            return VesselRecord(
                imo_number=base_record.imo_number,
                name=base_record.name,
                ship_type=base_record.ship_type,
                length_m=base_record.length_m,
                beam_m=base_record.beam_m,
                draft_m=base_record.draft_m,
                cruising_speed_kn=base_record.cruising_speed_kn,
                max_speed_kn=base_record.max_speed_kn,
                status=live_ais.nav_status,
                position_lat=live_ais.latitude,
                position_lon=live_ais.longitude,
                last_updated=live_ais.timestamp_utc,
                mmsi=live_ais.mmsi or base_record.mmsi,
                source=live_ais.source,
                is_live_position=True,
            )

        return base_record


class MockVesselProvider(VesselProvider):
    """Deterministic mock provider for offline tests and fixture injection."""

    def __init__(self, fixtures: Optional[Dict[str, VesselRecord]] = None) -> None:
        self.fixtures = fixtures or {}

    def add_vessel(self, record: VesselRecord) -> None:
        self.fixtures[record.imo_number] = record

    def get_vessel_by_imo(self, imo_number: str) -> Optional[VesselRecord]:
        return self.fixtures.get(imo_number)
