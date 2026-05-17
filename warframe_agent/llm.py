from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from . import config
from .dictionary import normalize_market_id

logger = logging.getLogger(__name__)

# ── 云端模型 ──────────────────────────────────────────────────────────────


def _ensure_cloud_api_key() -> None:
    if not config.CLOUD_API_KEY:
        raise RuntimeError("CLOUD_API_KEY is not configured")


def _cloud_chat_sync(messages: list[dict[str, str]], model: str = config.CLOUD_MODEL) -> str:
    """同步调用云端 OpenAI 兼容 API"""
    _ensure_cloud_api_key()
    import urllib.request
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": config.CLOUD_MAX_TOKENS,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{config.CLOUD_API_BASE}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.CLOUD_API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


async def _cloud_chat_stream(messages: list[dict[str, str]], model: str = config.CLOUD_MODEL) -> AsyncIterator[str]:
    """流式调用云端 OpenAI 兼容 API（使用 httpx 异步客户端）"""
    _ensure_cloud_api_key()
    import httpx
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": config.CLOUD_MAX_TOKENS,
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{config.CLOUD_API_BASE}/chat/completions", json=payload, headers=headers) as resp:
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# ── 复杂度评估 ────────────────────────────────────────────────────────────


def estimate_complexity(message: str) -> int:
    """评估查询复杂度，返回分数。越高越复杂，需要云端模型。

    分数规则：
    - 长度 > 50 字符: +1
    - 包含对比/分析关键词: +2
    - 包含多个物品名: +1 per extra item
    - 包含投资/策略关键词: +2
    """
    score = 0
    if len(message) > 50:
        score += 1

    analysis_keywords = ["对比", "比较", "哪个更", "划算", "推荐", "分析", "投资", "策略", "收益", "风险", "组合"]
    if any(kw in message for kw in analysis_keywords):
        score += 2

    invest_keywords = ["预算", "ROI", "翻转", "利润", "低买高卖", "赚钱"]
    if any(kw in message for kw in invest_keywords):
        score += 2

    # 多物品检测（"和"、"、"、"vs"分隔）
    import re
    separators = re.compile(r"[和、,，vs]+")
    parts = separators.split(message)
    item_count = sum(1 for p in parts if len(p.strip()) > 1 and len(p.strip()) < 30)
    if item_count > 2:
        score += item_count - 2

    return score


def should_use_cloud(message: str) -> bool:
    """根据配置和复杂度决定是否使用云端模型。"""
    if not config.CLOUD_API_KEY:
        return False
    if config.MODEL_ROUTING == "cloud":
        return True
    if config.MODEL_ROUTING == "local":
        return False
    # auto 模式
    return estimate_complexity(message) >= config.COMPLEXITY_THRESHOLD


# ── 统一接口 ──────────────────────────────────────────────────────────────


def chat_with_model(messages: list[dict[str, str]], model: str | None = None) -> str:
    """统一 LLM 调用接口。model="local" | "cloud" | None(自动)"""
    from .model_orchestrator import ModelOrchestrator, ModelRequest

    orchestrator = ModelOrchestrator(
        cloud_call=lambda payload, selected_model: _cloud_chat_sync(payload, model=selected_model),
        local_call=chat_with_ollama,
    )
    return orchestrator.chat(ModelRequest(messages=messages, model=model, task="chat", use_cache=False)).content


async def stream_chat_model(messages: list[dict[str, str]], model: str | None = None) -> AsyncIterator[str]:
    """统一流式 LLM 调用接口。"""
    if model == "cloud":
        async for chunk in _cloud_chat_stream(messages):
            yield chunk
        return
    if model == "local":
        async for chunk in stream_chat_ollama(messages):
            yield chunk
        return
    # 自动路由
    user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_msg = m["content"]
            break
    if should_use_cloud(user_msg):
        try:
            async for chunk in _cloud_chat_stream(messages):
                yield chunk
            return
        except Exception as exc:
            logger.warning("云端流式调用失败，回退本地: %s", exc)
    async for chunk in stream_chat_ollama(messages):
        yield chunk


# ── Ollama 本地 ───────────────────────────────────────────────────────────


def resolve_with_ollama(name: str, model: str = config.MODEL_NAME) -> str | None:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc

    prompt = (
        "你是 Warframe 和 warframe.market 物品 URL 专家。"
        "把用户输入的中文或英文物品名转换成 warframe.market item url_name。"
        "只输出小写英文 url_name，不要解释，不要 Markdown。"
        "例如：充沛赋能 -> arcane_energize；川流不息 Prime -> primed_flow。"
        f"用户输入：{name}"
    )
    response = ollama.generate(model=model, prompt=prompt)
    text = response.get("response", "").strip().splitlines()[0]
    item_id = normalize_market_id(text)
    return item_id or None


def chat_with_ollama(messages: list[dict[str, str]], model: str = config.MODEL_NAME) -> str:
    """使用 Ollama chat API 进行多轮对话"""
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc

    response = ollama.chat(model=model, messages=messages)
    return response.get("message", {}).get("content", "")


async def stream_ollama_chat(prompt: str, model: str = config.MODEL_NAME):
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc

    client = ollama.AsyncClient()
    async for chunk in await client.generate(model=model, prompt=prompt, stream=True):
        text = chunk.get("response")
        if text:
            yield text


async def stream_chat_ollama(messages: list[dict[str, str]], model: str = config.MODEL_NAME):
    """使用 Ollama chat API 流式输出，逐 token yield"""
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc

    client = ollama.AsyncClient()
    async for chunk in await client.chat(model=model, messages=messages, stream=True):
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield content
