import unittest

from warframe_agent.warframes import parse_warframe_query, price_warframe_query


ITEMS = [
    {"item_id": "strun_prime_set", "zh_name": "\u65af\u7279\u6717 Prime \u4e00\u5957", "en_name": "Strun Prime Set", "tags": ["set", "prime", "weapon", "primary"]},
    {"item_id": "strun_prime_blueprint", "zh_name": "\u65af\u7279\u6717 Prime \u84dd\u56fe", "en_name": "Strun Prime Blueprint", "tags": ["blueprint", "prime", "weapon", "primary"]},
    {"item_id": "strun_prime_barrel", "zh_name": "\u65af\u7279\u6717 Prime \u67aa\u7ba1", "en_name": "Strun Prime Barrel", "tags": ["component", "prime", "weapon"]},
    {"item_id": "strun_prime_receiver", "zh_name": "\u65af\u7279\u6717 Prime \u67aa\u673a", "en_name": "Strun Prime Receiver", "tags": ["component", "prime", "weapon"]},
    {"item_id": "strun_prime_stock", "zh_name": "\u65af\u7279\u6717 Prime \u67aa\u6258", "en_name": "Strun Prime Stock", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_set", "zh_name": "Lex Prime \u4e00\u5957", "en_name": "Lex Prime Set", "tags": ["set", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_blueprint", "zh_name": "Lex Prime \u84dd\u56fe", "en_name": "Lex Prime Blueprint", "tags": ["blueprint", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_barrel", "zh_name": "Lex Prime \u67aa\u7ba1", "en_name": "Lex Prime Barrel", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_receiver", "zh_name": "Lex Prime \u67aa\u673a", "en_name": "Lex Prime Receiver", "tags": ["component", "prime", "weapon"]},
]


def orders_for(item_id):
    prices = {
        "lex_prime_set": (70, 50),
        "lex_prime_blueprint": (15, 7),
        "lex_prime_barrel": (20, 10),
        "lex_prime_receiver": (18, 9),
    }
    sell_price, buy_price = prices[item_id]
    return [
        {"type": "sell", "platinum": sell_price, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
        {"type": "buy", "platinum": buy_price, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
    ]


class PrimeSetGeneralizationTests(unittest.TestCase):
    def test_parse_prime_weapon_set_query(self):
        query = parse_warframe_query("Lex Prime \u4e00\u5957\u591a\u5c11\u94b1", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "lex_prime")
        self.assertEqual(query.query_type, "set")
        self.assertEqual(query.item_ids()[0], "lex_prime_set")

    def test_parse_prime_weapon_part_query(self):
        query = parse_warframe_query("Lex Prime \u67aa\u7ba1\u591a\u5c11\u94b1", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "lex_prime")
        self.assertEqual(query.query_type, "part")
        self.assertEqual(query.part_key, "barrel")

    def test_parse_chinese_weapon_shorthand_query(self):
        query = parse_warframe_query("\u65af\u7279\u6717p\u67aa\u7ba1\u591a\u5c11\u94b1", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "strun_prime")
        self.assertEqual(query.part_key, "barrel")

    def test_parse_chinese_weapon_receiver_synonym_query(self):
        query = parse_warframe_query("\u65af\u7279\u6717p\u673a\u5323\u591a\u5c11\u94b1", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "strun_prime")
        self.assertEqual(query.part_key, "receiver")

    def test_parse_chinese_weapon_blueprint_synonym_query(self):
        query = parse_warframe_query("\u65af\u7279\u6717p\u603b\u56fe\u591a\u5c11\u94b1", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "strun_prime")
        self.assertEqual(query.part_key, "blueprint")

    def test_price_prime_weapon_set_compares_set_and_parts(self):
        text = price_warframe_query("Lex Prime \u4e00\u5957\u591a\u5c11\u94b1", ITEMS, orders_for)

        self.assertIn("Lex Prime / lex_prime_set", text)
        self.assertIn("\u6574\u5957\u76f4\u63a5\u4e70\u6700\u4f4e: 70p", text)
        self.assertIn("\u62c6\u4ef6\u4e70\u6700\u4f4e\u5408\u8ba1: 53p", text)
        self.assertIn("\u67aa\u7ba1", text)


if __name__ == "__main__":
    unittest.main()
