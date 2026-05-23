from __future__ import annotations

import unittest
from unittest.mock import patch

from app.tools import (
    TOOLS,
    compare_live_item_tool,
    fetch_csfloat_snapshot_tool,
    list_tools,
)


class LiveToolsTests(unittest.TestCase):
    def test_live_tools_are_registered(self) -> None:
        for name in (
            "fetch_csfloat_snapshot",
            "search_uu_templates",
            "fetch_uu_snapshot",
            "compare_live_item",
            "refresh_watchlist",
        ):
            self.assertIn(name, TOOLS)

        metadata = {tool["name"]: tool for tool in list_tools()}
        self.assertEqual(metadata["compare_live_item"]["kind"], "live_comparison")
        self.assertIn("CSFLOAT_API_KEY", metadata["fetch_csfloat_snapshot"]["requires"])

    @patch("app.tools.fetch_snapshot_by_params")
    def test_fetch_csfloat_snapshot_tool_normalises_required_fields(self, fetch_snapshot) -> None:
        fetch_snapshot.return_value = {
            "source": "strict(name+cat+wear)",
            "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
            "lowest_ask": 100.0,
        }

        output = fetch_csfloat_snapshot_tool(
            base_name="Sport Gloves | Nocts",
            wear="ft",
            category="normal",
        )

        fetch_snapshot.assert_called_once_with(
            base_name="Sport Gloves | Nocts",
            wear_key="ft",
            category_key="normal",
            debug=False,
        )
        self.assertEqual(output["source"], "csfloat")
        self.assertEqual(output["currency"], "USD")
        self.assertIn("highest_bid_qty", output)

    @patch("app.tools.compare_snapshots")
    @patch("app.tools.get_template_snapshot")
    @patch("app.tools.search_templates")
    @patch("app.tools.fetch_snapshot_by_params")
    def test_compare_live_item_tool_calls_components(
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
        compare_snapshots.return_value = {"matched": True, "market_hash_name": "Sport Gloves | Nocts (Field-Tested)"}

        output = compare_live_item_tool(
            base_name="Sport Gloves | Nocts",
            wear="ft",
            category="normal",
            uu_keyword="夜行衣",
        )

        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["selected_uu_candidate"]["template_id"], "51135")
        self.assertEqual([step["name"] for step in output["steps"]], [
            "fetch_csfloat_snapshot",
            "search_uu_templates",
            "choose_uu_candidate",
            "fetch_uu_snapshot",
            "compare_snapshots",
        ])
        fetch_snapshot.assert_called_once()
        search_templates.assert_called_once_with(keyword="夜行衣", debug=False)
        get_template_snapshot.assert_called_once_with(template_id="51135", debug=False)
        compare_snapshots.assert_called_once()

    @patch("app.tools.search_templates", return_value=[])
    @patch("app.tools.fetch_snapshot_by_params")
    def test_compare_live_item_tool_returns_error_when_no_uu_candidates(
        self,
        fetch_snapshot,
        _search_templates,
    ) -> None:
        fetch_snapshot.return_value = {
            "market_hash_name": "Sport Gloves | Nocts (Field-Tested)",
            "lowest_ask": 100.0,
        }

        output = compare_live_item_tool(
            base_name="Sport Gloves | Nocts",
            wear="ft",
            category="normal",
            uu_keyword="missing",
        )

        self.assertEqual(output["status"], "error")
        self.assertEqual(output["error"], "No UU candidates found")
        self.assertEqual(output["steps"][-1]["name"], "search_uu_templates")


if __name__ == "__main__":
    unittest.main()
