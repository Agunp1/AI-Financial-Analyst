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
    ratings = _load("day77_current_ratings.csv")
    analytics = _load("day76c_asset_analytics.csv")
    us = _load("day76_us_fundamental_scores.csv")
    clients = BASE_DIR / "advisory_clients.json"
    out["Stocks rated"] = len(ratings) if not ratings.empty else "—"
    if not us.empty:
        out["US companies scored"] = f"{len(us):,}"
    out["Instruments tracked"] = len(analytics) if not analytics.empty else "—"
    out["Clients (sample)"] = len(json.loads(clients.read_text())["clients"]) if clients.exists() else "—"
    out["Rule & formula tests"] = _count_tests()
    live = _load("day75_live_instrument_prices.csv")
    out["Data as of"] = (pd.to_datetime(live["as_of_date"].dropna().max()).strftime("%d %b %Y")
                         if not live.empty else "sample")
    return out


def render_home() -> None:
    st.markdown(
        """
        <div class="vt-hero">
          <div class="vt-eyebrow">VITTANTRA</div>
          <div class="vt-hero-title">Investment research you can trust — every number traced, every decision human.</div>
          <div class="vt-hero-sub">One platform for the analyst, the equity researcher, the portfolio manager, the risk
          team and the advisor. Built on free public data, finance-textbook methods, and governance that never lets a
          model trade on its own.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    snapshot = _snapshot()
    # A wrapping stat strip instead of fixed columns, so labels and numbers never truncate on narrow screens
    short = {"US companies scored": "US companies", "Instruments tracked": "Instruments",
             "Clients (sample)": "Sample clients", "Rule & formula tests": "Automated tests"}
    st.markdown('<div class="vt-stats">' + "".join(
        f'<div class="vt-stat"><div class="vt-stat-label">{short.get(label, label)}</div>'
        f'<div class="vt-stat-value">{value}</div></div>' for label, value in snapshot.items()) + "</div>",
        unsafe_allow_html=True)

    st.markdown('<div class="vt-section">Six desks, one workflow</div>', unsafe_allow_html=True)
    for start in range(0, len(DESKS), 3):          # rows of three stay readable on laptop screens
        cols = st.columns(3)
        for col, (desk, page, text) in zip(cols, DESKS[start:start + 3]):
            with col:
                st.markdown(f'<div class="vt-card"><div class="vt-card-title">{desk}</div>'
                            f'<div class="vt-card-text">{text}</div></div>', unsafe_allow_html=True)
                st.button("Open", key=f"desk-{desk}", on_click=_go, args=(page,), width="stretch")

    st.markdown('<div class="vt-section">How it works</div>', unsafe_allow_html=True)
    steps = ["Free data", "Research & valuation", "Portfolio & risk", "Governance & approval", "Human decision"]
    st.markdown('<div class="vt-flow">' + "".join(
        f'<span class="vt-step">{s}</span>' + ('<span class="vt-arrow">→</span>' if i < len(steps) - 1 else "")
        for i, s in enumerate(steps)) + "</div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2])
    with left:
        highlights = _highlights()
        if highlights:
            st.markdown('<div class="vt-section">Today from the data</div>', unsafe_allow_html=True)
            cols = st.columns(2)
            for i, (label, value, note) in enumerate(highlights):
                with cols[i % 2]:
                    st.markdown(f'<div class="vt-card"><div class="vt-card-label">{label}</div>'
                                f'<div class="vt-card-value">{value}</div><div class="vt-card-text">{note}</div></div>',
                                unsafe_allow_html=True)
    with right:
        st.markdown('<div class="vt-section">Trust by design</div>', unsafe_allow_html=True)
        st.markdown(
            "- **Sourced:** SEC EDGAR filings, FRED, Yahoo Finance, official RSS — free and labelled\n"
            "- **Point in time:** a backtest only sees facts filed by that date\n"
            "- **Evidence-linked:** every research claim cites its file, field and value\n"
            "- **No invented answers:** the copilot says when the data does not cover a question\n"
            "- **Suitability first:** advice is checked against the client profile or IPS\n"
            "- **Human in the loop:** proposals wait for approval; automatic execution is always 0\n"
            f"- **Tested:** {snapshot['Rule & formula tests']} automated tests pin formulas and rules")

    st.markdown('<div class="vt-section">Guided tour (5 minutes)</div>', unsafe_allow_html=True)
    for i, (page, text) in enumerate(TOUR, start=1):
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"**{i}.** {text}")
        c2.button("Go", key=f"tour-{i}", on_click=_go, args=(page,), width="stretch")

