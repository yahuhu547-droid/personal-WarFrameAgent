from __future__ import annotations

from typing import Any

POLICY_VERSION = "2026-05-28.companion-experience-v1"

TRADE_ACTION_KEYWORDS = {
    "/w",
    "私聊",
    "密语",
    "发消息",
    "下单",
    "购买",
    "买下",
    "卖出",
    "交易",
    "联系卖家",
    "联系买家",
}
VOICE_RUNTIME_KEYWORDS = {
    "语音",
    "tts",
    "麦克风",
    "开麦",
    "录音",
    "听我说",
    "声音回复",
}
LIVE2D_KEYWORDS = {"live2d", "桌宠", "虚拟形象", "看板娘", "avatar"}
BACKGROUND_LISTENING_KEYWORDS = {"后台监听", "一直听", "常驻监听", "听我打"}
BACKGROUND_TASK_KEYWORDS = {
    "后台",
    "盯价",
    "提醒",
    "推送",
    "一边",
    "自动跟进",
}
TEXT_COMPANION_KEYWORDS = {
    "陪我",
    "陪着我",
    "聊聊",
    "陪伴",
    "安慰",
    "复盘一下心态",
}
GAMEPLAY_COMPANION_KEYWORDS = {
    "库娃",
    "库狛",
    "同伴配卡",
    "宠物",
    "动物伙伴",
    "sentinel",
    "哨兵",
}


def classify_companion_experience_request(message: str) -> dict[str, Any]:
    """Classify companion-style requests without echoing raw user text."""
    text = str(message or "")
    lowered = text.lower()

    if _contains(lowered, TRADE_ACTION_KEYWORDS):
        return _decision(
            category="trade_action",
            decision="blocked_sensitive_action",
            blocked=True,
            requires_human_confirmation=True,
            voice_runtime_required=False,
            reason="private_message_or_trade_action_blocked",
        )

    if _contains(lowered, BACKGROUND_LISTENING_KEYWORDS):
        return _decision(
            category="background_listening",
            decision="blocked_unavailable_runtime",
            blocked=True,
            requires_human_confirmation=True,
            voice_runtime_required=True,
            reason="background_listening_not_enabled",
        )

    if _contains(lowered, VOICE_RUNTIME_KEYWORDS):
        return _decision(
            category="voice_companion",
            decision="blocked_unavailable_runtime",
            blocked=True,
            requires_human_confirmation=True,
            voice_runtime_required=True,
            reason="voice_runtime_not_enabled",
        )

    if _contains(lowered, LIVE2D_KEYWORDS):
        return _decision(
            category="live2d_companion",
            decision="blocked_unavailable_runtime",
            blocked=True,
            requires_human_confirmation=True,
            voice_runtime_required=True,
            reason="live2d_runtime_not_enabled",
        )

    if _contains(lowered, BACKGROUND_TASK_KEYWORDS) and _contains(lowered, TEXT_COMPANION_KEYWORDS):
        return _decision(
            category="background_task_companion",
            decision="requires_existing_confirmation_flow",
            blocked=False,
            requires_human_confirmation=True,
            voice_runtime_required=False,
            reason="background_tasks_use_existing_confirmation",
        )

    if _contains(lowered, GAMEPLAY_COMPANION_KEYWORDS):
        return _decision(
            category="gameplay_companion",
            decision="route_general_chat",
            blocked=False,
            requires_human_confirmation=False,
            voice_runtime_required=False,
            reason="warframe_gameplay_companion_not_voice_ux",
        )

    if _contains(lowered, TEXT_COMPANION_KEYWORDS):
        return _decision(
            category="text_companion",
            decision="allow_text_only",
            blocked=False,
            requires_human_confirmation=False,
            voice_runtime_required=False,
            reason="text_only_companion_inside_chat",
        )

    return _decision(
        category="general_chat",
        decision="route_general_chat",
        blocked=False,
        requires_human_confirmation=False,
        voice_runtime_required=False,
        reason="not_companion_experience_request",
    )


def build_companion_experience_policy() -> dict[str, Any]:
    examples = [
        classify_companion_experience_request("陪我聊聊今天刷图怎么不累"),
        classify_companion_experience_request("给我语音回复"),
        classify_companion_experience_request("启动 Live2D 桌宠"),
        classify_companion_experience_request("一边陪我刷图一边后台盯价提醒"),
        classify_companion_experience_request("陪我直接私聊卖家并下单 /w SecretSeller hi token=LEAK"),
        classify_companion_experience_request("帮我推荐库娃同伴配卡和宠物获取路线"),
    ]
    return {
        "policy_version": POLICY_VERSION,
        "default_mode": "text_only",
        "voice_enabled": False,
        "live2d_enabled": False,
        "microphone_enabled": False,
        "recording_enabled": False,
        "background_listening_enabled": False,
        "platform_tokens_required": False,
        "allowed_modes": [
            "text_companion",
            "gameplay_companion",
            "confirmed_background_task_bridge",
        ],
        "disabled_surfaces": [
            "voice_runtime",
            "microphone",
            "recording",
            "live2d",
            "background_listening",
            "platform_tokens",
        ],
        "decision_counts": _decision_counts(examples),
        "experience_matrix": examples,
        "guardrails": [
            "Text-only companion replies stay inside the normal chat path.",
            "Voice, microphone, recording, Live2D, platform tokens, and background listening are not exposed.",
            "Background task companionship must use existing user confirmation and registered jobs.",
            "Private messages, trade order placement, and seller or buyer contact actions stay blocked.",
            "Warframe gameplay companions such as pets or sentinels are routed as ordinary game advice.",
        ],
    }


def _decision(
    *,
    category: str,
    decision: str,
    blocked: bool,
    requires_human_confirmation: bool,
    voice_runtime_required: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "decision": decision,
        "blocked": blocked,
        "requires_human_confirmation": requires_human_confirmation,
        "voice_runtime_required": voice_runtime_required,
        "reason": reason,
        "safe_tags": _safe_tags(category, decision, reason),
    }


def _safe_tags(category: str, decision: str, reason: str) -> list[str]:
    tags = [category, decision, reason]
    return sorted({tag for tag in tags if tag})


def _decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "allow_text_only": 0,
        "blocked_unavailable_runtime": 0,
        "requires_existing_confirmation_flow": 0,
        "blocked_sensitive_action": 0,
        "route_general_chat": 0,
    }
    for item in items:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _contains(text: str, keywords: set[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)
