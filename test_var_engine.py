
import unittest

import pandas as pd

from var_engine import calculate_historical_var


class TestHistoricalVaR(unittest.TestCase):

    def setUp(self):
        dates = pd.bdate_range("2026-01-01", periods=60)

        # Deterministic sample prices for reproducible tests.
        prices = [
            100 * (1 + 0.002 * i + 0.015 * ((i % 7) - 3))
            for i in range(60)
        ]

        self.history = pd.DataFrame(
            {
                "date": dates,
                "ticker": "AAPL",
                "close_price": prices,
            }
        )

        self.holdings = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "market_value": [2000.0],
            }
        )

    def test_returns_two_confidence_levels(self):
        result, losses = calculate_historical_var(
            self.holdings,
            self.history,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(len(losses), 59)
        self.assertEqual(
            result["Confidence"].tolist(),
            ["95%", "99%"],
        )

    def test_expected_shortfall_at_least_var(self):
        result, _ = calculate_historical_var(
            self.holdings,
            self.history,
        )

        self.assertTrue(
            (
                result["Expected Shortfall ($)"]
                >= result["Historical VaR ($)"]
            ).all()
        )

    def test_missing_prices_rejected(self):
        bad_holdings = pd.DataFrame(
            {
                "ticker": ["MSFT"],
                "market_value": [2000.0],
            }
        )

        with self.assertRaises(ValueError):
            calculate_historical_var(
                bad_holdings,
                self.history,
            )

    def test_insufficient_history_rejected(self):
        with self.assertRaises(ValueError):
            calculate_historical_var(
                self.holdings,
                self.history.head(10),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)