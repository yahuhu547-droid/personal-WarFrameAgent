from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

Clock = Callable[[], datetime]

_MAX_ERROR_LENGTH = 300
_SENSITIVE_LINE_RE = re.compile(
    r"(?im)\b(password|token|secret|api_key|apikey|authorization|cookie|app_secret|chat_id)\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


@dataclass(frozen=True)
class IntervalSchedule:
    seconds: int
    run_immediately: bool = False


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    callback: Callable[[], Any]
    schedule: IntervalSchedule
    enabled: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    running: bool = False
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_duration_ms: float | None = None
    last_success: bool | None = None
    last_error_summary: str | None = None
    safety_level: str = "read_only"
    external_side_effect: bool = False


@dataclass(frozen=True)
class JobRunResult:
    job_id: str
    name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error: str | None = None


class Scheduler:
    def __init__(self, clock: Clock | None = None):
        self._clock = clock or datetime.now
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock = threading.RLock()
        self._running = False

    def add_interval_job(
        self,
        job_id: str,
        name: str,
        callback: Callable[[], Any],
        seconds: int,
        *,
        run_immediately: bool = False,
        enabled: bool = True,
        initial_delay_seconds: int | None = None,
        safety_level: str = "read_only",
        external_side_effect: bool = False,
    ) -> ScheduledJob:
        if seconds <= 0:
            raise ValueError("interval seconds 必须大于 0")
        if initial_delay_seconds is not None and initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds 必须大于等于 0")
        if run_immediately and initial_delay_seconds is not None:
            raise ValueError("run_immediately 和 initial_delay_seconds 不能同时使用")
        with self._lock:
            if job_id in self._jobs:
                raise ValueError(f"调度任务已存在: {job_id}")
            now = self._clock()
            schedule = IntervalSchedule(seconds=seconds, run_immediately=run_immediately)
            first_delay = seconds if initial_delay_seconds is None else initial_delay_seconds
            job = ScheduledJob(
                job_id=job_id,
                name=name,
                callback=callback,
                schedule=schedule,
                enabled=enabled,
                next_run_at=now if run_immediately else now + timedelta(seconds=first_delay),
                safety_level=safety_level,
                external_side_effect=external_side_effect,
            )
            self._jobs[job_id] = job
            return job

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def get_job(self, job_id: str) -> ScheduledJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[ScheduledJob]:
        with self._lock:
            return list(self._jobs.values())

    def due_jobs(self, now: datetime | None = None) -> list[ScheduledJob]:
        current = now or self._clock()
        with self._lock:
            return [
                job
                for job in self._jobs.values()
                if job.enabled and job.next_run_at is not None and job.next_run_at <= current
            ]

    def run_due(self, now: datetime | None = None) -> list[JobRunResult]:
        with self._lock:
            if self._running:
                return []
            self._running = True
            jobs = self.due_jobs(now)
        try:
            results = []
            for job in jobs:
                results.append(self._run_job(job))
            return results
        finally:
            with self._lock:
                self._running = False

    def tick(self, now: datetime | None = None) -> list[JobRunResult]:
        return self.run_due(now)

    def _run_job(self, job: ScheduledJob) -> JobRunResult:
        started_at = self._clock()
        with self._lock:
            current = self._jobs.get(job.job_id)
            if current is job:
                job.running = True
                job.last_started_at = started_at
        error = None
        success = True
        try:
            job.callback()
        except Exception as exc:
            success = False
            error = _format_error(exc)
        finished_at = self._clock()
        duration_ms = max(0.0, (finished_at - started_at).total_seconds() * 1000)
        with self._lock:
            current = self._jobs.get(job.job_id)
            if current is job:
                job.running = False
                job.last_run_at = finished_at
                job.last_finished_at = finished_at
                job.last_duration_ms = duration_ms
                job.last_success = success
                job.last_error_summary = error
                job.next_run_at = finished_at + timedelta(seconds=job.schedule.seconds)
                if success:
                    job.run_count += 1
                else:
                    job.error_count += 1
        return JobRunResult(
            job_id=job.job_id,
            name=job.name,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )


def serialize_scheduled_job(job: ScheduledJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule": {
            "type": "interval",
            "seconds": job.schedule.seconds,
            "run_immediately": job.schedule.run_immediately,
        },
        "next_run_at": _format_datetime(job.next_run_at),
        "last_run_at": _format_datetime(job.last_run_at),
        "run_count": job.run_count,
        "error_count": job.error_count,
        "running": job.running,
        "last_started_at": _format_datetime(job.last_started_at),
        "last_finished_at": _format_datetime(job.last_finished_at),
        "last_duration_ms": job.last_duration_ms,
        "last_success": job.last_success,
        "last_error_summary": job.last_error_summary,
        "safety_level": job.safety_level,
        "external_side_effect": job.external_side_effect,
    }


def serialize_scheduler_jobs(scheduler: Scheduler) -> list[dict[str, Any]]:
    return [serialize_scheduled_job(job) for job in scheduler.list_jobs()]


class SchedulerRunner:
    def __init__(self, scheduler: Scheduler, poll_seconds: float = 1.0):
        if poll_seconds <= 0:
            raise ValueError("poll_seconds 必须大于 0")
        self.scheduler = scheduler
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.scheduler.tick()
            self._stop_event.wait(self.poll_seconds)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _format_error(exc: Exception) -> str:
    text = _redact_sensitive_text(f"{type(exc).__name__}: {exc}")
    if len(text) > _MAX_ERROR_LENGTH:
        return f"{text[:_MAX_ERROR_LENGTH]}... [len={len(text)}]"
    return text


def _redact_sensitive_text(text: str) -> str:
    text = _BEARER_RE.sub("[REDACTED]", text)
    return _SENSITIVE_LINE_RE.sub("[REDACTED]", text)
