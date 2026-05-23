from __future__ import annotations

import json
from typing import Any

import httpx


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:3b"


class LocalLLMError(RuntimeError):
    pass


def ollama_generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        response = httpx.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise LocalLLMError("Ollama is not running at http://localhost:11434.") from exc
    except httpx.TimeoutException as exc:
        raise LocalLLMError("Ollama request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        text = exc.response.text[:300] if exc.response is not None else ""
        raise LocalLLMError(f"Ollama HTTP error: {exc.response.status_code}. {text}") from exc
    except httpx.HTTPError as exc:
        raise LocalLLMError(f"Ollama request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise LocalLLMError("Ollama returned invalid JSON.") from exc

    text = data.get("response")
    if not isinstance(text, str):
        raise LocalLLMError("Ollama response missing text field.")
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LocalLLMError("Local LLM returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise LocalLLMError("Local LLM tool call must be a JSON object.")
    return value


def parse_tool_call_with_llm(
    question: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    prompt = f"""
Return ONLY valid JSON. Do not explain.

Choose exactly one tool from:
- compare_live_item
- top_opportunities
- data_quality
- label_distribution
- liquidity_analysis
- recommendation_summary
- refresh_watchlist

Do not invent missing arguments.
If required arguments are missing, return:
{{"tool": "unknown", "args": {{}}, "reason": "missing required arguments"}}

For compare_live_item, required args are:
{{
  "base_name": "string",
  "wear": "fn|mw|ft|ww|bs|null",
  "category": "normal|stattrak|souvenir|null",
  "uu_keyword": "string",
  "uu_index": 0
}}

Example user question:
Compare Sport Gloves Nocts Field-Tested with UU keyword 夜行衣

Expected JSON:
{{
  "tool": "compare_live_item",
  "args": {{
    "base_name": "Sport Gloves | Nocts",
    "wear": "ft",
    "category": "normal",
    "uu_keyword": "夜行衣",
    "uu_index": 0
  }}
}}

User question:
{question}
"""
    return _extract_json(ollama_generate(prompt=prompt, model=model, temperature=0.0))


def summarize_tool_output_with_llm(
    question: str,
    tool_name: str,
    tool_output: dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> str:
    prompt = f"""
You are a grounded market data analyst.
Summarize the provided tool output.

Rules:
- Do not invent numbers.
- Only use numbers present in the tool output.
- Do not make trading recommendations beyond the computed signals.
- Mention if the item did not match.
- Mention if data quality is weak.
- Mention that UU bid_reference is reference-only if present.
- Keep the answer concise.

Question:
{question}

Tool:
{tool_name}

Tool output JSON:
{json.dumps(tool_output, ensure_ascii=False, indent=2)}
"""
    return ollama_generate(prompt=prompt, model=model, temperature=0.0)
