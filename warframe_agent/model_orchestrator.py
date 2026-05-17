from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import config
from .llm import estimate_complexity

logger = logging.getLogger(__name__)

Message = Dict[str, str]
CloudCall = Callable[[List[Message], str], str]
LocalCall = Callable[[List[Message]], str]


@dataclass(frozen=True)
class ModelRequest:
    messages: list[dict[str, str]]
    task: str = "chat"
    model: str | None = None
    use_cache: bool = True


@dataclass(frozen=True)
class ModelResult:
    content: str
    provider: str
    model: str
    fallback_reason: str = ""
    cached: bool = False


class ModelOrchestrator:
    def __init__(
        self,
        *,
        cloud_call: CloudCall,
        local_call: LocalCall,
        scout_models: dict[str, str] | None = None,
        routing: str | None = None,
        cloud_api_key: str | None = None,
        cloud_model: str | None = None,
        local_model: str | None = None,
        complexity_threshold: int | None = None,
        cache_ttl: int = 300,
    ):
        self.cloud_call = cloud_call
        self.local_call = local_call
        self.scout_models = scout_models or dict(config.SCOUT_MODELS)
        self.routing = routing or config.MODEL_ROUTING
        self.cloud_api_key = config.CLOUD_API_KEY if cloud_api_key is None else cloud_api_key
        self.cloud_model = cloud_model or config.CLOUD_MODEL
        self.local_model = local_model or config.MODEL_NAME
        self.complexity_threshold = complexity_threshold or config.COMPLEXITY_THRESHOLD
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, ModelResult]] = {}

    def chat(self, request: ModelRequest) -> ModelResult:
        provider, model = self._select_route(request)
        cache_key = self._cache_key(request, provider, model)
        if request.use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                return cached

        if provider == "cloud":
            try:
                result = ModelResult(
                    content=self.cloud_call(request.messages, model),
                    provider="cloud",
                    model=model,
                )
                self._set_cached(cache_key, result, request.use_cache)
                return result
            except Exception as exc:
                logger.warning("云端模型 %s 调用失败，回退本地: %s", model, exc)
                local_result = ModelResult(
                    content=self.local_call(request.messages),
                    provider="local",
                    model=self.local_model,
                    fallback_reason=str(exc),
                )
                self._set_cached(cache_key, local_result, request.use_cache)
                return local_result

        result = ModelResult(
            content=self.local_call(request.messages),
            provider="local",
            model=self.local_model,
        )
        self._set_cached(cache_key, result, request.use_cache)
        return result

    def _select_route(self, request: ModelRequest) -> tuple[str, str]:
        if request.model == "local":
            return "local", self.local_model
        if request.model == "cloud":
            return "cloud", self.cloud_model
        if request.model:
            return "cloud", request.model

        task_model = self.scout_models.get(request.task)
        if task_model and self.cloud_api_key:
            return "cloud", task_model

        if self.routing == "local" or not self.cloud_api_key:
            return "local", self.local_model
        if self.routing == "cloud":
            return "cloud", self.cloud_model

        user_message = self._last_user_message(request.messages)
        if self._complexity_score(user_message) >= self.complexity_threshold:
            return "cloud", self.cloud_model
        return "local", self.local_model

    @staticmethod
    def _complexity_score(message: str) -> int:
        score = estimate_complexity(message)
        lowered = message.lower()
        english_analysis = ["analysis", "compare", "recommend", "strategy", "risk", "portfolio"]
        english_investment = ["roi", "profit", "budget", "flip", "investment"]
        if any(keyword in lowered for keyword in english_analysis):
            score += 2
        if any(keyword in lowered for keyword in english_investment):
            score += 2
        return score

    def _get_cached(self, key: str) -> ModelResult | None:
        cached = self._cache.get(key)
        if not cached:
            return None
        timestamp, result = cached
        if time.time() - timestamp > self.cache_ttl:
            del self._cache[key]
            return None
        return ModelResult(
            content=result.content,
            provider=result.provider,
            model=result.model,
            fallback_reason=result.fallback_reason,
            cached=True,
        )

    def _set_cached(self, key: str, result: ModelResult, enabled: bool) -> None:
        if enabled and self.cache_ttl > 0:
            self._cache[key] = (time.time(), result)

    @staticmethod
    def _last_user_message(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return ""

    @staticmethod
    def _cache_key(request: ModelRequest, provider: str, model: str) -> str:
        payload = {
            "provider": provider,
            "model": model,
            "task": request.task,
            "messages": request.messages,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
