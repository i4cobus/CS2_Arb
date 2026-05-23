from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent import classify_intent, run_agent
from app.tool_schema import validate_tool_call


class AgentEvaluationTests(unittest.TestCase):
    def test_rule_based_routing_expected_mappings(self) -> None:
        cases = [
            ("Which items are worth watching?", "top_opportunities"),
            ("Summarize data quality", "data_quality"),
            ("Show label distribution", "label_distribution"),
            ("Which items have strong liquidity?", "liquidity"),
            ("Refresh the watchlist", "refresh_watchlist"),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question), expected)

    @patch("app.agent.get_tool")
    def test_explicit_tool_execution_contains_trace_result_answer(self, get_tool) -> None:
        class FakeTool:
            name = "compare_live_item"
            kind = "live_comparison"
            description = "fake"
            requires = []

            @staticmethod
            def handler(**kwargs):
                return {
                    "tool": "compare_live_item",
                    "status": "ok",
                    "steps": [
                        {"name": "fetch_csfloat_snapshot", "status": "ok"},
                        {"name": "search_uu_templates", "status": "ok"},
                        {"name": "compare_snapshots", "status": "ok"},
                    ],
                    "comparison": {
                        "matched": True,
                        "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
                        "uu_lowest_ask_usd": 84.0,
                        "cs_highest_bid_usd": 95.0,
                        "spread_to_cs_bid_pct": 0.13,
                    },
                }

        get_tool.return_value = FakeTool()

        result = run_agent(
            question="compare",
            tool_name="compare_live_item",
            tool_args={
                "base_name": "Sport Gloves | Nocts",
                "wear": "ft",
                "category": "normal",
                "uu_keyword": "夜行衣",
                "uu_index": 0,
            },
        )

        self.assertEqual(result["selected_tool"], "compare_live_item")
        self.assertTrue(result["trace"]["live_api_used"])
        self.assertEqual(result["trace"]["steps"][-1]["name"], "compare_snapshots")
        self.assertIn("answer", result)
        self.assertIn("result", result)
        self.assertIn("trace", result)

    @patch("app.agent.get_tool")
    @patch("app.local_llm.ollama_generate")
    def test_local_llm_parser_valid_json_executes_tool(self, ollama_generate, get_tool) -> None:
        ollama_generate.return_value = (
            '{"tool":"compare_live_item","args":{"base_name":"Sport Gloves | Nocts",'
            '"wear":"ft","category":"normal","uu_keyword":"夜行衣","uu_index":0}}'
        )

        class FakeTool:
            name = "compare_live_item"
            kind = "live_comparison"
            description = "fake"
            requires = []

            @staticmethod
            def handler(**kwargs):
                return {
                    "tool": "compare_live_item",
                    "status": "error",
                    "error": "No UU candidates found",
                    "steps": [{"name": "search_uu_templates", "status": "ok"}],
                }

        get_tool.return_value = FakeTool()

        result = run_agent("Compare Sport Gloves Nocts Field-Tested with UU keyword 夜行衣", use_llm=True)

        self.assertEqual(result["tool_call"]["tool"], "compare_live_item")
        self.assertEqual(result["selected_tool"], "compare_live_item")
        self.assertTrue(result["trace"]["live_api_used"])

    @patch("app.agent.get_tool")
    @patch("app.local_llm.ollama_generate", return_value="not json")
    def test_local_llm_parser_invalid_json_does_not_execute(self, _ollama_generate, get_tool) -> None:
        result = run_agent("Compare Sport Gloves Nocts Field-Tested with UU keyword 夜行衣", use_llm=True)

        get_tool.assert_not_called()
        self.assertIsNone(result["selected_tool"])
        self.assertIn("failed", result["answer"].lower())
        self.assertEqual(result["trace"]["steps"][0]["status"], "error")

    def test_tool_schema_validation(self) -> None:
        invalid_missing = {"tool": "compare_live_item", "args": {"base_name": "A"}}
        invalid_wear = {
            "tool": "compare_live_item",
            "args": {
                "base_name": "A",
                "wear": "bad",
                "category": "normal",
                "uu_keyword": "x",
                "uu_index": 0,
            },
        }
        invalid_category = {
            "tool": "compare_live_item",
            "args": {
                "base_name": "A",
                "wear": "ft",
                "category": "bad",
                "uu_keyword": "x",
                "uu_index": 0,
            },
        }
        unknown = {"tool": "make_trade", "args": {}}

        self.assertFalse(validate_tool_call(invalid_missing)[0])
        self.assertFalse(validate_tool_call(invalid_wear)[0])
        self.assertFalse(validate_tool_call(invalid_category)[0])
        self.assertFalse(validate_tool_call(unknown)[0])


if __name__ == "__main__":
    unittest.main()
