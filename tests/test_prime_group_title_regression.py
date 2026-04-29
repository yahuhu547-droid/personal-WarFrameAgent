import unittest

from warframe_agent.warframes import build_prime_groups, price_warframe_query


ITEMS_UNORDERED = [
    {"item_id": "lex_prime_barrel", "zh_name": "Lex Prime 枪管", "en_name": "Lex Prime Barrel", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_receiver", "zh_name": "Lex Prime 枪机", "en_name": "Lex Prime Receiver", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_set", "zh_name": "Lex Prime 一套", "en_name": "Lex Prime Set", "tags": ["set", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_blueprint", "zh_name": "Lex Prime 蓝图", "en_name": "Lex Prime Blueprint", "tags": ["blueprint", "prime", "weapon", "secondary"]},
]


def orders_for(item_id):
    return [
        {"type": "sell", "platinum": 5, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
        {"type": "buy", "platinum": 3, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
    ]


class PrimeGroupTitleRegressionTests(unittest.TestCase):
    def test_group_prefers_set_title_over_component_title(self):
        groups = build_prime_groups(ITEMS_UNORDERED)

        self.assertEqual(groups['lex_prime'].en_title, 'Lex Prime')
        self.assertEqual(groups['lex_prime'].zh_title, 'Lex Prime')

    def test_price_output_uses_base_title_not_component_title(self):
        text = price_warframe_query('Lex Prime 一套多少钱', ITEMS_UNORDERED, orders_for)

        self.assertIn('Lex Prime / Lex Prime / lex_prime_set', text)
        self.assertNotIn('Lex Prime Barrel / Lex Prime Barrel / lex_prime_set', text)


if __name__ == '__main__':
    unittest.main()
