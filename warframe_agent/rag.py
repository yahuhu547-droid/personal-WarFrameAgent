from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

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


class SemanticRAG:
    """基于 embedding 的语义搜索 RAG"""

    def __init__(self, cache_path: Path = config.EMBEDDING_CACHE_PATH):
        self.cache_path = cache_path
        self._item_ids: list[str] = []
        self._texts: list[str] = []
        self._embeddings: np.ndarray | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.cache_path.exists():
            data = np.load(str(self.cache_path), allow_pickle=True)
            self._item_ids = list(data["item_ids"])
            self._texts = list(data["texts"])
            self._embeddings = data["embeddings"]
        self._loaded = True

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._embeddings is not None and len(self._item_ids) > 0

    def search(self, query: str, limit: int = 5) -> list[RagResult]:
        self._ensure_loaded()
        if not self.is_available():
            return []
        query_vec = _embed_text(query)
        if query_vec is None:
            return []
        sims = _cosine_similarity(query_vec, self._embeddings)
        top_indices = np.argsort(sims)[::-1][:limit]
        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score <= 0:
                continue
            results.append(RagResult(
                item_id=self._item_ids[idx],
                text=self._texts[idx],
                score=int(score * 1000),
            ))
        return results


def _embed_text(text: str, model: str = config.EMBEDDING_MODEL) -> np.ndarray | None:
    try:
        import ollama
    except ImportError:
        return None
    try:
        response = ollama.embeddings(model=model, prompt=text)
        return np.array(response.get("embedding", []), dtype=np.float32)
    except Exception:
        return None


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return np.zeros(matrix.shape[0])
    matrix_norms = np.linalg.norm(matrix, axis=1)
    matrix_norms[matrix_norms == 0] = 1
    return (matrix @ query) / (matrix_norms * query_norm)


_semantic_rag: SemanticRAG | None = None


def _get_semantic_rag() -> SemanticRAG:
    global _semantic_rag
    if _semantic_rag is None:
        _semantic_rag = SemanticRAG()
    return _semantic_rag


def smart_search_rag(query: str, limit: int = 5) -> list[RagResult]:
    """先语义搜索，无结果时回退到 n-gram"""
    if config.EMBEDDING_ENABLED:
        semantic = _get_semantic_rag()
        if semantic.is_available():
            results = semantic.search(query, limit=limit)
            if results:
                return results
    return search_rag_items(query, limit=limit)
