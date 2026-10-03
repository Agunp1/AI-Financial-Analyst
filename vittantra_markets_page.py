"""
Day 76c — Markets page for the Vittantra app (all asset classes).

Reads the day76c_* files written by multi_asset_universe.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent

TABS = [
    ("Overview", None),
    ("Rates & Credit", "Fixed Income"),
    ("FX", "FX"),
    ("Commodities", "Commodity"),
    ("Digital Assets", "Digital Asset"),
    ("Real Estate", "Real Estate"),
    ("Alternatives", "Alternative"),
    ("Equity Indices", "Equity"),
]

PERCENT_COLUMNS = {
    "return_1m": "1M", "return_12m": "12M", "momentum_12_1": "12-1 mom.",
    "volatility_1y": "Volatility", "max_drawdown_1y": "Max DD (1Y)", "trend_vs_200d": "vs 200-day",
}


@st.cache_data(show_spinner=False, ttl=60)
def _load(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _instrument_table(df: pd.DataFrame) -> None:
    table = df[["symbol", "name", "sub_class", "price", *PERCENT_COLUMNS, "beta_to_spx", "as_of"]].copy()
    for column in PERCENT_COLUMNS:
        table[column] = pd.to_numeric(table[column], errors="coerce") * 100
    table = table.rename(columns={**PERCENT_COLUMNS, "symbol": "Symbol", "name": "Name",
                                  "sub_class": "Segment", "price": "Price",
                                  "beta_to_spx": "Beta (S&P)", "as_of": "As of"})
    config = {label: st.column_config.NumberColumn(label, format="%.1f%%") for label in PERCENT_COLUMNS.values()}
    config["Price"] = st.column_config.NumberColumn("Price", format="%.4g")
    config["Beta (S&P)"] = st.column_config.NumberColumn("Beta (S&P)", format="%.2f")
    st.dataframe(table, width="stretch", hide_index=True, column_config=config)


def _rates_and_credit(analytics: pd.DataFrame) -> None:
    curve = _load("day76c_yield_curve.csv")
    credit = _load("day76c_credit_spreads.csv")
    if not curve.empty:
        first = curve.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("10Y Treasury", f"{curve.set_index('maturity').get('yield_pct', {}).get('10Y', float('nan')):.2f}%")
        c2.metric("2s10s slope", f"{first.get('slope_2s10s_bp', float('nan')):.0f} bp")
        c3.metric("3M–10Y slope", f"{first.get('slope_3m10y_bp', float('nan')):.0f} bp",
                  help="Negative (inverted) has historically preceded US recessions.")
        c4.metric("10Y breakeven inflation", f"{first.get('breakeven_10y_pct', float('nan')):.2f}%")
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=curve["maturity"], y=curve["yield_pct"], mode="lines+markers",
                                    name=f"Latest ({curve['date'].max()})", line=dict(color="#2E6BE6", width=3)))
        if curve["yield_1y_ago_pct"].notna().any():
            figure.add_trace(go.Scatter(x=curve["maturity"], y=curve["yield_1y_ago_pct"], mode="lines+markers",
                                        name="1 year ago", line=dict(color="#9AA4B2", dash="dash")))
        figure.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Yield (%)",
                             title="US Treasury yield curve")
        st.plotly_chart(figure, width="stretch")
    if not credit.empty:
        st.markdown("**Credit spreads (option-adjusted, ICE BofA via FRED)**")
        table = credit[["segment", "spread_bp", "change_1y_bp", "percentile_in_history", "history_start"]].rename(
            columns={"segment": "Segment", "spread_bp": "Spread (bp)", "change_1y_bp": "1Y change (bp)",
                     "percentile_in_history": "Percentile in history", "history_start": "History from"})
        st.dataframe(table.round(0), width="stretch", hide_index=True)
        st.caption("Percentile 0 = tightest spread in the available history (credit looks expensive); "
                   "100 = widest (credit looks cheap).")
    st.markdown("**Bond ETFs**")
    _instrument_table(analytics[(analytics["asset_class"] == "Fixed Income")
                                & (analytics["source"] == "Yahoo Finance")])
    st.caption("Individual corporate bonds have no free market-wide prices; credit is covered by "
               "spread indices and bond ETFs.")


def render_markets() -> None:
    st.markdown("### Markets — All Asset Classes")
    analytics = _load("day76c_asset_analytics.csv")
    if analytics.empty:
        st.info("No multi-asset data yet. Run `python multi_asset_universe.py`.")
        return
    validation = _load("day76c_validation_summary.csv")
    summary = _load("day76c_asset_class_summary.csv")
    market = analytics[analytics["source"] == "Yahoo Finance"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Instruments", len(analytics))
    c2.metric("Asset classes", analytics["asset_class"].nunique())
    c3.metric("Latest price date", str(pd.to_datetime(market["as_of"], errors="coerce").max().date())
              if market["as_of"].notna().any() else "n/a")
    c4.metric("Data checks", f"{int(validation['passed'].sum())}/{len(validation)}" if not validation.empty else "n/a")

    tabs = st.tabs([label for label, _ in TABS])
    for tab, (label, asset_class) in zip(tabs, TABS):
        with tab:
            if asset_class is None:
                if not summary.empty:
                    view = summary.copy()
                    for column in ("median_return_1m", "median_return_12m", "median_volatility"):
                        view[column] = view[column] * 100
                    view = view.rename(columns={
                        "asset_class": "Asset class", "sub_class": "Segment", "instruments": "Instruments",
                        "median_return_1m": "Median 1M %", "median_return_12m": "Median 12M %",
                        "median_volatility": "Median vol %", "median_beta_to_spx": "Median beta"})
                    st.dataframe(view.round(2), width="stretch", hide_index=True)
                st.caption("Volatility is annualized with each instrument's own trading days "
                           "(crypto trades every day; stocks and bonds about 252 days).")
            elif asset_class == "Fixed Income":
                _rates_and_credit(analytics)
            else:
                subset = market[market["asset_class"] == asset_class]
                if asset_class == "FX":
                    carry = _load("day76c_fx_carry.csv")
                    if not carry.empty:
                        st.markdown("**FX carry** (interest earned for holding the pair long, "
                                    "from OECD 3-month rates)")
                        st.dataframe(carry[["pair", "base_rate_pct", "quote_rate_pct", "carry_long_pair_pct",
                                            "carry_to_vol", "rates_as_of"]].round(3),
                                     width="stretch", hide_index=True)
                _instrument_table(subset)
                if asset_class == "Real Estate":
                    st.caption("Individual REITs are scored on fundamentals in Research → All US-listed stocks.")
                if asset_class == "Alternative":
                    st.caption("Private assets publish no free data; these are listed proxies "
                               "(managers, BDCs, infrastructure, managed futures, volatility, real assets).")
    st.caption("Sources: Yahoo Finance and FRED (free; prices may be delayed). Research only.")
