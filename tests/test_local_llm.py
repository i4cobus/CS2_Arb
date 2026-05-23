from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import httpx

from app.local_llm import LocalLLMError, ollama_generate, parse_tool_call_with_llm
from app.tool_schema import validate_tool_call


class LocalLLMTests(unittest.TestCase):
    @patch("app.local_llm.ollama_generate")
    def test_parse_tool_call_with_llm_valid_json(self, ollama_generate_mock) -> None:
        ollama_generate_mock.return_value = (
            '{"tool":"compare_live_item","args":{"base_name":"Sport Gloves | Nocts",'
            '"wear":"ft","category":"normal","uu_keyword":"夜行衣","uu_index":0}}'
        )

        tool_call = parse_tool_call_with_llm("Compare Sport Gloves Nocts Field-Tested")

        self.assertEqual(tool_call["tool"], "compare_live_item")
        self.assertTrue(validate_tool_call(tool_call)[0])

    @patch("app.local_llm.ollama_generate", return_value="not json")
    def test_parse_tool_call_with_llm_invalid_json(self, _ollama_generate_mock) -> None:
        with self.assertRaises(LocalLLMError):
            parse_tool_call_with_llm("bad")

    @patch("app.local_llm.httpx.post")
    def test_ollama_generate_returns_plain_text(self, post) -> None:
        response = Mock()
        response.json.return_value = {"response": "hello"}
        response.raise_for_status.return_value = None
        post.return_value = response

        self.assertEqual(ollama_generate("prompt"), "hello")

    @patch("app.local_llm.httpx.post")
    def test_ollama_generate_handles_connection_error(self, post) -> None:
        post.side_effect = httpx.ConnectError("failed")

        with self.assertRaises(LocalLLMError):
            ollama_generate("prompt")


if __name__ == "__main__":
    unittest.main()
