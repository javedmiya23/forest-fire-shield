from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .config import get_settings
from .database import SessionLocal
from .models import Device, FireEvent
from .schemas import AutomationJobStatus, AutomationStatusResponse
from .weather_service import get_current_weather


settings = get_settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _calculate_device_status(last_seen_at: datetime | None) -> str:
    if last_seen_at is None:
        return "unknown"

    seconds_since_last_seen = max(int((utcnow() - last_seen_at).total_seconds()), 0)
    if seconds_since_last_seen <= settings.device_connected_seconds:
        return "connected"
    if seconds_since_last_seen <= settings.device_warning_seconds:
        return "warning"
    return "disconnected"


def _append_note(existing: str | None, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}\n{note}"


@dataclass
class _JobState:
    name: str
    status: str = "idle"
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    detail: str | None = "Waiting for first run."
    affected_count: int | None = None


@dataclass
class _AutomationRuntime:
    worker_started_at: datetime | None = None
    weather_refresh: _JobState = field(default_factory=lambda: _JobState(name="weather_refresh"))
    fire_event_cleanup: _JobState = field(default_factory=lambda: _JobState(name="fire_event_cleanup"))
    device_status_sync: _JobState = field(default_factory=lambda: _JobState(name="device_status_sync"))


@dataclass
class AutomationWorker:
    stop_event: asyncio.Event
    task: asyncio.Task[None]


_runtime = _AutomationRuntime()
_runtime_lock = Lock()


def _job_to_response(job: _JobState) -> AutomationJobStatus:
    return AutomationJobStatus(
        name=job.name,
        status=job.status,
        last_run_at=job.last_run_at,
        last_success_at=job.last_success_at,
        detail=job.detail,
        affected_count=job.affected_count,
    )


def get_automation_status() -> AutomationStatusResponse:
    with _runtime_lock:
        runtime = _AutomationRuntime(
            worker_started_at=_runtime.worker_started_at,
            weather_refresh=_JobState(**_runtime.weather_refresh.__dict__),
            fire_event_cleanup=_JobState(**_runtime.fire_event_cleanup.__dict__),
            device_status_sync=_JobState(**_runtime.device_status_sync.__dict__),
        )

    return AutomationStatusResponse(
        enabled=settings.background_jobs_enabled,
        poll_interval_seconds=settings.background_job_poll_seconds,
        weather_refresh_interval_seconds=settings.weather_refresh_interval_seconds,
        fire_event_cleanup_interval_seconds=settings.fire_event_cleanup_interval_seconds,
        device_status_sync_interval_seconds=settings.device_status_sync_interval_seconds,
        stale_fire_event_seconds=settings.stale_fire_event_seconds,
        worker_started_at=runtime.worker_started_at,
        weather_refresh=_job_to_response(runtime.weather_refresh),
        fire_event_cleanup=_job_to_response(runtime.fire_event_cleanup),
        device_status_sync=_job_to_response(runtime.device_status_sync),
    )


def _mark_job_running(job_name: str) -> None:
    with _runtime_lock:
        job = getattr(_runtime, job_name)
        job.status = "running"
        job.last_run_at = utcnow()
        job.detail = "Job is running."
        job.affected_count = None


def _mark_job_finished(job_name: str, *, detail: str, affected_count: int | None = None) -> None:
    with _runtime_lock:
        job = getattr(_runtime, job_name)
        job.status = "ok"
        job.last_success_at = utcnow()
        job.detail = detail
        job.affected_count = affected_count


def _mark_job_failed(job_name: str, error: Exception) -> None:
    with _runtime_lock:
        job = getattr(_runtime, job_name)
        job.status = "error"
        job.detail = str(error)


def _job_is_due(job_name: str, interval_seconds: int) -> bool:
    with _runtime_lock:
        last_run_at = getattr(_runtime, job_name).last_run_at
    if last_run_at is None:
        return True
    return (utcnow() - last_run_at).total_seconds() >= interval_seconds


