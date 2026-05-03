import unittest
from unittest.mock import MagicMock

from warframe_agent.tool_router import (
    ToolCall,
    build_router_prompt,
    parse_tool_call,
    react_loop,
    _extract_tool_calls,
)


class ParseToolCallTests(unittest.TestCase):
    def test_parse_valid_json(self):
        raw = '{"tool": "query_price", "args": {"item_name": "充沛"}}'
        tc = parse_tool_call(raw)
        self.assertIsNotNone(tc)
        self.assertEqual(tc.name, "query_price")
        self.assertEqual(tc.arguments["item_name"], "充沛")

    def test_parse_json_with_markdown(self):
        raw = '```json\n{"tool": "scan_favorites", "args": {}}\n```'
        tc = parse_tool_call(raw)
        self.assertIsNotNone(tc)
        self.assertEqual(tc.name, "scan_favorites")

    def test_parse_invalid_tool_name(self):
        raw = '{"tool": "nonexistent", "args": {}}'
        tc = parse_tool_call(raw)
        self.assertIsNone(tc)

    def test_parse_malformed_json(self):
        tc = parse_tool_call("not json at all")
        self.assertIsNone(tc)

    def test_parse_with_think_tags(self):
        raw = '<think>thinking...</think>\n{"tool": "query_price", "args": {"item_name": "test"}}'
        tc = parse_tool_call(raw)
        self.assertIsNotNone(tc)
        self.assertEqual(tc.name, "query_price")


class ExtractToolCallsTests(unittest.TestCase):
    def test_extract_single_call(self):
        response = '{"tool": "query_price", "args": {"item_name": "充沛"}}'
        calls = _extract_tool_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "query_price")

    def test_extract_array_of_calls(self):
        response = '[{"tool": "query_price", "args": {"item_name": "充沛"}}, {"tool": "price_trend", "args": {"item_name": "充沛"}}]'
        calls = _extract_tool_calls(response)
        self.assertEqual(len(calls), 2)

    def test_extract_no_calls(self):
        calls = _extract_tool_calls("这是普通回答，没有工具调用")
        self.assertEqual(len(calls), 0)


class ReactLoopTests(unittest.TestCase):
    def test_react_returns_direct_answer(self):
        def mock_model_call(messages):
            return "这是直接回答"

        result = react_loop(
            message="你好",
            tool_executor=lambda tc: None,
            model_call=mock_model_call,
        )
        self.assertEqual(result, "这是直接回答")

    def test_react_executes_tool_then_answers(self):
        call_count = [0]

        def mock_model_call(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                return '{"tool": "query_price", "args": {"item_name": "充沛"}}'
            return "充沛当前价格45p"

        def mock_executor(tc):
            return "充沛: 最低卖价 45p"

        result = react_loop(
            message="充沛多少钱",
            tool_executor=mock_executor,
            model_call=mock_model_call,
            max_iterations=3,
        )
        self.assertEqual(result, "充沛当前价格45p")

    def test_react_returns_none_on_failure(self):
        def mock_model_call(messages):
            raise RuntimeError("model failed")

        result = react_loop(
            message="test",
            tool_executor=lambda tc: None,
            model_call=mock_model_call,
        )
        self.assertIsNone(result)

    def test_react_respects_max_iterations(self):
        iteration_count = [0]

        def mock_model_call(messages):
            iteration_count[0] += 1
            return '{"tool": "query_price", "args": {"item_name": "test"}}'

        def mock_executor(tc):
            return "result"

        result = react_loop(
            message="test",
            tool_executor=mock_executor,
            model_call=mock_model_call,
            max_iterations=2,
        )
        # Should stop after 2 iterations and return None (no final answer)
        self.assertIsNone(result)
        self.assertEqual(iteration_count[0], 2)


class BuildRouterPromptTests(unittest.TestCase):
    def test_prompt_contains_tools(self):
        prompt = build_router_prompt("充沛多少钱")
        self.assertIn("query_price", prompt)
        self.assertIn("充沛多少钱", prompt)


if __name__ == "__main__":
    unittest.main()
