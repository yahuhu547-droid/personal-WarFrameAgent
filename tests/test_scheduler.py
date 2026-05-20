from datetime import datetime, timedelta

import pytest

from warframe_agent.scheduler import (
    Scheduler,
    SchedulerRunner,
    serialize_scheduled_job,
    serialize_scheduler_jobs,
)


class FakeClock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def test_add_interval_job_sets_initial_next_run():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)

    job = scheduler.add_interval_job("scan", "Scan", lambda: None, 60)

    assert job.next_run_at == datetime(2026, 5, 17, 10, 1, 0)
    assert job.last_run_at is None
    assert job.run_count == 0
    assert job.error_count == 0


def test_add_interval_job_with_run_immediately_is_due_now():
    now = datetime(2026, 5, 17, 10, 0, 0)
    clock = FakeClock(now)
    scheduler = Scheduler(clock=clock)

    job = scheduler.add_interval_job("scan", "Scan", lambda: None, 60, run_immediately=True)

    assert job.next_run_at == now
    assert scheduler.due_jobs() == [job]


def test_add_interval_job_with_initial_delay_sets_first_next_run():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)

    job = scheduler.add_interval_job(
        "maintenance",
        "Maintenance",
        lambda: clock.advance(5),
        300,
        initial_delay_seconds=120,
    )

    assert job.next_run_at == datetime(2026, 5, 17, 10, 2, 0)
    assert scheduler.due_jobs() == []

    clock.advance(120)
    result = scheduler.run_due()[0]

    assert result.started_at == datetime(2026, 5, 17, 10, 2, 0)
    assert result.finished_at == datetime(2026, 5, 17, 10, 2, 5)
    assert job.next_run_at == datetime(2026, 5, 17, 10, 7, 5)


def test_add_interval_job_rejects_negative_initial_delay():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))

    with pytest.raises(ValueError, match="大于等于 0"):
        scheduler.add_interval_job("maintenance", "Maintenance", lambda: None, 60, initial_delay_seconds=-1)


def test_add_interval_job_rejects_initial_delay_with_run_immediately():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))

    with pytest.raises(ValueError, match="不能同时"):
        scheduler.add_interval_job(
            "maintenance",
            "Maintenance",
            lambda: None,
            60,
            run_immediately=True,
            initial_delay_seconds=10,
        )


def test_rejects_duplicate_job_id():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    scheduler.add_interval_job("scan", "Scan", lambda: None, 60)

    with pytest.raises(ValueError, match="已存在"):
        scheduler.add_interval_job("scan", "Scan Again", lambda: None, 60)


def test_rejects_non_positive_interval():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))

    with pytest.raises(ValueError, match="大于 0"):
        scheduler.add_interval_job("zero", "Zero", lambda: None, 0)
    with pytest.raises(ValueError, match="大于 0"):
        scheduler.add_interval_job("negative", "Negative", lambda: None, -1)


def test_due_jobs_returns_only_due_enabled_jobs():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)
    due = scheduler.add_interval_job("due", "Due", lambda: None, 60, run_immediately=True)
    scheduler.add_interval_job("future", "Future", lambda: None, 60)
    scheduler.add_interval_job("disabled", "Disabled", lambda: None, 60, run_immediately=True, enabled=False)

    assert scheduler.due_jobs() == [due]


def test_run_due_executes_due_jobs_in_registration_order():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)
    calls = []

    scheduler.add_interval_job("a", "A", lambda: calls.append("a"), 60, run_immediately=True)
    scheduler.add_interval_job("b", "B", lambda: calls.append("b"), 60, run_immediately=True)

    results = scheduler.run_due()

    assert calls == ["a", "b"]
    assert [result.job_id for result in results] == ["a", "b"]
    assert all(result.success for result in results)


def test_run_due_reschedules_after_success_from_finished_at():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)

    def callback():
        clock.advance(5)

    job = scheduler.add_interval_job("scan", "Scan", callback, 60, run_immediately=True)

    result = scheduler.run_due()[0]

    assert result.started_at == datetime(2026, 5, 17, 10, 0, 0)
    assert result.finished_at == datetime(2026, 5, 17, 10, 0, 5)
    assert result.duration_ms == 5000.0
    assert job.last_run_at == datetime(2026, 5, 17, 10, 0, 5)
    assert job.next_run_at == datetime(2026, 5, 17, 10, 1, 5)
    assert job.run_count == 1


def test_run_due_captures_exception_and_continues():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)
    calls = []

    def failing():
        raise ValueError("bad input")

    scheduler.add_interval_job("bad", "Bad", failing, 60, run_immediately=True)
    good = scheduler.add_interval_job("good", "Good", lambda: calls.append("good"), 60, run_immediately=True)

    results = scheduler.run_due()

    assert calls == ["good"]
    assert results[0].success is False
    assert results[0].error == "ValueError: bad input"
    assert results[1].success is True
    assert scheduler.get_job("bad").error_count == 1
    assert good.run_count == 1


