import unittest

from warframe_agent.formatter import build_whisper, format_order_table, market_item_url, summarize_trade_order
from warframe_agent.market import best_buyers, best_sellers, build_buy_plan
from warframe_agent.trade_plan import build_trade_plan, trade_plan_safe_summary, trade_step_from_order


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

    def test_market_item_url_uses_item_id_slug(self):
        self.assertEqual(market_item_url("arcane_energize"), "https://warframe.market/items/arcane_energize")
        self.assertEqual(market_item_url("Mesa Prime Set"), "https://warframe.market/items/mesa_prime_set")
        self.assertEqual(market_item_url(""), "")

    def test_summarize_trade_order_contains_player_price_link_and_whisper(self):
        seller = best_sellers(SAMPLE_ORDERS, limit=1)[0]

        summary = summarize_trade_order(seller, "arcane_energize")

        self.assertEqual(summary["player"], "CheapSeller")
        self.assertEqual(summary["price"], 30)
        self.assertEqual(summary["quantity"], 1)
        self.assertEqual(summary["reputation"], 12)
        self.assertEqual(summary["market_url"], "https://warframe.market/items/arcane_energize")
        self.assertIn("/w CheapSeller", summary["whisper"])

    def test_build_buy_plan_aggregates_multiple_seller_quantities(self):
        orders = [
            {"order_type": "sell", "platinum": 4, "quantity": 10, "user": {"ingame_name": "CheapBulk", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 6, "quantity": 12, "user": {"ingame_name": "NextBulk", "status": "ingame", "reputation": 9}, "rank": 0},
            {"order_type": "sell", "platinum": 1, "quantity": 99, "user": {"ingame_name": "OfflineBulk", "status": "offline", "reputation": 99}, "rank": 0},
            {"order_type": "sell", "platinum": 2, "quantity": 21, "user": {"ingame_name": "WrongRank", "status": "ingame", "reputation": 99}, "rank": 5},
        ]

        plan = build_buy_plan(orders, needed=21, rank_filter=0)

        self.assertTrue(plan.fulfilled)
        self.assertEqual(plan.total_quantity, 21)
        self.assertEqual(plan.total_cost, 106)
        self.assertEqual([(entry.user_name, entry.platinum, entry.quantity, entry.subtotal) for entry in plan.entries], [
            ("CheapBulk", 4, 10, 40),
            ("NextBulk", 6, 11, 66),
        ])

    def test_build_buy_plan_uses_partial_quantity_from_next_price_tier(self):
        orders = [
            {"order_type": "sell", "platinum": 7, "quantity": 5, "user": {"ingame_name": "SevenPlat", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 9, "quantity": 22, "user": {"ingame_name": "NinePlat", "status": "ingame", "reputation": 9}, "rank": 0},
        ]

        plan = build_buy_plan(orders, needed=21, rank_filter=0)

        self.assertTrue(plan.fulfilled)
        self.assertEqual(plan.total_quantity, 21)
        self.assertEqual(plan.total_cost, 179)
        self.assertEqual([(entry.user_name, entry.platinum, entry.quantity, entry.subtotal) for entry in plan.entries], [
            ("SevenPlat", 7, 5, 35),
            ("NinePlat", 9, 16, 144),
        ])

    def test_build_buy_plan_reports_unfulfilled_when_quantity_insufficient(self):
        orders = [
            {"order_type": "sell", "platinum": 4, "quantity": 6, "user": {"ingame_name": "FewA", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 5, "quantity": 6, "user": {"ingame_name": "FewB", "status": "ingame", "reputation": 5}, "rank": 0},
        ]

        plan = build_buy_plan(orders, needed=21, rank_filter=0)

        self.assertFalse(plan.fulfilled)
        self.assertEqual(plan.total_quantity, 12)
        self.assertEqual(plan.total_cost, 54)

    def test_trade_step_includes_display_only_links_and_whisper(self):
        seller = best_sellers(SAMPLE_ORDERS, limit=1)[0]

        step = trade_step_from_order(
            side="buy",
            label="买入 R0",
            item_id="arcane_energize",
            order=seller,
            quantity=1,
            rank=0,
        )

        self.assertEqual(step["player"], "CheapSeller")
        self.assertEqual(step["quantity"], 1)
        self.assertEqual(step["unit_price"], 30)
        self.assertEqual(step["subtotal"], 30)
        self.assertEqual(step["market_url"], "https://warframe.market/items/arcane_energize")
        self.assertEqual(step["profile_url"], "https://warframe.market/profile/CheapSeller")
        self.assertIn("/w CheapSeller", step["whisper"])

    def test_trade_plan_safe_summary_excludes_display_only_fields(self):
        seller = best_sellers(SAMPLE_ORDERS, limit=1)[0]
        buyer = best_buyers(SAMPLE_ORDERS, limit=1)[0]
        buy_step = trade_step_from_order(side="buy", label="买入 R0", item_id="arcane_energize", order=seller, quantity=1, rank=0)
        sell_step = trade_step_from_order(side="sell", label="出售 R5", item_id="arcane_energize", order=buyer, quantity=1, rank=5)
        plan = build_trade_plan(
            source="arcane_flip",
            strategy="arcane_r0_to_r5",
            display_strategy="买 R0 合成 R5 后卖出",
            item_id="arcane_energize",
            display_name="Arcane Energize",
            required_quantity=21,
            buy_steps=[buy_step],
            sell_steps=[sell_step],
            total_cost=30,
            total_revenue=80,
            profit=50,
            roi_pct=166.7,
            volume_48h=100,
            risk_level="medium",
        )

        summary = trade_plan_safe_summary(plan)
        text = str(summary)

        self.assertEqual(summary["source"], "arcane_flip")
        self.assertEqual(summary["strategy"], "arcane_r0_to_r5")
        self.assertEqual(summary["profit"], 50)
        self.assertEqual(summary["required_quantity"], 21)
        for forbidden in ["CheapSeller", "HighBuyer", "/w", "profile", "warframe.market", "whisper", "market_url"]:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
