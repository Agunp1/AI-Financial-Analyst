
import numpy as np
import pandas as pd

def calculate_historical_var(
    holdings,
    price_history,
    confidence_levels=(0.95, 0.99),
):

    """
    Calculate one-day historical VaR and Expected Shortfall.

    holdings: DataFrame from build_risk_report()["holdings"]
              with ticker and market_value columns.
    price_history: DataFrame with date, ticker, close_price.
    """

    required_holdings = {"ticker", "market_value"}
    required_prices = {"date", "ticker", "close_price"}

    if not required_holdings.issubset(holdings.columns):
        raise ValueError("Holdings must contain ticker and market_value.")

    if not required_prices.issubset(price_history.columns):
        raise ValueError(
            "Price history must contain date, ticker and close_price."
        )

    if holdings.empty:
        raise ValueError("No open positions for historical VaR.")

    if any(not 0 < level < 1 for level in confidence_levels):
        raise ValueError("Confidence levels must be between 0 and 1.")

    exposure = holdings.groupby("ticker")["market_value"].sum()

    if exposure.isna().any() or (exposure < 0).any():
        raise ValueError("Holdings must have valid, nonnegative values.")

    prices = price_history.copy()
    prices["date"] = pd.to_datetime(prices["date"])

    matrix = (
        prices.pivot(
            index="date",
            columns="ticker",
            values="close_price",
        )
        .sort_index()
    )

    missing = exposure.index.difference(matrix.columns)

    if len(missing):
        raise ValueError(
            "Missing historical prices for: " + ", ".join(missing)
        )

    matrix = matrix[exposure.index].dropna()

    if len(matrix) < 31:
        raise ValueError(
            "At least 31 aligned price observations are required."
        )

    if (matrix <= 0).any().any():
        raise ValueError("Historical prices must be positive.")

    returns = matrix.pct_change().dropna()

    # Revalue today's holdings under each historical daily return.
    # Cash is assumed unchanged, so it contributes zero daily P&L.
    scenario_pnl = returns.mul(exposure, axis=1).sum(axis=1)

    # Positive values represent losses.
    losses = -scenario_pnl

    results = []

    for confidence in confidence_levels:
        var = max(
            0.0,
            float(np.quantile(losses, confidence)),
        )

        tail = losses[losses >= var]

        expected_shortfall = max(
            0.0,
            float(tail.mean()),
        )

        results.append(
            {
                "Confidence": f"{confidence:.0%}",
                "Historical VaR ($)": var,
                "Expected Shortfall ($)": expected_shortfall,
                "Observations": len(losses),
            }
        )

    return pd.DataFrame(results), losses