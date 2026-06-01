from __future__ import annotations

import re
from typing import Any

POLICY_VERSION = "2026-05-30.gateway-policy-v1"

INTERACTIVE_ENTRYPOINTS = {"web_chat", "websocket_chat", "local_cli"}
CONFIGURED_EXTERNAL_INBOUND = {"feishu_bot", "feishu_message"}
OUTBOUND_NOTIFICATION_CHANNELS = {"wxpusher", "feishu_push", "feishu_card"}
PUBLIC_OR_ANONYMOUS_INBOUND = {
    "anonymous_webhook",
    "bilibili_comment",
    "bilibili_dm",
    "github_issue",
    "public_comment",
    "seller_dm",
    "buyer_dm",
    "x_reply",
}
MESSAGE_ACTIONS = {"message", "chat", "ask", "reply"}
OUTBOUND_ACTIONS = {"send_notification", "push_card", "push_message", "daily_report"}
HIGH_RISK_ACTIONS = {
    "browser_control",
    "delete",
    "execute_script",
    "execute_tool",
    "login",
    "place_order",
    "private_message",
    "run_shell",
    "schedule_job",
    "send_whisper",
    "write_file",
}

_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHISPER_RE = re.compile(r"(?i)(^|\s)/w\s+[^\r\n]+")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_MARKET_PROFILE_RE = re.compile(r"(?i)(?:https?://)?(?:www\.)?warframe\.market/profile/[^\s,;]+")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b[a-z0-9_.-]*(?:password|token|secret|api[_-]?key|apikey|authorization|cookie|app[_-]?secret|chat[_-]?id)[a-z0-9_.-]*\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_PLAYER_HANDLE_RE = re.compile(r"(?i)\b(?:Seller|Buyer|Player)[A-Za-z0-9_\-]*\b")


def classify_gateway_request(
    channel: str,
    *,
    action: str = "message",
    authenticated: bool = False,
    payload_text: str = "",
) -> dict[str, Any]:
    safe_channel = _safe_identifier(channel) or "unknown"
    safe_action = _safe_identifier(action) or "unknown"

    if safe_action in HIGH_RISK_ACTIONS:
        decision = "blocked_sensitive_action"
        trust_boundary = _trust_boundary_for_channel(safe_channel, authenticated=authenticated)
    elif safe_channel in INTERACTIVE_ENTRYPOINTS and safe_action in MESSAGE_ACTIONS:
        decision = "allow_interactive_chat"
        trust_boundary = "local_user_interactive"
    elif safe_channel in CONFIGURED_EXTERNAL_INBOUND and safe_action in MESSAGE_ACTIONS:
        if authenticated:
            decision = "requires_existing_confirmation_flow"
            trust_boundary = "configured_external_inbound"
        else:
            decision = "blocked_untrusted_external_inbound"
            trust_boundary = "untrusted_external_inbound"
    elif safe_channel in OUTBOUND_NOTIFICATION_CHANNELS:
        if safe_action in OUTBOUND_ACTIONS and authenticated:
            decision = "allow_outbound_notification"
            trust_boundary = "configured_outbound_push"
        else:
            decision = "blocked_outbound_only_channel"
            trust_boundary = "configured_outbound_push"
    elif safe_channel in PUBLIC_OR_ANONYMOUS_INBOUND:
        decision = "blocked_public_or_anonymous_inbound"
        trust_boundary = "public_or_anonymous_inbound"
    else:
        decision = "blocked_unknown_gateway"
        trust_boundary = "unknown_gateway"

    blocked = decision.startswith("blocked")
    return {
        "channel": safe_channel,
        "action": safe_action,
        "decision": decision,
        "trust_boundary": trust_boundary,
        "blocked": blocked,
        "requires_human_confirmation": blocked or decision == "requires_existing_confirmation_flow",
        "reason": _decision_reason(decision),
        "payload_summary": _safe_text(payload_text, max_chars=120) if payload_text else "",
    }


