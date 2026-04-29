import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.dictionary import ItemResolver


class ItemResolverTests(unittest.TestCase):
    def test_resolves_manual_chinese_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = Path(tmp) / "aliases.json"
            alias_path.write_text(json.dumps({"充沛赋能": "arcane_energize"}, ensure_ascii=False), encoding="utf-8")
            resolver = ItemResolver(alias_path=alias_path, export_dir=Path(tmp), fallback=None)

            result = resolver.resolve("充沛赋能")

            self.assertEqual(result.item_id, "arcane_energize")
            self.assertEqual(result.source, "alias")

    def test_normalizes_english_name_when_no_alias_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = Path(tmp) / "aliases.json"
            alias_path.write_text("{}", encoding="utf-8")
            resolver = ItemResolver(alias_path=alias_path, export_dir=Path(tmp), fallback=None)

            result = resolver.resolve("Arcane Energize")

            self.assertEqual(result.item_id, "arcane_energize")
            self.assertEqual(result.source, "normalized")

    def test_uses_fallback_for_unknown_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = Path(tmp) / "aliases.json"
            alias_path.write_text("{}", encoding="utf-8")
            resolver = ItemResolver(
                alias_path=alias_path,
                export_dir=Path(tmp),
                fallback=lambda name: "primed_flow",
            )

            result = resolver.resolve("黄金川流不息")

            self.assertEqual(result.item_id, "primed_flow")
            self.assertEqual(result.source, "llm")


if __name__ == "__main__":
    unittest.main()
