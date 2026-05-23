from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from app.agent_trace import AgentTrace
from app.local_llm import DEFAULT_MODEL, LocalLLMError, parse_tool_call_with_llm
from app.local_llm import summarize_tool_output_with_llm as local_llm_summary
from app.tool_schema import validate_tool_call
from app.tools import TOOLS, ToolSpec, get_tool


SUPPORTED_QUESTIONS = [
    "compare live item",
    "fetch CSFloat snapshot",
    "search UU templates",
    "fetch UU snapshot",
    "refresh watchlist",
    "top opportunities",
    "data quality",
    "label distribution",
    "liquidity analysis",
    "recommendation summary",
    "item comparison",
]

RULE_TO_TOOL = {
    "liquidity": "liquidity_analysis",
}


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["compare live", "compare today", "across markets", "live comparison"]):
        return "compare_live_item"
    if any(k in q for k in ["fetch csfloat", "csfloat snapshot"]):
        return "fetch_csfloat_snapshot"
    if any(k in q for k in ["search uu", "search youpin", "uu templates"]):
        return "search_uu_templates"
    if any(k in q for k in ["fetch uu", "fetch youpin", "uu snapshot", "youpin snapshot"]):
        return "fetch_uu_snapshot"
    if any(k in q for k in ["refresh watchlist", "refresh the watchlist", "rebuild dataset", "update recommendations"]):
        return "refresh_watchlist"
    if any(k in q for k in ["quality", "missing", "data issue", "matched", "mismatch"]):
        return "data_quality"
    if any(k in q for k in ["label", "distribution", "category"]):
        return "label_distribution"
    if any(k in q for k in ["liquidity", "volume", "bid depth", "active"]):
        return "liquidity"
    if any(k in q for k in ["recommendation", "summary", "why"]):
        return "recommendation_summary"
    if any(k in q for k in ["compare", "show item", "specific item"]):
        return "compare_item"
    if any(k in q for k in ["top", "best", "strong", "worth watching", "candidate"]):
        return "top_opportunities"
    return "unknown"


def summarize_with_llm(question: str, tool_output: dict) -> str:
    """
    Backward-compatible extension point.
    The local LLM may summarize tool output, but must not compute numbers.
    """
    return local_llm_summary(question, tool_output.get("tool_name") or tool_output.get("tool", ""), tool_output)


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "n/a"
    return f"{number:.2f}%"


