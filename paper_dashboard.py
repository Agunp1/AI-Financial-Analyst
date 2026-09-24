
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from paper_order_form import show_order_form


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

DB_PATH = Path(__file__).resolve().parent / "paper_trading.db"


def load_paper_data():
    """Read existing paper-trading records without modifying them."""

    if not DB_PATH.exists():
        st.error("paper_trading.db was not found.")
        st.stop()

    with sqlite3.connect(DB_PATH) as conn:
        accounts = pd.read_sql_query(
            """
            SELECT account_id, starting_capital, cash_balance
            FROM accounts
            ORDER BY account_id
            """,
            conn,
        )

        positions = pd.read_sql_query(
            """
            SELECT ticker, quantity, average_cost
            FROM positions
            WHERE quantity > 0
            ORDER BY ticker
            """,
            conn,
        )

        trades = pd.read_sql_query(
            """
            SELECT
                trade_id,
                timestamp,
                ticker,
                side,
                quantity,
                execution_price,
                fees,
                realized_pnl
            FROM trades
            ORDER BY trade_id DESC
            """,
            conn,
        )

        snapshots = pd.read_sql_query(
            """
            SELECT
                snapshot_id,
                timestamp,
                cash_balance,
                holdings_value,
                total_equity
            FROM equity_snapshots
            ORDER BY snapshot_id
            """,
            conn,
        )

    return accounts, positions, trades, snapshots


# --------------------------------------------------
# HISTORICAL PRICE LOOKUP
# --------------------------------------------------

def latest_historical_prices(prices):
    """Return the latest stored historical close for each ticker."""

    required = {"date", "ticker", "close_price"}

    if not required.issubset(prices.columns):
        st.error("The historical prices dataset is missing required columns.")
        st.stop()

    latest = prices.copy()
    latest["date"] = pd.to_datetime(latest["date"])
    latest["close_price"] = pd.to_numeric(
        latest["close_price"],
        errors="coerce",
    )

    latest = (
        latest.dropna(subset=["date", "ticker", "close_price"])
        .sort_values("date")
        .drop_duplicates(subset=["ticker"], keep="last")
    )

    return latest[["ticker", "date", "close_price"]]


# --------------------------------------------------
# PAPER TRADING DASHBOARD
# --------------------------------------------------

