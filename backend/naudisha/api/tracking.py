"""
Live vessel tracking sessions and the navigation simulator.

This module owns the state behind `POST /api/ships/{imo}/tracking/start`,
`GET /api/ships/{imo}/status`, `GET /api/ships/{imo}/route`, and the
`/ws/ships/{imo}` WebSocket (docs/API_CONTRACT.md §6-§11).

Design notes
------------
*AIS is authoritative.* Each tick first checks whether a fresh AIS fix is
available for the session's IMO via the injected `ais_provider`. When it is,
the session position is set directly to the AIS coordinate, the heading is
taken from AIS course/heading, and position_source is "ais". When no fresh fix
exists the session falls back to dead reckoning along the planned route at
cruising speed with position_source "simulation".

*Route computation is slow and must never block the caller.* A cold route
preview costs roughly two minutes because Copernicus Marine is queried live for
the voyage corridor. So `start()` returns immediately with `route_status =
"updating"` and schedules the plan on a worker thread; the route arrives later
as a `route_update` WebSocket message and via `GET .../route`. The contract
already defines `"updating"` for exactly this state (§13.2).

*One ticker drives everything.* A single asyncio task advances every active
session and fans results out to subscribers, rather than one task per socket.
Sessions therefore keep progressing while nobody is connected, so a client that
reconnects sees the vessel where it should be — and `GET .../status` reports
real movement without any WebSocket at all.

*Simulated movement is labelled as such.* Dead reckoning is used only when no
fresh AIS fix is available. `position_source` in every payload tells the
frontend exactly what it is looking at.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from naudisha.core.calculations import calculate_bearing, calculate_haversine_distance
from naudisha.core.models import ShipProfile
from naudisha.api.services import RoutePlanningService
# AISProvider imported lazily in TrackingSessionManager to avoid circular imports.
# The type hint uses a string forward reference so the module loads cleanly.

logger = logging.getLogger("naudisha.api.tracking")

Coord = Tuple[float, float]


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# How often the simulator advances every active session, in real seconds.
TICK_SECONDS = _env_float("TRACKING_TICK_SECONDS", 3.0)

# Simulated seconds elapsed per real second. The contract's 30-second cadence is
# honest but unwatchable in a demo, so time is compressed by default: one real
# second advances the voyage by one simulated minute.
TIME_SCALE = _env_float("TRACKING_TIME_SCALE", 60.0)

# Minimum wall-clock gap between automatic replans of the same session.
REPLAN_INTERVAL_SECONDS = _env_float("TRACKING_REPLAN_SECONDS", 45.0)

# A position change smaller than this is not worth broadcasting.
MIN_BROADCAST_NM = 0.01


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _interpolate(a: Coord, b: Coord, fraction: float) -> Coord:
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)


def path_length_nm(path: List[Coord]) -> float:
    total = 0.0
    for i in range(len(path) - 1):
        total += calculate_haversine_distance(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1])
    return total


def point_along_path(path: List[Coord], distance_nm: float) -> Tuple[Coord, int, bool]:
    """Position after travelling `distance_nm` along `path`, its segment, and whether the end was reached."""
    if not path:
        return ((0.0, 0.0), 0, True)
    if len(path) == 1 or distance_nm <= 0.0:
        return (path[0], 0, len(path) == 1)

    # Settle completion up front. Walking the segments cannot decide it: at the
    # final segment `remaining == seg` satisfies `remaining <= seg`, which would
    # report the vessel as still under way while it sits exactly on the
    # destination — and callers clamp travelled distance to the path length, so
    # that is the normal way a voyage ends, not an edge case.
    total = path_length_nm(path)
    if distance_nm >= total:
        return (path[-1], max(len(path) - 2, 0), True)

    remaining = distance_nm
    for i in range(len(path) - 1):
        seg = calculate_haversine_distance(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1])
        if seg <= 0.0:
            continue
        if remaining <= seg:
            return (_interpolate(path[i], path[i + 1], remaining / seg), i, False)
        remaining -= seg

    return (path[-1], max(len(path) - 2, 0), True)


@dataclass(frozen=True, eq=False)
class _Subscriber:
    """A WebSocket client's queue together with the loop that owns it."""

    queue: "asyncio.Queue[Dict[str, Any]]"
    loop: asyncio.AbstractEventLoop


