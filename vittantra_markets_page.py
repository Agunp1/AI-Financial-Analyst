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
    ("World Brief", "world"),
    ("Overview", None),
    ("Macro & Economy", "macro"),
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


FACTOR_LABELS = {
    "equity_market": "Equity market", "interest_rates": "Rates", "inflation_expectations": "Inflation exp.",
    "credit_spreads": "Credit", "us_dollar": "US dollar", "oil": "Oil",
}


def _macro_and_economy() -> None:
    economy = _load("day76c_economic_dashboard.csv")
    if not economy.empty:
        st.markdown("**Economic dashboard** — the regular releases professionals track")
        for category, group in economy.groupby("category", sort=False):
            st.markdown(f"*{category}*")
            view = group[["indicator", "latest", "previous", "change", "year_ago", "release_period"]].rename(
                columns={"indicator": "Indicator", "latest": "Latest", "previous": "Previous", "change": "Change",
                         "year_ago": "A year ago", "release_period": "Period"})
            st.dataframe(view.round(2), width="stretch", hide_index=True)
    else:
        st.info("Run `python multi_asset_universe.py` to load the economic releases.")

    moves = _load("day76d_factor_moves.csv")
    stories = _load("day76d_macro_narrative.csv")
    betas = _load("day76d_macro_betas.csv")
    if moves.empty:
        st.info("Run `python macro_drivers.py` to see what moved each asset class.")
        return
    st.markdown("**Macro factor moves**")
    pivot = moves.pivot(index="label", columns="window", values="move")[["1 week", "1 month", "3 months"]]
    st.dataframe(pivot.round(4), width="stretch")
    st.caption("Rates, inflation expectations and credit are changes in percentage points; equity, dollar and oil "
               "are returns.")
    if not stories.empty:
        st.markdown("**What moved each asset class over the last month**")
        for row in stories.itertuples():
            st.markdown(f"- **{row.asset_class}** — {row.story}")
    if not betas.empty:
        reps = betas[betas["symbol"].isin(stories["symbol"])] if not stories.empty else betas.head(20)
        columns = [f"std_beta_{k}" for k in FACTOR_LABELS if f"std_beta_{k}" in reps.columns]
        matrix = reps.set_index("name")[columns].rename(columns=lambda c: FACTOR_LABELS[c.replace("std_beta_", "")])
        figure = go.Figure(go.Heatmap(z=matrix.to_numpy() * 100, x=matrix.columns, y=matrix.index,
                                      colorscale="RdBu", zmid=0, colorbar=dict(title="% per 1 s.d.")))
        figure.update_layout(height=max(320, 22 * len(matrix)), margin=dict(l=10, r=10, t=30, b=10),
                             title="Sensitivity to a typical daily factor move")
        st.plotly_chart(figure, width="stretch")
        st.caption("Blue = rises when the factor rises; red = falls. Estimated by regression on one year of "
                   "daily data.")


def _world_brief() -> None:
    brief = _load("day78b_brief.csv")
    headlines = _load("day78b_headlines.csv")
    calendar = _load("day78b_calendar.csv")
    if brief.empty:
        st.info("Run `python world_brief.py` to load this week's headlines and calendar.")
        return
    st.markdown("**This week by theme** — the data move next to the headlines that could explain it")
    for row in brief.itertuples():
        with st.expander(f"{row.theme} · {row.data_move} · {row.headline_count} headlines",
                         expanded=row.Index < 3 and row.headline_count > 0):
            if row.headline_count and not headlines.empty:
                related = headlines[headlines["themes"].fillna("").str.contains(row.theme, regex=False)].head(6)
                for h in related.itertuples():
                    when = pd.to_datetime(h.published).strftime("%a %d %b %H:%M") if pd.notna(h.published) else ""
                    st.markdown(f"- [{h.title}]({h.link}) — *{h.source}*, {when}")
            else:
                st.caption("No headlines on this theme this week.")
    st.caption("Headlines are possible drivers to check, not proven causes. Themes are assigned by keyword "
               "rules, so read the article before citing it.")
    if not calendar.empty:
        st.markdown("**Coming up**")
        view = calendar[["date", "event", "indicator", "latest", "previous", "period"]].rename(columns={
            "date": "Date", "event": "Event", "indicator": "Indicator", "latest": "Latest", "previous": "Previous",
            "period": "Latest period"})
        st.dataframe(view.round(2), width="stretch", hide_index=True)
    if not headlines.empty:
        with st.expander(f"All headlines ({len(headlines)})"):
            st.dataframe(headlines[["published", "source", "title", "themes"]], width="stretch", hide_index=True,
                         column_config={"published": st.column_config.DatetimeColumn("Published",
                                                                                    format="ddd D MMM, HH:mm")})
    st.caption("Sources: Federal Reserve, ECB, Bank of England, SEC, BLS, BEA, CNBC, MarketWatch and Yahoo Finance "
               "RSS feeds (free); FOMC dates from the Federal Reserve; release dates from FRED.")


def _real_estate(market: pd.DataFrame) -> None:
    economy = _load("day76c_economic_dashboard.csv")
    cre = economy[economy["category"] == "Commercial real estate"] if not economy.empty else economy
    if not cre.empty:
        st.markdown("**Commercial real estate indicators**")
        st.dataframe(cre[["indicator", "latest", "previous", "year_ago", "release_period"]].round(2),
                     width="stretch", hide_index=True)
    subset = market[market["asset_class"] == "Real Estate"]
    by_type = subset.groupby("sub_class").agg(companies=("symbol", "count"), median_1m=("return_1m", "median"),
                                             median_12m=("return_12m", "median"),
                                             median_vol=("volatility_1y", "median")).reset_index()
    for column in ("median_1m", "median_12m", "median_vol"):
        by_type[column] = by_type[column] * 100
    st.markdown("**By property type**")
    st.dataframe(by_type.rename(columns={"sub_class": "Property type", "companies": "Companies",
                                         "median_1m": "Median 1M %", "median_12m": "Median 12M %",
                                         "median_vol": "Median vol %"}).round(1),
                 width="stretch", hide_index=True)
    _instrument_table(subset)
    st.caption("Hotels reprice nightly, so they react fastest to travel demand and the economy; motels and "
               "economy hotels are covered through the listed brand owners (Wyndham, Choice). Individual "
               "REITs are also scored on fundamentals in Research → All US-listed stocks.")


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
            if asset_class == "world":
                _world_brief()
            elif asset_class is None:
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
            elif asset_class == "macro":
                _macro_and_economy()
            elif asset_class == "Fixed Income":
                _rates_and_credit(analytics)
            elif asset_class == "Real Estate":
                _real_estate(market)
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
