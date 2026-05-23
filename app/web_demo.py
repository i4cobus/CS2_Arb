from __future__ import annotations

import streamlit as st

from app.agent import run_agent
from app.local_llm import DEFAULT_MODEL
from app.tools import list_tools


st.set_page_config(page_title="Tool-Using Market Intelligence Agent", layout="wide")

st.title("Tool-Using Market Intelligence Agent")
st.caption("Grounded live data collection, cross-source comparison, and local LLM-assisted analysis.")

live_tab, analyst_tab, tools_tab = st.tabs(["Live Compare", "Analyst Agent", "Tool Registry"])

with live_tab:
    st.subheader("Live Cross-Source Compare")
    base_name = st.text_input("base_name", value="Sport Gloves | Nocts")
    wear = st.selectbox("wear", options=["fn", "mw", "ft", "ww", "bs", None], index=2)
    category = st.selectbox("category", options=["normal", "stattrak", "souvenir", None], index=0)
    uu_keyword = st.text_input("uu_keyword", value="夜行衣")
    uu_index = st.number_input("uu_index", min_value=0, value=0, step=1)
    use_summary = st.checkbox("Use local LLM summary", value=False)

    if st.button("Run live comparison"):
        result = run_agent(
            question="live compare",
            tool_name="compare_live_item",
            tool_args={
                "base_name": base_name,
                "wear": wear,
                "category": category,
                "uu_keyword": uu_keyword,
                "uu_index": int(uu_index),
            },
            summarize_with_llm=use_summary,
        )
        st.write("Answer")
        st.write(result["answer"])
        st.write("Agent trace")
        st.json(result["trace"])
        output = result.get("result") or {}
        st.write("Comparison result")
        st.json(output.get("comparison", {}))
        st.write("CSFloat snapshot")
        st.json(output.get("cs_snapshot", {}))
        st.write("UU snapshot")
        st.json(output.get("uu_snapshot", {}))
        if result["trace"].get("warnings"):
            st.warning("; ".join(result["trace"]["warnings"]))

with analyst_tab:
    st.subheader("Ask The Agent")
    question = st.text_area("Question", value="Which items are worth watching today?")
    use_llm = st.checkbox("Use local LLM parser", value=False)
    use_llm_summary = st.checkbox("Use local LLM summary", value=False, key="analyst_summary")
    model = st.text_input("Model", value=DEFAULT_MODEL)

    if st.button("Ask agent"):
        result = run_agent(
            question=question,
            use_llm=use_llm,
            summarize_with_llm=use_llm_summary,
            model=model,
        )
        st.write("Answer")
        st.write(result["answer"])
        st.write("Tool call")
        st.json(result.get("tool_call", {}))
        st.write("Trace")
        st.json(result.get("trace", {}))
        st.write("Raw result")
        st.json(result.get("result", {}))

with tools_tab:
    st.subheader("Available Tools")
    st.dataframe(list_tools(), use_container_width=True)
