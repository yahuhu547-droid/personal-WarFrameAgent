import tempfile
import unittest
from pathlib import Path

from warframe_agent.rag import search_rag_items


class RagSearchTests(unittest.TestCase):
    def test_search_rag_items_returns_matching_item_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag_items.jsonl"
            path.write_text('{"id":"arcane_energize","text":"充沛赋能 / Arcane Energize / arcane_energize"}\n', encoding="utf-8")

            results = search_rag_items("充沛现在价格怎么样", path=path, limit=3)

        self.assertEqual(results[0].item_id, "arcane_energize")
        self.assertGreater(results[0].score, 0)


if __name__ == "__main__":
    unittest.main()
