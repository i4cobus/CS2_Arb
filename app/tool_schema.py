from __future__ import annotations

from typing import Any


ALLOWED_TOOLS: dict[str, dict[str, Any]] = {
    "compare_live_item": {
        "required": ["base_name", "wear", "category", "uu_keyword", "uu_index"],
    },
    "top_opportunities": {"required": []},
    "data_quality": {"required": []},
    "label_distribution": {"required": []},
    "liquidity_analysis": {"required": []},
    "recommendation_summary": {"required": []},
    "refresh_watchlist": {"required": []},
    "fetch_csfloat_snapshot": {"required": ["base_name"]},
    "search_uu_templates": {"required": ["keyword"]},
    "fetch_uu_snapshot": {"required": ["template_id"]},
}

VALID_WEAR = {"fn", "mw", "ft", "ww", "bs", None}
VALID_CATEGORY = {"normal", "stattrak", "souvenir", None}


def _args(tool_call: dict[str, Any]) -> dict[str, Any]:
    args = tool_call.get("args")
    return args if isinstance(args, dict) else {}


def validate_tool_call(tool_call: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(tool_call, dict):
        return False, ["Tool call must be a dictionary."]

    tool_name = tool_call.get("tool")
    if tool_name not in ALLOWED_TOOLS:
        return False, [f"Unknown or unsupported tool: {tool_name}"]

    args = _args(tool_call)
    for required in ALLOWED_TOOLS[tool_name]["required"]:
        if required not in args:
            errors.append(f"Missing required arg: {required}")

    if "wear" in args and args.get("wear") not in VALID_WEAR:
        errors.append("Invalid wear. Expected one of fn, mw, ft, ww, bs, or null.")

    if "category" in args and args.get("category") not in VALID_CATEGORY:
        errors.append("Invalid category. Expected normal, stattrak, souvenir, or null.")

    if "uu_index" in args and not isinstance(args.get("uu_index"), int):
        errors.append("Invalid uu_index. Expected int.")

    return not errors, errors
