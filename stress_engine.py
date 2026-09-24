
import pandas as pd


DEFAULT_SCENARIOS = {
    "Mild decline": -0.05,
    "Market correction": -0.10,
    "Severe decline": -0.20,
}


def run_stress_tests(report, scenarios=None):
    """
    Apply hypothetical percentage shocks to all stock holdings.

    Cash is unchanged. No trades are executed and no
    databases are modified.
    """
    if scenarios is None:
        scenarios = DEFAULT_SCENARIOS

    cash = float(report["cash"])
    holdings = report["holdings"]
    starting_equity = float(report["equity"])
    starting_holdings = float(report["holdings_value"])

    if starting_equity <= 0:
        raise ValueError("Starting equity must be positive.")

    results = []

    for scenario_name, shock in scenarios.items():
        shock = float(shock)

        if not -1 <= shock <= 0:
            raise ValueError(
                "Stress shocks must be between -100% and 0%."
            )

        stressed_holdings = starting_holdings * (1 + shock)
        stressed_equity = cash + stressed_holdings
        portfolio_loss = stressed_equity - starting_equity
        portfolio_return = portfolio_loss / starting_equity

        if holdings.empty:
            largest_position_weight = 0.0
        else:
            stressed_values = (
                holdings["market_value"] * (1 + shock)
            )
            largest_position_weight = float(
                stressed_values.max() / stressed_equity
            ) if stressed_equity > 0 else 0.0

        results.append({
            "Scenario": scenario_name,
            "Stock Shock (%)": shock * 100,
            "Stressed Holdings ($)": stressed_holdings,
            "Stressed Equity ($)": stressed_equity,
            "Portfolio P&L ($)": portfolio_loss,
            "Portfolio Return (%)": portfolio_return * 100,
            "Largest Position Weight (%)":
                largest_position_weight * 100,
        })

    return pd.DataFrame(results)