from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import config
from .dictionary import normalize_lookup_key


@dataclass(frozen=True)
class RagResult:
    item_id: str
    text: str
    score: int


def search_rag_items(query: str, path: Path = config.RAG_ITEMS_PATH, limit: int = 5) -> list[RagResult]:
    if not path.exists():
        return []
    query_key = normalize_lookup_key(query)
    if not query_key:
        return []
    results = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            if not line.strip():
                continue
            item = json.loads(line)
            text = str(item.get("text", ""))
            score = _score(query_key, normalize_lookup_key(text))
            if score > 0:
                results.append(RagResult(item_id=str(item.get("id", "")), text=text, score=score))
    return sorted(results, key=lambda result: (-result.score, result.item_id))[:limit]


def _score(query_key: str, text_key: str) -> int:
    if not text_key:
        return 0
    score = 0
    if text_key in query_key or query_key in text_key:
        score += min(len(query_key), len(text_key)) * 4
    for length in range(min(6, len(query_key)), 1, -1):
        for start in range(0, len(query_key) - length + 1):
            piece = query_key[start : start + length]
            if piece in text_key:
                score += length
                break
    return score
