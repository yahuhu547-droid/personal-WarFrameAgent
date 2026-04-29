import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.names import display_item_name, english_name, preferred_chinese_name


class NamesTests(unittest.TestCase):
    def write_aliases(self, aliases):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "aliases.json"
        path.write_text(json.dumps(aliases, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(tmp.cleanup)
        return path

    def test_display_item_name_uses_preferred_chinese_alias(self):
        alias_path = self.write_aliases({"充沛": "arcane_energize", "充沛赋能": "arcane_energize"})

        self.assertEqual(
            display_item_name("arcane_energize", alias_path=alias_path),
            "充沛赋能 / Arcane Energize / arcane_energize",
        )

    def test_unknown_item_still_has_english_and_id(self):
        alias_path = self.write_aliases({})

        self.assertEqual(preferred_chinese_name("new_prime_part", alias_path=alias_path), None)
        self.assertEqual(english_name("new_prime_part"), "New Prime Part")
        self.assertEqual(
            display_item_name("new_prime_part", alias_path=alias_path),
            "New Prime Part / new_prime_part",
        )


if __name__ == "__main__":
    unittest.main()