def test_overdue_job_runs_once_per_tick_not_catch_up_loop():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)
    calls = []
    job = scheduler.add_interval_job("scan", "Scan", lambda: calls.append("scan"), 60, run_immediately=True)
    clock.advance(3600)

    scheduler.run_due()

    assert calls == ["scan"]
    assert job.next_run_at == datetime(2026, 5, 17, 11, 1, 0)
    assert scheduler.due_jobs() == []


def test_remove_job_prevents_future_execution():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    calls = []
    scheduler.add_interval_job("scan", "Scan", lambda: calls.append("scan"), 60, run_immediately=True)

    assert scheduler.remove_job("scan") is True
    assert scheduler.remove_job("scan") is False
    assert scheduler.run_due() == []
    assert calls == []


def test_disabled_job_does_not_run():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    calls = []
    job = scheduler.add_interval_job("scan", "Scan", lambda: calls.append("scan"), 60, run_immediately=True, enabled=False)

    assert scheduler.due_jobs() == []
    assert scheduler.run_due() == []
    assert calls == []
    assert scheduler.list_jobs() == [job]


def test_list_jobs_returns_stable_registration_order():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    scheduler.add_interval_job("a", "A", lambda: None, 60)
    scheduler.add_interval_job("b", "B", lambda: None, 60)
    scheduler.add_interval_job("c", "C", lambda: None, 60)

    assert [job.job_id for job in scheduler.list_jobs()] == ["a", "b", "c"]


def test_tick_is_alias_for_run_due():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    calls = []
    scheduler.add_interval_job("scan", "Scan", lambda: calls.append("scan"), 60, run_immediately=True)

    results = scheduler.tick()

    assert calls == ["scan"]
    assert [result.job_id for result in results] == ["scan"]


def test_serialize_scheduled_job_formats_public_fields():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    job = scheduler.add_interval_job("scan", "Scan", lambda: None, 60, run_immediately=True)

    snapshot = serialize_scheduled_job(job)

    assert snapshot == {
        "job_id": "scan",
        "name": "Scan",
        "enabled": True,
        "schedule": {
            "type": "interval",
            "seconds": 60,
            "run_immediately": True,
        },
        "next_run_at": "2026-05-17T10:00:00",
        "last_run_at": None,
        "run_count": 0,
        "error_count": 0,
        "running": False,
        "last_started_at": None,
        "last_finished_at": None,
        "last_duration_ms": None,
        "last_success": None,
        "last_error_summary": None,
        "safety_level": "read_only",
        "external_side_effect": False,
    }
    assert "callback" not in snapshot


def test_serialize_scheduler_jobs_preserves_order_and_counts():
    clock = FakeClock(datetime(2026, 5, 17, 10, 0, 0))
    scheduler = Scheduler(clock=clock)

    scheduler.add_interval_job("success", "Success", lambda: None, 60, run_immediately=True)

    def failing():
        raise ValueError("token=secret-token Authorization: Bearer abc app_secret=hidden chat_id=oc_123")

    scheduler.add_interval_job("failure", "Failure", failing, 60, run_immediately=True)
    scheduler.add_interval_job("disabled", "Disabled", lambda: None, 60, run_immediately=True, enabled=False)
    scheduler.run_due()

    snapshots = serialize_scheduler_jobs(scheduler)

    assert [snapshot["job_id"] for snapshot in snapshots] == ["success", "failure", "disabled"]
    assert snapshots[0]["run_count"] == 1
    assert snapshots[0]["error_count"] == 0
    assert snapshots[0]["last_success"] is True
    assert snapshots[0]["last_duration_ms"] == 0.0
    assert snapshots[1]["run_count"] == 0
    assert snapshots[1]["error_count"] == 1
    assert snapshots[1]["last_success"] is False
    assert "ValueError" in snapshots[1]["last_error_summary"]
    assert snapshots[2]["enabled"] is False
    assert snapshots[2]["run_count"] == 0
    assert snapshots[2]["error_count"] == 0
    assert all("callback" not in snapshot for snapshot in snapshots)
    serialized = str(snapshots)
    for forbidden in ["secret-token", "Bearer abc", "hidden", "oc_123", "token=", "app_secret=", "chat_id="]:
        assert forbidden not in serialized


def test_add_interval_job_accepts_observability_metadata():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))

    job = scheduler.add_interval_job(
        "push",
        "Push",
        lambda: None,
        60,
        safety_level="external_side_effect",
        external_side_effect=True,
    )
    snapshot = serialize_scheduled_job(job)

    assert snapshot["safety_level"] == "external_side_effect"
    assert snapshot["external_side_effect"] is True



def test_runner_rejects_non_positive_poll_seconds():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))

    with pytest.raises(ValueError, match="大于 0"):
        SchedulerRunner(scheduler, poll_seconds=0)


def test_runner_start_stop_idempotent():
    scheduler = Scheduler(clock=FakeClock(datetime(2026, 5, 17, 10, 0, 0)))
    runner = SchedulerRunner(scheduler, poll_seconds=0.01)

    runner.start()
    runner.start()
    assert runner.is_running is True

    runner.stop()
    runner.stop()
    assert runner.is_running is False
