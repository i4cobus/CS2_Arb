from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent import classify_intent, run_agent


class LiveAgentTests(unittest.TestCase):
    def test_live_intent_detection(self) -> None:
        self.assertEqual(classify_intent("compare live across markets"), "compare_live_item")
        self.assertEqual(classify_intent("fetch csfloat snapshot"), "fetch_csfloat_snapshot")
        self.assertEqual(classify_intent("search uu templates"), "search_uu_templates")
        self.assertEqual(classify_intent("refresh watchlist"), "refresh_watchlist")

    @patch("app.tools.compare_snapshots")
    @patch("app.tools.get_template_snapshot")
    @patch("app.tools.search_templates")
    @patch("app.tools.fetch_snapshot_by_params")
    def test_explicit_live_agent_route_has_live_trace(
        self,
        fetch_snapshot,
        search_templates,
        get_template_snapshot,
        compare_snapshots,
    ) -> None:
        fetch_snapshot.return_value = {
            "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
            "lowest_ask": 100.0,
            "highest_bid": 95.0,
        }
        search_templates.return_value = [
            {"template_id": "51135", "commodity_name_cn": "运动手套 | 夜行衣"}
        ]
        get_template_snapshot.return_value = {
            "source": "uu",
            "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
            "lowest_ask": 600.0,
            "highest_bid": 590.0,
            "currency": "CNY",
        }
        compare_snapshots.return_value = {
            "matched": True,
            "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
            "uu_lowest_ask_usd": 84.0,
            "cs_highest_bid_usd": 95.0,
            "spread_to_cs_bid_pct": 0.13,
        }

        result = run_agent(
            "compare live item",
            tool_name="compare_live_item",
            tool_args={
                "base_name": "Sport Gloves | Nocts",
                "wear": "ft",
                "category": "normal",
                "uu_keyword": "夜行衣",
            },
        )

        self.assertEqual(result["selected_tool"], "compare_live_item")
        self.assertEqual(result["trace"]["tool_kind"], "live_comparison")
        self.assertTrue(result["trace"]["live_api_used"])
        self.assertEqual(result["trace"]["steps"][-1]["name"], "compare_snapshots")
        self.assertIn("Live comparison", result["answer"])

    def test_readme_mentions_live_tool_using_agent(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Tool-Using Market Intelligence Agent", readme)
        self.assertIn("Live data tools", readme)
        self.assertIn("compare_live_item", readme)


if __name__ == "__main__":
    unittest.main()
