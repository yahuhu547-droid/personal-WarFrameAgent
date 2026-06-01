from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from warframe_agent import config
from warframe_agent.llm import _cloud_chat_sync, chat_with_ollama
from warframe_agent.model_orchestrator import ModelOrchestrator, ModelRequest

DEFAULT_REVIEW_SUMMARY = Path("Extra Resource/exports/bilibili_metadata/bilibili_recommendation_review_summary.json")
DEFAULT_OUTPUT = Path("Extra Resource/exports/bilibili_metadata/bilibili_recommendation_model_suggestions.json")
ALLOWED_CATEGORIES = {"primary", "secondary", "melee"}
FORBIDDEN_KEYS = {"mods", "mod", "arcanes", "arcane", "incarnon", "build", "school", "warframe", "riven", "damage", "playstyle"}
REVIEW_TASKS = ("bilibili_title_review", "bilibili_category_review", "bilibili_alias_review")


@dataclass(frozen=True)
class ModelVote:
    reviewer: str
    provider: str = ""
    model: str = ""
    category: str = ""
    weapons: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reject_reason: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "provider": self.provider,
            "model": self.model,
            "category": self.category,
            "weapons": self.weapons,
            "aliases": self.aliases,
            "confidence": self.confidence,
            "reject_reason": self.reject_reason,
            "error": self.error,
        }


def parse_model_vote(text: str, *, reviewer: str, expected_bvid: str) -> ModelVote:
    try:
        payload = _parse_json_object(text)
    except ValueError as exc:
        return ModelVote(reviewer=reviewer, error=str(exc))
    forbidden = sorted(key for key in payload if str(key).lower() in FORBIDDEN_KEYS)
    if forbidden:
        return ModelVote(reviewer=reviewer, error=f"forbidden_fields:{','.join(forbidden)}")
    if str(payload.get("bvid") or "") != expected_bvid:
        return ModelVote(reviewer=reviewer, error="bvid_mismatch")
    category = _clean_category(payload.get("category"))
    if category and category not in ALLOWED_CATEGORIES:
        return ModelVote(reviewer=reviewer, error="invalid_category")
    weapons = _clean_string_list(payload.get("weapons"))[:3]
    aliases = _clean_aliases(payload.get("aliases"), weapons)
    confidence = _clean_confidence(payload.get("confidence"))
    reject_reason = str(payload.get("reject_reason") or "")[:200]
    return ModelVote(
        reviewer=reviewer,
        category=category,
        weapons=weapons,
        aliases=aliases,
        confidence=confidence,
        reject_reason=reject_reason,
    )


def build_consensus(candidate: dict[str, Any], votes: list[ModelVote]) -> dict[str, Any]:
    collection_category = _clean_category(candidate.get("collection_category") or candidate.get("category"))
    title_subject = str(candidate.get("title_subject") or "").strip()
    accepted = [vote for vote in votes if not vote.error and vote.weapons and vote.confidence >= 0.6]
    buckets: dict[str, list[ModelVote]] = {}
    for vote in accepted:
        key = _normalize_token(vote.weapons[0])
        if key:
            buckets.setdefault(key, []).append(vote)
    best_votes: list[ModelVote] = []
    for bucket_votes in buckets.values():
        if len(bucket_votes) > len(best_votes):
            best_votes = bucket_votes
    consensus_status = "needs_human_review"
    consensus_reason = "model_consensus_not_reached"
    weapons: list[str] = []
    aliases: list[str] = []
    category = collection_category
    if len(best_votes) >= 2:
        category = collection_category or best_votes[0].category
        weapons = best_votes[0].weapons
        aliases = _merge_aliases(best_votes, weapons)
        if not _weapon_matches_title_subject(weapons[0], title_subject):
            consensus_status = "needs_human_review"
            consensus_reason = "weapon_not_derivable_from_title_subject"
        else:
            consensus_status = "suggested_approved"
            consensus_reason = "two_of_three_model_consensus"
    elif any(vote.reject_reason for vote in accepted):
        consensus_status = "rejected"
        consensus_reason = "model_rejected_candidate"
    if not weapons:
        weapons = _clean_string_list(candidate.get("weapons"))[:3]
    if not aliases and weapons:
        aliases = _default_aliases(weapons)
    return {
        "bvid": candidate.get("bvid", ""),
        "title": candidate.get("title", ""),
        "url": candidate.get("url", ""),
        "title_subject": title_subject,
        "category": category,
        "collection_category": collection_category,
        "weapons": weapons,
        "aliases": aliases,
        "source": candidate.get("source", ""),
        "consensus_status": consensus_status,
        "consensus_reason": consensus_reason,
        "approved": False,
        "model_votes": [vote.to_dict() for vote in votes],
    }