def _run_weather_refresh_job() -> tuple[str, int]:
    with SessionLocal() as db:
        weather = get_current_weather(db, force_refresh=True)
        if weather is None:
            return "No forest context is available yet for scheduled weather refresh.", 0
        return (
            f"Weather cache refreshed for {weather.location_source} at {weather.latitude:.4f}, {weather.longitude:.4f}.",
            1,
        )


def _run_device_status_sync_job() -> tuple[str, int]:
    with SessionLocal() as db:
        devices = list(db.scalars(select(Device).order_by(Device.id.asc())))
        updated = 0
        for device in devices:
            new_status = _calculate_device_status(device.last_seen_at)
            if device.status != new_status:
                device.status = new_status
                db.add(device)
                updated += 1
        if updated:
            db.commit()
        return (f"Device status sync completed for {len(devices)} device(s).", updated)


def _run_fire_event_cleanup_job() -> tuple[str, int]:
    with SessionLocal() as db:
        now = utcnow()
        resolved = 0
        active_events = list(
            db.scalars(
                select(FireEvent)
                .options(joinedload(FireEvent.device))
                .where(FireEvent.status == "active")
                .order_by(FireEvent.started_at.asc(), FireEvent.id.asc())
            )
        )

        for event in active_events:
            reference = event.last_alarm_at or event.started_at
            if reference is None:
                continue

            seconds_since_alarm = int((now - reference).total_seconds())
            if seconds_since_alarm < settings.stale_fire_event_seconds:
                continue

            resolve_at = reference + timedelta(seconds=settings.fire_cooldown_seconds)
            if event.device is not None and event.device.last_seen_at is not None:
                resolve_at = max(resolve_at, min(event.device.last_seen_at, now))

            note = f"Auto-resolved by maintenance after {seconds_since_alarm}s without alarm heartbeat."
            if event.device is not None and event.device.last_seen_at is not None:
                stale_for = int((now - event.device.last_seen_at).total_seconds())
                if stale_for >= settings.device_warning_seconds:
                    note += f" Device heartbeat was stale for {stale_for}s."

            event.status = "resolved"
            event.ended_at = min(resolve_at, now)
            event.notes = _append_note(event.notes, note)
            db.add(event)
            resolved += 1

        if resolved:
            db.commit()

        if not active_events:
            return ("No active fire events required cleanup.", 0)
        return (f"Fire event cleanup scanned {len(active_events)} active event(s).", resolved)


def _run_due_jobs() -> None:
    jobs = [
        ("fire_event_cleanup", settings.fire_event_cleanup_interval_seconds, _run_fire_event_cleanup_job),
        ("device_status_sync", settings.device_status_sync_interval_seconds, _run_device_status_sync_job),
        ("weather_refresh", settings.weather_refresh_interval_seconds, _run_weather_refresh_job),
    ]

    for job_name, interval_seconds, runner in jobs:
        if not _job_is_due(job_name, interval_seconds):
            continue

        _mark_job_running(job_name)
        try:
            detail, affected_count = runner()
            _mark_job_finished(job_name, detail=detail, affected_count=affected_count)
        except Exception as exc:  # pragma: no cover - defensive runtime handling
            _mark_job_failed(job_name, exc)


async def _automation_loop(stop_event: asyncio.Event) -> None:
    with _runtime_lock:
        _runtime.worker_started_at = utcnow()

    while not stop_event.is_set():
        await asyncio.to_thread(_run_due_jobs)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.background_job_poll_seconds)
        except asyncio.TimeoutError:
            continue


def start_automation_worker() -> AutomationWorker | None:
    if not settings.background_jobs_enabled:
        return None

    stop_event = asyncio.Event()
    task = asyncio.create_task(_automation_loop(stop_event))
    return AutomationWorker(stop_event=stop_event, task=task)


async def stop_automation_worker(worker: AutomationWorker | None) -> None:
    if worker is None:
        return

    worker.stop_event.set()
    worker.task.cancel()
    with suppress(asyncio.CancelledError):
        await worker.task