def show_paper_dashboard(prices):

    st.header("Paper Trading Dashboard")

    st.caption(
        "Simulated trading account. Historical prices and "
        "illustrative transactions only. No real orders."
    )

    accounts, positions, trades, snapshots = load_paper_data()

    if accounts.empty:
        st.error("No simulated trading account was found.")
        st.stop()

    account = accounts.iloc[0]

    starting_capital = float(account["starting_capital"])
    cash_balance = float(account["cash_balance"])

    realized_pnl = (
        float(trades["realized_pnl"].fillna(0).sum())
        if not trades.empty
        else 0.0
    )

    # ----------------------------------------------
    # ACCOUNT OVERVIEW
    # ----------------------------------------------

    st.subheader("Simulated Account Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Starting Capital",
        f"${starting_capital:,.2f}",
    )

    col2.metric(
        "Current Cash Balance",
        f"${cash_balance:,.2f}",
    )

    col3.metric(
        "Recorded Realized P&L",
        f"${realized_pnl:,.2f}",
    )

    # ----------------------------------------------
    # OPEN POSITIONS
    # ----------------------------------------------

    st.subheader("Open Positions")

    holdings_value = 0.0
    unrealized_pnl = 0.0

    if positions.empty:
        st.info("There are currently no open positions.")

    else:
        latest_prices = latest_historical_prices(prices)

        position_values = positions.merge(
            latest_prices,
            on="ticker",
            how="left",
        )

        position_values["Cost Basis ($)"] = (
            position_values["quantity"]
            * position_values["average_cost"]
        )

        position_values["Historical Market Value ($)"] = (
            position_values["quantity"]
            * position_values["close_price"]
        )

        position_values["Illustrative Unrealized P&L ($)"] = (
            position_values["Historical Market Value ($)"]
            - position_values["Cost Basis ($)"]
        )

        missing_prices = position_values[
            position_values["close_price"].isna()
        ]

        if not missing_prices.empty:
            missing_tickers = ", ".join(
                missing_prices["ticker"].astype(str)
            )

            st.warning(
                "No stored historical price is available for: "
                f"{missing_tickers}. Their market values cannot "
                "be included in the estimated account equity."
            )

        display_positions = position_values.rename(
            columns={
                "ticker": "Ticker",
                "quantity": "Quantity",
                "average_cost": "Average Cost ($)",
                "date": "Price Date",
                "close_price": "Historical Close ($)",
            }
        )

        st.dataframe(
            display_positions[
                [
                    "Ticker",
                    "Quantity",
                    "Average Cost ($)",
                    "Price Date",
                    "Historical Close ($)",
                    "Cost Basis ($)",
                    "Historical Market Value ($)",
                    "Illustrative Unrealized P&L ($)",
                ]
            ].round(2),
            width="stretch",
            hide_index=True,
        )

        st.caption(
            "Open positions are marked using the latest "
            "stored historical closing price, not live quotes."
        )

        holdings_value = float(
            position_values["Historical Market Value ($)"]
            .fillna(0)
            .sum()
        )

        unrealized_pnl = float(
            position_values["Illustrative Unrealized P&L ($)"]
            .fillna(0)
            .sum()
        )

    estimated_equity = cash_balance + holdings_value

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Historical Holdings Value",
        f"${holdings_value:,.2f}",
    )

    col2.metric(
        "Illustrative Unrealized P&L",
        f"${unrealized_pnl:,.2f}",
    )

    col3.metric(
        "Estimated Account Equity",
        f"${estimated_equity:,.2f}",
    )

    # ----------------------------------------------
    # POSITION ALLOCATION
    # ----------------------------------------------

    if not positions.empty:

        allocation = position_values.dropna(
            subset=["Historical Market Value ($)"]
        )

        allocation = allocation[
            allocation["Historical Market Value ($)"] > 0
        ]

        if not allocation.empty:

            st.subheader("Open Position Allocation")

            fig = px.pie(
                allocation,
                names="ticker",
                values="Historical Market Value ($)",
                title="Historical-Price-Based Holdings Allocation",
            )

            st.plotly_chart(
                fig,
                width="stretch",
            )

    # ----------------------------------------------
    # TRADE HISTORY
    # ----------------------------------------------

    st.subheader("Simulated Trade History")

    if trades.empty:
        st.info("No simulated trades have been recorded.")

    else:
        st.dataframe(
            trades,
            width="stretch",
            hide_index=True,
        )

    # ----------------------------------------------
    # RECORDED EQUITY SNAPSHOTS
    # ----------------------------------------------

    st.subheader("Recorded Account Equity")

    if snapshots.empty:
        st.info("No equity snapshots have been recorded.")

    else:
        snapshots["timestamp"] = pd.to_datetime(
            snapshots["timestamp"],
            utc=True,
        )

        fig = px.line(
            snapshots,
            x="timestamp",
            y="total_equity",
            markers=True,
            title="Recorded Simulated Account Equity",
            labels={
                "timestamp": "Snapshot Date",
                "total_equity": "Account Equity ($)",
            },
        )

        st.plotly_chart(
            fig,
            width="stretch",
        )

        st.dataframe(
            snapshots.sort_values(
                "timestamp",
                ascending=False,
            ),
            width="stretch",
            hide_index=True,
        )

        st.caption(
            "Equity snapshots reflect the prices used when "
            "they were originally recorded. They may differ "
            "from today's historical-price-based estimate."
        )

    # ----------------------------------------------
    # SIMULATED ORDER FORM
    # ----------------------------------------------

    st.divider()

    show_order_form(prices)