"""
Guide page and the 'How to use this page' box shown at the top of every page.
"""

from __future__ import annotations

import streamlit as st

import vittantra_guide as guide


def _go(page: str) -> None:
    st.session_state["nav"] = page


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:+.1%}"


def page_help(page: str, labels: dict) -> None:
    """Collapsed help box at the top of a page."""
    help_ = guide.PAGE_HELP.get(page)
    if not help_ or page == "Guide":
        return
    with st.expander(f"How to use this page — {labels.get(page, page)}"):
        st.markdown(f"**What it is for:** {help_['what']}")
        st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(help_["steps"], start=1)))
        st.caption(f"Tip: {help_['tip']}")
        st.button("Open the full Guide", key=f"help-guide-{page}", on_click=_go, args=("Guide",))


def _navigation_tab(labels: dict) -> None:
    st.markdown("#### Find your way")
    st.info("💡 Hover over any number or table column header to see what it means and why professionals use it.")
    for title, text in guide.NAVIGATION:
        st.markdown(f"**{title}.** {text}")
    st.markdown("#### What each page is for")
    for page, help_ in guide.PAGE_HELP.items():
        if page == "Guide":
            continue
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"**{labels.get(page, page)}** — {help_['what']}")
        c2.button("Go", key=f"guide-page-{page}", on_click=_go, args=(page,), width="stretch")


def _playbooks_tab() -> None:
    st.markdown("#### Do the job, step by step")
    st.caption("Each playbook is how a professional would do the task in Vittantra. Press Go to open each step's "
               "page, then come back here for the next step.")
    titles = [p["title"] for p in guide.PLAYBOOKS]
    choice = st.radio("Playbook", titles, horizontal=True, key="guide-playbook", label_visibility="collapsed")
    playbook = guide.PLAYBOOKS[titles.index(choice)]
    st.markdown(f"**{playbook['title']}** · {playbook['role']}  \nGoal: {playbook['goal']}")
    for i, (page, text) in enumerate(playbook["steps"], start=1):
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"**{i}.** {text}")
        c2.button("Go", key=f"guide-step-{choice}-{i}", on_click=_go, args=(page,), width="stretch")


def _asset_classes_tab() -> None:
    from academy_content import LESSONS

    lessons = {lesson["id"]: lesson for lesson in LESSONS}
    st.markdown("#### Every asset class")
    st.caption("What it is, why investors own it, what moves it, how professionals analyse it, and where to "
               "find it in Vittantra. Live numbers come from Vittantra's own market data.")
    for asset in guide.ASSET_CLASSES:
        with st.expander(asset["name"]):
            st.markdown(f"**What it is.** {asset['what']}")
            st.markdown(f"**Why investors own it.** {asset['why']}")
            left, right = st.columns(2)
            left.markdown("**What moves it**\n" + "\n".join(f"- {d}" for d in asset["drivers"]))
            right.markdown("**Main risks**\n" + "\n".join(f"- {r}" for r in asset["risks"]))
            st.markdown("**Numbers professionals watch:** " + " · ".join(asset["metrics"]))
            st.markdown(f"**How professionals analyse it.** {asset['how_pros']}")
            snap = guide.asset_snapshot(asset["key"])
            if snap:
                m = st.columns(4)
                m[0].metric("Instruments tracked", snap["instruments"])
                m[1].metric("Median 12-month return", _pct(snap["median_return_12m"]))
                m[2].metric("Median volatility", "n/a" if snap["median_volatility"] is None
                            else f"{snap['median_volatility']:.0%}")
                m[3].metric("Worst 1-year drawdown", _pct(snap["worst_drawdown"]))
                notes = []
                if snap["best"]:
                    notes.append(f"best 12 months: {snap['best'][0]} ({_pct(snap['best'][1])})")
                if snap["worst"]:
                    notes.append(f"worst: {snap['worst'][0]} ({_pct(snap['worst'][1])})")
                st.caption(f"Live from Vittantra data as of {snap['as_of']}: " + "; ".join(notes)
                           + ". Covers: " + ", ".join(snap["sub_classes"]) + ". Past returns, not forecasts.")
            else:
                st.caption("Live numbers are not available until the market data has been refreshed.")
            drivers = guide.macro_drivers(asset["key"])
            if drivers is not None and not drivers.empty:
                strong = drivers[drivers["median_abs_t"] >= 2]["factor"].tolist()
                st.markdown("**What actually moved it last year (measured):** "
                            + (", ".join(strong) if strong else "no single macro factor stood out")
                            + f" — strongest: {drivers.iloc[0]['factor']} (median |t| "
                            f"{drivers.iloc[0]['median_abs_t']:.1f}).")
            st.markdown(f"**In Vittantra:** {asset['in_vittantra']}")
            st.button(f"Open Markets → {asset['markets_tab']}", key=f"guide-asset-{asset['name']}",
                      on_click=_go, args=("Markets",))
            found = [lessons[i] for i in asset["lessons"] if i in lessons]
            if found:
                st.markdown("**Lessons:** " + " · ".join(f"{l['id']} {l['title']}" for l in found)
                            + " (Academy → Lessons)")