def review_candidates(
    review_summary: dict[str, Any],
    *,
    orchestrator_factory: Callable[[], ModelOrchestrator] | None = None,
    limit: int | None = None,
    offset: int = 0,
    delay_seconds: float = 0.0,
) -> dict[str, Any]:
    factory = orchestrator_factory or _build_orchestrator
    suggestions = []
    processed = 0
    skipped = 0
    for category, entries in (review_summary.get("groups") or {}).items():
        for candidate in entries:
            if skipped < offset:
                skipped += 1
                continue
            if limit is not None and processed >= limit:
                break
            votes = _review_candidate(candidate, category=category, orchestrator=factory())
            suggestions.append(build_consensus(candidate, votes))
            processed += 1
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        if limit is not None and processed >= limit:
            break
    return {
        "generated_from": "bilibili_recommendation_review_summary.json",
        "offset": offset,
        "limit": limit,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "notes": [
            "Model suggestions are not trusted until a human sets approved:true.",
            "Only video metadata may be applied; MOD/arcanes/incarnon/build details are forbidden.",
        ],
    }


def _review_candidate(candidate: dict[str, Any], *, category: str, orchestrator: ModelOrchestrator) -> list[ModelVote]:
    votes = []
    for task in REVIEW_TASKS:
        prompt = _build_prompt(candidate, task=task, category=category)
        try:
            result = orchestrator.chat(ModelRequest(messages=[{"role": "user", "content": prompt}], task=task, use_cache=True))
            vote = parse_model_vote(result.content, reviewer=task, expected_bvid=str(candidate.get("bvid") or ""))
            votes.append(ModelVote(
                reviewer=task,
                provider=result.provider,
                model=result.model,
                category=vote.category,
                weapons=vote.weapons,
                aliases=vote.aliases,
                confidence=vote.confidence,
                reject_reason=vote.reject_reason,
                error=vote.error,
            ))
        except Exception as exc:
            votes.append(ModelVote(reviewer=task, error=str(exc)))
    return votes


def _build_prompt(candidate: dict[str, Any], *, task: str, category: str) -> str:
    safe_candidate = {
        "bvid": candidate.get("bvid", ""),
        "title": candidate.get("title", ""),
        "title_subject": candidate.get("title_subject", ""),
        "url": candidate.get("url", ""),
        "collection_category": candidate.get("collection_category") or category,
        "source": candidate.get("source", ""),
        "review_reason": candidate.get("review_reason", ""),
    }
    return (
        "你只负责确认 B 站 Warframe 配卡视频的安全元数据。"
        "禁止输出 MOD、赋能、灵化、流派、枪架子、配卡细节、玩法建议。"
        "只返回一个 JSON 对象，不要 Markdown，不要解释。"
        "字段必须是 bvid, category, weapons, aliases, confidence, reject_reason。"
        "category 直接照抄 collection_category，不要重新判断合集分类。"
        "weapons 只能填写从标题前缀可直接看出的武器名。"
        f"\n任务角色: {task}\n候选: {json.dumps(safe_candidate, ensure_ascii=False)}"
    )


def _build_orchestrator() -> ModelOrchestrator:
    endpoint = os.getenv("BILIBILI_REVIEW_ENDPOINT", "").strip()
    cloud_call = _endpoint_cloud_call(endpoint) if endpoint else (lambda messages, model: _cloud_chat_sync(messages, model=model))
    return ModelOrchestrator(
        cloud_call=cloud_call,
        local_call=chat_with_ollama,
        scout_models=_review_scout_models(),
        routing="cloud",
        cloud_api_key=os.getenv("CLOUD_API_KEY", config.CLOUD_API_KEY),
    )


def _endpoint_cloud_call(endpoint: str) -> Callable[[list[dict[str, str]], str], str]:
    def call(messages: list[dict[str, str]], model: str) -> str:
        return _call_model_endpoint(endpoint, messages=messages, model=model)
    return call


