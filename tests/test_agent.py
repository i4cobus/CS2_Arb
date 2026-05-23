from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent import classify_intent, run_agent


class AgentTests(unittest.TestCase):
    def test_classify_intent_examples(self) -> None:
        self.assertEqual(classify_intent("Which items are worth watching?"), "top_opportunities")
        self.assertEqual(classify_intent("Summarize data quality"), "data_quality")
        self.assertEqual(classify_intent("Show label distribution"), "label_distribution")
        self.assertEqual(classify_intent("Which items have strong liquidity?"), "liquidity")
        self.assertEqual(classify_intent("Explain recommendation summary"), "recommendation_summary")
        self.assertEqual(classify_intent("What is the weather?"), "unknown")

    @patch("app.agent.get_tool")
    def test_agent_output_contains_trace_fields(self, get_tool) -> None:
        class FakeTool:
            name = "top_opportunities"
            description = "fake"
            requires = ["data/recommendations.csv"]

            @staticmethod
            def handler(**kwargs):
                return {
                    "tool_name": "top_opportunities",
                    "evidence_files": ["data/recommendations.csv"],
                    "rows": [
                        {
                            "market_hash_name": "A",
                            "recommendation_label": "watchlist",
                            "opportunity_score": 0.5,
                            "instant_exit_margin_pct": 1.0,
                            "risk_score": 0.2,
                        }
                    ],
                    "row_count": 1,
                    "warnings": [],
                }

        get_tool.return_value = FakeTool()

        result = run_agent("Which items are worth watching?", limit=3)

        self.assertEqual(result["intent"], "top_opportunities")
        self.assertEqual(result["selected_tool"], "top_opportunities")
        self.assertEqual(result["trace"]["question"], "Which items are worth watching?")
        self.assertEqual(result["trace"]["rows_returned"], 1)
        self.assertIn("A", result["answer"])

    def test_unknown_intent_lists_supported_questions(self) -> None:
        result = run_agent("Tell me a joke")

        self.assertEqual(result["intent"], "unknown")
        self.assertIsNone(result["selected_tool"])
        self.assertEqual(result["rows"], [])
        self.assertIn("Supported questions", result["answer"])
        self.assertTrue(result["trace"]["warnings"])

    @patch("app.agent.get_tool")
    def test_no_hallucinated_answer_when_tool_returns_empty_rows(self, get_tool) -> None:
        class EmptyTool:
            name = "top_opportunities"
            description = "fake"
            requires = ["data/recommendations.csv"]

            @staticmethod
            def handler(**kwargs):
                return {
                    "tool_name": "top_opportunities",
                    "evidence_files": ["data/recommendations.csv"],
                    "rows": [],
                    "row_count": 0,
                    "warnings": [],
                }

        get_tool.return_value = EmptyTool()

        result = run_agent("Which items are worth watching?")

        self.assertEqual(result["rows"], [])
        self.assertIn("returned no rows", result["answer"])


if __name__ == "__main__":
    unittest.main()