def _day_tab() -> None:
    st.markdown("#### A day on the desk — what professionals actually do")
    st.caption("Follow a real working day, hour by hour. Press Go to do each step in Vittantra, then the Academy "
               "turns it into a graded task. Repeat daily and the routine becomes yours.")
    roles = list(guide.DAY_ON_THE_DESK)
    role = st.radio("Role", roles, horizontal=True, key="guide-day-role", label_visibility="collapsed")
    info = guide.DAY_ON_THE_DESK[role]
    st.markdown(f"**{role}** — {info['who']}")
    for i, (time, task, page, why) in enumerate(info["day"]):
        c1, c2, c3 = st.columns([1, 6, 1])
        c1.markdown(f"**{time}**")
        c2.markdown(f"{task}  \n<span style='opacity:0.7'>Why: {why}</span>", unsafe_allow_html=True)
        c3.button("Go", key=f"guide-day-{role}-{i}", on_click=_go, args=(page,), width="stretch")
    st.info("Make it a habit: do this day once a week for each role, and the Academy's daily task for your main "
            "role every day. Your work record (Academy → My Work Record) becomes your interview evidence.")


def _factors_tab() -> None:
    st.markdown("#### How professionals decide which factors matter")
    st.caption("A factor is a characteristic that may explain returns (cheapness, momentum, interest rates...). "
               "Professionals do not assume a factor works: they test it.")
    for i, (title, text) in enumerate(guide.PRO_METHOD, start=1):
        st.markdown(f"**{i}. {title}.** {text}")

    st.markdown("#### Stock factors — and what Vittantra's tests found")
    evidence = guide.factor_evidence()
    if evidence is not None and not evidence.empty:
        shown = evidence.assign(hit_rate=evidence["hit_rate"] * 100).rename(columns={
            "factor": "Factor", "mean_ic": "Average IC", "t_stat": "t-stat", "hit_rate": "Hit rate",
            "periods": "Periods", "verdict": "Verdict"})
        st.dataframe(shown, hide_index=True, width="stretch",
                     column_config={"Average IC": st.column_config.NumberColumn(format="%.3f"),
                                    "t-stat": st.column_config.NumberColumn(format="%.1f"),
                                    "Hit rate": st.column_config.NumberColumn(format="%.0f%%")})
        st.caption("IC = correlation between the factor score and the next 20 days' returns, measured point in "
                   "time across rebalance dates; t-stat above 2 = unlikely to be luck. Historical research on a "
                   "short sample of 33 stocks, not a promise.")
    else:
        st.caption("Factor tests appear once the ratings engine has run.")
    for factor in guide.STOCK_FACTORS:
        with st.expander(factor["name"]):
            st.markdown(f"**What it asks.** {factor['what']}")
            st.markdown(f"**Why it might work.** {factor['why']}")
            st.markdown(f"**How Vittantra measures it.** {factor['measure']}")
    st.button("See the ratings and IC tests (Research → Multi-factor ratings)", key="guide-factors-go",
              on_click=_go, args=("Research",))

    st.markdown("#### Macro factors — what actually moves each asset class")
    st.caption("Daily returns of each instrument regressed on six macro factors over the past year. A median "
               "|t| above 2 means the factor clearly moved that asset class.")
    rows = []
    for asset in guide.ASSET_CLASSES:
        drivers = guide.macro_drivers(asset["key"])
        if drivers is None or drivers.empty or asset["name"].startswith("Corporate"):
            continue
        top = drivers.iloc[0]
        clear = top["median_abs_t"] >= 2
        rows.append({"Asset class": asset["name"].split(" (")[0],
                     "Main driver": top["factor"] if clear else "No single macro factor (own supply/demand)",
                     "Median |t|": round(top["median_abs_t"], 1),
                     "Second": drivers.iloc[1]["factor"] if clear and len(drivers) > 1
                     and drivers.iloc[1]["median_abs_t"] >= 2 else "—"})
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("Read it like a professional: bonds are a rates bet, crypto and listed alternatives behave like "
                   "equity risk, real estate is rate-sensitive. Details per instrument: Markets → Macro & Economy.")
    else:
        st.caption("Macro factor results appear once the macro drivers engine has run.")


def _pages_tab(labels: dict) -> None:
    st.markdown("#### How to use every page")
    for page, help_ in guide.PAGE_HELP.items():
        if page == "Guide":
            continue
        with st.expander(labels.get(page, page)):
            st.markdown(f"**What it is for:** {help_['what']}")
            st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(help_["steps"], start=1)))
            st.caption(f"Tip: {help_['tip']}")
            st.button("Go to this page", key=f"guide-howto-{page}", on_click=_go, args=(page,))


def _glossary_tab() -> None:
    st.markdown("#### Glossary")
    query = st.text_input("Search a term", key="guide-glossary", placeholder="e.g. duration, IRR, VaR")
    found = guide.search_glossary(query)
    if not found:
        st.info("No term matches. Try a shorter word, or ask the Copilot.")
    for term, text in found.items():
        st.markdown(f"**{term}** — {text}")


def render_guide(labels: dict) -> None:
    st.markdown("### Guide — learn Vittantra and the markets")
    st.caption("How to find your way, how to do each job step by step, what every asset class is, and the words "
               "you will meet. For hands-on practice, use the Academy.")
    tabs = st.tabs(["🧭 Find your way", "🗓️ A day on the desk", "🛠️ Playbooks", "📐 Factors", "🌍 Asset classes",
                    "📄 Every page", "🔤 Glossary"])
    with tabs[0]:
        _navigation_tab(labels)
    with tabs[1]:
        _day_tab()
    with tabs[2]:
        _playbooks_tab()
    with tabs[3]:
        _factors_tab()
    with tabs[4]:
        _asset_classes_tab()
    with tabs[5]:
        _pages_tab(labels)
    with tabs[6]:
        _glossary_tab()
