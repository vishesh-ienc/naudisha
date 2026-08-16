"""
Global live AIS ingestion via AISStream.io.

Why this exists alongside the Digitraffic provider: Digitraffic serves the
Finnish Maritime Administration feed, which is excellent but regional — it only
knows vessels in Baltic and Finnish waters. Any globally-trading ship (Emma
Maersk, Ever Given, a tanker off Mumbai) is simply absent from it, so
`get_live_position` correctly returns `None` and the API reports `position:
null`. AISStream provides worldwide coverage, which is what the demo needs.

Transport
---------
AISStream is a *push* feed, not a request/response API: you open a WebSocket,
send one subscription frame, and it streams messages until you disconnect. That
does not fit the synchronous `AISProvider.get_live_position()` interface, so this
class runs the socket on a daemon thread and maintains an in-memory snapshot that
the synchronous accessor reads. Nothing blocks a request thread.

IMO resolution
--------------
AIS position reports (message types 1/2/3) carry MMSI, *not* IMO. The IMO number
only appears in ShipStaticData (type 5), which each vessel broadcasts roughly
every six minutes. So the MMSI->IMO mapping builds up over time rather than being
available immediately: a freshly-started backend can see a vessel's position
without yet knowing its IMO. `mapping_size()` exposes that warm-up state so
callers can report it honestly instead of implying a vessel does not exist.

The provider is inert without `AISSTREAM_API_KEY` — it never opens a socket and
always returns `None`, so offline test runs and key-less development are
unaffected.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from naudisha.data.vessel_provider import AISDataRecord, AISProvider

logger = logging.getLogger("naudisha.data.aisstream")

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Whole-globe bounding box. AISStream requires at least one box; this asks for
# everything and lets the local filters decide what to keep.
WORLD_BBOX: List[List[List[float]]] = [[[-90.0, -180.0], [90.0, 180.0]]]

# Position reports older than this are not worth returning as "live".
DEFAULT_STALE_SECONDS = 3600.0

# Bound on retained vessels, so a long-running process cannot grow without limit
# while streaming the entire globe.
MAX_TRACKED_VESSELS = 20000

# Reconnect pacing. AISStream allows one concurrent connection per API key, so a
# 429 needs a much longer pause than an ordinary network blip — retrying fast
# just keeps the key locked out.
INITIAL_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 300.0
RATE_LIMIT_BACKOFF_SECONDS = 120.0

# AIS NavigationalStatus code -> the vocabulary used by AISDataRecord.
_NAV_STATUS = {
    0: "underway",   # under way using engine
    1: "at_anchor",
    2: "stopped",    # not under command
    3: "underway",   # restricted manoeuvrability
    4: "underway",   # constrained by draught
    5: "moored",
    6: "stopped",    # aground
    7: "underway",   # engaged in fishing
    8: "underway",   # under way sailing
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AISStreamProvider(AISProvider):
    """
    Worldwide live AIS positions from AISStream.io.

    Thread-safety: the socket thread writes the snapshot and request threads read
    it, so every access to the shared dictionaries goes through `_lock`.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        bounding_boxes: Optional[List[List[List[float]]]] = None,
        stale_threshold_seconds: float = DEFAULT_STALE_SECONDS,
        autostart: bool = True,
        url: str = AISSTREAM_URL,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("AISSTREAM_API_KEY", "").strip()
        self.bounding_boxes = bounding_boxes or WORLD_BBOX
        self.stale_threshold_seconds = stale_threshold_seconds
        self.autostart = autostart
        self.url = url

        self._lock = threading.RLock()
        self._positions_by_mmsi: Dict[str, Tuple[AISDataRecord, float]] = {}
        self._mmsi_to_imo: Dict[str, str] = {}
        self._imo_to_mmsi: Dict[str, str] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = False
        self._messages_seen = 0
        self._last_error: Optional[str] = None

    # -- public state ------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected

    def stats(self) -> Dict[str, Any]:
        """Diagnostics — surfaced so 'no position' can be explained precisely."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "connected": self._connected,
                "messages_seen": self._messages_seen,
                "vessels_with_position": len(self._positions_by_mmsi),
                "imo_mappings": len(self._imo_to_mmsi),
                "last_error": self._last_error,
            }

    def mapping_size(self) -> int:
        with self._lock:
            return len(self._imo_to_mmsi)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Starts the background socket thread. Idempotent and non-blocking."""
        if not self.enabled:
            logger.info("AISStream disabled — AISSTREAM_API_KEY is not set")
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="aisstream", daemon=True)
            self._thread.start()
        logger.info("AISStream ingestion thread started")

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        with self._lock:
            self._connected = False
            self._thread = None

    # -- AISProvider -------------------------------------------------------

    def get_live_position(self, imo_number: str) -> Optional[AISDataRecord]:
        if not self.enabled:
            return None

        # Lazy start: the socket only opens once someone actually asks for a
        # position, so importing this module has no side effects.
        if self.autostart:
            with self._lock:
                needs_start = self._thread is None or not self._thread.is_alive()
            if needs_start:
                self.start()

        with self._lock:
            mmsi = self._imo_to_mmsi.get(str(imo_number))
            if mmsi is None:
                return None
            entry = self._positions_by_mmsi.get(mmsi)
            if entry is None:
                return None
            record, received_at = entry

        if (time.time() - received_at) > self.stale_threshold_seconds:
            return None
        return record

    # -- ingestion ---------------------------------------------------------

    def _run(self) -> None:
        """Thread entrypoint: owns a private event loop for the socket."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._consume_forever())
        except Exception as exc:  # noqa: BLE001 - thread must not propagate
            logger.warning("AISStream ingestion thread exiting: %s", exc)
        finally:
            try:
                loop.close()
            except Exception:  # noqa: BLE001
                pass

    async def _consume_forever(self) -> None:
        backoff = INITIAL_BACKOFF_SECONDS
        while not self._stop_event.is_set():
            try:
                await self._consume_once()
                backoff = INITIAL_BACKOFF_SECONDS  # a clean session resets the penalty
            except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                message = str(exc)
                with self._lock:
                    self._connected = False
                    self._last_error = message

                # AISStream permits a single concurrent connection per API key
                # and answers 429 to any extra one. Reconnecting quickly then
                # keeps the key locked out, so this backs off hard rather than
                # fighting a limit it cannot win.
                if "429" in message:
                    backoff = max(backoff, RATE_LIMIT_BACKOFF_SECONDS)
                    logger.warning(
                        "AISStream rate-limited (429) — only one connection per API key is allowed. "
                        "Retrying in %.0fs",
                        backoff,
                    )
                else:
                    logger.debug("AISStream connection lost (%s); retrying in %.0fs", exc, backoff)

            if self._stop_event.is_set():
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

    async def _consume_once(self) -> None:
        try:
            import websockets
        except ImportError:  # pragma: no cover - dependency is declared
            with self._lock:
                self._last_error = "websockets package not installed"
            logger.warning("AISStream requires the 'websockets' package")
            self._stop_event.set()
            return

        # ping_interval=None: AISStream does not reply to WebSocket ping frames,
        # so client-side keepalive tears down a perfectly healthy connection
        # after one interval with "1011 keepalive ping timeout". Liveness is
        # instead enforced by the recv() timeout below.
        async with websockets.connect(self.url, ping_interval=None) as socket:
            await socket.send(
                json.dumps(
                    {
                        "APIKey": self.api_key,
                        "BoundingBoxes": self.bounding_boxes,
                        # Both types are needed: PositionReport carries the fix,
                        # ShipStaticData is the only source of the IMO number.
                        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                    }
                )
            )

            with self._lock:
                self._connected = True
                self._last_error = None
            logger.info("AISStream connected — subscribed to global position and static data")

            while not self._stop_event.is_set():
                raw = await asyncio.wait_for(socket.recv(), timeout=90)
                self.ingest_raw(raw)

    # -- message handling (public for testing) -----------------------------

    def ingest_raw(self, raw: Any) -> None:
        """Parses one raw frame. Malformed frames are ignored, never fatal."""
        try:
            payload = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
        except (ValueError, TypeError):
            return
        if isinstance(payload, dict):
            self.ingest_message(payload)

    def ingest_message(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._messages_seen += 1

        message_type = payload.get("MessageType")
        metadata = payload.get("MetaData") or {}
        body = payload.get("Message") or {}

        mmsi = metadata.get("MMSI") or metadata.get("mmsi")
        if mmsi is None:
            return
        mmsi = str(mmsi)

        if message_type == "ShipStaticData":
            self._ingest_static(mmsi, body.get("ShipStaticData") or {})
        elif message_type == "PositionReport":
            self._ingest_position(mmsi, metadata, body.get("PositionReport") or {})

    def _ingest_static(self, mmsi: str, static: Dict[str, Any]) -> None:
        imo_raw = static.get("ImoNumber")
        if not imo_raw:
            return
        imo = str(imo_raw).strip()
        # AIS transmits 0 when the sender has no IMO (fishing vessels, tugs).
        if not imo.isdigit() or len(imo) != 7:
            return

        with self._lock:
            self._mmsi_to_imo[mmsi] = imo
            self._imo_to_mmsi[imo] = mmsi

            # Backfill the IMO onto a position already received for this MMSI,
            # so a vessel seen before its static broadcast becomes resolvable
            # without waiting for the next position report.
            existing = self._positions_by_mmsi.get(mmsi)
            if existing is not None and existing[0].imo_number is None:
                record, received_at = existing
                self._positions_by_mmsi[mmsi] = (
                    AISDataRecord(
                        mmsi=record.mmsi,
                        imo_number=imo,
                        latitude=record.latitude,
                        longitude=record.longitude,
                        speed_kn=record.speed_kn,
                        course_deg=record.course_deg,
                        heading_deg=record.heading_deg,
                        nav_status=record.nav_status,
                        timestamp_utc=record.timestamp_utc,
                        source="aisstream",
                    ),
                    received_at,
                )

    def _ingest_position(self, mmsi: str, metadata: Dict[str, Any], report: Dict[str, Any]) -> None:
        latitude = report.get("Latitude", metadata.get("latitude"))
        longitude = report.get("Longitude", metadata.get("longitude"))
        if latitude is None or longitude is None:
            return

        try:
            lat = float(latitude)
            lon = float(longitude)
        except (TypeError, ValueError):
            return

        # AIS uses 91/181 as "position not available" sentinels.
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return

        def _opt_float(value: Any) -> Optional[float]:
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        sog = _opt_float(report.get("Sog"))
        cog = _opt_float(report.get("Cog"))
        heading = _opt_float(report.get("TrueHeading"))
        # 511 is the AIS "heading unavailable" sentinel.
        if heading is not None and heading >= 360.0:
            heading = None

        nav_status = _NAV_STATUS.get(report.get("NavigationalStatus", 0), "unknown")

        with self._lock:
            imo = self._mmsi_to_imo.get(mmsi)
            record = AISDataRecord(
                mmsi=mmsi,
                imo_number=imo,
                latitude=lat,
                longitude=lon,
                speed_kn=sog,
                course_deg=cog,
                heading_deg=heading,
                nav_status=nav_status,
                timestamp_utc=metadata.get("time_utc") or _utc_now_iso(),
                source="aisstream",
            )
            self._positions_by_mmsi[mmsi] = (record, time.time())
            self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Drops the oldest fixes once the snapshot exceeds its bound. Caller holds the lock."""
        if len(self._positions_by_mmsi) <= MAX_TRACKED_VESSELS:
            return
        ordered = sorted(self._positions_by_mmsi.items(), key=lambda kv: kv[1][1])
        for mmsi, _ in ordered[: len(ordered) - MAX_TRACKED_VESSELS]:
            self._positions_by_mmsi.pop(mmsi, None)