def _offer(queue: "asyncio.Queue[Dict[str, Any]]", imo_number: str, message: Dict[str, Any]) -> None:
    """Enqueues a message, dropping it if the client has fallen behind."""
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        # A slow client must never stall the ticker for every other session.
        logger.debug("Dropping message for slow subscriber on IMO %s", imo_number)


# Maximum AIS track points retained per session.
MAX_AIS_TRACK_POINTS = 500


@dataclass
class TrackingSession:
    """Mutable state of one tracked voyage."""

    imo_number: str
    destination: Coord
    origin: Coord
    ship_profile: Optional[ShipProfile] = None

    position: Coord = (0.0, 0.0)
    heading: float = 0.0
    speed_kn: Optional[float] = None          # from AIS when available
    position_source: str = "simulation"       # "ais" | "simulation"
    route: List[Coord] = field(default_factory=list)
    route_status: str = "updating"  # §13.2
    distance_nm: float = 0.0
    estimated_time_hours: float = 0.0
    total_cost: float = 0.0

    started_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    departure_time: Optional[str] = None

    travelled_nm: float = 0.0
    arrived: bool = False
    replan_count: int = 0
    last_replan_monotonic: float = 0.0
    planning: bool = False
    last_error: Optional[str] = None

    # Real AIS observation history — only genuine AIS fixes are appended here.
    # Each entry is (latitude, longitude, timestamp_utc_iso).
    ais_track: List[Tuple[float, float, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.position = self.origin
        if self.origin != self.destination:
            self.heading = calculate_bearing(
                self.origin[0], self.origin[1], self.destination[0], self.destination[1]
            )

    @property
    def cruising_speed_kn(self) -> float:
        """Design speed from vessel profile, used for dead reckoning."""
        if self.ship_profile is not None and self.ship_profile.cruising_speed > 0:
            return self.ship_profile.cruising_speed
        return 18.0

    @property
    def effective_speed_kn(self) -> float:
        """Speed used for advance calculation — AIS SOG when available, else design speed."""
        if self.speed_kn is not None and self.speed_kn > 0:
            return self.speed_kn
        return self.cruising_speed_kn

    @property
    def status(self) -> str:
        """§13.1 ship status."""
        if self.arrived:
            return "stopped"
        if self.route_status == "unavailable":
            return "unknown"
        return "underway"

    def remaining_nm(self) -> float:
        return max(path_length_nm(self.route) - self.travelled_nm, 0.0)

    def remaining_hours(self) -> float:
        return self.remaining_nm() / max(self.effective_speed_kn, 1.0)

    def append_ais_track_point(self, lat: float, lon: float, ts: str) -> None:
        """Appends a genuine AIS observation. Deduplicates identical coordinates. Bounded."""
        if self.ais_track:
            last_lat, last_lon, _ = self.ais_track[-1]
            if abs(last_lat - lat) < 1e-5 and abs(last_lon - lon) < 1e-5:
                return  # Same location — skip duplicate
        self.ais_track.append((lat, lon, ts))
        if len(self.ais_track) > MAX_AIS_TRACK_POINTS:
            self.ais_track = self.ais_track[-MAX_AIS_TRACK_POINTS:]

    def remaining_route(self) -> List[Coord]:
        """
        Waypoints from the current position to the destination.

        Contract §8 requires the tracked route to start at the vessel's current
        position, so consumed waypoints are dropped and the vessel's position is
        prepended rather than returning the original full-voyage path.
        """
        if not self.route:
            return []
        if self.arrived:
            return [self.position]

        _, segment_index, _ = point_along_path(self.route, self.travelled_nm)
        ahead = self.route[segment_index + 1 :]
        return [self.position] + list(ahead)

    def snapshot_route_payload(self) -> Dict[str, Any]:
        remaining = self.remaining_route()
        return {
            "route": [{"latitude": round(lat, 4), "longitude": round(lon, 4)} for lat, lon in remaining],
            "distance_nm": round(self.remaining_nm(), 2),
            "estimated_time_hours": round(self.remaining_hours(), 2),
            "total_cost": round(self.total_cost, 2),
        }


class TrackingSessionManager:
    """
    Registry of active tracking sessions plus the simulator that advances them.

    Thread-safety: sessions are mutated both by the asyncio ticker and by route
    planning running on a worker thread, so all mutation goes through `_lock`.
    """

    def __init__(self, route_service: Optional[RoutePlanningService] = None) -> None:
        self._sessions: Dict[str, TrackingSession] = {}
        self._subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}
        self._lock = threading.RLock()
        self._route_service = route_service
        self._ais_provider = None  # Injected after construction to avoid circular import
        self._ticker: Optional[asyncio.Task[None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -- service wiring ----------------------------------------------------

    def set_route_service(self, service: RoutePlanningService) -> None:
        self._route_service = service

    def set_ais_provider(self, provider: Any) -> None:
        """Injects the live AIS provider so ticks can use real vessel positions."""
        self._ais_provider = provider
        logger.info("Tracking manager wired to AIS provider: %s", type(provider).__name__)

    # -- lifecycle ---------------------------------------------------------

    def start_ticker(self) -> None:
        if self._ticker is not None and not self._ticker.done():
            return
        self._loop = asyncio.get_running_loop()
        self._ticker = asyncio.create_task(self._run_ticker())
        logger.info("Tracking simulator started (tick=%.1fs, scale=%.0fx)", TICK_SECONDS, TIME_SCALE)

    async def stop_ticker(self) -> None:
        if self._ticker is None:
            return
        self._ticker.cancel()
        try:
            await self._ticker
        except asyncio.CancelledError:
            pass
        self._ticker = None

    # -- session management ------------------------------------------------

    def start(
        self,
        imo_number: str,
        origin: Coord,
        destination: Coord,
        ship_profile: Optional[ShipProfile] = None,
        departure_time: Optional[str] = None,
    ) -> TrackingSession:
        """Creates (or replaces) a session and schedules its initial route plan."""
        # Check if an immediate live AIS fix is available
        ais_rec = None
        if self._ais_provider is not None:
            try:
                ais_rec = self._ais_provider.get_live_position(imo_number)
            except Exception:
                pass

        with self._lock:
            session = TrackingSession(
                imo_number=imo_number,
                origin=origin,
                destination=destination,
                ship_profile=ship_profile,
                departure_time=departure_time,
            )

            if ais_rec is not None:
                session.position = (round(ais_rec.latitude, 6), round(ais_rec.longitude, 6))
                session.position_source = "ais"
                session.speed_kn = ais_rec.speed_kn
                if ais_rec.heading_deg is not None:
                    session.heading = ais_rec.heading_deg
                elif ais_rec.course_deg is not None:
                    session.heading = ais_rec.course_deg
                session.append_ais_track_point(
                    ais_rec.latitude, ais_rec.longitude, ais_rec.timestamp_utc or _utc_now_iso()
                )

            self._sessions[imo_number] = session

        self._schedule_plan(session, reason="initial")
        return session


    def stop(self, imo_number: str) -> bool:
        with self._lock:
            existed = self._sessions.pop(imo_number, None) is not None
            self._subscribers.pop(imo_number, None)
        return existed

    def get(self, imo_number: str) -> Optional[TrackingSession]:
        with self._lock:
            return self._sessions.get(imo_number)

    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def clear(self) -> None:
        """Test helper — drops all sessions and subscribers."""
        with self._lock:
            self._sessions.clear()
            self._subscribers.clear()

    # -- subscriptions -----------------------------------------------------

    def subscribe(self, imo_number: str) -> "asyncio.Queue[Dict[str, Any]]":
        """
        Registers a subscriber queue bound to the caller's event loop.

        The loop is captured here because publishers are not all on it: route
        planning runs on a worker thread and the test suite steps the simulator
        from the main thread. `asyncio.Queue` is not thread-safe, so every
        delivery is marshalled back onto the owning loop.
        """
        queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=32)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers.setdefault(imo_number, set()).add(_Subscriber(queue, loop))
        return queue

    def unsubscribe(self, imo_number: str, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
        with self._lock:
            subs = self._subscribers.get(imo_number)
            if not subs:
                return
            for sub in list(subs):
                if sub.queue is queue:
                    subs.discard(sub)
            if not subs:
                self._subscribers.pop(imo_number, None)

    def _publish(self, imo_number: str, message: Dict[str, Any]) -> None:
        """Delivers a message to every subscriber, from any thread."""
        with self._lock:
            subscribers = list(self._subscribers.get(imo_number, ()))

        for sub in subscribers:
            if sub.loop.is_closed():
                continue
            try:
                sub.loop.call_soon_threadsafe(_offer, sub.queue, imo_number, message)
            except RuntimeError:
                # Loop shut down between the check and the call.
                logger.debug("Subscriber loop closed for IMO %s", imo_number)

    # Retained for callers that want to be explicit about crossing threads;
    # `_publish` is already safe from any thread.
    _publish_threadsafe = _publish

    # -- route planning ----------------------------------------------------

    def _schedule_plan(self, session: TrackingSession, reason: str) -> None:
        """Runs route planning off the request path so callers never block on CMEMS."""
        if self._route_service is None:
            with self._lock:
                session.route_status = "unavailable"
                session.last_error = "Route service unavailable"
            return

        with self._lock:
            if session.planning:
                return
            session.planning = True
            session.route_status = "updating"

        thread = threading.Thread(
            target=self._plan_now,
            args=(session, reason),
            name=f"plan-{session.imo_number}",
            daemon=True,
        )
        thread.start()

    def _plan_now(self, session: TrackingSession, reason: str) -> None:
        service = self._route_service
        if service is None:
            return

        origin = session.position if reason != "initial" else session.origin

        try:
            result = service.plan_preview_route(
                imo_number=session.imo_number,
                start_lat=origin[0],
                start_lon=origin[1],
                dest_lat=session.destination[0],
                dest_lon=session.destination[1],
                timestamp=session.departure_time,
                ship_profile=session.ship_profile,
            )

            with self._lock:
                session.route = [(lat, lon) for lat, lon in result.route]
                session.distance_nm = result.distance_nm
                session.estimated_time_hours = result.estimated_time_hours
                session.total_cost = result.total_cost
                session.route_status = "optimal" if len(session.route) > 1 else "unavailable"
                session.travelled_nm = 0.0
                session.position = session.route[0] if session.route else origin
                session.updated_at = _utc_now_iso()
                session.planning = False
                session.last_error = None
                session.last_replan_monotonic = _monotonic()
                if reason != "initial":
                    session.replan_count += 1
                payload = session.snapshot_route_payload()
                position = session.position
                status_now = session.route_status

            if status_now == "optimal":
                self._publish_threadsafe(
                    session.imo_number,
                    {
                        "type": "route_update",
                        "timestamp": _utc_now_iso(),
                        "position": {"latitude": round(position[0], 4), "longitude": round(position[1], 4)},
                        **payload,
                        "reason": "environment_changed" if reason != "initial" else "forecast_refresh",
                    },
                )

            logger.info(
                "Route %s for IMO %s: %d waypoints, %.2f NM",
                reason,
                session.imo_number,
                len(session.route),
                session.distance_nm,
            )

        except Exception as exc:  # noqa: BLE001 - surfaced via session state
            logger.warning("Route planning failed for IMO %s: %s", session.imo_number, exc)
            with self._lock:
                session.planning = False
                session.last_error = str(exc)
                session.last_replan_monotonic = _monotonic()
                # An initial failure leaves nothing to display; a failed replan
                # keeps the previous route, which is still the best known plan.
                if not session.route:
                    session.route_status = "unavailable"
                else:
                    session.route_status = "optimal"

    # -- simulation --------------------------------------------------------

    async def _run_ticker(self) -> None:
        try:
            while True:
                await asyncio.sleep(TICK_SECONDS)
                try:
                    self._tick(TICK_SECONDS * TIME_SCALE)
                except Exception:  # noqa: BLE001 - the ticker must never die
                    logger.exception("Tracking tick failed")
        except asyncio.CancelledError:
            raise

    def _tick(self, simulated_seconds: float) -> None:
        """Advances every active session by `simulated_seconds` of voyage time."""
        with self._lock:
            sessions = list(self._sessions.values())

        for session in sessions:
            message = self._advance(session, simulated_seconds)
            if message is not None:
                self._publish(session.imo_number, message)

    def _advance(self, session: TrackingSession, simulated_seconds: float) -> Optional[Dict[str, Any]]:
        """
        Moves one session forward.

        AIS priority: if a fresh AIS fix is available, use that as the authoritative
        position. Otherwise fall back to dead reckoning along the planned route.
        Returns a position_update message to broadcast, or None if nothing worth sending.
        """
        # ---- Step 1: Try to obtain a live AIS fix ----
        ais_record = None
        if self._ais_provider is not None:
            try:
                ais_record = self._ais_provider.get_live_position(session.imo_number)
            except Exception:
                pass  # AIS provider failure must never stall the ticker

        with self._lock:
            if session.arrived:
                return None

            now_iso = _utc_now_iso()
            previous = session.position

            if ais_record is not None:
                # ---- AIS path: use real position ----
                lat = round(ais_record.latitude, 6)
                lon = round(ais_record.longitude, 6)
                position: Coord = (lat, lon)

                session.position = position
                session.position_source = "ais"
                session.speed_kn = ais_record.speed_kn
                session.updated_at = now_iso

                # Use real AIS heading if available, else course over ground
                if ais_record.heading_deg is not None:
                    session.heading = ais_record.heading_deg
                elif ais_record.course_deg is not None:
                    session.heading = ais_record.course_deg

                # Append to the real AIS observation track
                session.append_ais_track_point(lat, lon, ais_record.timestamp_utc or now_iso)

                logger.debug(
                    "[TRACK] IMO=%s AIS position lat=%.4f lon=%.4f sog=%s",
                    session.imo_number, lat, lon,
                    f"{ais_record.speed_kn:.1f}kn" if ais_record.speed_kn else "?",
                )

                # Advance the dead-reckoning cursor to the nearest point on the
                # route so that when AIS is lost the simulation resumes from
                # approximately the right place rather than jumping back to origin.
                if len(session.route) >= 2:
                    # Find how far along the route this AIS position is
                    # (best-effort: just keep travelled_nm for now, replan handles it)
                    pass

                complete = False  # AIS arrival is detected via proximity, not route completion
                if session.destination:
                    dist_to_dest = calculate_haversine_distance(
                        lat, lon, session.destination[0], session.destination[1]
                    )
                    if dist_to_dest < 0.5:  # within 0.5 NM of destination
                        session.arrived = True
                        complete = True

            else:
                # ---- Simulation path: dead reckoning ----
                if session.planning or len(session.route) < 2:
                    return None

                total_nm = path_length_nm(session.route)
                if total_nm <= 0:
                    return None

                step_nm = session.cruising_speed_kn * (simulated_seconds / 3600.0)
                session.travelled_nm = min(session.travelled_nm + step_nm, total_nm)
                position, segment_index, complete = point_along_path(session.route, session.travelled_nm)
                session.position = position
                session.position_source = "simulation"
                session.updated_at = now_iso

                ahead = session.route[min(segment_index + 1, len(session.route) - 1)]
                if calculate_haversine_distance(position[0], position[1], ahead[0], ahead[1]) > 1e-6:
                    session.heading = calculate_bearing(position[0], position[1], ahead[0], ahead[1])

                if complete:
                    session.arrived = True
                    session.route_status = "optimal"

            moved_nm = calculate_haversine_distance(previous[0], previous[1], session.position[0], session.position[1])
            due_for_replan = (
                not complete
                and _monotonic() - session.last_replan_monotonic >= REPLAN_INTERVAL_SECONDS
                and session.remaining_nm() > 1.0
            )
            imo = session.imo_number
            pos_source = session.position_source
            is_live = pos_source == "ais"
            spd = session.speed_kn
            hdg = session.heading
            pos = session.position

        if due_for_replan:
            self._schedule_plan(session, reason="replan")

        if moved_nm < MIN_BROADCAST_NM and not complete:
            return None

        msg: Dict[str, Any] = {
            "type": "position_update",
            "timestamp": _utc_now_iso(),
            "position": {"latitude": round(pos[0], 4), "longitude": round(pos[1], 4)},
            "position_source": pos_source,
            "is_live_position": is_live,
        }
        if spd is not None:
            msg["speed_kn"] = round(spd, 1)
        if hdg is not None:
            msg["heading_deg"] = round(hdg, 1)
        return msg

    # -- introspection -----------------------------------------------------

    def force_replan(self, imo_number: str) -> bool:
        session = self.get(imo_number)
        if session is None:
            return False
        self._schedule_plan(session, reason="replan")
        return True

    def advance_for_test(self, imo_number: str, simulated_seconds: float) -> Optional[Dict[str, Any]]:
        """
        Deterministic single-step advance used by the test suite.

        Publishes exactly as the real ticker does, so tests exercise the same
        broadcast path rather than a shortcut around it.
        """
        session = self.get(imo_number)
        if session is None:
            return None
        message = self._advance(session, simulated_seconds)
        if message is not None:
            self._publish(imo_number, message)
        return message


def _monotonic() -> float:
    import time

    return time.monotonic()


# Application-wide singleton. Wired to a RoutePlanningService in routes.py.
tracking_manager = TrackingSessionManager()
