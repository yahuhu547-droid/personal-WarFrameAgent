from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

POLICY_VERSION = "2026-05-28.browser-gui-safety-v1"
ALLOW_READ_ONLY_ACTIONS = {"open_url", "read_page", "extract_text", "screenshot", "inspect_dom"}
CONFIRMATION_ACTIONS = {"click", "type_text", "submit_form", "download_file", "upload_file", "clipboard_write"}
BLOCKED_ACTIONS = {
    "login",
    "credential_entry",
    "payment",
    "delete",
    "send_whisper",
    "private_message",
    "place_order",
    "execute_script",
}
PUBLIC_READ_DOMAINS = {
    "warframe.market",
    "api.warframe.market",
    "wiki.warframe.com",
    "warframe.fandom.com",
    "www.bilibili.com",
    "bilibili.com",
    "b23.tv",
}
_ACTION_RE = re.compile(r"[^a-z0-9_]+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHISPER_RE = re.compile(r"(?i)/w\s+\S+[^\r\n]*")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_MARKET_PROFILE_RE = re.compile(r"https?://(?:www\.)?warframe\.market/profile/\S+")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(password|token|secret|api[_-]?key|apikey|authorization|cookie|app_secret|chat_id|localstorage|sessionstorage|profile_url)\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_PLAYER_HANDLE_RE = re.compile(r"(?i)\b(?:Seller|Buyer|Player)[A-Za-z0-9_\-]*\b")


def classify_browser_gui_action(action: str, *, target_url: str = "", text: str = "") -> dict[str, Any]:
    safe_action = _safe_identifier(action)
    target_scope = _target_scope(target_url)
    if target_scope == "private_network" or safe_action in BLOCKED_ACTIONS:
        decision = "blocked"
    elif safe_action in CONFIRMATION_ACTIONS:
        decision = "requires_human_confirmation"
    elif safe_action in ALLOW_READ_ONLY_ACTIONS and target_scope.startswith("public_"):
        decision = "allow_read_only"
    else:
        decision = "requires_human_confirmation"
    return {
        "action": safe_action or "unknown",
        "decision": decision,
        "target_scope": target_scope,
        "requires_human_confirmation": decision != "allow_read_only",
        "blocked": decision == "blocked",
        "reason": _decision_reason(decision, safe_action, target_scope),
        "text_summary": _safe_text(text, max_chars=120) if text else "",
    }


def build_browser_gui_safety_policy() -> dict[str, Any]:
    examples = [
        classify_browser_gui_action("read_page", target_url="https://warframe.market/items/arcane_energize"),
        classify_browser_gui_action("type_text", target_url="https://wiki.warframe.com"),
        classify_browser_gui_action("login", target_url="https://warframe.market"),
        classify_browser_gui_action("read_page", target_url="http://127.0.0.1:3000/admin?token=secret-token"),
    ]
    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "read_only",
        "automation_enabled": False,
        "human_takeover_required": True,
        "allowed_scopes": sorted(PUBLIC_READ_DOMAINS),
        "decision_counts": _decision_counts(examples),
        "action_matrix": examples,
        "guardrails": [
            "Browser and GUI automation is not exposed as an Agent executor.",
            "Read-only public pages may be inspected only after explicit implementation.",
            "Clicks, typing, downloads, uploads, and clipboard writes require human confirmation.",
            "Login, payment, deletion, private messages, trade order placement, credentials, arbitrary scripts, and private-network targets are blocked.",
        ],
    }


def _target_scope(target_url: str) -> str:
    if not target_url:
        return "none"
    parsed = urlparse(str(target_url))
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme in {"file", "ftp"}:
        return "private_network"
    if _is_private_host(host):
        return "private_network"
    if host in {"warframe.market", "api.warframe.market"}:
        return "public_warframe_market"
    if host in {"wiki.warframe.com", "warframe.fandom.com"}:
        return "public_warframe_wiki"
    if host in {"www.bilibili.com", "bilibili.com", "b23.tv"}:
        return "public_bilibili"
    if host in PUBLIC_READ_DOMAINS:
        return "public_allowed"
    return "external_unknown"


def _is_private_host(host: str) -> bool:
    if not host:
        return False
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _decision_reason(decision: str, action: str, target_scope: str) -> str:
    if decision == "allow_read_only":
        return "public_read_only_observation"
    if decision == "blocked" and target_scope == "private_network":
        return "private_network_target_blocked"
    if decision == "blocked":
        return "sensitive_or_trade_action_blocked"
    if action in CONFIRMATION_ACTIONS:
        return "ui_mutation_requires_human_confirmation"
    return "unknown_or_unclassified_action_requires_confirmation"


def _decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"allow_read_only": 0, "requires_human_confirmation": 0, "blocked": 0}
    for item in items:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ACTION_RE.sub("_", text).strip("_")[:80]


def _safe_text(value: Any, *, max_chars: int = 240) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    text = _WHISPER_RE.sub("[REDACTED]", text)
    text = _MARKET_PROFILE_RE.sub("[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KV_RE.sub("[REDACTED]", text)
    text = _PLAYER_HANDLE_RE.sub("[REDACTED]", text)
    compact = " ".join(part.strip() for part in text.split() if part.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return compact
