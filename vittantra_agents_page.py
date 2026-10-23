"""
Agent Desk page (Day 94): seven analyst agents draft each desk's work on live
data; the person reviews, challenges and decides. Reviews are saved to the
work record and count as desk work in the Job Tracker.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import academy_desk as desk
import analyst_agents as aa
import vittantra_cloud as cloud


# Which Academy role a review of each agent counts for.
REVIEW_ROLE = {"investment_analyst": "investment_analyst", "equity_research": "equity_researcher",
               "portfolio_construction": "portfolio_manager", "portfolio_manager": "portfolio_manager",
               "portfolio_analyst": "portfolio_analyst", "risk_analyst": "portfolio_analyst", "trader": "trader"}
REVIEW_CHECKS = ["I checked at least one cited number against its source",
                 "I wrote my own call, not just the agent's",
                 "I named a risk or question the agent did not cover"]


@st.cache_data(ttl=900, show_spinner=False)
def _run(key: str, ticker: str, stamp: str) -> aa.AgentRun:
    return aa.run_agent(key, ticker=ticker)


def _stamp() -> str:
    path = aa.BASE_DIR / "day75_refresh_stamp.csv"
    return path.read_text() if path.exists() else ""


def _review(run: aa.AgentRun, key: str) -> None:
    st.markdown("#### Your review")
    st.caption("This is the skill employers now test: checking an AI's first draft and making the call yourself.")
    verdict = st.radio("Do you agree with the agent?", ["Agree", "Partly", "Disagree"], horizontal=True,
                       key=f"ag-verdict-{key}")
    call = st.text_area("Your call (what you would tell your PM, and why)", key=f"ag-call-{key}")
    ticks = [st.checkbox(c, key=f"ag-check-{key}-{i}") for i, c in enumerate(REVIEW_CHECKS)]
    signed_out = cloud.cloud_mode() and cloud.current_user() is None
    if st.button("Save review", key=f"ag-save-{key}", type="primary", disabled=signed_out):
        if not call.strip():
            st.error("Write your call first.")
            return
        from vittantra_academy_page import _save
        path = cloud.progress_path()
        progress = desk.load_progress(path) if path is not None else desk.load_progress()
        score = 100 * sum(ticks) / len(ticks)
        desk.record_task(progress, REVIEW_ROLE[key], f"Agent review: {aa.AGENTS[key]['label']}", score,
                         {"verdict": verdict, "call": call.strip()},
                         "Self-review checklist: " + ", ".join(c for c, t in zip(REVIEW_CHECKS, ticks) if t))
        _save(progress)
        st.success(f"Review saved to your work record ({score:.0f}/100 on the review checklist).")
    if signed_out:
        st.caption("Sign in (sidebar) to save reviews to your work record.")


def render_agents() -> None:
    st.markdown("### Agent Desk")
    st.markdown('<div class="vt-lede">Seven analyst agents draft the work of each desk on live data — a morning '
                'note, a research note, a portfolio review, a PM memo, attribution, a risk report, a trading plan. '
                'Every number cites its source. You review, challenge and decide; nothing is executed.</div>',
                unsafe_allow_html=True)
    single, pack = st.tabs(["Run an agent", "Morning pack (all agents)"])
    stamp = _stamp()

    with single:
        keys = list(aa.AGENTS)
        key = st.radio("Agent", keys, format_func=lambda k: aa.AGENTS[k]["label"], horizontal=True, key="ag-pick")
        st.caption(aa.AGENTS[key]["does"])
        ticker = "NVDA"
        if aa.AGENTS[key].get("needs_ticker"):
            ticker = st.text_input("Company ticker (any US-listed company)", value="NVDA", key="ag-ticker").strip() \
                or "NVDA"
        run = _run(key, ticker.upper(), stamp)
        show_sources = st.toggle("Show sources next to each finding", value=False, key="ag-cite")
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown(aa.to_markdown(run, cite=show_sources).replace("$", "\\$"))
            st.download_button("Download this deliverable (Markdown)", aa.to_markdown(run, cite=True),
                               file_name=f"vittantra_{key}.md", key=f"ag-dl-{key}")
        with right:
            st.markdown("#### How the agent worked")
            if run.steps:
                st.dataframe(pd.DataFrame(run.steps).rename(columns={"step": "#", "action": "Step", "source": "Read",
                                                                     "result": "Found"}),
                             hide_index=True, width="stretch")
            findings = pd.DataFrame(run.findings())
            if len(findings):
                st.markdown("#### Evidence")
                st.dataframe(findings[["section", "source", "field", "value"]].rename(columns={
                    "section": "Section", "source": "Source file", "field": "Field", "value": "Value"}).astype(str),
                    hide_index=True, width="stretch", height=280)
        st.divider()
        _review(run, key)

    with pack:
        st.caption("Every agent run in sequence — the pack a desk head reads before the morning meeting.")
        if st.button("Prepare the morning pack", key="ag-pack", type="primary"):
            runs = [_run(k, "NVDA", stamp) for k in aa.AGENTS]
            st.session_state["ag-pack-md"] = "\n\n---\n\n".join(aa.to_markdown(r, cite=True) for r in runs)
            st.session_state["ag-pack-titles"] = [(r.title, aa.to_markdown(r, cite=False)) for r in runs]
        for title, text in st.session_state.get("ag-pack-titles", []):
            with st.expander(title):
                st.markdown(text.replace("$", "\\$"))
        if st.session_state.get("ag-pack-md"):
            st.download_button("Download the morning pack (Markdown)", st.session_state["ag-pack-md"],
                               file_name="vittantra_morning_pack.md", key="ag-pack-dl")
