from __future__ import annotations

import re
from typing import Any

POLICY_VERSION = "2026-05-30.future-capability-admission-v1"

DESIGN_ONLY_CAPABILITIES = {
    "architecture_review",
    "audit_design",
    "design_doc",
    "permission_design",
    "risk_assessment",
}
FROZEN_BY_USER_INSTRUCTION = {
    "audio_recording",
    "background_listening",
    "live2d_runtime",
    "microphone_recording",
    "real_voice_service",
    "stt",
    "tts",
    "voice_runtime",
}
PUBLIC_OR_PRIVATE_INBOUND = {
    "anonymous_webhook",
    "buyer_dm_commands",
    "platform_dm_commands",
    "public_comment_commands",
    "seller_dm_commands",
    "webhook_inbound_command",
}
NEW_STAGE_REQUIRED = {
    "arbitrary_trigger_platform",
    "browser_gui_executor",
    "connector_enable",
    "plugin_install",
    "private_network_browser",
    "scheduler_create",
    "service_recovery",
}
UNCONTROLLED_RUNTIME = {
    "credential_access",
    "generic_file_write",
    "shell",
    "social_post",
    "trade_action",
}

_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|apikey|authorization|cookie|account[_-]?id|"
    r"raw[_-]?(?:payload|manifest|arguments|message|result)|handler|params|profile/|/w\b|"
    r"127\.0\.0\.1|localhost|bearer\s+|[a-z]:[\\/]|/(?:users|home)/)"
)


def classify_future_capability(capability: str, *, request_text: str = "") -> dict[str, Any]:
    safe_capability = _safe_capability_identifier(capability)

    if safe_capability in DESIGN_ONLY_CAPABILITIES:
        decision = "allow_design_only"
        trust_boundary = "documentation_only"
    elif safe_capability in FROZEN_BY_USER_INSTRUCTION:
        decision = "frozen_by_current_user_instruction"
        trust_boundary = "user_frozen_surface"
    elif safe_capability in PUBLIC_OR_PRIVATE_INBOUND:
        decision = "blocked_public_or_private_inbound"
        trust_boundary = "untrusted_inbound_surface"
    elif safe_capability in UNCONTROLLED_RUNTIME:
        decision = "blocked_uncontrolled_runtime"
        trust_boundary = "uncontrolled_runtime_surface"
    elif safe_capability in NEW_STAGE_REQUIRED:
        decision = "requires_new_stage_design"
        trust_boundary = "future_high_privilege_surface"
    else:
        decision = "requires_new_stage_design"
        trust_boundary = "unknown_future_surface"

    return {
        "capability": safe_capability,
        "decision": decision,
        "trust_boundary": trust_boundary,
        "runtime_enabled": False,
        "requires_new_stage_design": decision != "allow_design_only",
        "requires_explicit_user_approval": decision != "allow_design_only",
        "blocked": decision.startswith("blocked"),
        "reason": _decision_reason(decision),
        "request_summary": _safe_text(request_text),
    }


def build_future_capability_policy() -> dict[str, Any]:
    examples = [
        classify_future_capability(
            "browser_gui_executor",
            request_text="enable Playwright login automation token=secret-token /w Player",
        ),
        classify_future_capability("real_voice_service", request_text="turn on microphone"),
        classify_future_capability("anonymous_webhook", request_text="raw_payload=/w Player"),
        classify_future_capability(
            "shell",
            request_text="handler=run params={api_key:secret-token account_id=user-123}",
        ),
        classify_future_capability("design_doc", request_text="draft permission design"),
    ]
    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "design_required_before_runtime",
        "runtime_enablement_allowed": False,
        "automatic_enable_enabled": False,
        "design_review_required": True,
        "human_confirmation_required_before_runtime": True,
        "frozen_by_current_user_instruction": sorted(FROZEN_BY_USER_INSTRUCTION),
        "review_required_capabilities": sorted(NEW_STAGE_REQUIRED),
        "blocked_inbound_surfaces": sorted(PUBLIC_OR_PRIVATE_INBOUND),
        "blocked_runtime_capabilities": sorted(UNCONTROLLED_RUNTIME),
        "decision_counts": _decision_counts(examples),
        "capability_matrix": examples,
        "guardrails": [
            "Completed learning-borrowing work does not enable future high-privilege runtime features.",
            "Real voice, TTS, STT, microphone, recording, Live2D, and background listening remain frozen by current user instruction.",
            "Browser/GUI executors, service recovery, arbitrary triggers, plugin installs, and connector enablement require a new design stage.",
            "Public comments, anonymous webhooks, and platform DMs are not command entrypoints.",
            "Shell, generic file writes, credential access, social posting, and trade actions are not exposed to runtime.",
        ],
    }


def _decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "allow_design_only": 0,
        "requires_new_stage_design": 0,
        "frozen_by_current_user_instruction": 0,
        "blocked_public_or_private_inbound": 0,
        "blocked_uncontrolled_runtime": 0,
    }
    for item in items:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _decision_reason(decision: str) -> str:
    reasons = {
        "allow_design_only": "design_documentation_allowed_without_runtime_enablement",
        "requires_new_stage_design": "future_capability_requires_permissions_confirmation_interrupts_and_audit_design",
        "frozen_by_current_user_instruction": "current_user_instruction_freezes_real_voice_and_companion_runtime",
        "blocked_public_or_private_inbound": "public_or_private_inbound_commands_are_not_trusted_entrypoints",
        "blocked_uncontrolled_runtime": "uncontrolled_runtime_capability_not_exposed",
    }
    return reasons.get(decision, "future_capability_requires_review")


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _IDENTIFIER_RE.sub("_", text).strip("_")[:80]


def _safe_capability_identifier(value: Any) -> str:
    raw_text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    safe_identifier = _safe_identifier(raw_text)
    if _SENSITIVE_TEXT_RE.search(raw_text) or _SENSITIVE_TEXT_RE.search(safe_identifier):
        return "unknown_future_capability"
    return safe_identifier or "unknown"


def _safe_text(value: Any, *, max_chars: int = 120) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    if not text.strip():
        return ""
    if _SENSITIVE_TEXT_RE.search(text):
        return "[REDACTED]"
    compact = " ".join(part.strip() for part in text.split() if part.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return compact
