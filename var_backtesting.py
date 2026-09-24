
import numpy as np
import pandas as pd


def backtest_historical_var(
    portfolio_returns,
    confidence=0.95,
    window=60,
    portfolio_value=100_000,
):
    """
    Backtest one-day historical VaR using rolling daily returns.

    Each day's VaR uses only the preceding `window` returns.
    The VaR estimate is compared with that day's realized loss.

    Parameters
    ----------
    portfolio_returns : pd.Series
        Historical daily portfolio returns in decimal form.
    confidence : float
        VaR confidence level, e.g. 0.95 or 0.99.
    window : int
        Number of previous trading days used for each estimate.
    portfolio_value : float
        Fixed illustrative portfolio value in dollars.
    """
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between 0 and 1.")

    if window < 2:
        raise ValueError("Window must be at least 2.")

    if portfolio_value <= 0:
        raise ValueError("Portfolio value must be positive.")

    returns = pd.Series(portfolio_returns, dtype=float).dropna()

    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Returns must contain only finite values.")

    if len(returns) <= window:
        raise ValueError("Not enough returns for the selected window.")

    results = []

    for i in range(window, len(returns)):
        historical_returns = returns.iloc[i - window:i]

        var_return = max(
            0.0,
            -float(historical_returns.quantile(1 - confidence)),
        )

        estimated_var = portfolio_value * var_return
        realized_loss = -portfolio_value * float(returns.iloc[i])

        results.append(
            {
                "Date": returns.index[i],
                "Estimated VaR ($)": estimated_var,
                "Realized Loss ($)": realized_loss,
                "Exception": realized_loss > estimated_var,
            }
        )

    result = pd.DataFrame(results)

    exception_count = int(result["Exception"].sum())
    observations = len(result)

    summary = {
        "Confidence": confidence,
        "Expected Exception Rate": 1 - confidence,
        "Observations": observations,
        "Exceptions": exception_count,
        "Observed Exception Rate": exception_count / observations,
    }

    return result, summary
