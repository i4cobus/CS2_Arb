from __future__ import annotations

import unittest

from app.agent_trace import AgentTrace


class AgentTraceTests(unittest.TestCase):
    def test_trace_to_dict_steps_and_warnings(self) -> None:
        trace = AgentTrace(
            question="q",
            mode="deterministic",
            intent="top_opportunities",
            selected_tool="top_opportunities",
            tool_kind="offline_analytics",
        )

        trace.add_step("validate_tool_call")
        trace.add_warning("weak data")
        data = trace.to_dict()

        self.assertEqual(data["question"], "q")
        self.assertEqual(data["steps"][0]["name"], "validate_tool_call")
        self.assertEqual(data["steps"][0]["status"], "ok")
        self.assertEqual(data["warnings"], ["weak data"])


if __name__ == "__main__":
    unittest.main()