def _fmt_score(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "n/a"
    return f"{number:.3f}"


def _grounded_summary(intent: str, tool_output: Dict[str, Any], limit: int = 5) -> str:
    rows = tool_output.get("rows") or []
    warnings = tool_output.get("warnings") or []

    if intent == "data_quality":
        if warnings and not rows:
            return "I could not produce an analytical answer because: " + "; ".join(warnings)
        if not rows:
            return "The selected tool returned no rows, so I cannot make a grounded claim."
        row = rows[0]
        return (
            f"The dataset has {row.get('total_rows')} rows, {row.get('match_rate_pct')}% match rate, "
            f"{row.get('ok_rate_pct')}% OK rows, {row.get('missing_uu_ask_rows')} missing UU asks, "
            f"{row.get('missing_uu_bid_rows')} missing UU bids, and "
            f"{row.get('negative_exit_margin_rows')} rows with negative instant-exit margin."
        )

    if intent == "label_distribution":
        if warnings and not rows:
            return "I could not produce an analytical answer because: " + "; ".join(warnings)
        if not rows:
            return "The selected tool returned no rows, so I cannot make a grounded claim."
        parts = [f"{row.get('recommendation_label')}: {row.get('row_count')} rows" for row in rows[:limit]]
        return "The recommendation label distribution is: " + "; ".join(parts) + "."

    if intent in {"liquidity", "liquidity_analysis"}:
        if warnings and not rows:
            return "I could not produce an analytical answer because: " + "; ".join(warnings)
        if not rows:
            return "The selected tool returned no rows, so I cannot make a grounded claim."
        parts = []
        for row in rows[:limit]:
            parts.append(
                f"{row.get('market_hash_name')} has liquidity score "
                f"{_fmt_score(row.get('cs_liquidity_score'))}, CS 24h volume "
                f"{row.get('cs_vol24h')}, and UU listings {row.get('uu_listings')}"
            )
        return "Liquidity analysis: " + "; ".join(parts) + "."

    if intent == "recommendation_summary":
        if warnings and not rows:
            return "I could not produce an analytical answer because: " + "; ".join(warnings)
        if not rows:
            return "The selected tool returned no rows, so I cannot make a grounded claim."
        parts = []
        for row in rows[:limit]:
            parts.append(
                f"{row.get('market_hash_name')} is {row.get('recommendation_label')} "
                f"with score {_fmt_score(row.get('opportunity_score'))}"
            )
        return "Recommendation summary: " + "; ".join(parts) + "."

    if intent == "compare_item":
        if warnings and not rows:
            return "I could not produce an analytical answer because: " + "; ".join(warnings)
        if not rows:
            return "The selected tool returned no rows, so I cannot make a grounded claim."
        row = rows[0]
        return (
            f"{row.get('market_hash_name')} has UU ask {row.get('uu_lowest_ask_usd')}, "
            f"CS bid {row.get('cs_highest_bid_usd')}, instant-exit margin "
            f"{_fmt_pct(row.get('instant_exit_margin_pct'))}, and label "
            f"{row.get('recommendation_label')}."
        )

    if intent == "compare_live_item":
        if tool_output.get("status") == "error":
            return f"The live comparison could not be completed: {tool_output.get('error')}."
        comparison = tool_output.get("comparison") or {}
        if not comparison.get("matched"):
            return (
                "The live snapshots were fetched, but the item comparison is not matched: "
                f"{comparison.get('reason')}."
            )
        return (
            f"Live comparison for {comparison.get('market_hash_name')}: UU ask is "
            f"{comparison.get('uu_lowest_ask_usd')} USD after conversion, CSFloat bid is "
            f"{comparison.get('cs_highest_bid_usd')} USD, and spread to CSFloat bid is "
            f"{_fmt_pct(comparison.get('spread_to_cs_bid_pct'))}."
        )

    if intent == "fetch_csfloat_snapshot":
        return (
            f"Fetched live CSFloat snapshot for {tool_output.get('market_hash_name')}: "
            f"lowest ask {tool_output.get('lowest_ask')} USD, highest bid "
            f"{tool_output.get('highest_bid')} USD, 24h volume {tool_output.get('vol24h')}."
        )

    if intent == "fetch_uu_snapshot":
        return (
            f"Fetched live UU snapshot for {tool_output.get('market_hash_name')}: "
            f"lowest ask {tool_output.get('lowest_ask')} CNY, highest bid "
            f"{tool_output.get('highest_bid')} CNY, listings {tool_output.get('listings')}."
        )

    if intent == "search_uu_templates":
        candidates = tool_output.get("candidates") or []
        if not candidates:
            return "The UU template search returned no candidates."
        parts = [f"{row.get('template_id')}: {row.get('commodity_name_cn')}" for row in candidates[:limit]]
        return "UU template candidates: " + "; ".join(parts) + "."

    if intent == "refresh_watchlist":
        outputs = tool_output.get("outputs") or {}
        return (
            "Refreshed the watchlist pipeline and wrote snapshot, feature, and "
            f"recommendation outputs: {outputs}."
        )

    if warnings and not rows:
        return "I could not produce an analytical answer because: " + "; ".join(warnings)
    if not rows:
        return "The selected tool returned no rows, so I cannot make a grounded claim."

    parts = []
    for row in rows[:limit]:
        parts.append(
            f"{row.get('market_hash_name')} is {row.get('recommendation_label')} "
            f"with opportunity score {_fmt_score(row.get('opportunity_score'))}, "
            f"instant-exit margin {_fmt_pct(row.get('instant_exit_margin_pct'))}, "
            f"and risk {_fmt_score(row.get('risk_score'))}"
        )
    return (
        "The strongest watchlist candidates are: "
        + "; ".join(parts)
        + ". This is based on deterministic recommendation outputs."
    )


def _extract_item_name(question: str) -> Optional[str]:
    q = question.strip()
    lowered = q.lower()
    for prefix in ("compare", "show item", "specific item"):
        if lowered.startswith(prefix):
            return q[len(prefix) :].strip(" :")
    return None


def _is_live_tool(tool: ToolSpec) -> bool:
    return getattr(tool, "kind", "offline_analytics") in {
        "live_collection",
        "live_comparison",
        "dataset_refresh",
    }


def _tool_rows(tool_output: Any) -> List[Any]:
    if isinstance(tool_output, dict):
        return tool_output.get("rows") or tool_output.get("candidates") or []
    if isinstance(tool_output, list):
        return tool_output
    return []


def _tool_steps(tool_output: Any, tool_name: str) -> List[Dict[str, Any]]:
    if isinstance(tool_output, dict) and isinstance(tool_output.get("steps"), list):
        return tool_output["steps"]
    return [{"name": tool_name, "status": "ok"}]


def _normalise_live_output(intent: str, output: Any) -> Dict[str, Any]:
    if isinstance(output, dict):
        return output
    if intent == "search_uu_templates":
        return {
            "tool": intent,
            "status": "ok",
            "candidates": output,
            "steps": [{"name": intent, "status": "ok"}],
        }
    return {"tool": intent, "status": "ok", "result": output, "steps": [{"name": intent, "status": "ok"}]}


def _result_preview(tool_output: Any) -> Dict[str, Any]:
    if not isinstance(tool_output, dict):
        return {"type": type(tool_output).__name__}
    preview: Dict[str, Any] = {}
    for key in ("tool", "tool_name", "status", "error", "row_count"):
        if key in tool_output:
            preview[key] = tool_output[key]
    if "comparison" in tool_output and isinstance(tool_output["comparison"], dict):
        comparison = tool_output["comparison"]
        preview["comparison"] = {
            "matched": comparison.get("matched"),
            "market_hash_name": comparison.get("market_hash_name"),
        }
    return preview


def _trace_dict(trace: AgentTrace, rows_returned: Optional[int] = None) -> Dict[str, Any]:
    data = trace.to_dict()
    data["rows_returned"] = rows_returned
    return data


def _contains_bid_reference(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("bid_reference") is not None or value.get("uu_bid_reference") is not None:
            return True
        return any(_contains_bid_reference(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_bid_reference(child) for child in value)
    return False


def _canonical_tool_name(name: str) -> str:
    return RULE_TO_TOOL.get(name, name)


def _tool_call_from_rule(question: str) -> dict[str, Any]:
    intent = classify_intent(question)
    if intent == "unknown":
        return {"tool": "unknown", "args": {}, "reason": "rule-based routing could not classify question"}
    return {"tool": _canonical_tool_name(intent), "args": {}}


def _execution_tool_name(tool_name: str) -> str:
    if tool_name == "liquidity_analysis":
        return "liquidity"
    return tool_name


def _call_tool(tool: ToolSpec, question: str, limit: int, args: Dict[str, Any]) -> Dict[str, Any]:
    if _is_live_tool(tool):
        return _normalise_live_output(tool.name, tool.handler(**args))
    return tool.handler(limit=limit, item_name=_extract_item_name(question), **args)


def _unsupported_response(question: str, mode: str, tool_call: dict[str, Any], message: str) -> Dict[str, Any]:
    trace = AgentTrace(
        question=question,
        mode=mode,
        intent=tool_call.get("tool"),
        selected_tool=None,
        tool_kind=None,
    )
    trace.add_step("select_tool", "error", message)
    trace.add_warning(message)
    return {
        "answer": (
            "I could not confidently map this request to an executable tool. "
            "Supported questions: " + ", ".join(SUPPORTED_QUESTIONS) + "."
        ),
        "tool_call": tool_call,
        "result": {},
        "trace": trace.to_dict(),
        "question": question,
        "intent": tool_call.get("tool"),
        "selected_tool": None,
        "rows": [],
    }


def run_agent(
    question: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_args: Optional[dict[str, Any]] = None,
    use_llm: bool = False,
    summarize_with_llm: bool = False,
    model: str = DEFAULT_MODEL,
    limit: int = 5,
) -> dict[str, Any]:
    question_text = question or tool_name or ""
    mode = "local_llm" if use_llm else "deterministic"

    if tool_name:
        tool_call = {"tool": _canonical_tool_name(tool_name), "args": dict(tool_args or {})}
    elif use_llm:
        try:
            tool_call = parse_tool_call_with_llm(question_text, model=model)
        except LocalLLMError as exc:
            trace = AgentTrace(
                question=question_text,
                mode=mode,
                intent=None,
                selected_tool=None,
                tool_kind=None,
            )
            trace.add_step("parse_tool_call_with_llm", "error", str(exc))
            trace.add_warning(str(exc))
            return {
                "answer": f"Local LLM tool parsing failed: {exc}",
                "tool_call": {"tool": "unknown", "args": {}, "reason": str(exc)},
                "result": {},
                "trace": _trace_dict(trace),
                "question": question_text,
                "intent": "unknown",
                "selected_tool": None,
                "rows": [],
            }
    else:
        tool_call = _tool_call_from_rule(question_text)

    if tool_call.get("tool") == "unknown":
        return _unsupported_response(
            question_text,
            mode,
            tool_call,
            tool_call.get("reason") or "Unknown intent.",
        )

    if tool_name and tool_call.get("tool") == "compare_live_item":
        tool_call.setdefault("args", {}).setdefault("uu_index", 0)

    is_valid, validation_errors = validate_tool_call(tool_call)
    if not is_valid:
        trace = AgentTrace(
            question=question_text,
            mode=mode,
            intent=tool_call.get("tool"),
            selected_tool=None,
            tool_kind=None,
        )
        trace.add_step("validate_tool_call", "error", "; ".join(validation_errors))
        for error in validation_errors:
            trace.add_warning(error)
        return {
            "answer": "Tool call validation failed: " + "; ".join(validation_errors),
            "tool_call": tool_call,
            "result": {},
            "trace": trace.to_dict(),
            "question": question_text,
            "intent": tool_call.get("tool"),
            "selected_tool": None,
            "rows": [],
        }

    selected_tool_name = _execution_tool_name(tool_call["tool"])
    tool = get_tool(selected_tool_name)
    if tool is None:
        return _unsupported_response(
            question_text,
            mode,
            tool_call,
            f"No registered tool for: {selected_tool_name}",
        )

    trace = AgentTrace(
        question=question_text,
        mode=mode,
        intent=tool_call["tool"],
        selected_tool=selected_tool_name,
        tool_kind=getattr(tool, "kind", None),
        live_api_used=_is_live_tool(tool),
        evidence_files=[] if _is_live_tool(tool) else tool.requires,
    )
    trace.add_step("validate_tool_call", "ok")

    args = dict(tool_call.get("args") or {})
    if tool_call["tool"] == "compare_live_item":
        args.setdefault("uu_index", 0)
        tool_call["args"] = args
    try:
        tool_output = _call_tool(tool, question_text, limit, args)
    except Exception as exc:
        trace.add_step(selected_tool_name, "error", repr(exc))
        trace.add_warning(repr(exc))
        return {
            "answer": f"Tool execution failed: {exc!r}",
            "tool_call": tool_call,
            "result": {},
            "trace": _trace_dict(trace),
            "question": question_text,
            "intent": tool_call["tool"],
            "selected_tool": selected_tool_name,
            "rows": [],
        }

    for step in _tool_steps(tool_output, selected_tool_name):
        trace.add_step(step.get("name", selected_tool_name), step.get("status", "ok"), step.get("message"))

    rows = _tool_rows(tool_output)
    if isinstance(tool_output, dict):
        trace.evidence_files = tool_output.get("evidence_files") or trace.evidence_files
        for warning in tool_output.get("warnings") or []:
            trace.add_warning(warning)
        if _contains_bid_reference(tool_output):
            trace.add_warning(
                "UU bid_reference is reference-only and should not be treated as a reliable highest_bid."
            )
    trace.result_preview = _result_preview(tool_output)

    if summarize_with_llm:
        try:
            answer = local_llm_summary(
                question=question_text,
                tool_name=tool_call["tool"],
                tool_output=tool_output,
                model=model,
            )
            trace.add_step("summarize_tool_output_with_llm", "ok")
        except LocalLLMError as exc:
            answer = _grounded_summary(tool_call["tool"], tool_output, limit=limit)
            trace.add_step("summarize_tool_output_with_llm", "error", str(exc))
            trace.add_warning(f"Local LLM summary failed; used deterministic summary. {exc}")
    else:
        answer = _grounded_summary(tool_call["tool"], tool_output, limit=limit)

    return {
        "answer": answer,
        "tool_call": tool_call,
        "result": tool_output,
        "trace": _trace_dict(
            trace,
            tool_output.get("row_count", len(rows)) if isinstance(tool_output, dict) else len(rows),
        ),
        "question": question_text,
        "intent": tool_call["tool"],
        "selected_tool": selected_tool_name,
        "tool_description": tool.description,
        "tool_kind": getattr(tool, "kind", None),
        "tool_output": tool_output,
        "rows": rows,
    }


def _print_result(result: Dict[str, Any]) -> None:
    trace = result["trace"]
    print(f"Question: {result.get('question')}")
    print(f"Mode: {trace.get('mode')}")
    print(f"Intent: {result.get('intent')}")
    print(f"Tool selected: {result.get('selected_tool')}")
    print(f"Tool kind: {trace.get('tool_kind')}")
    print(f"Live API used: {str(trace.get('live_api_used')).lower()}")
    print(f"Evidence: {', '.join(trace.get('evidence_files') or []) or 'none'}")
    if trace.get("warnings"):
        print("Warnings: " + "; ".join(trace["warnings"]))
    print()
    print("Answer:")
    print(result["answer"])
    print()
    print("Tool call:")
    print(json.dumps(result.get("tool_call"), ensure_ascii=False, indent=2))
    print()
    print("Trace:")
    steps = trace.get("steps") or []
    if steps:
        for index, step in enumerate(steps, start=1):
            message = f" - {step.get('message')}" if step.get("message") else ""
            print(f"{index}. {step.get('name')}: {step.get('status')}{message}")
        print()
    print(json.dumps(trace, ensure_ascii=False, indent=2))
    if result.get("result"):
        print()
        print("Result:")
        print(json.dumps(result["result"], ensure_ascii=False, indent=2))


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Grounded local-LLM-assisted tool-using market intelligence agent.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("question", nargs="?", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--llm", action="store_true", help="Use local Ollama model for tool-call parsing.")
    parser.add_argument("--llm-summary", action="store_true", help="Use local Ollama model for final summary.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--tool",
        choices=[
            "compare_live_item",
            "fetch_csfloat_snapshot",
            "search_uu_templates",
            "fetch_uu_snapshot",
            "refresh_watchlist",
        ],
        help="Explicit live tool selection. Offline analytics still use natural-language routing.",
    )
    parser.add_argument("--base-name")
    parser.add_argument("--wear")
    parser.add_argument("--category")
    parser.add_argument("--uu-keyword")
    parser.add_argument("--uu-index", type=int, default=0)
    parser.add_argument("--template-id")
    parser.add_argument("--keyword")
    parser.add_argument("--cny-to-usd", type=float, default=0.14)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def _build_tool_args(args: argparse.Namespace) -> Dict[str, Any]:
    if args.tool == "compare_live_item":
        required = {
            "--base-name": args.base_name,
            "--uu-keyword": args.uu_keyword,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise SystemExit(f"{args.tool} requires: {', '.join(missing)}")
        return {
            "base_name": args.base_name,
            "wear": args.wear,
            "category": args.category,
            "uu_keyword": args.uu_keyword,
            "uu_index": args.uu_index,
            "cny_to_usd": args.cny_to_usd,
            "debug": args.debug,
        }
    if args.tool == "fetch_csfloat_snapshot":
        if not args.base_name:
            raise SystemExit("fetch_csfloat_snapshot requires: --base-name")
        return {
            "base_name": args.base_name,
            "wear": args.wear,
            "category": args.category,
            "debug": args.debug,
        }
    if args.tool == "search_uu_templates":
        keyword = args.keyword or args.uu_keyword
        if not keyword:
            raise SystemExit("search_uu_templates requires: --keyword or --uu-keyword")
        return {"keyword": keyword, "debug": args.debug}
    if args.tool == "fetch_uu_snapshot":
        if not args.template_id:
            raise SystemExit("fetch_uu_snapshot requires: --template-id")
        return {"template_id": args.template_id, "debug": args.debug}
    if args.tool == "refresh_watchlist":
        return {"cny_to_usd": args.cny_to_usd, "debug": args.debug}
    return {}


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    result = run_agent(
        question=args.question or args.tool or "",
        tool_name=args.tool,
        tool_args=_build_tool_args(args),
        use_llm=args.llm,
        summarize_with_llm=args.llm_summary,
        model=args.model,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_result(result)


if __name__ == "__main__":
    main()
