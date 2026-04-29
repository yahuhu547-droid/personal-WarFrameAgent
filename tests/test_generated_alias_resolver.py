import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.dictionary import ItemResolver


class GeneratedAliasResolverTests(unittest.TestCase):
    def test_resolver_uses_generated_aliases_after_manual_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alias_path = tmp_path / "manual.json"
            generated_alias_path = tmp_path / "generated.json"
            cache_path = tmp_path / "cache.json"
            alias_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
            generated_alias_path.write_text(json.dumps({"赤毒布拉玛": "kuva_bramma"}, ensure_ascii=False), encoding="utf-8")
            resolver = ItemResolver(alias_path=alias_path, generated_alias_path=generated_alias_path, cache_path=cache_path, export_dir=tmp_path)

            result = resolver.resolve("赤毒布拉玛")

        self.assertEqual(result.item_id, "kuva_bramma")
        self.assertEqual(result.source, "generated_alias")

    def test_resolver_supports_safe_weapon_shorthand_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            alias_path = tmp_path / "manual.json"
            generated_alias_path = tmp_path / "generated.json"
            cache_path = tmp_path / "cache.json"
            alias_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
            generated_alias_path.write_text(json.dumps({"斯特朗p枪管": "strun_prime_barrel"}, ensure_ascii=False), encoding="utf-8")
            resolver = ItemResolver(alias_path=alias_path, generated_alias_path=generated_alias_path, cache_path=cache_path, export_dir=tmp_path)

            result = resolver.resolve("斯特朗p枪管")

        self.assertEqual(result.item_id, "strun_prime_barrel")
        self.assertEqual(result.source, "generated_alias")


if __name__ == "__main__":
    unittest.main()
