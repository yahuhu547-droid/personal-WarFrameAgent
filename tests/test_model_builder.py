import json
import tempfile
import unittest
from pathlib import Path

from tools.build_ollama_model import build_modelfile


class ModelBuilderTests(unittest.TestCase):
    def test_build_modelfile_embeds_local_trading_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alias_path = tmp_path / "aliases.json"
            watchlist_path = tmp_path / "watchlist.json"
            alias_path.write_text(json.dumps({"充沛赋能": "arcane_energize"}, ensure_ascii=False), encoding="utf-8")
            watchlist_path.write_text(json.dumps({"arcanes": ["arcane_energize"]}, ensure_ascii=False), encoding="utf-8")

            text = build_modelfile(alias_path=alias_path, watchlist_path=watchlist_path, model_name="qwen2.5:1.5b")

        self.assertIn("FROM qwen2.5:1.5b", text)
        self.assertIn("PARAMETER temperature 0.1", text)
        self.assertIn("资深星际战甲玩家", text)
        self.assertIn("中文名 / English Name / market_id", text)
        self.assertIn("充沛赋能 -> arcane_energize", text)
        self.assertIn("绝不能把充沛赋能回答成 condition_overload", text)
        self.assertIn("充沛赋能 / Arcane Energize / arcane_energize", text)
        self.assertIn("arcane_energize", text)


if __name__ == "__main__":
    unittest.main()
