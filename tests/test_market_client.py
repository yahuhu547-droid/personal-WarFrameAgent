import unittest
from unittest.mock import patch

from warframe_agent.market import fetch_orders


class MarketClientTests(unittest.TestCase):
    def test_fetch_orders_sends_market_headers(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"payload": {"orders": []}}

        with patch("warframe_agent.market.requests.get", return_value=Response()) as get:
            fetch_orders("arcane_energize")

        url = get.call_args[0][0]
        headers = get.call_args[1]["headers"]
        self.assertEqual(url, "https://api.warframe.market/v2/orders/item/arcane_energize")
        self.assertEqual(headers["Platform"], "pc")
        self.assertEqual(headers["Language"], "en")
        self.assertEqual(headers["Crossplay"], "true")
        self.assertIn("User-Agent", headers)

    def test_fetch_orders_reads_v2_data_wrapper(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"data": [{"type": "sell", "platinum": 10}]}

        with patch("warframe_agent.market.requests.get", return_value=Response()):
            orders = fetch_orders("arcane_energize")

        self.assertEqual(orders, [{"type": "sell", "platinum": 10}])


if __name__ == "__main__":
    unittest.main()
