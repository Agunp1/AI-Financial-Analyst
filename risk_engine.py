
from dataclasses import dataclass, field
from math import isfinite


# Day 35 default limits.
# These are configurable simulation rules, not regulatory limits.
MAX_ORDER_VALUE = 10_000.00
MAX_POSITION_WEIGHT = 0.25
MAX_ORDER_WEIGHT = 0.10
MIN_CASH_RESERVE = 1_000.00


@dataclass
class RiskResult:
    approved: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _valid_number(value, name):
    """Convert a value to a finite, nonnegative number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a valid number.")

    if not isfinite(number) or number < 0:
        raise ValueError(
            f"{name} must be finite and cannot be negative."
        )

    return number


def evaluate_order(
    ticker,
    side,
    quantity,
    price,
    cash_balance,
    current_position_quantity,
    current_position_value,
    total_equity,
):
    """
    Evaluate a proposed simulated BUY or SELL order.

    All monetary values must use the same currency.

    This function does not place orders, change positions,
    or write to a database.
    """

    errors = []
    warnings = []
    metrics = {}

    ticker = str(ticker).strip().upper()
    side = str(side).strip().upper()

    if not ticker:
        errors.append("A stock ticker is required.")

    if side not in ("BUY", "SELL"):
        errors.append("Order side must be BUY or SELL.")

    try:
        quantity = _valid_number(quantity, "Quantity")
        price = _valid_number(price, "Execution price")
        cash = _valid_number(cash_balance, "Cash balance")
        position_quantity = _valid_number(
            current_position_quantity,
            "Current position quantity",
        )
        position_value = _valid_number(
            current_position_value,
            "Current position value",
        )
        equity = _valid_number(
            total_equity,
            "Total account equity",
        )
    except ValueError as error:
        errors.append(str(error))
        return RiskResult(
            approved=False,
            errors=errors,
        )

    if quantity == 0:
        errors.append("Order quantity must exceed zero.")

    if price == 0:
        errors.append("Execution price must exceed zero.")

    if equity == 0:
        errors.append("Account equity must exceed zero.")

    if errors:
        return RiskResult(
            approved=False,
            errors=errors,
        )

    order_value = quantity * price

    if not isfinite(order_value):
        errors.append("Calculated order value is invalid.")
        return RiskResult(
            approved=False,
            errors=errors,
        )

    order_weight = order_value / equity

    metrics["ticker"] = ticker
    metrics["side"] = side
    metrics["order_value"] = round(order_value, 2)
    metrics["order_weight"] = order_weight

    if side == "BUY":
        cash_after = cash - order_value
        position_after = position_value + order_value
        position_weight_after = position_after / equity

        metrics["estimated_cash_after"] = round(
            cash_after, 2
        )
        metrics["estimated_position_weight_after"] = (
            position_weight_after
        )

        if order_value > cash:
            errors.append(
                "Insufficient simulated cash for this order."
            )

        if order_value > MAX_ORDER_VALUE:
            errors.append(
                "Order exceeds the $10,000 maximum "
                "simulated order value."
            )

        if cash_after < MIN_CASH_RESERVE:
            errors.append(
                "Order would breach the $1,000 "
                "minimum simulated cash reserve."
            )

        if position_weight_after > MAX_POSITION_WEIGHT:
            errors.append(
                "Order would exceed the 25% "
                "single-position concentration limit."
            )

        if order_weight > MAX_ORDER_WEIGHT:
            warnings.append(
                "This order exceeds 10% of estimated "
                "account equity. Review its size."
            )

    else:
        # Selling an existing long position only.
        if quantity > position_quantity + 1e-9:
            errors.append(
                "Cannot sell more shares than the "
                "simulated account currently owns."
            )

        metrics["estimated_cash_after"] = round(
            cash + order_value, 2
        )

        if order_value > MAX_ORDER_VALUE:
            warnings.append(
                "This sale exceeds $10,000. "
                "Review the transaction before proceeding."
            )

    warnings.append(
        "Execution price is manually supplied. "
        "Historical prices are not live quotes."
    )

    return RiskResult(
        approved=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        metrics=metrics,
    )