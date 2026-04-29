import unittest

from tools.build_item_data import build_item_records, build_lookup_entries


class AliasConflictTests(unittest.TestCase):
    def test_ambiguous_prime_weapon_shorthand_is_skipped(self):
        payload = [
            {"slug": "alpha_prime_barrel", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "阿尔法 Prime 枪管"}, "en": {"name": "Alpha Prime Barrel"}}},
            {"slug": "alpha_alt_prime_barrel", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "阿尔法 Prime 枪管"}, "en": {"name": "Alpha Alt Prime Barrel"}}},
        ]

        records = build_item_records(payload)
        aliases = build_lookup_entries(records)

        self.assertNotIn("阿尔法p枪管", aliases)

    def test_ambiguous_prime_weapon_synonym_alias_is_skipped(self):
        payload = [
            {"slug": "alpha_prime_receiver", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "阿尔法 Prime 枪机"}, "en": {"name": "Alpha Prime Receiver"}}},
            {"slug": "alpha_alt_prime_receiver", "tags": ["prime", "weapon", "component"], "i18n": {"zh-hans": {"name": "阿尔法 Prime 枪机"}, "en": {"name": "Alpha Alt Prime Receiver"}}},
        ]

        records = build_item_records(payload)
        aliases = build_lookup_entries(records)

        self.assertNotIn("阿尔法p机匣", aliases)


if __name__ == "__main__":
    unittest.main()
