import json
import tempfile
import unittest
from pathlib import Path

from tools.build_item_data import build_item_records, build_lookup_entries, write_item_data


class ItemDataBuilderTests(unittest.TestCase):
    def test_build_item_records_reads_market_v2_i18n(self):
        payload = [
            {
                "slug": "arcane_energize",
                "tags": ["arcane"],
                "i18n": {
                    "zh-hans": {"name": "充沛赋能"},
                    "en": {"name": "Arcane Energize"},
                },
            }
        ]

        records = build_item_records(payload)

        self.assertEqual(records[0]["item_id"], "arcane_energize")
        self.assertEqual(records[0]["zh_name"], "充沛赋能")
        self.assertEqual(records[0]["en_name"], "Arcane Energize")
        self.assertIn("充沛", records[0]["search_terms"])

    def test_write_item_data_creates_full_json_aliases_and_rag_docs(self):
        payload = [
            {
                "slug": "arcane_energize",
                "tags": ["arcane"],
                "i18n": {"zh-hans": {"name": "充沛赋能"}, "en": {"name": "Arcane Energize"}},
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_item_data(payload, output_dir)

            items = json.loads((output_dir / "items_full.json").read_text(encoding="utf-8"))
            aliases = json.loads((output_dir / "generated_aliases.json").read_text(encoding="utf-8"))
            rag_lines = (output_dir / "rag_items.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(items[0]["item_id"], "arcane_energize")
        self.assertEqual(aliases["充沛"], "arcane_energize")
        self.assertIn("充沛赋能", rag_lines[0])

    def test_safe_prime_weapon_shorthand_alias_is_generated(self):
        payload = [
            {"slug": "strun_prime_set", "tags": ["prime", "weapon", "set", "primary"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 一套"}, "en": {"name": "Strun Prime Set"}}},
            {"slug": "strun_prime_blueprint", "tags": ["prime", "weapon", "blueprint", "primary"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 蓝图"}, "en": {"name": "Strun Prime Blueprint"}}},
            {"slug": "strun_prime_barrel", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 枪管"}, "en": {"name": "Strun Prime Barrel"}}},
        ]

        records = build_item_records(payload)
        aliases = build_lookup_entries(records)

        self.assertEqual(aliases["斯特朗p枪管"], "strun_prime_barrel")

    def test_safe_prime_weapon_shorthand_alias_generates_broader_variants(self):
        payload = [
            {"slug": "strun_prime_set", "tags": ["prime", "weapon", "set", "primary"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 一套"}, "en": {"name": "Strun Prime Set"}}},
            {"slug": "strun_prime_blueprint", "tags": ["prime", "weapon", "blueprint", "primary"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 蓝图"}, "en": {"name": "Strun Prime Blueprint"}}},
            {"slug": "strun_prime_receiver", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "斯特朗 Prime 枪机"}, "en": {"name": "Strun Prime Receiver"}}},
        ]

        records = build_item_records(payload)
        aliases = build_lookup_entries(records)

        self.assertEqual(aliases["斯特朗p整套"], "strun_prime_set")
        self.assertEqual(aliases["斯特朗p全套"], "strun_prime_set")
        self.assertEqual(aliases["斯特朗p总图"], "strun_prime_blueprint")
        self.assertEqual(aliases["斯特朗p机匣"], "strun_prime_receiver")


    def test_safe_prime_weapon_shorthand_alias_generates_symbol_free_variants(self):
        payload = [
            {"slug": "silva_and_aegis_prime_blueprint", "tags": ["prime", "weapon", "blueprint", "melee"], "i18n": {"zh-hans": {"name": "席瓦 & 神盾 Prime 蓝图"}, "en": {"name": "Silva & Aegis Prime Blueprint"}}},
        ]

        records = build_item_records(payload)
        aliases = build_lookup_entries(records)

        self.assertEqual(aliases["席瓦和神盾p蓝图"], "silva_and_aegis_prime_blueprint")
        self.assertEqual(aliases["席瓦神盾p蓝图"], "silva_and_aegis_prime_blueprint")



if __name__ == "__main__":
    unittest.main()
