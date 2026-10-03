"""
Days 82–84 — Advisory page for the Vittantra app (retail and institutional).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import advisory_engine as ae


BASE_DIR = Path(__file__).resolve().parent
PALETTE = ["#2E6BE6", "#5B8DEF", "#8FB3F5", "#0F9D58", "#34A853", "#7CC48F", "#F4B400", "#E5484D", "#B8860B",
           "#9AA4B2"]


@st.cache_data(show_spinner=False, ttl=60)
def _load(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=600)
def _market():
    cma = ae.capital_market_assumptions(BASE_DIR)
    cov = ae.sleeve_covariance(BASE_DIR)
    return cma, cov, cma.attrs["inflation"]


def _donut(weights: pd.Series, title: str):
    w = weights[weights > 0.001].sort_values(ascending=False)
    figure = go.Figure(go.Pie(labels=w.index, values=w.values, hole=0.55, sort=False,
                              marker=dict(colors=PALETTE[:len(w)]), textinfo="percent"))
    figure.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title=title, showlegend=True,
                         legend=dict(font=dict(size=11)))
    return figure


def _fan(projection: pd.DataFrame, target: float = 0.0):
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=projection["year"], y=projection["p90"], line=dict(width=0), mode="lines", showlegend=False,
                                hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=projection["year"], y=projection["p10"], fill="tonexty", line=dict(width=0), mode="lines",
                                fillcolor="rgba(46,107,230,0.18)", name="10th–90th percentile"))
    figure.add_trace(go.Scatter(x=projection["year"], y=projection["p50"], line=dict(color="#2E6BE6", width=3),
                                mode="lines", name="Median"))
    if target > 0:
        figure.add_hline(y=target, line_dash="dash", line_color="#E5484D", annotation_text="Goal")
    figure.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), title="Projected wealth (today's money)",
                         xaxis_title="Years", yaxis_title="$",
                         legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1))
    return figure


def _clients_tab() -> None:
    profiles = _load(ae.OUT["profiles"])
    reports = _load(ae.OUT["reports"])
    projections = _load(ae.OUT["projections"])
    goals = _load(ae.OUT["goals"])
    if profiles.empty:
        st.info("Run `python advisory_engine.py` to build the client book.")
        return
    view = profiles[["client_id", "name", "type", "profile_name", "expected_return", "volatility", "suitability"]]
    view = view.merge(goals[["client_id", "probability"]], on="client_id")
    for column in ("expected_return", "volatility", "probability"):
        view[column] = view[column] * 100
    st.dataframe(view.rename(columns={"client_id": "ID", "name": "Client", "type": "Type",
                                      "profile_name": "Profile", "expected_return": "Expected return %",
                                      "volatility": "Volatility %", "suitability": "Suitability",
                                      "probability": "Goal probability %"}).round(1),
                 width="stretch", hide_index=True)
    client_id = st.selectbox("Client", profiles["client_id"],
                             format_func=lambda c: profiles.set_index("client_id").at[c, "name"])
    row = profiles.set_index("client_id").loc[client_id]
    weights = pd.Series({s: row.get(f"w_{s}", 0.0) for s in ae.SLEEVES}).fillna(0.0)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(_donut(weights, "Recommended allocation"), width="stretch")
    with right:
        goal = goals.set_index("client_id").loc[client_id]
        st.plotly_chart(_fan(projections[projections["client_id"] == client_id], float(goal["target_real"])),
                        width="stretch")
    report = reports.set_index("client_id").at[client_id, "report"]
    shown = report.replace("$", "\\$").replace("\n## ", "\n#### ").replace("# ", "### ", 1)
    with st.container(border=True):
        st.markdown(shown)
    st.download_button("Download client report (Markdown)", report, file_name=f"vittantra_proposal_{client_id}.md")


def _new_client_tab() -> None:
    st.markdown("Answer the questionnaire; the profile, allocation, suitability checks and goal projection update "
                "as you go.")
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Client name", "New client")
    horizon = c2.slider("Investment horizon (years)", 1, 40, 15)
    goal = c3.text_input("Goal", "Retirement")
    c1, c2, c3 = st.columns(3)
    wealth = c1.number_input("Current investments ($)", 1_000.0, 1e9, 50_000.0, 1_000.0)
    contribution = c2.number_input("Annual saving ($)", 0.0, 1e8, 6_000.0, 500.0)
    withdrawal = c3.number_input("Annual withdrawal ($)", 0.0, 1e8, 0.0, 500.0)
    c1, c2, c3 = st.columns(3)
    target = c1.number_input("Goal amount in today's money ($, 0 = none)", 0.0, 1e10, 300_000.0, 10_000.0)
    reaction = c2.radio("If your investments fell 20% in a year, you would…", list(ae.LOSS_TOLERANCE), index=1)
    experience = c3.radio("Investment experience", list(ae.EXPERIENCE_SCORE), index=1)
    c1, c2 = st.columns(2)
    income = c1.selectbox("Income", list(ae.INCOME_SCORE), index=1)
    liquidity = c2.number_input("Cash needed in the next 12 months ($)", 0.0, 1e9, 0.0, 500.0)
    client = {"client_id": "NEW", "type": "retail", "name": name, "horizon_years": int(horizon), "goal": goal,
              "wealth": wealth, "annual_contribution": contribution, "annual_withdrawal": withdrawal,
              "goal_target_real": target, "income_stability": income, "loss_reaction": reaction,
              "experience": experience, "liquidity_need_12m": liquidity}
    try:
        cma, cov, inflation = _market()
    except FileNotFoundError:
        st.info("Run `python multi_asset_universe.py` first (yields and ETF history).")
        return
    mu = cma.set_index("sleeve")["expected_return"]
    profile = ae.retail_profile(client)
    weights = ae.recommend(client, profile, mu, cov)
    stats = ae.portfolio_stats(weights, mu, cov)
    results = ae.suitability(client, profile, weights, mu, cov)
    paths = ae.simulate_wealth(wealth, contribution, withdrawal, int(horizon), stats["expected_return"],
                               stats["volatility"], inflation, 5000, ae.ASSUMPTIONS["seed"])
    probability = ae.goal_probability(paths, target, withdrawal)
    m = st.columns(4)
    m[0].metric("Risk profile", ae.PROFILES[profile["profile"]]["name"],
                help=f"Willingness {profile['willingness']}/5, capacity {profile['capacity']}/5")
    m[1].metric("Expected return", f"{stats['expected_return']:.1%}")
    m[2].metric("Bad year (1 in 20)", f"−{stats['bad_year_loss']:.0%}")
    m[3].metric("Goal probability", f"{probability:.0%}")
    st.caption(profile["profile_note"])
    left, right = st.columns(2)
    with left:
        st.plotly_chart(_donut(weights, "Recommended allocation"), width="stretch")
    with right:
        projection = pd.DataFrame({"year": range(int(horizon) + 1), "p10": np.percentile(paths, 10, axis=0),
                                   "p50": np.percentile(paths, 50, axis=0), "p90": np.percentile(paths, 90, axis=0)})
        st.plotly_chart(_fan(projection, target), width="stretch")
    st.markdown(f"**Suitability: {ae.suitability_verdict(results)}**")
    st.dataframe(results[["rule", "passed", "detail", "basis"]], width="stretch", hide_index=True)
    if st.button("Save to my client book"):
        data = json.loads(ae.CLIENTS_FILE.read_text())
        client["client_id"] = f"U{sum(c['client_id'].startswith('U') for c in data['clients']) + 1}"
        data["clients"].append(client)
        ae.CLIENTS_FILE.write_text(json.dumps(data, indent=2))
        st.success(f"Saved as {client['client_id']}. Run `python advisory_engine.py` to refresh the client book.")


def _allocations_tab() -> None:
    allocations = _load(ae.OUT["allocations"])
    cma = _load(ae.OUT["cma"])
    if allocations.empty:
        st.info("Run `python advisory_engine.py`.")
        return
    figure = go.Figure()
    for i, sleeve in enumerate(ae.SLEEVES):
        if allocations[sleeve].sum() > 0:
            figure.add_trace(go.Bar(x=allocations["profile_name"], y=allocations[sleeve] * 100, name=sleeve,
                                    marker_color=PALETTE[i % len(PALETTE)]))
    figure.update_layout(barmode="stack", height=380, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="%",
                         title="Model allocation by risk profile")
    st.plotly_chart(figure, width="stretch")
    summary = allocations[["profile_name", "expected_return", "volatility", "bad_year_loss", "equity_share"]].copy()
    summary[["expected_return", "volatility", "bad_year_loss", "equity_share"]] *= 100
    st.dataframe(summary.rename(columns={"profile_name": "Profile", "expected_return": "Expected return %",
                                         "volatility": "Volatility %", "bad_year_loss": "Bad year (1 in 20) %",
                                         "equity_share": "Equity %"}).round(1), width="stretch", hide_index=True)
    st.markdown("**Capital market assumptions** (building blocks from today's yields and spreads)")
    view = cma[["sleeve", "ticker", "expected_return", "volatility", "volatility_past_year", "volatility_long_run",
                "method"]].copy()
    for column in ("expected_return", "volatility", "volatility_past_year", "volatility_long_run"):
        view[column] = view[column] * 100
    st.dataframe(view.rename(columns={"sleeve": "Sleeve", "ticker": "Example fund", "expected_return":
                                      "Expected return %", "volatility": "Volatility used %",
                                      "volatility_past_year": "Past year %", "volatility_long_run": "Long run %",
                                      "method": "Method"}).round(2), width="stretch", hide_index=True)
    st.caption("Optimizer: highest expected return at each target volatility, with equity caps, minimum cash and "
               "policy ranges per sleeve. Volatility = 50% past year + 50% long-run level; correlations from one "
               "year of daily data.")


def _goal_planner_tab() -> None:
    try:
        cma, cov, inflation = _market()
    except FileNotFoundError:
        st.info("Run `python multi_asset_universe.py` first.")
        return
    mu = cma.set_index("sleeve")["expected_return"]
    c1, c2, c3, c4 = st.columns(4)
    level = c1.select_slider("Risk profile", options=list(ae.PROFILES), value=3,
                             format_func=lambda k: ae.PROFILES[k]["name"])
    years = c2.slider("Years", 1, 50, 20, key="gp-years")
    start = c3.number_input("Starting amount ($)", 0.0, 1e10, 100_000.0, 5_000.0, key="gp-start")
    flow = c4.number_input("Annual saving (+) or withdrawal (−) ($)", -1e8, 1e8, 5_000.0, 1_000.0, key="gp-flow")
    target = st.number_input("Goal in today's money ($, 0 = 'money lasts')", 0.0, 1e10, 400_000.0, 10_000.0)
    p = ae.PROFILES[level]
    weights = ae.optimize_allocation(mu, cov, p["target_vol"], p["max_equity"], p["min_cash"])
    stats = ae.portfolio_stats(weights, mu, cov)
    paths = ae.simulate_wealth(start, max(flow, 0), max(-flow, 0), years, stats["expected_return"],
                               stats["volatility"], inflation, 5000, ae.ASSUMPTIONS["seed"])
    probability = ae.goal_probability(paths, target, max(-flow, 0))
    m = st.columns(4)
    m[0].metric("Chance of success", f"{probability:.0%}")
    m[1].metric("Median outcome", f"${np.median(paths[:, -1]):,.0f}")
    m[2].metric("Poor case (10th pct)", f"${np.percentile(paths[:, -1], 10):,.0f}")
    m[3].metric("Expected return / volatility", f"{stats['expected_return']:.1%} / {stats['volatility']:.0%}")
    projection = pd.DataFrame({"year": range(years + 1), "p10": np.percentile(paths, 10, axis=0),
                               "p50": np.percentile(paths, 50, axis=0), "p90": np.percentile(paths, 90, axis=0)})
    st.plotly_chart(_fan(projection, target), width="stretch")
    st.caption(f"5,000 simulated lognormal market paths; amounts in today's money (inflation {inflation:.1%} from "
               "the 10-year breakeven). Estimates, not guarantees.")


def render_advisory() -> None:
    st.markdown("### Advisory — Retail & Institutional")
    st.caption("Know the client → recommend → check suitability → plan the goal → report. Proposals need client "
               "and advisor approval; nothing executes.")
    tabs = st.tabs(["Clients", "New client questionnaire", "Model allocations", "Goal planner"])
    with tabs[0]:
        _clients_tab()
    with tabs[1]:
        _new_client_tab()
    with tabs[2]:
        _allocations_tab()
    with tabs[3]:
        _goal_planner_tab()
