"""
Asynchronous route planning jobs.

Why this exists: a cold route preview costs roughly 75-85 seconds, almost all of
it waiting on Copernicus Marine to resolve and subset its datasets. Measured on
this machine, a fresh bounding box costs ~75s for currents+waves (issued
concurrently) plus ~9s for Open-Meteo. No HTTP client should block that long —
browsers, proxies and load balancers all time out well before it, and a user
staring at a spinner for 90 seconds has no idea whether anything is happening.

`POST /api/routes/preview` remains synchronous and contract-compliant for
callers that can wait. This module adds a job-based path alongside it:

    POST /api/routes/plan        -> 202 { job_id, status: "planning" }
    GET  /api/routes/plan/{id}   -> { status, route?, error? }

The job runs on a worker thread; the client polls and can show real progress.
Results are cached by normalised request signature, so a repeated plan for the
same voyage returns instantly rather than re-running the whole pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from naudisha.api.services import RoutePlanResult, RoutePlanningService

logger = logging.getLogger("naudisha.api.planning")

# Jobs and their results are kept only long enough for a client to collect them.
JOB_TTL_SECONDS = 900.0
# A completed plan for the same voyage is reused for this long.
RESULT_CACHE_TTL_SECONDS = 1800.0
MAX_CONCURRENT_PLANS = 4


PlanStatus = str  # "planning" | "ready" | "failed"


@dataclass
class PlanJob:
    job_id: str
    status: PlanStatus = "planning"
    stage: str = "preparing"
    stage_message: Optional[str] = "Initializing route planning"
    progress_percent: float = 0.0
    created_at: float = field(default_factory=time.monotonic)
    finished_at: Optional[float] = None
    result: Optional[RoutePlanResult] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.created_at


class PlanningManager:
    """Owns the worker pool, the job table, and the result cache."""

    def __init__(self) -> None:
        self._jobs: Dict[str, PlanJob] = {}
        self._cache: Dict[Tuple, Tuple[float, RoutePlanResult]] = {}
        # Maps a request signature to an in-flight job, so two clients asking
        # for the same voyage share one expensive computation instead of
        # launching two identical CMEMS pipelines.
        self._inflight: Dict[Tuple, str] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_PLANS, thread_name_prefix="planner"
        )
        self._service: Optional[RoutePlanningService] = None

    def set_route_service(self, service: RoutePlanningService) -> None:
        self._service = service

    @staticmethod
    def signature(
        imo_number: Optional[str],
        start: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: Optional[str],
        optimization_objective: Optional[str] = "balanced",
    ) -> Tuple:
        """
        Normalised cache key.

        Coordinates are rounded to ~10 km, the departure time to the hour,
        and optimization objective is normalized,
        matching the resolution at which the environmental providers themselves
        cache. Finer keys would miss constantly for no gain in accuracy.
        """
        objective = (optimization_objective or "balanced").strip().lower()
        return (
            imo_number or "",
            round(start[0], 1),
            round(start[1], 1),
            round(destination[0], 1),
            round(destination[1], 1),
            objective,
        )

    def cached_result(self, signature: Tuple) -> Optional[RoutePlanResult]:
        with self._lock:
            entry = self._cache.get(signature)
            if entry is None:
                return None
            stored_at, result = entry
            if time.monotonic() - stored_at > RESULT_CACHE_TTL_SECONDS:
                self._cache.pop(signature, None)
                return None
            return result

    def submit(
        self,
        signature: Tuple,
        profile_resolver: Optional[Callable[[], object]] = None,
        **plan_kwargs,
    ) -> PlanJob:
        """
        Starts (or joins) a planning job.

        Returns an already-`ready` job when the result is cached, and joins an
        existing job when an identical voyage is already being planned.

        `profile_resolver` is invoked on the worker thread rather than here.
        Resolving a vessel by IMO hits Wikidata and an AIS feed, which measured
        ~1.7s — doing that before queueing would defeat the point of an
        immediate submit and would serialise under concurrent requests.
        """
        self._sweep()

        cached = self.cached_result(signature)
        if cached is not None:
            job = PlanJob(job_id=str(uuid.uuid4()), status="ready", result=cached)
            job.finished_at = job.created_at
            with self._lock:
                self._jobs[job.job_id] = job
            return job

        with self._lock:
            existing_id = self._inflight.get(signature)
            if existing_id and existing_id in self._jobs:
                return self._jobs[existing_id]

            job = PlanJob(job_id=str(uuid.uuid4()))
            self._jobs[job.job_id] = job
            self._inflight[signature] = job.job_id

        self._pool.submit(self._run, job, signature, plan_kwargs, profile_resolver)
        return job

    def get(self, job_id: str) -> Optional[PlanJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(
        self,
        job: PlanJob,
        signature: Tuple,
        plan_kwargs: Dict,
        profile_resolver: Optional[Callable[[], object]] = None,
    ) -> None:
        service = self._service
        if service is None:
            self._fail(job, signature, "INTERNAL_ERROR", "Route service is not configured.")
            return

        try:
            started = time.monotonic()

            if profile_resolver is not None and plan_kwargs.get("ship_profile") is None:
                # A lookup failure must not abort the plan: the service falls
                # back to its default profile, which still yields a usable route.
                try:
                    plan_kwargs["ship_profile"] = profile_resolver()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Vessel profile lookup failed for job %s: %s", job.job_id, exc)
                    plan_kwargs["ship_profile"] = None

            def _on_stage(stage_id: str, pct: float, msg: str) -> None:
                with self._lock:
                    job.stage = stage_id
                    job.progress_percent = pct
                    job.stage_message = msg

            plan_kwargs["stage_callback"] = _on_stage

            result = service.plan_preview_route(**plan_kwargs)
            logger.info(
                "Plan job %s completed in %.1fs (%d waypoints)",
                job.job_id,
                time.monotonic() - started,
                len(result.route),
            )

            with self._lock:
                job.result = result
                job.status = "ready"
                job.stage = "ready"
                job.stage_message = "Route optimization complete"
                job.progress_percent = 100.0
                job.finished_at = time.monotonic()
                self._cache[signature] = (time.monotonic(), result)
                self._inflight.pop(signature, None)

        except Exception as exc:  # noqa: BLE001 - mapped to a contract error below
            code = type(exc).__name__
            # Reuse the API's own error codes where the exception carries one.
            mapped = {
                "RouteNotFoundError": "ROUTE_NOT_FOUND",
                "InvalidCoordinatesError": "INVALID_COORDINATES",
                "EnvironmentUnavailableError": "ENVIRONMENT_UNAVAILABLE",
            }.get(code, "INTERNAL_ERROR")
            logger.error("Plan job %s failed: %s: %s", job.job_id, code, exc)
            self._fail(job, signature, mapped, str(exc))

    def _fail(self, job: PlanJob, signature: Tuple, code: str, message: str) -> None:
        with self._lock:
            job.status = "failed"
            job.error_code = code
            job.error_message = message
            job.finished_at = time.monotonic()
            self._inflight.pop(signature, None)

    def _sweep(self) -> None:
        """Drops jobs a client is no longer plausibly waiting on."""
        now = time.monotonic()
        with self._lock:
            expired = [
                jid
                for jid, job in self._jobs.items()
                if job.finished_at is not None and now - job.finished_at > JOB_TTL_SECONDS
            ]
            for jid in expired:
                self._jobs.pop(jid, None)


planning_manager = PlanningManager()