def build_gateway_policy() -> dict[str, Any]:
    examples = [
        classify_gateway_request("web_chat", action="message"),
        classify_gateway_request(
            "feishu_bot",
            action="message",
            authenticated=True,
            payload_text="run /w SellerGateway hi token=secret-token https://warframe.market/profile/SellerGateway chat_id=oc_gateway",
        ),
        classify_gateway_request("wxpusher", action="send_notification", authenticated=True),
        classify_gateway_request("bilibili_comment", action="message"),
        classify_gateway_request("anonymous_webhook", action="message"),
        classify_gateway_request("web_chat", action="execute_tool", authenticated=True),
    ]
    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "explicit_gateway_only",
        "automatic_inbound_execution_enabled": False,
        "anonymous_inbound_enabled": False,
        "outbound_push_requires_configuration": True,
        "interactive_entrypoints": sorted(INTERACTIVE_ENTRYPOINTS),
        "configured_external_inbound": sorted(CONFIGURED_EXTERNAL_INBOUND),
        "outbound_notification_channels": sorted(OUTBOUND_NOTIFICATION_CHANNELS),
        "blocked_inbound_surfaces": sorted(PUBLIC_OR_ANONYMOUS_INBOUND),
        "decision_counts": _decision_counts(examples),
        "gateway_matrix": examples,
        "guardrails": [
            "Web chat, websocket chat, and local CLI are treated as interactive user input.",
            "Configured external inbound messages must reuse existing confirmation flows before project writes or side effects.",
            "WxPusher and Feishu push are outbound notification surfaces, not inbound command gateways.",
            "Public comments, anonymous webhooks, seller or buyer DMs, arbitrary tools, shell, browser control, and file writes are blocked.",
            "Gateway policy is a read-only runtime snapshot and does not create new platform connectors.",
        ],
    }


def _decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "allow_interactive_chat": 0,
        "requires_existing_confirmation_flow": 0,
        "allow_outbound_notification": 0,
        "blocked_public_or_anonymous_inbound": 0,
        "blocked_sensitive_action": 0,
        "blocked_outbound_only_channel": 0,
        "blocked_untrusted_external_inbound": 0,
        "blocked_unknown_gateway": 0,
    }
    for item in items:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _trust_boundary_for_channel(channel: str, *, authenticated: bool) -> str:
    if channel in INTERACTIVE_ENTRYPOINTS:
        return "local_user_interactive"
    if channel in CONFIGURED_EXTERNAL_INBOUND:
        return "configured_external_inbound" if authenticated else "untrusted_external_inbound"
    if channel in OUTBOUND_NOTIFICATION_CHANNELS:
        return "configured_outbound_push"
    if channel in PUBLIC_OR_ANONYMOUS_INBOUND:
        return "public_or_anonymous_inbound"
    return "unknown_gateway"


def _decision_reason(decision: str) -> str:
    reasons = {
        "allow_interactive_chat": "interactive_user_channel",
        "requires_existing_confirmation_flow": "external_inbound_must_use_existing_confirmation",
        "allow_outbound_notification": "configured_outbound_notification",
        "blocked_public_or_anonymous_inbound": "public_or_anonymous_inbound_not_trusted",
        "blocked_sensitive_action": "gateway_sensitive_action_blocked",
        "blocked_outbound_only_channel": "outbound_channel_not_an_input_gateway",
        "blocked_untrusted_external_inbound": "external_inbound_not_authenticated",
        "blocked_unknown_gateway": "unknown_gateway_blocked",
    }
    return reasons.get(decision, "unknown_gateway_decision")


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _IDENTIFIER_RE.sub("_", text).strip("_")[:80]


def _safe_text(value: Any, *, max_chars: int = 240) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    text = _WHISPER_RE.sub(" [REDACTED]", text)
    text = _MARKET_PROFILE_RE.sub("[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KV_RE.sub("[REDACTED]", text)
    text = _PLAYER_HANDLE_RE.sub("[REDACTED]", text)
    compact = " ".join(part.strip() for part in text.split() if part.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return compact
