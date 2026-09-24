
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "paper_trading.db"


class OrderError(Exception):
    """A simulated order failed validation."""


def execute_paper_order(ticker, side, quantity, price):
    """
    Execute a simulated order at a user-supplied price.

    No brokerage connection or real-money trading.
    """

    ticker = ticker.strip().upper()
    side = side.strip().upper()

    quantity = float(quantity)
    price = float(price)

    if not ticker:
        raise OrderError("Select a valid ticker.")

    if side not in ("BUY", "SELL"):
        raise OrderError("Side must be BUY or SELL.")

    if not (0 < quantity < float("inf")):
        raise OrderError("Quantity must be positive and finite.")

    if not (0 < price < float("inf")):
        raise OrderError("Price must be positive and finite.")

    if not DB_PATH.exists():
        raise OrderError("paper_trading.db was not found.")

    conn = sqlite3.connect(DB_PATH)

    try:
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
            raise OrderError("No simulated account exists.")

        account_id, cash_balance = account

        position = conn.execute(
            """
            SELECT quantity, average_cost
            FROM positions
            WHERE ticker = ?
            """,
            (ticker,)
        ).fetchone()

        old_quantity = (
            float(position[0]) if position else 0.0
        )

        old_average_cost = (
            float(position[1]) if position else 0.0
        )

        fees = 0.0
        realized_pnl = 0.0

        trade_value = quantity * price

        if side == "BUY":

            if trade_value > cash_balance + 1e-8:
                raise OrderError(
                    "Insufficient simulated cash."
                )

            new_cash = cash_balance - trade_value

            new_quantity = old_quantity + quantity

            new_average_cost = (
                old_quantity * old_average_cost
                + trade_value
            ) / new_quantity

        else:

            if quantity > old_quantity + 1e-8:
                raise OrderError(
                    "Insufficient shares to sell."
                )

            new_cash = cash_balance + trade_value

            new_quantity = old_quantity - quantity

            new_average_cost = old_average_cost

            realized_pnl = (
                price - old_average_cost
            ) * quantity

        conn.execute(
            """
            UPDATE accounts
            SET cash_balance = ?
            WHERE account_id = ?
            """,
            (new_cash, account_id)
        )

        if new_quantity <= 1e-8:

            conn.execute(
                """
                DELETE FROM positions
                WHERE ticker = ?
                """,
                (ticker,)
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
                    new_average_cost
                )
            )

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

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
                realized_pnl
            )
        )

        # Use the latest stored historical closing
        # prices for the recorded equity estimate.
        #
        # The submitted execution price is used
        # for the traded ticker in this snapshot.

        holdings_value = 0.0

        with sqlite3.connect(
            Path(__file__).resolve().parent
            / "hedge_fund.db"
        ) as market_conn:

            positions = conn.execute(
                """
                SELECT ticker, quantity
                FROM positions
                WHERE quantity > 0
                """
            ).fetchall()

            for position_ticker, position_quantity in positions:

                if position_ticker == ticker:

                    mark_price = price

                else:

                    row = market_conn.execute(
                        """
                        SELECT close_price
                        FROM daily_prices
                        WHERE ticker = ?
                        ORDER BY date DESC
                        LIMIT 1
                        """,
                        (position_ticker,)
                    ).fetchone()

                    if row is None:
                        raise OrderError(
                            "Missing historical price for "
                            + position_ticker
                        )

                    mark_price = float(row[0])

                holdings_value += (
                    float(position_quantity)
                    * mark_price
                )

        total_equity = (
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
                total_equity
            )
        )

        conn.commit()

        return {
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "cash_balance": new_cash,
            "realized_pnl": realized_pnl,
            "total_equity": total_equity
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()