"""
India market pages (Day 93): Markets (indices, sectors, Nifty 50 stocks,
economy, rupee, gold, gilts, REITs), the India view of Home and the sidebar
snapshot. Data: day93_* files from india_markets.py. Kept separate from the
US pages; amounts in INR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import india_markets as im
import vittantra_theme as vt


BASE_DIR = Path(__file__).resolve().parent
TICKER = [("^NSEI", "Nifty 50"), ("^BSESN", "Sensex"), ("^NSEBANK", "Bank Nifty"), ("^CNXIT", "Nifty IT"),
          ("^NSEMDCP50", "Midcap 50"), ("^INDIAVIX", "India VIX"), ("INR=X", "USD/INR"),
          ("GOLDBEES.NS", "Gold ETF")]
HEADLINE = [("^NSEI", "Nifty 50"), ("^BSESN", "Sensex"), ("^NSEBANK", "Bank Nifty"), ("^INDIAVIX", "India VIX"),
            ("INR=X", "USD/INR")]
MISSING = ("India market data arrives with the next scheduled refresh (it runs on GitHub, not in the browser). "
           "Run `python india_markets.py` to load it now.")


def load() -> Optional[pd.DataFrame]:
    path = BASE_DIR / im.OUTPUT_ANALYTICS
    return pd.read_csv(path) if path.exists() else None


def load_macro() -> pd.DataFrame:
    path = BASE_DIR / im.OUTPUT_MACRO
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_history() -> pd.DataFrame:
    path = BASE_DIR / im.OUTPUT_HISTORY
    return pd.read_csv(path, parse_dates=["date"]).set_index("date") if path.exists() else pd.DataFrame()


def _level(price: float) -> str:
    return f"{price:,.0f}" if price >= 1000 else f"{price:,.2f}"


def ticker_items():
    """(label, level text, 1-day move) for the top bar while India is selected."""
    data = load()
    if data is None:
        return []
    data = data.set_index("symbol")
    out = []
    for symbol, label in TICKER:
        if symbol in data.index and pd.notna(data.at[symbol, "price"]):
            out.append((label, _level(float(data.at[symbol, "price"])), data.at[symbol, "return_1d"]))
    return out


def sidebar_snapshot() -> None:
    data = load()
    if data is None:
        return
    data = data.set_index("symbol")
    st.caption("INDIA MARKETS TODAY")
    lines = []
    for symbol, label in TICKER[:7]:
        if symbol in data.index and pd.notna(data.at[symbol, "return_1d"]):
            move = float(data.at[symbol, "return_1d"])
            lines.append(f"{label} :{'green' if move >= 0 else 'red'}[{'▲' if move >= 0 else '▼'} {abs(move):.1%}]")
    st.markdown("  \n".join(lines))


def _headline(data: pd.DataFrame) -> None:
    rows = data.set_index("symbol")
    cols = st.columns(len(HEADLINE))
    for col, (symbol, label) in zip(cols, HEADLINE):
        if symbol in rows.index and pd.notna(rows.at[symbol, "price"]):
            move = rows.at[symbol, "return_1d"]
            col.metric(label, _level(float(rows.at[symbol, "price"])),
                       f"{move:+.2%}" if pd.notna(move) else None,
                       delta_color="inverse" if symbol in ("^INDIAVIX", "INR=X") else "normal")
        else:
            col.metric(label, "—")


def _index_chart(history: pd.DataFrame, symbol: str, name: str) -> Optional[go.Figure]:
    if symbol not in history:
        return None
    s = history[symbol].dropna().tail(260)
    if len(s) < 20:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s, name=name, line={"color": vt.INK, "width": 1.6}))
    full = history[symbol].dropna()
    sma = full.rolling(200).mean().reindex(s.index)
    fig.add_trace(go.Scatter(x=s.index, y=sma, name="200-day", line={"color": vt.BRASS, "width": 1, "dash": "dot"}))
    fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 10, "b": 10}, legend={"orientation": "h"},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": vt.INK})
    return fig


PERCENT = {c: st.column_config.NumberColumn(format="percent") for c in
           ["1 day", "1 month", "3 months", "12 months", "Volatility (1y)", "Max drawdown (1y)", "vs 200-day"]}


def _table(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={"name": "Name", "symbol": "Symbol", "sub_class": "Segment", "price": "Price (INR)",
                              "return_1d": "1 day", "return_1m": "1 month", "return_3m": "3 months",
                              "return_12m": "12 months", "volatility_1y": "Volatility (1y)",
                              "max_drawdown_1y": "Max drawdown (1y)", "trend_vs_200d": "vs 200-day",
                              "beta_to_nifty": "Beta to Nifty 50"})


COLUMNS = ["name", "symbol", "price", "return_1d", "return_1m", "return_3m", "return_12m", "volatility_1y",
           "max_drawdown_1y", "trend_vs_200d", "beta_to_nifty"]


def render_india_markets() -> None:
    st.markdown("### India Markets")
    st.markdown('<div class="vt-lede">NSE and BSE indices, sectors, Nifty 50 stocks, the rupee, gold, gilts, REITs '
                'and the Indian economy — separate from the US view. Prices in INR from Yahoo Finance (about 15 '
                'minutes delayed); economic data from FRED (OECD/IMF), monthly.</div>', unsafe_allow_html=True)
    data = load()
    if data is None:
        st.info(MISSING)
        return
    priced = data.dropna(subset=["price"])
    _headline(priced)
    st.caption(f"Prices as of {priced['as_of'].max()} · {len(priced)} of {len(data)} instruments priced")
    history = load_history()
    stocks = priced[priced["symbol"].isin([s for s, _, _ in im.NIFTY_50])]

    overview, stock_tab, economy, rupee, reits = st.tabs(
        ["Indices and sectors", "Nifty 50 stocks", "Economy", "Rupee, gold and gilts", "REITs and InvITs"])

    with overview:
        fig = _index_chart(history, "^NSEI", "Nifty 50")
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
        indices = priced[priced["sub_class"].isin(["Index", "Sector index"])]
        sectors = indices[indices["sub_class"] == "Sector index"].dropna(subset=["return_1m"])
        if len(sectors):
            sectors = sectors.sort_values("return_1m")
            bar = go.Figure(go.Bar(x=sectors["return_1m"], y=sectors["name"], orientation="h",
                                   marker_color=[vt.POSITIVE if v >= 0 else vt.NEGATIVE for v in sectors["return_1m"]]))
            bar.update_layout(height=340, margin={"l": 10, "r": 10, "t": 30, "b": 10}, xaxis_tickformat=".0%",
                              title="Sector indices · 1-month return", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", font={"color": vt.INK})
            st.plotly_chart(bar, width="stretch")
        st.dataframe(_table(indices[COLUMNS]), hide_index=True, width="stretch", column_config=PERCENT)

    with stock_tab:
        if stocks.empty:
            st.info("No Nifty 50 stock prices yet.")
        else:
            by_sector = (stocks.groupby("sub_class")
                         .agg(Stocks=("symbol", "count"), **{"Median 1 month": ("return_1m", "median"),
                                                              "Median 12 months": ("return_12m", "median")})
                         .reset_index().rename(columns={"sub_class": "Sector"}))
            st.dataframe(by_sector, hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="percent")
                                        for c in ["Median 1 month", "Median 12 months"]})
            st.dataframe(_table(stocks[["name", "symbol", "sub_class"] + COLUMNS[2:]]
                                .sort_values("return_12m", ascending=False)),
                         hide_index=True, width="stretch", column_config=PERCENT)
            st.caption("Nifty 50 members as listed in india_markets.py; the official list changes at index reviews.")

    with economy:
        macro = load_macro()
        if macro.empty:
            st.info("Indian economic data arrives with the next daily refresh.")
        else:
            if "status" not in macro:
                macro["status"] = "—"
            st.dataframe(macro[["name", "value", "unit", "change", "change_basis", "as_of", "status", "source"]].rename(
                columns={"name": "Indicator", "value": "Latest", "unit": "Unit", "change": "Change",
                         "change_basis": "Change basis", "as_of": "As of", "status": "Status", "source": "Source"}),
                hide_index=True, width="stretch",
                column_config={"Latest": st.column_config.NumberColumn(format="%.2f"),
                               "Change": st.column_config.NumberColumn(format="%+.2f")})
            st.caption("Free international sources publish Indian data monthly or quarterly, so readings lag by weeks; "
                       "some series have stopped updating at the source and are marked Stale rather than hidden. "
                       "The RBI repo rate has no reliable free API; the 3-month interbank rate is shown as a proxy. "
                       "For current CPI and RBI decisions, check MOSPI and rbi.org.in.")

    with rupee:
        fx = priced[priced["asset_class"].isin(["FX", "Commodity", "Fixed Income"])]
        st.dataframe(_table(fx[["name", "symbol", "sub_class"] + COLUMNS[2:-1]]), hide_index=True, width="stretch",
                     column_config=PERCENT)
        st.caption("USD/INR rising means a weaker rupee. Gold and silver are the listed ETFs in INR; gilt ETFs stand in "
                   "for Indian government bond prices.")

    with reits:
        re = priced[priced["asset_class"] == "Real Estate"]
        st.dataframe(_table(re[COLUMNS]), hide_index=True, width="stretch", column_config=PERCENT)
        st.caption("Indian REITs own office parks and malls; InvITs own infrastructure such as power lines. Both pay "
                   "out most of their cash flow.")


def render_india_home() -> None:
    st.markdown("### India")
    st.markdown('<div class="vt-lede">The Indian market at a glance. Switch to US in the sidebar for the US view; '
                'the two are kept separate.</div>', unsafe_allow_html=True)
    data = load()
    if data is None:
        st.info(MISSING)
        return
    priced = data.dropna(subset=["price"])
    _headline(priced)
    stocks = priced[priced["symbol"].isin([s for s, _, _ in im.NIFTY_50])].dropna(subset=["return_1d"])
    left, right = st.columns(2)
    with left:
        st.markdown("#### Nifty 50 · best today")
        st.dataframe(_table(stocks.nlargest(5, "return_1d")[["name", "price", "return_1d", "return_12m"]]),
                     hide_index=True, width="stretch", column_config=PERCENT)
    with right:
        st.markdown("#### Nifty 50 · worst today")
        st.dataframe(_table(stocks.nsmallest(5, "return_1d")[["name", "price", "return_1d", "return_12m"]]),
                     hide_index=True, width="stretch", column_config=PERCENT)
    try:
        import trader_agent as ta
        reg = ta.regime(ta.load_history(market="India"), "India")
        vix = f"India VIX {reg['vix']:.1f}" if reg["vix"] else "India VIX n/a"
        trend = f"Nifty 50 {reg['spy_vs_200d']:+.1%} vs its 200-day average" if reg["spy_vs_200d"] is not None else ""
        st.markdown(f"**Regime: {reg['state']}.** {trend}; {vix}.")
    except FileNotFoundError:
        pass
    st.markdown("#### Workspaces")
    c1, c2, c3 = st.columns(3)
    for col, page, text in ((c1, "Markets", "Indices, sectors, Nifty 50, economy, rupee, gold, REITs"),
                            (c2, "Trading Desk", "Trader agent on NSE stocks and ETFs; paper blotter in INR"),
                            (c3, "Job Tracker", "Your daily desk duty, CFA Level II step and lesson")):
        with col.container(border=True):
            st.markdown(f"**{page}**")
            st.caption(text)
            st.button(f"Open {page}", key=f"in-home-{page}", on_click=lambda p=page: st.session_state.update(nav=p))
