
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from paper_dashboard import show_paper_dashboard


# ==================================================
# VITTANTRA — PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Vittantra",
    page_icon="📈",
    layout="wide"
)

st.title("Vittantra")

st.caption(
    "AI-powered investment research, portfolio analytics "
    "and simulated trading"
)


# ==================================================
# DATABASE CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent

HEDGE_FUND_DB = PROJECT_DIR / "hedge_fund.db"


# ==================================================
# LOAD HISTORICAL MARKET AND ECONOMIC DATA
# ==================================================

if not HEDGE_FUND_DB.exists():
    st.error("hedge_fund.db was not found in the project folder.")
    st.stop()

with sqlite3.connect(
    f"{HEDGE_FUND_DB.as_uri()}?mode=ro",
    uri=True
) as conn:

    prices = pd.read_sql_query(
        """
        SELECT
            date,
            ticker,
            close_price
        FROM daily_prices
        ORDER BY date, ticker
        """,
        conn
    )

    economic = pd.read_sql_query(
        """
        SELECT
            indicator,
            observation_date,
            available_date,
            value
        FROM economic_vintages
        ORDER BY available_date
        """,
        conn
    )


# Convert database dates to pandas datetime.

prices["date"] = pd.to_datetime(
    prices["date"]
)

economic["observation_date"] = pd.to_datetime(
    economic["observation_date"]
)

economic["available_date"] = pd.to_datetime(
    economic["available_date"]
)


# ==================================================
# SIDEBAR NAVIGATION
# ==================================================

st.sidebar.title("Vittantra")

section = st.sidebar.radio(
    "Navigation",
    [
        "Market Overview",
        "Economic Indicators",
        "Portfolio Analytics",
        "Paper Trading"
    ]
)

st.sidebar.divider()

st.sidebar.caption(
    "Historical investment research and simulated trading. "
    "Not live investment advice."
)


# ==================================================
# PAGE 1 — MARKET OVERVIEW
# ==================================================

if section == "Market Overview":

    st.header("Market Overview")

    if prices.empty:
        st.warning("No historical stock prices are available.")
        st.stop()

    tickers = sorted(
        prices["ticker"].unique()
    )

    selected_ticker = st.selectbox(
        "Select a stock",
        tickers
    )

    stock = (
        prices[
            prices["ticker"] == selected_ticker
        ]
        .sort_values("date")
        .copy()
    )

    latest_price = float(
        stock["close_price"].iloc[-1]
    )

    latest_date = stock["date"].iloc[-1]

    col1, col2 = st.columns(2)

    col1.metric(
        "Latest Historical Closing Price",
        f"${latest_price:,.2f}"
    )

    col2.metric(
        "Latest Available Date",
        latest_date.strftime("%b %d, %Y")
    )

    price_fig = px.line(
        stock,
        x="date",
        y="close_price",
        title=(
            f"{selected_ticker} — "
            "Historical Closing Prices"
        ),
        labels={
            "date": "Date",
            "close_price": "Closing Price ($)"
        }
    )

    st.plotly_chart(
        price_fig,
        width="stretch"
    )

    st.subheader("Historical Price Data")

    st.dataframe(
        stock.sort_values(
            "date",
            ascending=False
        ),
        width="stretch",
        hide_index=True
    )

    st.caption(
        "These are stored historical closing prices, "
        "not live market quotes."
    )


# ==================================================
# PAGE 2 — ECONOMIC INDICATORS
# ==================================================

elif section == "Economic Indicators":

    st.header("Economic Indicators")

    st.caption(
        "Historical economic data using the latest "
        "stored vintage for each observation. "
        "This page is not a point-in-time backtest."
    )

    if economic.empty:
        st.warning("No economic indicators are available.")
        st.stop()

    indicators = sorted(
        economic["indicator"].unique()
    )

    selected_indicator = st.selectbox(
        "Select an economic indicator",
        indicators
    )

    series = (
        economic[
            economic["indicator"] == selected_indicator
        ]
        .sort_values("available_date")
        .drop_duplicates(
            subset=["observation_date"],
            keep="last"
        )
        .sort_values("observation_date")
        .copy()
    )

    if series.empty:
        st.warning("No observations found.")
        st.stop()

    latest_observation = series.iloc[-1]

    col1, col2 = st.columns(2)

    col1.metric(
        "Latest Stored Observation",
        f"{latest_observation['value']:,.2f}"
    )

    col2.metric(
        "Observation Date",
        latest_observation[
            "observation_date"
        ].strftime("%b %d, %Y")
    )

    economic_fig = px.line(
        series,
        x="observation_date",
        y="value",
        markers=True,
        title=(
            f"{selected_indicator} — "
            "Historical Economic Data"
        ),
        labels={
            "observation_date": "Observation Date",
            "value": "Value"
        }
    )

    st.plotly_chart(
        economic_fig,
        width="stretch"
    )

    st.subheader("Economic Data")

    st.dataframe(
        series.sort_values(
            "observation_date",
            ascending=False
        ),
        width="stretch",
        hide_index=True
    )


# ==================================================
# PAGE 3 — PORTFOLIO ANALYTICS
# ==================================================

