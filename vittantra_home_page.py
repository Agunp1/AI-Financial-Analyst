"""
Day 87b — Home page: the Vittantra story, live highlights and a guided tour.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent

DESKS = [
    ("Investment Analyst", "Markets",
     "Every asset class, the economic dashboard, what moved each market and the headlines behind it."),
    ("Equity Research", "Research",
     "SEC point-in-time fundamentals, five-pillar ratings, DCF / residual income / DDM valuation and "
     "evidence-linked research notes."),
    ("Portfolio Management", "Portfolio Manager",
     "Signal → expected alpha → optimizer within a tracking-error budget, Brinson attribution and what-if."),
    ("Portfolio Risk", "Risk Intelligence",
     "VaR and stress tests, Euler risk budgets, governance, remediation and dual-approval workflow."),
    ("Advisory", "Advisory",
     "Risk questionnaire and IPS, capital market assumptions, suitability checks and Monte Carlo goal plans."),
    ("Private Equity / VC", "Academy",
     "A small fund's analyst desk: deal screening, term sheets and waterfalls, LBOs, fund math and mock interviews."),
]

TOUR = [
    ("My Portfolio", "Build your own portfolio (or start from a 60/40 template) and see its risk like a professional."),
    ("Guide", "New to Vittantra? The Guide explains every page, how professionals pick factors, and each asset class."),
    ("Markets", "Start like a desk analyst: open the World Brief — this week's data moves next to the headlines."),
    ("Research", "Open Research → Multi-factor ratings: which pillars actually predict returns (IC)."),
    ("Research", "Then Valuation & reports: pick a stock and read its evidence-linked note and reverse DCF."),
    ("Portfolio Manager", "See the ratings turned into a model portfolio, its attribution, and run a what-if crash."),
    ("Advisory", "Fill in the client questionnaire and watch the allocation, suitability and goal odds update."),
    ("Copilot", "Ask the copilot anything — it answers only from Vittantra's data, with citations."),
    ("Academy", "Finally, do the job: the Work Desk gives you each role's daily task and a CFA Level II item set."),
]


def _go(page: str) -> None:
    st.session_state["nav"] = page


def _load(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _count_tests() -> int:
    return sum(len(re.findall(r"\n\s+def test_", Path(p).read_text())) for p in glob.glob(str(BASE_DIR / "test_*.py")))


def _highlights() -> list:
    items = []
    ratings = _load("day77_current_ratings.csv")
    if not ratings.empty and "composite_ic_weighted" in ratings:
        top = ratings.sort_values("composite_ic_weighted", ascending=False).iloc[0]
        items.append(("Top-rated stock", f"{top['ticker']} · {top['composite_ic_weighted']:.0f}/100",
                      f"{top['name']}, strongest pillar: {top['strongest_pillar']}"))
    valuation = _load("day78_valuation.csv")
    if not valuation.empty and "implied_growth" in valuation:
        v = valuation.dropna(subset=["implied_growth", "dcf_initial_growth"])
        if len(v):
            gap = (v["implied_growth"] - v["dcf_initial_growth"]).idxmax()
            r = v.loc[gap]
            items.append(("Highest expectations priced in", f"{r['ticker']} needs {r['implied_growth']:.0%} growth",
                          f"vs {r['dcf_initial_growth']:.0%} recently (reverse DCF)"))
    portfolio = _load("day79_portfolio_summary.csv")
    if not portfolio.empty:
        s = portfolio.iloc[0]
        items.append(("Model portfolio", f"IR {s['information_ratio']:.2f}",
                      f"{s['expected_active_return']:+.1%} expected active return at {s['tracking_error']:.1%} "
                      "tracking error"))
    moves = _load("day76d_factor_moves.csv")
    if not moves.empty:
        r = moves[(moves["factor"] == "interest_rates") & (moves["window"] == "1 month")]
        if len(r):
            items.append(("10Y Treasury, 1 month", f"{r['move'].iloc[0] * 100:+.0f} bp",
                          "rate move feeding every bond and equity valuation"))
    return items


def _snapshot() -> dict:
    out = {}
    us = _load("day76_us_fundamental_scores.csv")
    analytics = _load("day76c_asset_analytics.csv")
    ratings = _load("day77_current_ratings.csv")
    out["US companies covered"] = f"{len(us):,}" if not us.empty else "—"
    out["Instruments"] = len(analytics) if not analytics.empty else "—"
    out["Rated stocks"] = len(ratings) if not ratings.empty else "—"
    out["Asset classes"] = analytics["asset_class"].nunique() if not analytics.empty else "—"
    out["Rule & formula tests"] = _count_tests()
    return out


OVERVIEW = [("Equities", ["SPY", "QQQ", "IWM", "EFA", "EEM"]), ("Rates & credit", ["TLT", "AGG", "LQD", "HYG"]),
            ("FX", ["DX-Y.NYB", "EURUSD=X", "USDJPY=X"]), ("Commodities", ["GC=F", "CL=F", "HG=F"]),
            ("Real assets & alternatives", ["VNQ", "PSP"]), ("Digital assets", ["BTC-USD", "ETH-USD"])]


def _market_overview() -> None:
    data = _load("day76c_asset_analytics.csv")
    if data.empty:
        return
    data = data.set_index("symbol")
    rows = []
    for group, symbols in OVERVIEW:
        for s in symbols:
            if s in data.index:
                r = data.loc[s]
                rows.append({"Class": group, "Instrument": r["name"], "Symbol": s, "Last": r["price"],
                             "1D %": r["return_1d"] * 100, "1M %": r["return_1m"] * 100,
                             "12M %": r["return_12m"] * 100, "Volatility (a year) %": r["volatility_1y"] * 100})
    st.markdown('<div class="vt-section">Market overview</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"Last": st.column_config.NumberColumn(format="%.2f"),
                                "1D %": st.column_config.NumberColumn(format="%+.2f"),
                                "1M %": st.column_config.NumberColumn(format="%+.1f"),
                                "12M %": st.column_config.NumberColumn(format="%+.1f"),
                                "Volatility (a year) %": st.column_config.NumberColumn(format="%.1f")})
    st.caption("Free market data, may be delayed. Full coverage: Markets.")


def render_home() -> None:
    import vittantra_cloud as cloud
    import vittantra_welcome
    vittantra_welcome.render_welcome()
    signed_in = cloud.current_user() if cloud.cloud_mode() else True
    if not signed_in:
        st.markdown('<div class="vt-lede">Investment research, portfolio construction and risk management on public '
                    'data — every figure sourced, every decision approved by a person.</div>',
                    unsafe_allow_html=True)
    snapshot = _snapshot()
    st.markdown('<div class="vt-stats">' + "".join(
        f'<div class="vt-stat"><div class="vt-stat-label">{label}</div>'
        f'<div class="vt-stat-value">{value}</div></div>' for label, value in snapshot.items()
        if label != "Rule & formula tests") + "</div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2])
    with left:
        _market_overview()
    with right:
        highlights = _highlights()
        if highlights:
            st.markdown('<div class="vt-section">Research highlights</div>', unsafe_allow_html=True)
            for label, value, note in highlights:
                st.markdown(f'<div class="vt-card"><div class="vt-card-label">{label}</div>'
                            f'<div class="vt-card-value">{value}</div><div class="vt-card-text">{note}</div></div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="vt-section">Workspaces</div>', unsafe_allow_html=True)
    for start in range(0, len(DESKS), 3):
        cols = st.columns(3)
        for col, (desk, page, text) in zip(cols, DESKS[start:start + 3]):
            with col:
                st.markdown(f'<div class="vt-card"><div class="vt-card-title">{desk}</div>'
                            f'<div class="vt-card-text">{text}</div></div>', unsafe_allow_html=True)
                st.button("Open", key=f"desk-{desk}", on_click=_go, args=(page,), width="stretch")

    with st.expander("Methodology and controls"):
        st.markdown(
            "- **Sources:** SEC EDGAR filings, FRED, Yahoo Finance and official RSS feeds — free and labelled.\n"
            "- **Point in time:** backtests use only facts filed by each date.\n"
            "- **Evidence-linked research:** every claim cites its file, field and value.\n"
            "- **No unsupported answers:** the copilot states when the data does not cover a question.\n"
            "- **Suitability:** advice is checked against the client profile or IPS.\n"
            "- **Human approval:** proposals wait for approval; automatic execution is always 0.\n"
            f"- **Testing:** {snapshot['Rule & formula tests']} automated tests pin formulas and rules.")
    with st.expander("Guided tour"):
        for i, (page, text) in enumerate(TOUR, start=1):
            c1, c2 = st.columns([6, 1])
            c1.markdown(f"**{i}.** {text}")
            c2.button("Go", key=f"tour-{i}", on_click=_go, args=(page,), width="stretch")
