import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="AI Investment Intelligence",
    page_icon="📈",
    layout="wide"
)

st.title("AI Investment Intelligence")
st.caption("Research, portfolio analytics and simulated trading")

# Read the existing project database.
with sqlite3.connect("hedge_fund.db") as conn:
    prices = pd.read_sql_query(
        """
        SELECT date, ticker, close_price
        FROM daily_prices
        ORDER BY date
        """,
        conn
    )

    economic = pd.read_sql_query(
        """
        SELECT indicator, observation_date,
               available_date, value
        FROM economic_vintages
        ORDER BY available_date
        """,
        conn
    )

prices["date"] = pd.to_datetime(prices["date"])

# Sidebar navigation
section = st.sidebar.radio(
    "Navigation",
    ["Market Overview", "Economic Indicators"]
)

if section == "Market Overview":
    st.header("Market Overview")

    tickers = sorted(prices["ticker"].unique())

    selected_ticker = st.selectbox(
        "Select a stock",
        tickers
    )

    stock = prices[
        prices["ticker"] == selected_ticker
    ].sort_values("date")

    latest_price = stock["close_price"].iloc[-1]

    st.metric(
        "Latest historical closing price",
        f"${latest_price:,.2f}"
    )

    fig = px.line(
        stock,
        x="date",
        y="close_price",
        title=f"{selected_ticker} — Historical Closing Prices",
        labels={
            "date": "Date",
            "close_price": "Closing Price ($)"
        }
    )

    st.plotly_chart(fig, width="stretch")

elif section == "Economic Indicators":
    st.header("Economic Indicators")

    indicators = sorted(economic["indicator"].unique())

    selected_indicator = st.selectbox(
        "Select an indicator",
        indicators
    )

    # Select the most recent available vintage for each
    # observation. This is a historical-data display,
    # not a point-in-time backtest.
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
    )

    fig = px.line(
        series,
        x="observation_date",
        y="value",
        markers=True,
        title=selected_indicator
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        series,
        width="stretch",
        hide_index=True
    )