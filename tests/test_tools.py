from __future__ import annotations

import unittest
from unittest.mock import patch

from app.tools import TOOLS, data_quality_tool, get_tool, top_opportunities_tool


class ToolsTests(unittest.TestCase):
    def test_tool_registry_contains_required_tools(self) -> None:
        for name in (
            "top_opportunities",
            "data_quality",
            "label_distribution",
            "liquidity",
            "recommendation_summary",
            "compare_item",
        ):
            self.assertIn(name, TOOLS)
            self.assertEqual(get_tool(name).name, name)  # type: ignore[union-attr]

    @patch("app.tools.run_query_file")
    @patch("app.tools.os.path.exists", return_value=True)
    def test_top_opportunities_tool_returns_rows(self, _exists, run_query_file) -> None:
        run_query_file.return_value = [{"market_hash_name": "A"}]

        output = top_opportunities_tool(limit=5)

        self.assertEqual(output["tool_name"], "top_opportunities")
        self.assertEqual(output["row_count"], 1)
        self.assertEqual(output["rows"], [{"market_hash_name": "A"}])
        self.assertEqual(output["warnings"], [])

    @patch("app.tools.os.path.exists", return_value=False)
    def test_tool_handles_missing_csv_without_crashing(self, _exists) -> None:
        output = data_quality_tool()

        self.assertEqual(output["rows"], [])
        self.assertEqual(output["row_count"], 0)
        self.assertTrue(output["warnings"])


if __name__ == "__main__":
    unittest.main()
