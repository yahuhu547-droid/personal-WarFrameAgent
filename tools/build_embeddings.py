"""离线预计算 RAG 条目的 embedding 向量。

用法:
    python -m tools.build_embeddings

输出: data/rag_embeddings.npz (包含 item_ids, texts, embeddings)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from warframe_agent import config


def main() -> None:
    rag_path = config.RAG_ITEMS_PATH
    if not rag_path.exists():
        print(f"RAG items file not found: {rag_path}")
        sys.exit(1)

    item_ids: list[str] = []
    texts: list[str] = []
    with rag_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            item_ids.append(str(item.get("id", "")))
            texts.append(str(item.get("text", "")))

    print(f"Loaded {len(item_ids)} items from {rag_path}")

    try:
        import ollama
    except ImportError:
        print("Error: ollama package not installed. Run: pip install ollama")
        sys.exit(1)

    model = config.EMBEDDING_MODEL
    print(f"Using embedding model: {model}")

    embeddings: list[list[float]] = []
    for i, text in enumerate(texts):
        try:
            response = ollama.embeddings(model=model, prompt=text)
            vec = response.get("embedding", [])
            embeddings.append(vec)
        except Exception as exc:
            print(f"  Error embedding item {i} ({item_ids[i]}): {exc}")
            embeddings.append([0.0] * 768)  # fallback zero vector
        if (i + 1) % 100 == 0:
            print(f"  Embedded {i + 1}/{len(texts)} items...")

    embeddings_array = np.array(embeddings, dtype=np.float32)
    out_path = config.EMBEDDING_CACHE_PATH
    np.savez(str(out_path), item_ids=np.array(item_ids), texts=np.array(texts), embeddings=embeddings_array)
    print(f"Saved embeddings to {out_path} ({embeddings_array.shape})")


if __name__ == "__main__":
    main()
