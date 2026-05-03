import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from warframe_agent.rag import search_rag_items, SemanticRAG, smart_search_rag, _cosine_similarity


class RagSearchTests(unittest.TestCase):
    def test_search_rag_items_returns_matching_item_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag_items.jsonl"
            path.write_text('{"id":"arcane_energize","text":"充沛赋能 / Arcane Energize / arcane_energize"}\n', encoding="utf-8")

            results = search_rag_items("充沛现在价格怎么样", path=path, limit=3)

        self.assertEqual(results[0].item_id, "arcane_energize")
        self.assertGreater(results[0].score, 0)


class SemanticRAGTests(unittest.TestCase):
    def test_not_available_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            rag = SemanticRAG(cache_path=Path(tmp) / "nonexistent.npz")
            self.assertFalse(rag.is_available())

    def test_search_returns_empty_when_not_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            rag = SemanticRAG(cache_path=Path(tmp) / "nonexistent.npz")
            results = rag.search("test query")
            self.assertEqual(results, [])

    def test_search_with_mock_embeddings(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "embeddings.npz"
            item_ids = np.array(["arcane_energize", "primed_flow", "arcane_grace"])
            texts = np.array(["充沛赋能", "川流不息Prime", "优雅赋能"])
            # Create distinct vectors so cosine similarity works
            embeddings = np.array([
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.5, 0.0, 0.5],
            ], dtype=np.float32)
            np.savez(str(cache_path), item_ids=item_ids, texts=texts, embeddings=embeddings)

            rag = SemanticRAG(cache_path=cache_path)
            self.assertTrue(rag.is_available())

            # Mock _embed_text to return a known vector
            with patch("warframe_agent.rag._embed_text", return_value=np.array([1.0, 0.0, 0.0], dtype=np.float32)):
                results = rag.search("test", limit=2)

            self.assertGreater(len(results), 0)
            self.assertEqual(results[0].item_id, "arcane_energize")


class CosineSimilarityTests(unittest.TestCase):
    def test_cosine_similarity_identical_vectors(self):
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        sims = _cosine_similarity(vec, matrix)
        self.assertAlmostEqual(sims[0], 1.0)
        self.assertAlmostEqual(sims[1], 0.0)

    def test_cosine_similarity_orthogonal_vectors(self):
        vec = np.array([1.0, 0.0], dtype=np.float32)
        matrix = np.array([[0.0, 1.0]], dtype=np.float32)
        sims = _cosine_similarity(vec, matrix)
        self.assertAlmostEqual(sims[0], 0.0)

    def test_cosine_similarity_zero_query(self):
        vec = np.array([0.0, 0.0], dtype=np.float32)
        matrix = np.array([[1.0, 0.0]], dtype=np.float32)
        sims = _cosine_similarity(vec, matrix)
        self.assertAlmostEqual(sims[0], 0.0)


if __name__ == "__main__":
    unittest.main()
