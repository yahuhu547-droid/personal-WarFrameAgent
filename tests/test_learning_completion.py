from warframe_agent.learning_completion import build_learning_completion_snapshot


def test_learning_completion_snapshot_marks_route_and_improvements_complete():
    snapshot = build_learning_completion_snapshot()

    assert snapshot["status"] == "complete"
    assert snapshot["legacy_non_voice_learning_complete"] is True
    assert snapshot["improvement_closure_complete"] is True
    assert snapshot["runtime_enablement_changed"] is False
    assert snapshot["completed_step_count"] >= 16
    assert "step49_future_capability_runtime_visibility" in snapshot["completed_steps"]
    assert "step48_future_capability_admission" in snapshot["improvement_steps"]


def test_learning_completion_acceptance_snapshot_anchors_step50_closure():
    snapshot = build_learning_completion_snapshot()

    assert snapshot["acceptance_status"] == "accepted"
    acceptance = snapshot["acceptance_snapshot"]
    assert acceptance["latest_closure_step"] == "step50_learning_completion_runtime_snapshot"
    assert acceptance["acceptance_record_step"] == "step51_learning_completion_acceptance_snapshot"
    assert acceptance["all_items_passed"] is True
    assert acceptance["checklist_count"] >= 7
    assert "step50_learning_completion_runtime_snapshot" in snapshot["completed_steps"]


def test_learning_completion_acceptance_checklist_keeps_runtime_high_risk_disabled():
    snapshot = build_learning_completion_snapshot()
    checklist = snapshot["acceptance_snapshot"]["checklist"]

    by_id = {item["id"]: item for item in checklist}
    assert by_id["runtime_high_privilege_not_enabled"]["status"] == "passed"
    assert by_id["runtime_high_privilege_not_enabled"]["runtime_enabled"] is False
    assert by_id["real_voice_runtime_frozen"]["runtime_enabled"] is False
    assert by_id["future_capabilities_require_new_stage"]["runtime_enabled"] is False
    assert by_id["step50_closure_snapshot_present"]["evidence"] == "step50_learning_completion_runtime_snapshot"


def test_learning_completion_snapshot_keeps_future_high_privilege_as_next_stage():
    snapshot = build_learning_completion_snapshot()

    assert "browser_gui_executor" in snapshot["next_stage_required"]
    assert "service_recovery" in snapshot["next_stage_required"]
    assert "plugin_install" in snapshot["next_stage_required"]
    assert "connector_enable" in snapshot["next_stage_required"]
    assert "real_voice_runtime" in snapshot["frozen_surfaces"]


def test_learning_completion_snapshot_is_safe_aggregate_only():
    snapshot = build_learning_completion_snapshot()
    serialized = str(snapshot)

    for forbidden in (
        "token",
        "secret",
        "api_key",
        "Authorization",
        "cookie",
        "account_id",
        "raw_payload",
        "raw_plan",
        "handler",
        "params",
        "/w",
        "C:\\Users",
        "127.0.0.1",
    ):
        assert forbidden not in serialized