def _call_model_endpoint(endpoint: str, *, messages: list[dict[str, str]], model: str) -> str:
    key = os.getenv("CLOUD_API_KEY", config.CLOUD_API_KEY)
    if not key:
        raise RuntimeError("CLOUD_API_KEY is not configured")
    if endpoint.rstrip("/").endswith("/messages"):
        payload = {"model": model, "max_tokens": config.CLOUD_MAX_TOKENS, "messages": messages}
        headers = {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        payload = {"model": model, "messages": messages, "max_tokens": config.CLOUD_MAX_TOKENS, "stream": False}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    if isinstance(data.get("content"), list):
        return "".join(str(part.get("text", "")) for part in data["content"] if isinstance(part, dict))
    raise ValueError("unsupported_model_response")


def _review_scout_models() -> dict[str, str]:
    model = os.getenv("BILIBILI_REVIEW_MODEL", config.CLOUD_MODEL)
    defaults = {task: model for task in REVIEW_TASKS}
    defaults.update({key: value for key, value in config.SCOUT_MODELS.items() if key not in defaults})
    return defaults


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise ValueError("response_not_json_object")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("response_not_json_object")
    return payload


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _clean_aliases(value: Any, weapons: list[str]) -> list[str]:
    aliases = []
    for alias in _clean_string_list(value):
        lowered = alias.lower()
        if any(token in lowered for token in ("mod", "赋能", "灵化", "流派", "枪架子", "紫卡")):
            continue
        if any(_normalize_token(weapon) and _normalize_token(weapon) in _normalize_token(alias) for weapon in weapons):
            aliases.append(alias)
    return aliases[:20]


def _merge_aliases(votes: list[ModelVote], weapons: list[str]) -> list[str]:
    aliases = []
    for vote in votes:
        for alias in vote.aliases:
            if alias not in aliases:
                aliases.append(alias)
    for alias in _default_aliases(weapons):
        if alias not in aliases:
            aliases.append(alias)
    return aliases[:20]


def _default_aliases(weapons: list[str]) -> list[str]:
    aliases = []
    for weapon in weapons[:3]:
        aliases.extend([f"{weapon}配卡", f"{weapon}攻略"])
        if re.fullmatch(r"[A-Za-z0-9 ]+", weapon):
            aliases.append(f"{weapon} build".lower())
    return aliases[:20]


def _clean_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))


def _clean_category(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "primary": "primary", "主手": "primary", "主武器": "primary",
        "secondary": "secondary", "副手": "secondary", "副武器": "secondary",
        "melee": "melee", "近战": "melee",
    }
    return aliases.get(normalized, "")


def _weapon_matches_title_subject(weapon: str, title_subject: str) -> bool:
    weapon_key = _normalize_token(weapon)
    subject_key = _normalize_token(title_subject)
    return bool(weapon_key and subject_key and (weapon_key == subject_key or weapon_key in subject_key or subject_key in weapon_key))


def _normalize_token(value: str) -> str:
    return re.sub(r"[^0-9a-z一-鿿]+", "", str(value).lower())


def merge_suggestions(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for suggestion in existing.get("suggestions") or []:
        if isinstance(suggestion, dict) and suggestion.get("bvid"):
            merged[str(suggestion["bvid"])] = suggestion
    for suggestion in new.get("suggestions") or []:
        if isinstance(suggestion, dict) and suggestion.get("bvid"):
            old = merged.get(str(suggestion["bvid"]))
            if old and old.get("approved") is True:
                suggestion = dict(suggestion, approved=True)
            merged[str(suggestion["bvid"])] = suggestion
    return {
        "generated_from": new.get("generated_from") or existing.get("generated_from", "bilibili_recommendation_review_summary.json"),
        "suggestion_count": len(merged),
        "suggestions": list(merged.values()),
        "notes": new.get("notes") or existing.get("notes", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate model-assisted Bilibili recommendation review suggestions.")
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--endpoint", default="", help="Full model endpoint, e.g. http://localhost:8080/v1/chat/completions or /v1/messages.")
    parser.add_argument("--merge-existing", action="store_true", help="Merge this batch into the existing output file by BVID.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.endpoint:
        os.environ["BILIBILI_REVIEW_ENDPOINT"] = args.endpoint
    review_summary = json.loads(args.review_summary.read_text(encoding="utf-8"))
    suggestions = review_candidates(review_summary, limit=args.limit, offset=args.offset, delay_seconds=args.delay_seconds)
    if args.merge_existing and args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        suggestions = merge_suggestions(existing, suggestions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "suggestion_count": suggestions["suggestion_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
