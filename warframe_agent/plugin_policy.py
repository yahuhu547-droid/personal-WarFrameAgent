from __future__ import annotations

import re
from typing import Any

POLICY_VERSION = "2026-05-30.plugin-policy-v1"

GUIDANCE_SOURCES = {"local_skill", "system_skill", "project_skill"}
LOCAL_EXTENSIONS = {"personal_plugin", "codex_plugin", "local_plugin"}
ACCOUNT_CONNECTORS = {"connector", "external_connector", "account_connector"}
KNOWN_SOURCES = GUIDANCE_SOURCES | LOCAL_EXTENSIONS | ACCOUNT_CONNECTORS
GUIDANCE_CAPABILITIES = {"prompt_guidance", "reference_docs", "template", "workflow"}
PLUGIN_CAPABILITIES = {"tool_provider", "ui_extension", "mcp_server", "resource_provider"}
CONNECTOR_CAPABILITIES = {"account_access", "external_api", "platform_read"}
HIGH_RISK_CAPABILITIES = {
    "browser_control",
    "credential_access",
    "file_write",
    "network_post",
    "scheduler_create",
    "shell",
    "social_post",
    "trade_action",
}

_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WINDOWS_PATH_RE = re.compile(r"(?i)\b[a-z]:[\\/][^\s,;]+")
_POSIX_SECRET_PATH_RE = re.compile(r"(?i)/(?:users|home)/[^\s,;]+")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b[a-z0-9_.-]*(?:password|token|secret|api[_-]?key|apikey|authorization|cookie|account[_-]?id|handler|params|raw[_-]?manifest)[a-z0-9_.-]*\b\s*[:=]\s*([^\s\r\n,;{}]+|\{[^}]*\})"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


def classify_plugin_capability(
    source: str,
    *,
    capability: str = "prompt_guidance",
    installed: bool = False,
    explicit_enable: bool = False,
    manifest_text: str = "",
) -> dict[str, Any]:
    safe_source = _safe_identifier(source) or "unknown"
    safe_capability = _safe_identifier(capability) or "unknown"

    if safe_capability in HIGH_RISK_CAPABILITIES:
        decision = "blocked_high_risk_capability"
        trust_boundary = _trust_boundary_for_source(safe_source)
    elif safe_source in GUIDANCE_SOURCES and safe_capability in GUIDANCE_CAPABILITIES:
        decision = "allow_guidance_only"
        trust_boundary = "local_guidance"
    elif safe_source in LOCAL_EXTENSIONS and safe_capability in PLUGIN_CAPABILITIES:
        if installed:
            decision = "requires_review"
            trust_boundary = "installed_local_extension"
        else:
            decision = "blocked_uninstalled_extension"
            trust_boundary = "uninstalled_extension"
    elif safe_source in ACCOUNT_CONNECTORS and safe_capability in CONNECTOR_CAPABILITIES:
        if installed and explicit_enable:
            decision = "requires_explicit_enable"
            trust_boundary = "external_account_connector"
        elif installed:
            decision = "blocked_missing_explicit_enable"
            trust_boundary = "external_account_connector"
        else:
            decision = "blocked_uninstalled_extension"
            trust_boundary = "uninstalled_extension"
    elif safe_source not in KNOWN_SOURCES:
        decision = "blocked_unknown_capability"
        trust_boundary = "unknown_extension"
    else:
        decision = "blocked_unknown_capability"
        trust_boundary = _trust_boundary_for_source(safe_source)

    blocked = decision.startswith("blocked")
    return {
        "source": safe_source,
        "capability": safe_capability,
        "decision": decision,
        "trust_boundary": trust_boundary,
        "blocked": blocked,
        "requires_human_confirmation": decision in {"requires_review", "requires_explicit_enable"} or blocked,
        "requires_explicit_enable": decision == "requires_explicit_enable",
        "reason": _decision_reason(decision),
        "manifest_summary": _safe_text(manifest_text, max_chars=120) if manifest_text else "",
    }


def build_plugin_policy() -> dict[str, Any]:
    examples = [
        classify_plugin_capability(
            "local_skill",
            capability="prompt_guidance",
            manifest_text="path=C:/Users/secret-token/skill token=abc123",
        ),
        classify_plugin_capability(
            "personal_plugin",
            capability="tool_provider",
            installed=True,
            manifest_text="handler=run params={api_key:secret-token}",
        ),
        classify_plugin_capability(
            "connector",
            capability="account_access",
            installed=True,
            explicit_enable=True,
            manifest_text="account_id=user-123 token=secret-token",
        ),
        classify_plugin_capability("personal_plugin", capability="shell", installed=True, explicit_enable=True),
        classify_plugin_capability("mystery_plugin", capability="tool_provider"),
    ]
    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "guidance_only",
        "plugin_runtime_enabled": False,
        "connector_runtime_enabled": False,
        "automatic_tool_install_enabled": False,
        "allowed_guidance_sources": sorted(GUIDANCE_SOURCES),
        "review_required_sources": sorted(LOCAL_EXTENSIONS),
        "explicit_enable_sources": sorted(ACCOUNT_CONNECTORS),
        "blocked_capabilities": sorted(HIGH_RISK_CAPABILITIES),
        "decision_counts": _decision_counts(examples),
        "capability_matrix": examples,
        "guardrails": [
            "Local skills are prompt and workflow guidance by default, not runtime tools.",
            "Personal plugins require review before their capabilities are mapped into ToolRegistry.",
            "Account connectors require explicit enablement and user confirmation before use.",
            "Shell, file writes, browser control, scheduler creation, credential access, social posting, and trade actions are blocked.",
            "Plugin policy is a read-only runtime snapshot and does not install or activate plugins.",
        ],
    }


def _decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "allow_guidance_only": 0,
        "requires_review": 0,
        "requires_explicit_enable": 0,
        "blocked_high_risk_capability": 0,
        "blocked_uninstalled_extension": 0,
        "blocked_missing_explicit_enable": 0,
        "blocked_unknown_capability": 0,
    }
    for item in items:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _trust_boundary_for_source(source: str) -> str:
    if source in GUIDANCE_SOURCES:
        return "local_guidance"
    if source in LOCAL_EXTENSIONS:
        return "installed_local_extension"
    if source in ACCOUNT_CONNECTORS:
        return "external_account_connector"
    return "unknown_extension"


def _decision_reason(decision: str) -> str:
    reasons = {
        "allow_guidance_only": "skill_guidance_only_no_runtime_tool",
        "requires_review": "plugin_capability_requires_mapping_review",
        "requires_explicit_enable": "connector_requires_explicit_enable_and_confirmation",
        "blocked_high_risk_capability": "high_risk_capability_not_exposed",
        "blocked_uninstalled_extension": "extension_not_installed_or_not_reviewed",
        "blocked_missing_explicit_enable": "connector_missing_explicit_enable",
        "blocked_unknown_capability": "unknown_plugin_or_capability_blocked",
    }
    return reasons.get(decision, "unknown_plugin_decision")


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _IDENTIFIER_RE.sub("_", text).strip("_")[:80]


def _safe_text(value: Any, *, max_chars: int = 240) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    text = _WINDOWS_PATH_RE.sub("[REDACTED]", text)
    text = _POSIX_SECRET_PATH_RE.sub("[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KV_RE.sub("[REDACTED]", text)
    compact = " ".join(part.strip() for part in text.split() if part.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return compact
