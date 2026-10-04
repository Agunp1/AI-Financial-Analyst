"""
Days 79–81 — Portfolio Manager page for the Vittantra app.

Tabs: Model portfolio (Day 79), Attribution (Day 80), What-if (Day 81).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import vittantra_cloud as cloud
import vittantra_theme as vt


BASE_DIR = Path(__file__).resolve().parent
BLUE, RED, GREY = vt.FOREST, vt.NEGATIVE, "#3B4F46"


@st.cache_data(show_spinner=False, ttl=60)
def _load(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_resource(show_spinner="Building the risk model…", ttl=600)
def _risk_model():
    import whatif_engine as we
    return we.RiskModel(we.load_prices(), we.load_fred())


def _model_portfolio() -> None:
    portfolio = _load("day79_model_portfolio.csv")
    summary = _load("day79_portfolio_summary.csv")
    sectors = _load("day79_sector_weights.csv")
    validation = _load("day79_validation_summary.csv")
    if portfolio.empty or summary.empty:
        st.info("Run `python portfolio_construction.py` to build the model portfolio.")
        return
    s = summary.iloc[0]
    c = st.columns(5)
    c[0].metric("Expected active return", f"{s['expected_active_return']:+.1%}",
                help="Grinold–Kahn alpha (IC × volatility × score) of the portfolio minus the benchmark, a year.")
    c[1].metric("Tracking error", f"{s['tracking_error']:.1%}", help=f"Budget {s['tracking_error_budget']:.0%}")
    c[2].metric("Information ratio", f"{s['information_ratio']:.2f}")
    c[3].metric("Holdings", int(s["holdings"]))
    c[4].metric("Checks", f"{int(validation['passed'].sum())}/{len(validation)}" if not validation.empty else "n/a")
    st.warning(f"Status: **{s['approval_status'].replace('_', ' ').title()}** — a proposal for the approval "
               "workflow. Nothing is executed automatically.")

    held = portfolio[portfolio["weight"] > 0].copy()
    left, right = st.columns([3, 2])
    with left:
        figure = go.Figure()
        figure.add_trace(go.Bar(y=held["ticker"], x=held["weight"] * 100, orientation="h", name="Portfolio",
                                marker_color=BLUE))
        figure.add_trace(go.Bar(y=held["ticker"], x=held["benchmark_weight"] * 100, orientation="h",
                                name="Benchmark", marker_color=GREY))
        figure.update_layout(barmode="group", height=max(360, 24 * len(held)), yaxis=dict(autorange="reversed"),
                             margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Weight (%)",
                             title="Weights vs equal-weight benchmark", legend=dict(orientation="h"))
        st.plotly_chart(figure, width="stretch")
    with right:
        if not sectors.empty:
            view = sectors.copy()
            for column in ("weight", "benchmark_weight", "active_weight", "risk_share"):
                view[column] = view[column] * 100
            st.markdown("**Sectors**")
            st.dataframe(view.rename(columns={"sector": "Sector", "weight": "Weight %", "benchmark_weight":
                                              "Benchmark %", "active_weight": "Active %", "risk_share": "Risk %"})
                         .round(1), width="stretch", hide_index=True)
        st.markdown(f"Volatility **{s['portfolio_volatility']:.1%}** vs benchmark {s['benchmark_volatility']:.1%} · "
                    f"beta **{s['beta_to_benchmark']:.2f}** · active share **{s['active_share']:.0%}** · turnover "
                    f"{s['turnover_traded']:.0%} (cost {s['estimated_cost']:.2%})")
    table = held[["ticker", "name", "sector", "rating", "score", "alpha", "weight", "active_weight", "risk_share"]
                 + [c for c in ("valuation_signal", "upside") if c in held.columns]].copy()
    for column in ("alpha", "weight", "active_weight", "risk_share", "upside"):
        if column in table:
            table[column] = table[column] * 100
    st.dataframe(table.rename(columns={"ticker": "Ticker", "name": "Name", "sector": "Sector", "rating": "Rating",
                                       "score": "Score", "alpha": "Alpha %", "weight": "Weight %",
                                       "active_weight": "Active %", "risk_share": "Risk share %",
                                       "valuation_signal": "Valuation", "upside": "Upside %"}).round(1),
                 width="stretch", hide_index=True)
    st.caption("Optimizer: maximize alpha minus active-risk penalty, with weights 0–8%, sector active weight "
               "±10%, tracking error ≤ 4%, no holding above 15% of portfolio risk and beta 0.9–1.1. Risk model: "
               "Ledoit–Wolf constant-correlation shrinkage covariance.")


def _attribution() -> None:
    summary = _load("day80_attribution_summary.csv")
    sectors = _load("day80_brinson_by_sector.csv")
    periods = _load("day80_brinson_by_period.csv")
    factors = _load("day80_factor_attribution.csv")
    if summary.empty:
        st.info("Run `python performance_attribution.py`.")
        return
    s = summary.iloc[0]
    c = st.columns(4)
    c[0].metric("Portfolio (cumulative)", f"{s['portfolio_cumulative']:+.1%}")
    c[1].metric("Benchmark (cumulative)", f"{s['benchmark_cumulative']:+.1%}")
    c[2].metric("Active return", f"{s['active_cumulative']:+.1%}")
    c[3].metric("Period", f"{s['start']} → {s['end']}")
    effects = {"Allocation": s["allocation_linked"], "Selection": s["selection_linked"],
               "Interaction": s["interaction_linked"], "Costs": s["costs_linked"]}
    figure = go.Figure(go.Waterfall(x=list(effects) + ["Active return"],
                                    measure=["relative"] * len(effects) + ["total"],
                                    y=[v * 100 for v in effects.values()] + [s["active_cumulative"] * 100],
                                    text=[f"{v:+.1%}" for v in effects.values()] + [f"{s['active_cumulative']:+.1%}"],
                                    increasing=dict(marker_color=BLUE), decreasing=dict(marker_color=RED),
                                    totals=dict(marker_color=vt.BRASS)))
    figure.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="%",
                         title="Brinson–Fachler attribution (Carino-linked)")
    st.plotly_chart(figure, width="stretch")
    left, right = st.columns(2)
    with left:
        st.markdown("**By sector**")
        view = sectors[["sector", "allocation", "selection", "interaction", "total"]].copy()
        view[["allocation", "selection", "interaction", "total"]] *= 100
        st.dataframe(view.rename(columns=str.title).round(2), width="stretch", hide_index=True)
    with right:
        if not factors.empty:
            totals = factors.filter(like="contribution_").sum() * 100
            totals.index = [i.replace("contribution_", "").title() for i in totals.index]
            totals["Stock-specific"] = factors["specific"].sum() * 100
            bar = go.Figure(go.Bar(x=totals.values, y=totals.index, orientation="h",
                                   marker_color=[BLUE if v >= 0 else RED for v in totals.values]))
            bar.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), title="By pillar (sum, %)")
            st.plotly_chart(bar, width="stretch")
    if not periods.empty:
        cumulative = pd.DataFrame({"Portfolio": (1 + periods["portfolio_return"]).cumprod() - 1,
                                   "Benchmark": (1 + periods["benchmark_return"]).cumprod() - 1})
        cumulative.index = pd.to_datetime(periods["date"])
        st.line_chart(cumulative * 100, height=260)
    st.caption("Allocation = sector bets, selection = stock picking within sectors. Pillar attribution: "
               "cross-sectional regression of returns on the five scores each period. Historical research "
               "results on the multi-factor backtest, not a promise of future returns.")


def _what_if() -> None:
    import whatif_engine as we

    try:
        model = _risk_model()
    except Exception as exc:  # no price history at all
        st.info(f"The what-if tool needs price history: run `python multi_asset_universe.py`. ({exc})")
        return
    portfolio = _load("day79_model_portfolio.csv")
    start = (portfolio[portfolio["weight"] > 0].set_index("ticker")["weight"].to_dict() if not portfolio.empty
             else {s: 0.2 for s in model.available()[:5]})
    st.markdown("Edit weights (%), add instruments, pick a scenario — risk recalculates instantly.")
    left, right = st.columns([2, 3])
    with left:
        extra = st.multiselect("Add instruments", [s for s in model.available() if s not in start],
                               default=[], placeholder="e.g. TLT, GC=F, HYG, BTC-USD")
        editor = pd.DataFrame({"Symbol": list(start) + extra,
                               "Current %": [start.get(s, 0.0) * 100 for s in list(start) + extra],
                               "What-if %": [start.get(s, 0.0) * 100 for s in list(start) + extra]})
        edited = st.data_editor(editor, hide_index=True, width="stretch", disabled=["Symbol", "Current %"],
                                column_config={"Current %": st.column_config.NumberColumn(format="%.2f"),
                                               "What-if %": st.column_config.NumberColumn(format="%.2f", min_value=-100.0,
                                                                                         max_value=100.0)},
                                key="whatif-editor")
        total = edited["What-if %"].sum()
        st.caption(f"What-if weights add to {total:.1f}%" + (" (scaled to 100% for risk)" if abs(total - 100) > 0.05
                                                              else ""))
        value = st.number_input("Portfolio value ($)", min_value=10_000.0, value=1_000_000.0, step=100_000.0)
    with right:
        choice = st.selectbox("Scenario", list(we.SCENARIOS) + ["Custom"])
        base = we.SCENARIOS.get(choice, {})
        shocks = {}
        cols = st.columns(3)
        for i, (key, (label, _, kind)) in enumerate(we.FACTORS.items()):
            default = float(base.get(key, 0.0))
            if kind == "return":
                shocks[key] = cols[i % 3].slider(label, -60, 60, int(round(default * 100)), key=f"s-{key}",
                                                 disabled=choice != "Custom") / 100
            else:
                shocks[key] = cols[i % 3].slider(label, -3.0, 8.0, default, 0.1, key=f"s-{key}",
                                                 disabled=choice != "Custom")
    current = {r["Symbol"]: r["Current %"] / 100 for _, r in edited.iterrows() if r["Current %"]}
    proposed = {r["Symbol"]: r["What-if %"] / 100 for _, r in edited.iterrows() if r["What-if %"]}
    if total > 0:
        proposed = {k: v * 100 / total for k, v in proposed.items()}
    table = we.compare(model, current, proposed, shocks, value)
    shown = table.copy()

    def delta(column, fmt):
        change = table.loc["Change", column]
        return None if pd.isna(change) or abs(change) < 1e-9 else fmt.format(change)

    c = st.columns(4)
    c[0].metric("Volatility (a year)", f"{table.loc['What-if', 'volatility_annual']:.1%}",
                delta("volatility_annual", "{:+.2%}"), delta_color="inverse")
    c[1].metric("1-day 99% VaR", f"${table.loc['What-if', 'var99_1d_parametric']:,.0f}",
                delta("var99_1d_parametric", "{:+,.0f}"), delta_color="inverse")
    c[2].metric("Beta to S&P 500", f"{table.loc['What-if', 'beta_spy']:.2f}",
                delta("beta_spy", "{:+.2f}"), delta_color="off")
    pnl_value = table.loc["What-if", "scenario_pnl"]
    c[3].metric(f"Scenario P&L: {choice}", "n/a" if pd.isna(pnl_value) else f"${pnl_value:,.0f}",
                delta("scenario_pnl", "{:+,.0f}"))
    pnl = we.scenario_pnl(model, proposed, shocks, value)
    risk = we.portfolio_risk(model, proposed, value)
    left, right = st.columns(2)
    with left:
        if pnl["pnl"].notna().any():
            fig = go.Figure(go.Bar(x=pnl["pnl"], y=pnl["symbol"], orientation="h",
                                   marker_color=[BLUE if v >= 0 else RED for v in pnl["pnl"].fillna(0)]))
            fig.update_layout(height=max(300, 22 * len(pnl)), margin=dict(l=10, r=10, t=40, b=10),
                              title="Scenario P&L by holding ($)", yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Not enough overlapping daily history to estimate factor sensitivities.")
    with right:
        shares = risk.get("risk_shares")
        if shares is not None:
            shares = shares.sort_values(ascending=False)
            fig = go.Figure(go.Bar(x=shares.values * 100, y=shares.index, orientation="h", marker_color=BLUE))
            fig.add_vline(x=15, line_dash="dash", line_color=RED, annotation_text="15% cap")
            fig.update_layout(height=max(300, 22 * len(shares)), margin=dict(l=10, r=10, t=40, b=10),
                              title="Share of portfolio risk (%)", yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")
    with st.expander("Before / after detail"):
        st.dataframe(shown.round(4), width="stretch")
        if risk.get("missing"):
            st.caption("No price history for: " + ", ".join(risk["missing"]))
    rationale = st.text_input("Rationale for the proposal", key="whatif-rationale")
    if not cloud.is_owner():
        cloud.owner_only_note("send proposals to the approval queue")
    elif st.button("Send what-if to the approval queue", disabled=not rationale.strip()):
        metrics = {k: float(v) for k, v in table.loc["What-if"].items() if pd.notna(v)}
        we.save_proposal(proposed, rationale, choice, metrics)
        cloud.persist(we.BASE_DIR / we.PROPOSALS, "What-if proposal (pending human approval)")
        st.success("Saved as a ticket with status PENDING HUMAN APPROVAL. Nothing was executed.")
    st.caption(f"Risk model: {len(model.returns)} observations, Ledoit–Wolf shrinkage {model.shrinkage:.2f}. "
               "Scenario P&L = Σ factor beta × shock (linear; ignores convexity and crisis correlation changes). "
               "Built-in scenarios are hypothetical, sized roughly like past episodes.")


def render_portfolio_manager() -> None:
    st.markdown("### Portfolio Manager")
    st.caption("Research → portfolio → attribution → what-if. Proposals go to human approval; nothing executes.")
    tabs = st.tabs(["Model portfolio", "Attribution", "What-if"])
    with tabs[0]:
        _model_portfolio()
    with tabs[1]:
        _attribution()
    with tabs[2]:
        _what_if()
