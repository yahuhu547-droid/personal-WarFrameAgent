import unittest

from warframe_agent.formatter import build_whisper, format_order_table
from warframe_agent.market import best_buyers, best_sellers


SAMPLE_ORDERS = [
    {
        "order_type": "sell",
        "platinum": 30,
        "quantity": 1,
        "user": {"ingame_name": "CheapSeller", "status": "ingame", "reputation": 12},
    },
    {
        "order_type": "sell",
        "platinum": 45,
        "quantity": 2,
        "user": {"ingame_name": "ExpensiveSeller", "status": "ingame", "reputation": 4},
    },
    {
        "order_type": "sell",
        "platinum": 20,
        "quantity": 1,
        "user": {"ingame_name": "OfflineSeller", "status": "offline", "reputation": 99},
    },
    {
        "order_type": "buy",
        "platinum": 18,
        "quantity": 1,
        "user": {"ingame_name": "LowBuyer", "status": "ingame", "reputation": 3},
    },
    {
        "order_type": "buy",
        "platinum": 25,
        "quantity": 3,
        "user": {"ingame_name": "HighBuyer", "status": "ingame", "reputation": 8},
    },
]


class MarketFormatterTests(unittest.TestCase):
    def test_best_sellers_are_ingame_and_cheapest_first(self):
        sellers = best_sellers(SAMPLE_ORDERS, limit=5)

        self.assertEqual([order.user_name for order in sellers], ["CheapSeller", "ExpensiveSeller"])
        self.assertEqual([order.platinum for order in sellers], [30, 45])

    def test_best_sellers_support_v2_order_shape(self):
        orders = [
            {
                "type": "sell",
                "platinum": 12,
                "quantity": 1,
                "user": {"ingameName": "V2Seller", "status": "ingame", "reputation": 4},
            }
        ]

        sellers = best_sellers(orders, limit=5)

        self.assertEqual(sellers[0].user_name, "V2Seller")
        self.assertEqual(sellers[0].platinum, 12)

    def test_best_buyers_are_ingame_and_highest_first(self):
        buyers = best_buyers(SAMPLE_ORDERS, limit=5)

        self.assertEqual([order.user_name for order in buyers], ["HighBuyer", "LowBuyer"])
        self.assertEqual([order.platinum for order in buyers], [25, 18])

    def test_whisper_commands_match_market_button_intent(self):
        seller_command = build_whisper("CheapSeller", "arcane_energize", 30, "sell")
        buyer_command = build_whisper("HighBuyer", "arcane_energize", 25, "buy")

        self.assertEqual(
            seller_command,
            '/w CheapSeller Hi! I want to buy: "Arcane Energize" for 30 platinum. (warframe.market)',
        )
        self.assertEqual(
            buyer_command,
            '/w HighBuyer Hi! I want to sell: "Arcane Energize" for 25 platinum. (warframe.market)',
        )

    def test_order_table_includes_commands(self):
        sellers = best_sellers(SAMPLE_ORDERS, limit=1)

        table = format_order_table("推荐卖家", sellers, "arcane_energize")

        self.assertIn("推荐卖家", table)
        self.assertIn("CheapSeller", table)
        self.assertIn("/w CheapSeller", table)


if __name__ == "__main__":
    unittest.main()
