from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Dict, List, Optional

from app.analytics import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_RECOMMENDATIONS_PATH,
    run_query_file,
)
from app.compare import compare_snapshots
from app.csfloat_client import fetch_snapshot_by_params
from app.dataset_builder import (
    DEFAULT_OUTPUT_PATH as DEFAULT_SNAPSHOT_PATH,
    DEFAULT_WATCHLIST_PATH,
    build_dataset,
)
from app.features import (
    DEFAULT_OUTPUT_PATH as DEFAULT_FEATURES_OUTPUT_PATH,
    build_feature_dataset,
)
from app.recommender import build_recommendations
from app.uu_client import get_template_snapshot, search_templates


ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: str
    description: str
    handler: ToolHandler
    requires: List[str]
    output_type: str
    examples: List[str]


def _missing_files(paths: List[str]) -> List[str]:
    return [path for path in paths if not os.path.exists(path)]


def _empty_result(tool_name: str, warnings: List[str]) -> Dict[str, Any]:
    return {
        "tool_name": tool_name,
        "rows": [],
        "row_count": 0,
        "warnings": warnings,
    }


def _read_csv_rows(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_plain_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TypeError(f"Cannot convert {type(value)} to dict")


def _step(name: str, status: str = "ok", **extra: Any) -> Dict[str, Any]:
    row = {"name": name, "status": status}
    row.update(extra)
    return row


def _run_sql_tool(
    tool_name: str,
    sql_file: str,
    requires: List[str],
    limit: int = 10,
) -> Dict[str, Any]:
    missing = _missing_files(requires + [sql_file])
    if missing:
        return _empty_result(tool_name, [f"Missing required file: {path}" for path in missing])

    rows = run_query_file(
        query_path=sql_file,
        table_sources={
            "features": DEFAULT_FEATURES_PATH,
            "recommendations": DEFAULT_RECOMMENDATIONS_PATH,
        },
    )
    return {
        "tool_name": tool_name,
        "sql_file": sql_file,
        "evidence_files": requires,
        "rows": rows[:limit],
        "row_count": len(rows),
        "warnings": [],
    }


def top_opportunities_tool(limit: int = 10, **_: Any) -> Dict[str, Any]:
    return _run_sql_tool(
        tool_name="top_opportunities",
        sql_file="sql/top_opportunities.sql",
        requires=[DEFAULT_RECOMMENDATIONS_PATH],
        limit=limit,
    )


def data_quality_tool(limit: int = 10, **_: Any) -> Dict[str, Any]:
    return _run_sql_tool(
        tool_name="data_quality",
        sql_file="sql/data_quality_report.sql",
        requires=[DEFAULT_FEATURES_PATH],
        limit=limit,
    )


def label_distribution_tool(limit: int = 10, **_: Any) -> Dict[str, Any]:
    return _run_sql_tool(
        tool_name="label_distribution",
        sql_file="sql/label_distribution.sql",
        requires=[DEFAULT_FEATURES_PATH],
        limit=limit,
    )


def liquidity_analysis_tool(limit: int = 10, **_: Any) -> Dict[str, Any]:
    return _run_sql_tool(
        tool_name="liquidity",
        sql_file="sql/liquidity_analysis.sql",
        requires=[DEFAULT_FEATURES_PATH],
        limit=limit,
    )


def recommendation_summary_tool(limit: int = 10, **_: Any) -> Dict[str, Any]:
    requires = [DEFAULT_FEATURES_PATH, DEFAULT_RECOMMENDATIONS_PATH]
    missing = _missing_files(requires)
    if missing:
        return _empty_result(
            "recommendation_summary",
            [f"Missing required file: {path}" for path in missing],
        )

    rows = build_recommendations(
        input_path=DEFAULT_FEATURES_PATH,
        output_path=DEFAULT_RECOMMENDATIONS_PATH,
        min_label="watchlist",
    )
    return {
        "tool_name": "recommendation_summary",
        "evidence_files": requires,
        "rows": rows[:limit],
        "row_count": len(rows),
        "warnings": [],
    }


def compare_item_tool(item_name: Optional[str] = None, limit: int = 10, **_: Any) -> Dict[str, Any]:
    requires = [DEFAULT_FEATURES_PATH]
    missing = _missing_files(requires)
    if missing:
        return _empty_result("compare_item", [f"Missing required file: {path}" for path in missing])

    rows = _read_csv_rows(DEFAULT_FEATURES_PATH)
    if item_name:
        item_text = item_name.lower()
        rows = [
            row
            for row in rows
            if item_text in row.get("market_hash_name", "").lower()
            or item_text in row.get("base_name", "").lower()
        ]

    return {
        "tool_name": "compare_item",
        "evidence_files": requires,
        "rows": rows[:limit],
        "row_count": len(rows),
        "warnings": [] if rows else ["No matching item rows found."],
    }


def fetch_csfloat_snapshot_tool(
    base_name: str,
    wear: Optional[str] = None,
    category: Optional[str] = None,
    debug: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    snapshot = dict(
        fetch_snapshot_by_params(
            base_name=base_name,
            wear_key=wear,
            category_key=category,
            debug=debug,
        )
    )
    raw_source = snapshot.get("source")
    if raw_source and raw_source != "csfloat":
        snapshot["collection_source"] = raw_source
    snapshot["source"] = "csfloat"
    snapshot.setdefault("market_hash_name", None)
    snapshot.setdefault("lowest_ask", None)
    snapshot.setdefault("highest_bid", None)
    snapshot.setdefault("highest_bid_qty", None)
    snapshot.setdefault("vol24h", None)
    snapshot.setdefault("asp24h", None)
    snapshot.setdefault("currency", "USD")
    return snapshot


def search_uu_templates_tool(keyword: str, debug: bool = False, **_: Any) -> List[Dict[str, Any]]:
    candidates = search_templates(keyword=keyword, debug=debug)
    return [
        {
            "template_id": str(candidate.get("template_id")),
            "commodity_name_cn": candidate.get("commodity_name_cn"),
        }
        for candidate in candidates
        if candidate.get("template_id") is not None
    ]


def fetch_uu_snapshot_tool(
    template_id: str,
    debug: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    snapshot = _to_plain_dict(get_template_snapshot(template_id=template_id, debug=debug))
    snapshot.setdefault("source", "uu")
    snapshot.setdefault("market_hash_name", None)
    snapshot.setdefault("lowest_ask", None)
    snapshot.setdefault("highest_bid", None)
    snapshot.setdefault("bid_reference", None)
    snapshot.setdefault("listings", None)
    snapshot.setdefault("bid_depth", None)
    snapshot.setdefault("bid_depth_reference", None)
    snapshot.setdefault("currency", "CNY")
    snapshot.setdefault("source_id", str(template_id))
    return snapshot


def compare_live_item_tool(
    base_name: str,
    wear: Optional[str],
    category: Optional[str],
    uu_keyword: str,
    uu_index: int = 0,
    cny_to_usd: float = 0.14,
    debug: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    cs_snapshot = fetch_csfloat_snapshot_tool(
        base_name=base_name,
        wear=wear,
        category=category,
        debug=debug,
    )
    steps.append(_step("fetch_csfloat_snapshot"))

    uu_candidates = search_uu_templates_tool(keyword=uu_keyword, debug=debug)
    steps.append(_step("search_uu_templates"))

    if not uu_candidates:
        return {
            "tool": "compare_live_item",
            "status": "error",
            "error": "No UU candidates found",
            "steps": steps,
            "cs_snapshot": cs_snapshot,
            "uu_candidates": [],
        }

    if uu_index < 0 or uu_index >= len(uu_candidates):
        return {
            "tool": "compare_live_item",
            "status": "error",
            "error": f"UU candidate index out of range: {uu_index}",
            "steps": steps,
            "cs_snapshot": cs_snapshot,
            "uu_candidates": uu_candidates,
        }

    selected = uu_candidates[uu_index]
    steps.append(_step("choose_uu_candidate"))
    uu_snapshot = fetch_uu_snapshot_tool(
        template_id=selected["template_id"],
        debug=debug,
    )
    steps.append(_step("fetch_uu_snapshot"))

    comparison = compare_snapshots(cs_snapshot, uu_snapshot, cny_to_usd=cny_to_usd)
    steps.append(_step("compare_snapshots"))

    return {
        "tool": "compare_live_item",
        "status": "ok",
        "steps": steps,
        "cs_snapshot": cs_snapshot,
        "uu_candidates": uu_candidates,
        "selected_uu_candidate": selected,
        "uu_snapshot": uu_snapshot,
        "comparison": comparison,
    }


def refresh_watchlist_tool(
    watchlist_path: str = DEFAULT_WATCHLIST_PATH,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    features_path: str = DEFAULT_FEATURES_OUTPUT_PATH,
    recommendations_path: str = DEFAULT_RECOMMENDATIONS_PATH,
    cny_to_usd: float = 0.14,
    append: bool = False,
    debug: bool = False,
    **_: Any,
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    snapshots = build_dataset(
        watchlist_path=watchlist_path,
        output_path=snapshot_path,
        cny_to_usd=cny_to_usd,
        append=append,
        debug=debug,
    )
    steps.append(_step("build_snapshot_dataset", rows=len(snapshots)))

    features = build_feature_dataset(input_path=snapshot_path, output_path=features_path)
    steps.append(_step("build_features", rows=len(features)))

    recommendations = build_recommendations(
        input_path=features_path,
        output_path=recommendations_path,
        min_label="watchlist",
    )
    steps.append(_step("build_recommendations", rows=len(recommendations)))

    return {
        "tool": "refresh_watchlist",
        "status": "ok",
        "steps": steps,
        "outputs": {
            "snapshots": snapshot_path,
            "features": features_path,
            "recommendations": recommendations_path,
        },
    }


TOOLS: Dict[str, ToolSpec] = {
    "top_opportunities": ToolSpec(
        name="top_opportunities",
        kind="offline_analytics",
        description="Return the highest ranked opportunities from recommendation outputs.",
        handler=top_opportunities_tool,
        requires=[DEFAULT_RECOMMENDATIONS_PATH],
        output_type="sql_rows",
        examples=["Which items are worth watching today?", "Show top candidates"],
    ),
    "data_quality": ToolSpec(
        name="data_quality",
        kind="offline_analytics",
        description="Summarize data quality and missing fields in generated datasets.",
        handler=data_quality_tool,
        requires=[DEFAULT_FEATURES_PATH],
        output_type="sql_rows",
        examples=["Summarize data quality", "Are there missing fields?"],
    ),
    "label_distribution": ToolSpec(
        name="label_distribution",
        kind="offline_analytics",
        description="Show recommendation label counts and aggregate scores.",
        handler=label_distribution_tool,
        requires=[DEFAULT_FEATURES_PATH],
        output_type="sql_rows",
        examples=["Show label distribution", "How many strong candidates are there?"],
    ),
    "liquidity": ToolSpec(
        name="liquidity",
        kind="offline_analytics",
        description="Analyze liquidity, volume, bid depth, and listing depth.",
        handler=liquidity_analysis_tool,
        requires=[DEFAULT_FEATURES_PATH],
        output_type="sql_rows",
        examples=["Which items have strong liquidity?", "Show active items"],
    ),
    "recommendation_summary": ToolSpec(
        name="recommendation_summary",
        kind="offline_analytics",
        description="Build and summarize explainable recommendation outputs.",
        handler=recommendation_summary_tool,
        requires=[DEFAULT_FEATURES_PATH, DEFAULT_RECOMMENDATIONS_PATH],
        output_type="recommendation_rows",
        examples=["Explain the recommendations", "Why are items recommended?"],
    ),
    "compare_item": ToolSpec(
        name="compare_item",
        kind="offline_analytics",
        description="Return feature and spread rows for a specific item name.",
        handler=compare_item_tool,
        requires=[DEFAULT_FEATURES_PATH],
        output_type="feature_rows",
        examples=["Compare Nocts", "Show AK-47 Empress"],
    ),
    "fetch_csfloat_snapshot": ToolSpec(
        name="fetch_csfloat_snapshot",
        kind="live_collection",
        description="Fetch a live CSFloat snapshot for one item.",
        handler=fetch_csfloat_snapshot_tool,
        requires=["CSFLOAT_API_KEY"],
        output_type="snapshot",
        examples=["Fetch CSFloat snapshot for Sport Gloves | Nocts"],
    ),
    "search_uu_templates": ToolSpec(
        name="search_uu_templates",
        kind="live_collection",
        description="Search UU / YouPin templates by keyword.",
        handler=search_uu_templates_tool,
        requires=["UU_AUTHORIZATION", "UU_DEVICE_ID", "UU_DEVICE_UK", "UU_UK"],
        output_type="template_candidates",
        examples=["Search UU templates for 夜行衣"],
    ),
    "fetch_uu_snapshot": ToolSpec(
        name="fetch_uu_snapshot",
        kind="live_collection",
        description="Fetch a live UU / YouPin market snapshot by template ID.",
        handler=fetch_uu_snapshot_tool,
        requires=["UU_AUTHORIZATION", "UU_DEVICE_ID", "UU_DEVICE_UK", "UU_UK"],
        output_type="snapshot",
        examples=["Fetch UU snapshot for template 51135"],
    ),
    "compare_live_item": ToolSpec(
        name="compare_live_item",
        kind="live_comparison",
        description="Fetch live CSFloat and UU data and compare one item.",
        handler=compare_live_item_tool,
        requires=["CSFLOAT_API_KEY", "UU_AUTHORIZATION"],
        output_type="live_comparison",
        examples=["Compare live Sport Gloves | Nocts against UU 夜行衣"],
    ),
    "refresh_watchlist": ToolSpec(
        name="refresh_watchlist",
        kind="dataset_refresh",
        description="Rebuild snapshots, features, and recommendations from the watchlist.",
        handler=refresh_watchlist_tool,
        requires=["CSFLOAT_API_KEY", "UU_AUTHORIZATION", "data/watchlist.csv"],
        output_type="pipeline_status",
        examples=["Refresh watchlist", "Update recommendations"],
    ),
}


def get_tool(name: str) -> Optional[ToolSpec]:
    return TOOLS.get(name)


def list_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "kind": tool.kind,
            "description": tool.description,
            "requires": tool.requires,
        }
        for tool in TOOLS.values()
    ]
