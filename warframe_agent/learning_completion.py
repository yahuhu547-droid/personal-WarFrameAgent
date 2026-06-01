from __future__ import annotations

POLICY_VERSION = "2026-05-31.learning-completion-v1"

COMPLETED_STEPS = (
    "step34_multi_agent_architecture_decision",
    "step35_plan_reviewer_verifier",
    "step36_ops_health_summary",
    "step37_memory_vault_index",
    "step38_browser_gui_safety_boundary",
    "step39_companion_experience_boundary_text_only",
    "step40_learning_phase_review",
    "step41_controlled_plan_confirmation",
    "step42_chat_plan_confirmation",
    "step43_gateway_boundary",
    "step44_plugin_policy",
    "step45_runtime_policy_visibility",
    "step46_non_voice_learning_closure",
    "step47_final_playwright_closure",
    "step48_future_capability_admission",
    "step49_future_capability_runtime_visibility",
    "step50_learning_completion_runtime_snapshot",
)

IMPROVEMENT_STEPS = (
    "step48_future_capability_admission",
    "step49_future_capability_runtime_visibility",
)

FROZEN_SURFACES = (
    "real_voice_runtime",
    "tts",
    "stt",
    "microphone",
    "recording",
    "live2d",
    "background_listening",
)

NEXT_STAGE_REQUIRED = (
    "browser_gui_executor",
    "service_recovery",
    "arbitrary_trigger_platform",
    "plugin_install",
    "connector_enable",
    "webhook_command_entry",
    "dm_command_entry",
)

ACCEPTANCE_CHECKLIST = (
    {
        "id": "legacy_non_voice_learning_route_complete",
        "status": "passed",
        "evidence": "step47_final_playwright_closure",
        "runtime_enabled": True,
    },
    {
        "id": "step48_49_improvements_complete",
        "status": "passed",
        "evidence": "step48_future_capability_admission+step49_future_capability_runtime_visibility",
        "runtime_enabled": True,
    },
    {
        "id": "runtime_status_api_exposes_completion",
        "status": "passed",
        "evidence": "runtime_status.learning_completion",
        "runtime_enabled": True,
    },
    {
        "id": "runtime_panel_exposes_completion",
        "status": "passed",
        "evidence": "runtime_panel.learning_completion",
        "runtime_enabled": True,
    },
    {
        "id": "runtime_high_privilege_not_enabled",
        "status": "passed",
        "evidence": "future_capability_admission.enabled_false",
        "runtime_enabled": False,
    },
    {
        "id": "real_voice_runtime_frozen",
        "status": "passed",
        "evidence": "current_user_instruction_freeze",
        "runtime_enabled": False,
    },
    {
        "id": "future_capabilities_require_new_stage",
        "status": "passed",
        "evidence": "next_stage_required",
        "runtime_enabled": False,
    },
    {
        "id": "step50_closure_snapshot_present",
        "status": "passed",
        "evidence": "step50_learning_completion_runtime_snapshot",
        "runtime_enabled": True,
    },
)


def build_learning_completion_snapshot() -> dict[str, object]:
    """Return a safe, read-only learning route completion snapshot."""
    return {
        "policy_version": POLICY_VERSION,
        "status": "complete",
        "acceptance_status": "accepted",
        "legacy_non_voice_learning_complete": True,
        "improvement_closure_complete": True,
        "runtime_enablement_changed": False,
        "completed_step_count": len(COMPLETED_STEPS),
        "completed_steps": list(COMPLETED_STEPS),
        "improvement_steps": list(IMPROVEMENT_STEPS),
        "frozen_surfaces": list(FROZEN_SURFACES),
        "next_stage_required": list(NEXT_STAGE_REQUIRED),
        "guardrails": [
            "Completed learning-borrowing work does not enable future high-privilege runtime features.",
            "Future high-privilege capabilities require a separate design stage.",
            "Real voice and companion runtime remain frozen by current user instruction.",
        ],
        "acceptance_snapshot": {
            "latest_closure_step": "step50_learning_completion_runtime_snapshot",
            "acceptance_record_step": "step51_learning_completion_acceptance_snapshot",
            "all_items_passed": True,
            "checklist_count": len(ACCEPTANCE_CHECKLIST),
            "checklist": [dict(item) for item in ACCEPTANCE_CHECKLIST],
        },
    }