elif section == "Portfolio Analytics":

    st.header("Portfolio Analytics")

    st.caption(
        "Historical equal-weight buy-and-hold simulation. "
        "Not actual trading performance."
    )

    # ----------------------------------------------
    # HISTORICAL PRICE MATRIX
    # ----------------------------------------------

    tickers = [
        "AAPL",
        "BLK",
        "GS",
        "JPM",
        "MSFT"
    ]

    portfolio_prices = (
        prices
        .pivot(
            index="date",
            columns="ticker",
            values="close_price"
        )
        .sort_index()
    )

    missing_tickers = [
        ticker
        for ticker in tickers
        if ticker not in portfolio_prices.columns
    ]

    if missing_tickers:
        st.error(
            "Missing historical prices for: "
            + ", ".join(missing_tickers)
        )
        st.stop()

    portfolio_prices = (
        portfolio_prices[tickers]
        .dropna()
    )

    if len(portfolio_prices) < 2:
        st.warning(
            "Insufficient historical price data."
        )
        st.stop()

    # ----------------------------------------------
    # INITIAL PORTFOLIO
    # ----------------------------------------------

    starting_capital = 100_000

    initial_weights = pd.Series(
        1 / len(tickers),
        index=tickers
    )

    initial_investment = (
        starting_capital * initial_weights
    )

    # Fractional shares are permitted.
    # Dividends, fees and taxes are excluded.

    shares = (
        initial_investment
        / portfolio_prices.iloc[0]
    )

    # ----------------------------------------------
    # BUY-AND-HOLD SIMULATION
    # ----------------------------------------------

    holdings_values = (
        portfolio_prices.mul(
            shares,
            axis=1
        )
    )

    portfolio_equity = (
        holdings_values.sum(axis=1)
    )

    cumulative_return = (
        portfolio_equity
        / starting_capital
        - 1
    )

    running_peak = (
        portfolio_equity.cummax()
    )

    drawdown = (
        portfolio_equity
        / running_peak
        - 1
    )

    current_weights = (
        holdings_values.iloc[-1]
        / portfolio_equity.iloc[-1]
    )

    # ----------------------------------------------
    # SUMMARY METRICS
    # ----------------------------------------------

    final_equity = float(
        portfolio_equity.iloc[-1]
    )

    total_return = float(
        cumulative_return.iloc[-1]
    )

    max_drawdown = float(
        drawdown.min()
    )

    start_date = (
        portfolio_prices.index[0]
    )

    end_date = (
        portfolio_prices.index[-1]
    )

    st.write(
        f"**Historical period:** "
        f"{start_date:%b %d, %Y} – "
        f"{end_date:%b %d, %Y}"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Final Portfolio Value",
        f"${final_equity:,.2f}"
    )

    col2.metric(
        "Historical Total Return",
        f"{total_return:.2%}"
    )

    col3.metric(
        "Maximum Drawdown",
        f"{max_drawdown:.2%}"
    )

    # ----------------------------------------------
    # PORTFOLIO EQUITY CHART
    # ----------------------------------------------

    st.subheader(
        "Historical Portfolio Equity"
    )

    equity_df = (
        portfolio_equity
        .rename("Portfolio Value")
        .reset_index()
    )

    equity_fig = px.line(
        equity_df,
        x="date",
        y="Portfolio Value",
        title=(
            "Historical Buy-and-Hold "
            "Portfolio Value"
        ),
        labels={
            "date": "Date",
            "Portfolio Value": "Portfolio Value ($)"
        }
    )

    st.plotly_chart(
        equity_fig,
        width="stretch"
    )

    # ----------------------------------------------
    # DRAWDOWN CHART
    # ----------------------------------------------

    st.subheader(
        "Historical Portfolio Drawdown"
    )

    drawdown_df = (
        drawdown
        .mul(100)
        .rename("Drawdown (%)")
        .reset_index()
    )

    drawdown_fig = px.area(
        drawdown_df,
        x="date",
        y="Drawdown (%)",
        title="Historical Portfolio Drawdown",
        labels={
            "date": "Date",
            "Drawdown (%)": "Drawdown (%)"
        }
    )

    st.plotly_chart(
        drawdown_fig,
        width="stretch"
    )

    # ----------------------------------------------
    # FINAL PORTFOLIO ALLOCATION
    # ----------------------------------------------

    st.subheader(
        "Final Portfolio Allocation"
    )

    allocation_df = pd.DataFrame({
        "Ticker": tickers,
        "Initial Weight (%)": (
            initial_weights.values * 100
        ),
        "Final Weight (%)": (
            current_weights.values * 100
        ),
        "Final Holding Value ($)": (
            holdings_values.iloc[-1].values
        )
    })

    allocation_fig = px.pie(
        allocation_df,
        names="Ticker",
        values="Final Holding Value ($)",
        title="Final Portfolio Allocation",
        hole=0.4
    )

    st.plotly_chart(
        allocation_fig,
        width="stretch"
    )

    st.dataframe(
        allocation_df.round(2),
        width="stretch",
        hide_index=True
    )

    st.info(
        "Simulation assumptions: $100,000 initial "
        "capital, 20% allocated to each stock, "
        "fractional shares and no rebalancing. "
        "Dividends, fees and taxes are excluded."
    )


# ==================================================
# PAGE 4 — PAPER TRADING
# ==================================================

elif section == "Paper Trading":

    show_paper_dashboard(prices)