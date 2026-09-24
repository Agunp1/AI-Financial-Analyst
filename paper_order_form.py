
import streamlit as st

from paper_orders import (
    execute_paper_order,
    OrderError,
)


def show_order_form(prices):
    """Display a form for placing simulated BUY and SELL orders."""

    st.subheader("Place a Simulated Order")

    st.warning(
        "Paper trading only. Execution prices are entered manually. "
        "No real brokerage orders will be placed."
    )

    if prices.empty:
        st.error("No historical stock prices are available.")
        return

    tickers = sorted(prices["ticker"].dropna().unique())

    if not tickers:
        st.error("No stock tickers are available.")
        return

    with st.form("paper_order_form"):
        ticker = st.selectbox(
            "Stock",
            tickers,
        )

        side = st.radio(
            "Order Side",
            ["BUY", "SELL"],
            horizontal=True,
        )

        quantity = st.number_input(
            "Quantity",
            min_value=0.01,
            value=1.0,
            step=1.0,
            format="%.2f",
        )

        stock_prices = (
            prices[prices["ticker"] == ticker]
            .sort_values("date")
        )

        historical_price = float(
            stock_prices["close_price"].iloc[-1]
        )

        latest_date = stock_prices["date"].iloc[-1]

        st.caption(
            f"Latest stored historical closing price: "
            f"${historical_price:,.2f} "
            f"(date: {latest_date})"
        )

        execution_price = st.number_input(
            "Illustrative Execution Price ($)",
            min_value=0.01,
            value=historical_price,
            step=0.01,
            format="%.2f",
        )

        estimated_value = quantity * execution_price

        st.write(
            f"**Estimated order value:** "
            f"${estimated_value:,.2f}"
        )

        st.caption(
            "This is a manually entered simulated execution price, "
            "not a live market quote."
        )

        submitted = st.form_submit_button(
            "Execute Simulated Order",
            type="primary",
        )

    if submitted:
        try:
            result = execute_paper_order(
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=execution_price,
            )

        except OrderError as error:
            st.error(str(error))

        except Exception as error:
            st.error(
                f"Order could not be completed: {error}"
            )

        else:
            st.success(
                f"Simulated {result['side']} completed: "
                f"{result['quantity']:g} "
                f"{result['ticker']} shares at "
                f"${result['price']:,.2f}."
            )

            st.info(
                "Refresh the Paper Trading page "
                "to see your updated account balances."
            )