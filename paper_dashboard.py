
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DB_PATH = Path(__file__).resolve().parent / "paper_trading.db"


def load_paper_data():
    """Read existing simulated trading records without modifying them."""

    if not DB_PATH.exists():
        st.error("paper_trading.db was not found.")
        st.stop()

    with sqlite3.connect(
        f"{DB_PATH.as_uri()}?mode=ro",
        uri=True
    ) as conn:

        accounts = pd.read_sql_query(
            """
            SELECT account_id, starting_capital, cash_balance
            FROM accounts
            ORDER BY account_id
            """,
            conn
        )

        positions = pd.read_sql_query(
            """
            SELECT ticker, quantity, average_cost
            FROM positions
            WHERE quantity > 0
            ORDER BY ticker
            """,
            conn
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
            ORDER BY timestamp DESC, trade_id DESC
            """,
            conn
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
            ORDER BY timestamp, snapshot_id
            """,
            conn
        )

    return accounts, positions, trades, snapshots


def show_paper_dashboard(prices):

    st.header("Paper Trading Dashboard")

    st.caption(
        "Simulated trading account. Historical prices and "
        "illustrative transactions only. No real orders."
    )

    accounts, positions, trades, snapshots = load_paper_data()

    if accounts.empty:
        st.warning("No simulated account was found.")
        return

    # ----------------------------------------------
    # ACCOUNT SUMMARY
    # ----------------------------------------------

    account = accounts.iloc[0]

    starting_capital = float(
        account["starting_capital"]
    )

    cash_balance = float(
        account["cash_balance"]
    )

    realized_pnl = (
        trades["realized_pnl"]
        .fillna(0)
        .sum()
        if not trades.empty
        else 0.0
    )

    st.subheader("Simulated Account Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Starting Capital",
        f"${starting_capital:,.2f}"
    )

    col2.metric(
        "Current Cash Balance",
        f"${cash_balance:,.2f}"
    )

    col3.metric(
        "Recorded Realized P&L",
        f"${realized_pnl:,.2f}"
    )

    # ----------------------------------------------
    # CURRENT POSITIONS
    # ----------------------------------------------

    st.subheader("Open Positions")

    if positions.empty:

        st.info("No open simulated positions.")

    else:

        latest_prices = (
            prices
            .sort_values("date")
            .drop_duplicates(
                subset=["ticker"],
                keep="last"
            )
            [
                ["ticker", "date", "close_price"]
            ]
        )

        holdings = positions.merge(
            latest_prices,
            on="ticker",
            how="left"
        )

        holdings["Cost Basis ($)"] = (
            holdings["quantity"]
            * holdings["average_cost"]
        )

        holdings["Historical Market Value ($)"] = (
            holdings["quantity"]
            * holdings["close_price"]
        )

        holdings["Illustrative Unrealized P&L ($)"] = (
            holdings["Historical Market Value ($)"]
            - holdings["Cost Basis ($)"]
        )

        display_holdings = holdings.rename(
            columns={
                "ticker": "Ticker",
                "quantity": "Quantity",
                "average_cost": "Average Cost ($)",
                "date": "Price Date",
                "close_price": "Historical Close ($)"
            }
        )

        st.dataframe(
            display_holdings.round(2),
            width="stretch",
            hide_index=True
        )

        missing_prices = holdings[
            holdings["close_price"].isna()
        ]

        if not missing_prices.empty:
            st.warning(
                "Historical prices are missing for: "
                + ", ".join(
                    missing_prices["ticker"].tolist()
                )
            )

        else:

            holdings_value = float(
                holdings[
                    "Historical Market Value ($)"
                ].sum()
            )

            estimated_equity = (
                cash_balance + holdings_value
            )

            unrealized_pnl = float(
                holdings[
                    "Illustrative Unrealized P&L ($)"
                ].sum()
            )

            st.caption(
                "Open positions are marked using the latest "
                "stored historical closing price, not live quotes."
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Historical Holdings Value",
                f"${holdings_value:,.2f}"
            )

            col2.metric(
                "Illustrative Unrealized P&L",
                f"${unrealized_pnl:,.2f}"
            )

            col3.metric(
                "Estimated Account Equity",
                f"${estimated_equity:,.2f}"
            )

            allocation = holdings[
                ["ticker", "Historical Market Value ($)"]
            ].copy()

            fig = px.pie(
                allocation,
                names="ticker",
                values="Historical Market Value ($)",
                title="Open Position Allocation",
                hole=0.4
            )

            st.plotly_chart(
                fig,
                width="stretch"
            )

    # ----------------------------------------------
    # TRADE HISTORY
    # ----------------------------------------------

    st.subheader("Simulated Trade History")

    if trades.empty:

        st.info("No simulated trades recorded.")

    else:

        trades["timestamp"] = pd.to_datetime(
            trades["timestamp"],
            errors="coerce"
        )

        st.dataframe(
            trades,
            width="stretch",
            hide_index=True
        )

    # ----------------------------------------------
    # RECORDED EQUITY SNAPSHOTS
    # ----------------------------------------------

    st.subheader("Recorded Account Equity")

    if snapshots.empty:

        st.info(
            "No historical account snapshots recorded."
        )

    else:

        snapshots["timestamp"] = pd.to_datetime(
            snapshots["timestamp"],
            errors="coerce"
        )

        snapshots = snapshots.dropna(
            subset=["timestamp"]
        )

        fig = px.line(
            snapshots,
            x="timestamp",
            y="total_equity",
            markers=True,
            title="Recorded Simulated Account Equity",
            labels={
                "timestamp": "Snapshot Date",
                "total_equity": "Account Equity ($)"
            }
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

        st.dataframe(
            snapshots.sort_values(
                "timestamp",
                ascending=False
            ),
            width="stretch",
            hide_index=True
        )

        st.caption(
            "Equity snapshots reflect the prices used when "
            "they were originally recorded. They may differ "
            "from today's historical-price-based estimate."
        )