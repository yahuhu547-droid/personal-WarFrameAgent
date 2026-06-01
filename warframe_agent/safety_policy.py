from __future__ import annotations

from typing import Any

from .browser_gui_safety import build_browser_gui_safety_policy
from .companion_experience import build_companion_experience_policy
from .future_capability_policy import build_future_capability_policy
from .gateway_policy import build_gateway_policy
from .plugin_policy import build_plugin_policy

POLICY_VERSION = "2026-05-26.personal-agent-safety-v1"


def _capability(
    *,
    available: bool,
    default: str,
    requires_explicit_enable: bool,
    enabled: bool | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "available": available,
        "default": default,
        "requires_explicit_enable": requires_explicit_enable,
    }
    if enabled is not None:
        data["enabled"] = enabled
    if scope:
        data["scope"] = scope
    return data


def _sorted_count_dict(counts: dict[str, int]) -> dict[str, int]:
    return {key: counts[key] for key in sorted(counts)}


def summarize_tool_registry_safety(registry: Any) -> dict[str, Any]:
    """Return aggregate-only ToolRegistry safety metadata."""
    try:
        specs = list(getattr(registry, "tool_map", {}).values())
    except Exception:
        specs = []

    safety_levels: dict[str, int] = {}
    skills: dict[str, int] = {}
    context_policies: dict[str, int] = {}
    exposed_schema_count = 0
    side_effect_count = 0
    read_only_candidate_count = 0

    for spec in specs:
        expose_schema = bool(getattr(spec, "expose_schema", False))
        side_effect = bool(getattr(spec, "side_effect", False))
        if expose_schema:
            exposed_schema_count += 1
        if side_effect:
            side_effect_count += 1
        if expose_schema and not side_effect:
            read_only_candidate_count += 1
        safety_level = str(getattr(spec, "safety_level", "unknown") or "unknown")
        skill = str(getattr(spec, "skill", "unknown") or "unknown")
        context_policy = str(getattr(spec, "context_policy", "default") or "default")
        safety_levels[safety_level] = safety_levels.get(safety_level, 0) + 1
        skills[skill] = skills.get(skill, 0) + 1
        context_policies[context_policy] = context_policies.get(context_policy, 0) + 1

    tool_count = len(specs)
    return {
        "tool_count": tool_count,
        "exposed_schema_count": exposed_schema_count,
        "private_schema_count": max(0, tool_count - exposed_schema_count),
        "side_effect_count": side_effect_count,
        "read_only_candidate_count": read_only_candidate_count,
        "safety_levels": _sorted_count_dict(safety_levels),
        "skills": _sorted_count_dict(skills),
        "context_policies": _sorted_count_dict(context_policies),
    }


def build_runtime_safety_policy(
    *,
    scheduler_snapshot: dict[str, Any] | None = None,
    feishu_snapshot: dict[str, Any] | None = None,
    wxpusher_snapshot: dict[str, Any] | None = None,
    tool_registry: Any = None,
) -> dict[str, Any]:
    """Return a safe, read-only description of current runtime capability boundaries."""
    scheduler_snapshot = scheduler_snapshot or {}
    feishu_snapshot = feishu_snapshot or {}
    wxpusher_snapshot = wxpusher_snapshot or {}
    scheduler_enabled = bool(scheduler_snapshot.get("running"))
    external_push_enabled = bool(
        (wxpusher_snapshot.get("enabled") and wxpusher_snapshot.get("configured"))
        or (feishu_snapshot.get("enabled") and feishu_snapshot.get("configured"))
    )

    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "read_only",
        "capabilities": {
            "shell": _capability(available=False, default="disabled", requires_explicit_enable=True),
            "generic_file_write": _capability(available=False, default="disabled", requires_explicit_enable=True),
            "browser_private_network": _capability(available=False, default="disabled", requires_explicit_enable=True),
            "browser_gui_automation": _capability(available=False, default="disabled", requires_explicit_enable=True),
            "voice_companion_experience": _capability(
                available=False,
                default="disabled",
                requires_explicit_enable=True,
            ),
            "arbitrary_scheduler": _capability(available=False, default="disabled", requires_explicit_enable=True),
            "market_network": _capability(
                available=True,
                default="read_only",
                requires_explicit_enable=False,
                enabled=True,
                scope="warframe_market_and_game_data",
            ),
            "project_data_write": _capability(
                available=True,
                default="restricted",
                requires_explicit_enable=False,
                enabled=True,
                scope="project_data_and_user_confirmed_preferences",
            ),
            "scheduler_jobs": _capability(
                available=True,
                default="restricted",
                requires_explicit_enable=False,
                enabled=scheduler_enabled,
                scope="registered_jobs_only",
            ),
            "external_push": _capability(
                available=True,
                default="explicit_config",
                requires_explicit_enable=True,
                enabled=external_push_enabled,
                scope="feishu_and_wxpusher_only",
            ),
            "multi_channel_gateway": _capability(
                available=True,
                default="restricted",
                requires_explicit_enable=False,
                enabled=True,
                scope="web_chat_ws_cli_and_configured_push_only",
            ),
            "skills_plugin_ecosystem": _capability(
                available=True,
                default="guidance_only",
                requires_explicit_enable=False,
                enabled=True,
                scope="local_skills_guidance_and_reviewed_plugins_only",
            ),
            "future_capability_admission": _capability(
                available=True,
                default="design_required",
                requires_explicit_enable=True,
                enabled=False,
                scope="future_high_risk_features_policy_only",
            ),
        },
        "browser_gui_policy": build_browser_gui_safety_policy(),
        "companion_experience_policy": build_companion_experience_policy(),
        "gateway_policy": build_gateway_policy(),
        "plugin_policy": build_plugin_policy(),
        "future_capability_policy": build_future_capability_policy(),
        "tool_registry": summarize_tool_registry_safety(tool_registry),
        "guardrails": [
            "No generic shell execution is exposed to the Agent runtime.",
            "No generic file write tool is exposed; writes stay within project data APIs.",
            "No browser private-network automation is exposed.",
            "Browser and GUI automation is not exposed; action-level policy is read-only.",
            "Voice, Live2D, microphone, recording, platform-token, and background-listening companion surfaces are not exposed.",
            "No arbitrary scheduler creation is exposed; only registered jobs are reported.",
            "External push channels require explicit configuration and secrets are never returned.",
            "Multi-channel gateway expansion is restricted to known interactive or configured channels; public, anonymous, and high-risk inbound commands are blocked.",
            "Skills and plugin ecosystem expansion is guidance-only by default; plugins and connectors require review before runtime use.",
            "Completed learning-borrowing work does not enable future high-privilege runtime features; new stages require design review first.",
        ],
    }
