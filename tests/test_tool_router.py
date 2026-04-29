import unittest

from warframe_agent.tool_router import build_router_prompt, parse_tool_call, ToolCall


class ToolRouterTests(unittest.TestCase):
    def test_build_router_prompt_contains_tools(self):
        prompt = build_router_prompt("充沛多少钱")
        self.assertIn("query_price", prompt)
        self.assertIn("query_set", prompt)
        self.assertIn("scan_favorites", prompt)
        self.assertIn("充沛多少钱", prompt)

    def test_parse_valid_tool_call(self):
        response = '{"tool": "query_price", "args": {"item_name": "充沛"}}'
        result = parse_tool_call(response)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "query_price")
        self.assertEqual(result.arguments["item_name"], "充沛")

    def test_parse_tool_call_with_markdown_wrapper(self):
        response = '```json\n{"tool": "scan_favorites", "args": {}}\n```'
        result = parse_tool_call(response)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "scan_favorites")

    def test_parse_tool_call_with_think_tags(self):
        response = '<think>用户想查价格</think>\n{"tool": "query_price", "args": {"item_name": "arcane_energize"}}'
        result = parse_tool_call(response)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "query_price")

    def test_parse_invalid_tool_name_returns_none(self):
        response = '{"tool": "nonexistent_tool", "args": {}}'
        result = parse_tool_call(response)
        self.assertIsNone(result)

    def test_parse_garbage_returns_none(self):
        result = parse_tool_call("I don't know what to do")
        self.assertIsNone(result)

    def test_router_fallback_in_chat_agent(self):
        from warframe_agent.chat import ChatAgent

        class FakeResolver:
            aliases = {}
            generated_aliases = {}
            def resolve(self, name):
                if name in ("充沛", "arcane_energize"):
                    class R:
                        item_id = "arcane_energize"
                    return R()
                raise LookupError(name)

        orders = [
            {"order_type": "sell", "platinum": 45, "quantity": 1, "user": {"ingame_name": "S1", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 38, "quantity": 1, "user": {"ingame_name": "B1", "status": "ingame", "reputation": 3}},
        ]

        def fake_router(prompt):
            return '{"tool": "query_price", "args": {"item_name": "充沛"}}'

        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: orders,
            model_call=lambda prompt: "unused",
            router_call=fake_router,
            rag_search=lambda msg: [],
        )
        answer = agent.answer("那个回蓝的赋能现在行情怎样")
        self.assertIn("45p", answer)

    def test_router_general_chat_falls_through(self):
        from warframe_agent.chat import ChatAgent

        class FakeResolver:
            aliases = {}
            generated_aliases = {}
            def resolve(self, name):
                raise LookupError(name)

        def fake_router(prompt):
            return '{"tool": "general_chat", "args": {"message": "你好"}}'

        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: [],
            model_call=lambda prompt: "unused",
            router_call=fake_router,
        )
        answer = agent.answer("你好啊")
        self.assertIn("没有找到", answer)


if __name__ == "__main__":
    unittest.main()
