
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from risk_engine import (
    MAX_POSITION_WEIGHT,
    MIN_CASH_RESERVE,
)
from stress_engine import run_stress_tests
from var_engine import calculate_historical_var

BASE_DIR = Path(__file__).resolve().parent
PAPER_DB = BASE_DIR / "paper_trading.db"
MARKET_DB = BASE_DIR / "hedge_fund.db"


def load_risk_data():
    """Read the simulated account and historical prices."""

    if not PAPER_DB.exists():
        raise FileNotFoundError("paper_trading.db is missing.")

    if not MARKET_DB.exists():
        raise FileNotFoundError("hedge_fund.db is missing.")

    with sqlite3.connect(PAPER_DB) as conn:
        account = pd.read_sql_query(
            """
            SELECT account_id, cash_balance
            FROM accounts
            ORDER BY account_id
            LIMIT 1
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

    if account.empty:
        raise ValueError("No simulated trading account exists.")

    with sqlite3.connect(MARKET_DB) as conn:
        prices = pd.read_sql_query(
            """
            SELECT p.ticker, p.date, p.close_price
            FROM daily_prices AS p
            INNER JOIN (
                SELECT ticker, MAX(date) AS latest_date
                FROM daily_prices
                GROUP BY ticker
            ) AS latest
                ON p.ticker = latest.ticker
               AND p.date = latest.latest_date
            """,
            conn,
        )
    with sqlite3.connect(MARKET_DB) as conn:
        price_history = pd.read_sql_query(
        """
        SELECT date, ticker, close_price
        FROM daily_prices
        ORDER BY date, ticker
        """,
        conn,
    )
    return account, positions, prices, price_history


def build_risk_report(account, positions, prices):
    """Calculate risk metrics without modifying either database."""

    cash = float(account.iloc[0]["cash_balance"])

    if positions.empty:
        holdings = pd.DataFrame(
            columns=[
                "ticker",
                "quantity",
                "average_cost",
                "date",
                "close_price",
                "market_value",
                "cost_basis",
                "unrealized_pnl",
                "portfolio_weight",
                "limit_breached",
            ]
        )
    else:
        holdings = positions.merge(
            prices,
            on="ticker",
            how="left",
            validate="many_to_one",
        )

        if holdings["close_price"].isna().any():
            missing = holdings.loc[
                holdings["close_price"].isna(), "ticker"
            ].tolist()
            raise ValueError(
                "Missing historical prices for: "
                + ", ".join(missing)
            )

        holdings["market_value"] = (
            holdings["quantity"] * holdings["close_price"]
        )

        holdings["cost_basis"] = (
            holdings["quantity"] * holdings["average_cost"]
        )

        holdings["unrealized_pnl"] = (
            holdings["market_value"] - holdings["cost_basis"]
        )

    holdings_value = float(
        holdings["market_value"].sum()
    )

    equity = cash + holdings_value

    if equity <= 0:
        raise ValueError(
            "Estimated account equity must be positive."
        )

    holdings["portfolio_weight"] = (
        holdings["market_value"] / equity
    )

    holdings["limit_breached"] = (
        holdings["portfolio_weight"] > MAX_POSITION_WEIGHT
    )

    cash_weight = cash / equity
    unrealized_pnl = float(
        holdings["unrealized_pnl"].sum()
    )

    alerts = []

    if cash < MIN_CASH_RESERVE:
        alerts.append(
            f"Cash reserve below ${MIN_CASH_RESERVE:,.2f}."
        )

    for _, position in holdings.iterrows():
        if position["limit_breached"]:
            alerts.append(
                f"{position['ticker']} exceeds the "
                f"{MAX_POSITION_WEIGHT:.0%} "
                "single-position limit."
            )

    return {
        "cash": cash,
        "holdings_value": holdings_value,
        "equity": equity,
        "cash_weight": cash_weight,
        "unrealized_pnl": unrealized_pnl,
        "holdings": holdings,
        "alerts": alerts,
    }


def render_risk_dashboard():
    """Render the Day 36 simulated risk dashboard."""

    st.header("Risk Monitoring")
    st.caption(
        "Simulated portfolio risk using stored historical "
        "closing prices. Not live market data."
    )

    try:
        account, positions, prices, price_history = load_risk_data()
        report = build_risk_report(
            account, positions, prices
        )
    except (
        FileNotFoundError,
        ValueError,
        sqlite3.Error,
    ) as error:
        st.error(str(error))
        return

    st.subheader("Account Risk Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Estimated Account Equity",
        f"${report['equity']:,.2f}",
    )

    col2.metric(
        "Available Cash",
        f"${report['cash']:,.2f}",
    )

    col3.metric(
        "Illustrative Unrealized P&L",
        f"${report['unrealized_pnl']:,.2f}",
    )

    st.metric(
        "Cash Allocation",
        f"{report['cash_weight']:.2%}",
    )

    st.subheader("Risk Alerts")

    if report["alerts"]:
        for alert in report["alerts"]:
            st.error(alert)
    else:
        st.success(
            "No breaches of the monitored Day 35 "
            "cash-reserve or position-concentration limits."
        )

    
        st.divider()
    st.subheader("Historical Value at Risk")
    st.caption(
        "One-day historical VaR and Expected Shortfall using "
        "stored closing prices. Estimates are not forecasts."
    )

    if report["holdings"].empty:
        st.info("Open a simulated position to calculate historical VaR.")
    else:
        try:
            var_results, daily_losses = calculate_historical_var(
                report["holdings"],
                price_history,
            )

            st.dataframe(
                var_results.round(2),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Based on {len(daily_losses)} historical daily observations. "
                "Historical VaR assumes past returns are informative "
                "about potential future losses."
            )

        except ValueError as error:
            st.warning(f"Historical VaR unavailable: {error}")

    holdings = report["holdings"]

        # Day 38 — Portfolio Stress Testing
    st.divider()
    st.subheader("Portfolio Stress Testing")

    st.caption(
        "Hypothetical market-decline scenarios applied "
        "to simulated holdings. Not a forecast."
    )

    stress_results = run_stress_tests(report)

    st.dataframe(
        stress_results.round(2),
        width="stretch",
        hide_index=True,
    )

    stress_fig = px.bar(
        stress_results,
        x="Scenario",
        y="Portfolio P&L ($)",
        title="Portfolio Impact Under Market Stress",
    )

    st.plotly_chart(
        stress_fig,
        width="stretch",
    )

    if holdings.empty:
        st.info(
            "No open positions. Your simulated "
            "account currently holds cash only."
        )
        return

    st.subheader("Portfolio Concentration")

    chart_data = holdings[
        ["ticker", "portfolio_weight"]
    ].copy()

    chart_data["portfolio_weight"] *= 100

    fig = px.bar(
        chart_data,
        x="ticker",
        y="portfolio_weight",
        title="Position Weight as a Percentage of Equity",
        labels={
            "ticker": "Ticker",
            "portfolio_weight": "Portfolio Weight (%)",
        },
    )

    fig.add_hline(
        y=MAX_POSITION_WEIGHT * 100,
        line_dash="dash",
        annotation_text=(
            f"Limit: {MAX_POSITION_WEIGHT:.0%}"
        ),
    )

    st.plotly_chart(fig, width="stretch")

    st.subheader("Position Risk Details")

    display = holdings[
        [
            "ticker",
            "quantity",
            "average_cost",
            "date",
            "close_price",
            "market_value",
            "unrealized_pnl",
            "portfolio_weight",
            "limit_breached",
        ]
    ].copy()

    display["portfolio_weight"] *= 100

    display = display.rename(
        columns={
            "ticker": "Ticker",
            "quantity": "Quantity",
            "average_cost": "Average Cost ($)",
            "date": "Historical Price Date",
            "close_price": "Historical Close ($)",
            "market_value": "Historical Market Value ($)",
            "unrealized_pnl": "Illustrative Unrealized P&L ($)",
            "portfolio_weight": "Weight (%)",
            "limit_breached": "Concentration Breach",
        }
    )

    st.dataframe(
        display.round(2),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Risk limits are configurable simulation rules, "
        "not regulatory limits. Historical prices may "
        "be stale and differ from executable prices."
    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="Vittantra Risk Monitoring",
        layout="wide",
    )
    render_risk_dashboard()
