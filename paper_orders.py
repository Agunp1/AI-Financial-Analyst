
import sqlite3
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path

from risk_engine import evaluate_order


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "paper_trading.db"
MARKET_DB_PATH = BASE_DIR / "hedge_fund.db"


class OrderError(Exception):
    """A simulated order failed validation."""


def _positive_number(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise OrderError(f"{name} must be a valid number.")

    if not isfinite(number) or number <= 0:
        raise OrderError(
            f"{name} must be positive and finite."
        )

    return number


def _latest_historical_prices(market_conn):
    """
    Load the latest stored historical closing price
    for each ticker.

    These are not live market quotes.
    """
    rows = market_conn.execute(
        """
        SELECT p.ticker, p.close_price
        FROM daily_prices AS p
        WHERE p.date = (
            SELECT MAX(p2.date)
            FROM daily_prices AS p2
            WHERE p2.ticker = p.ticker
        )
        """
    ).fetchall()

    result = {}

    for ticker, close_price in rows:
        price = float(close_price)

        if not isfinite(price) or price <= 0:
            raise OrderError(
                f"Invalid historical price for {ticker}."
            )

        result[ticker] = price

    return result


def execute_paper_order(ticker, side, quantity, price):
    """
    Validate and execute a simulated BUY or SELL.

    The execution price is supplied manually.
    No real brokerage orders are placed.

    Risk checks are performed before any database
    changes are committed.
    """

    ticker = str(ticker).strip().upper()
    side = str(side).strip().upper()

    if not ticker:
        raise OrderError("Select a valid ticker.")

    if side not in ("BUY", "SELL"):
        raise OrderError("Side must be BUY or SELL.")

    quantity = _positive_number(
        quantity,
        "Quantity",
    )

    price = _positive_number(
        price,
        "Execution price",
    )

    if not DB_PATH.is_file():
        raise OrderError(
            "paper_trading.db was not found."
        )

    if not MARKET_DB_PATH.is_file():
        raise OrderError(
            "hedge_fund.db was not found."
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        # Lock the simulated trading database while
        # validating and processing this order.
        conn.execute("BEGIN IMMEDIATE")

        account = conn.execute(
            """
            SELECT account_id, cash_balance
            FROM accounts
            ORDER BY account_id
            LIMIT 1
            """
        ).fetchone()

        if account is None:
            raise OrderError(
                "No simulated trading account exists."
            )

        account_id = account[0]
        cash_balance = float(account[1])

        if not isfinite(cash_balance):
            raise OrderError(
                "The simulated cash balance is invalid."
            )

        # Read every existing position so the risk
        # engine can estimate total account equity.
        positions = conn.execute(
            """
            SELECT ticker, quantity, average_cost
            FROM positions
            """
        ).fetchall()

        position_map = {}

        for (
            position_ticker,
            position_quantity,
            average_cost,
        ) in positions:

            position_map[position_ticker] = {
                "quantity": float(position_quantity),
                "average_cost": float(average_cost),
            }

        current_position = position_map.get(
            ticker,
            {
                "quantity": 0.0,
                "average_cost": 0.0,
            },
        )

        old_quantity = current_position["quantity"]
        old_average_cost = (
            current_position["average_cost"]
        )

        with sqlite3.connect(
            MARKET_DB_PATH
        ) as market_conn:

            historical_prices = (
                _latest_historical_prices(market_conn)
            )

        if ticker not in historical_prices:
            raise OrderError(
                f"No stored historical price exists "
                f"for {ticker}."
            )

        # Use stored historical closing prices for
        # the pre-trade portfolio risk estimate.
        historical_holdings_value = 0.0

        for position_ticker, details in (
            position_map.items()
        ):

            position_quantity = details["quantity"]

            if position_quantity <= 0:
                continue

            if position_ticker not in historical_prices:
                raise OrderError(
                    "Missing historical price for "
                    + position_ticker
                )

            historical_holdings_value += (
                position_quantity
                * historical_prices[position_ticker]
            )

        total_equity = (
            cash_balance + historical_holdings_value
        )

        current_position_value = (
            old_quantity
            * historical_prices[ticker]
        )

        # DAY 35:
        # Check cash, concentration, order size,
        # cash reserve and available shares.
        risk = evaluate_order(
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            cash_balance=cash_balance,
            current_position_quantity=old_quantity,
            current_position_value=current_position_value,
            total_equity=total_equity,
        )

        if not risk.approved:
            message = "; ".join(risk.errors)

            raise OrderError(
                message
                or "The simulated order failed "
                "the risk checks."
            )

        trade_value = quantity * price
        fees = 0.0
        realized_pnl = 0.0

        if side == "BUY":

            # Defense in depth: check cash again
            # even though the risk engine approved.
            if trade_value > cash_balance + 1e-8:
                raise OrderError(
                    "Insufficient simulated cash."
                )

            new_cash = cash_balance - trade_value

            new_quantity = (
                old_quantity + quantity
            )

            new_average_cost = (
                old_quantity * old_average_cost
                + trade_value
            ) / new_quantity

        else:

            if quantity > old_quantity + 1e-8:
                raise OrderError(
                    "Insufficient shares to sell."
                )

            new_cash = (
                cash_balance + trade_value
            )

            new_quantity = (
                old_quantity - quantity
            )

            new_average_cost = old_average_cost

            realized_pnl = (
                price - old_average_cost
            ) * quantity

        # Update the simulated account.
        conn.execute(
            """
            UPDATE accounts
            SET cash_balance = ?
            WHERE account_id = ?
            """,
            (
                new_cash,
                account_id,
            ),
        )

        # Update or close the affected position.
        if new_quantity <= 1e-8:

            conn.execute(
                """
                DELETE FROM positions
                WHERE ticker = ?
                """,
                (ticker,),
            )

        else:

            conn.execute(
                """
                INSERT INTO positions (
                    ticker,
                    quantity,
                    average_cost
                )
                VALUES (?, ?, ?)
                ON CONFLICT(ticker)
                DO UPDATE SET
                    quantity = excluded.quantity,
                    average_cost = excluded.average_cost
                """,
                (
                    ticker,
                    new_quantity,
                    new_average_cost,
                ),
            )

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        # Record the simulated trade.
        conn.execute(
            """
            INSERT INTO trades (
                timestamp,
                ticker,
                side,
                quantity,
                execution_price,
                fees,
                realized_pnl
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                ticker,
                side,
                quantity,
                price,
                fees,
                realized_pnl,
            ),
        )

        # Record an illustrative equity snapshot.
        #
        # The traded ticker is marked at its manually
        # supplied execution price. Other holdings
        # use their latest stored historical closes.
        #
        # This is not a live portfolio valuation.
        updated_positions = conn.execute(
            """
            SELECT ticker, quantity
            FROM positions
            WHERE quantity > 0
            """
        ).fetchall()

        holdings_value = 0.0

        for (
            position_ticker,
            position_quantity,
        ) in updated_positions:

            if position_ticker == ticker:
                mark_price = price

            else:
                if (
                    position_ticker
                    not in historical_prices
                ):
                    raise OrderError(
                        "Missing historical price for "
                        + position_ticker
                    )

                mark_price = historical_prices[
                    position_ticker
                ]

            holdings_value += (
                float(position_quantity)
                * mark_price
            )

        recorded_equity = (
            new_cash + holdings_value
        )

        conn.execute(
            """
            INSERT INTO equity_snapshots (
                timestamp,
                cash_balance,
                holdings_value,
                total_equity
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                timestamp,
                new_cash,
                holdings_value,
                recorded_equity,
            ),
        )

        # All validation and database operations
        # have succeeded. Commit them together.
        conn.commit()

        return {
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "cash_balance": new_cash,
            "realized_pnl": realized_pnl,
            "total_equity": recorded_equity,
            "risk_warnings": risk.warnings,
            "risk_metrics": risk.metrics,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()