class ChainedAISProvider(AISProvider):
    """
    Queries several AIS providers in order and returns the first live fix.

    Ordering matters: a global feed should be consulted before a regional one, so
    a vessel outside the regional coverage area still resolves. A provider that
    raises is skipped rather than failing the chain — losing one feed must not
    take out the others.
    """

    def __init__(self, providers: List[AISProvider]) -> None:
        self.providers = [p for p in providers if p is not None]

    def get_live_position(self, imo_number: str) -> Optional[AISDataRecord]:
        for provider in self.providers:
            try:
                record = provider.get_live_position(imo_number)
                if record is not None:
                    return record
            except Exception as exc:  # noqa: BLE001 - one bad feed must not break the rest
                logger.debug("AIS provider %s failed: %s", type(provider).__name__, exc)
        return None


def build_default_ais_provider() -> AISProvider:
    """
    Assembles the AIS chain from the environment.

    AISStream first when a key is configured (worldwide), Digitraffic second
    (Baltic, no key required). With no key this degenerates to Digitraffic alone,
    which is exactly the previous behaviour.
    """
    from naudisha.data.vessel_provider import DigitrafficAISProvider

    providers: List[AISProvider] = []

    aisstream = AISStreamProvider()
    if aisstream.enabled:
        providers.append(aisstream)
        logger.info("AIS chain: AISStream (global) -> Digitraffic (Baltic)")
    else:
        logger.info("AIS chain: Digitraffic (Baltic) only — set AISSTREAM_API_KEY for global coverage")

    providers.append(DigitrafficAISProvider())
    return ChainedAISProvider(providers)
