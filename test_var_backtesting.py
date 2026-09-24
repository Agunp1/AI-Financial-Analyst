
import unittest

import pandas as pd

from var_backtesting import backtest_historical_var


class TestVaRBacktesting(unittest.TestCase):

    def setUp(self):
        self.returns = pd.Series(
            [-0.01, 0.02, -0.03, 0.01, 0.00, -0.05, 0.02],
            index=pd.date_range("2026-01-01", periods=7, freq="B"),
        )

    def test_observation_count(self):
        result, summary = backtest_historical_var(
            self.returns, window=3
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(summary["Observations"], 4)

    def test_exception_detection(self):
        result, summary = backtest_historical_var(
            self.returns,
            confidence=0.95,
            window=3,
            portfolio_value=100_000,
        )

        # The -5% return exceeds the VaR estimated
        # using the preceding three returns.
        self.assertTrue(result["Exception"].any())
        self.assertGreaterEqual(summary["Exceptions"], 1)

    def test_no_lookahead(self):
        result, _ = backtest_historical_var(
            self.returns,
            confidence=0.95,
            window=3,
            portfolio_value=100_000,
        )

        # The first VaR estimate uses only the first
        # three returns, excluding the realized return.
        expected_var = max(
            0.0,
            -self.returns.iloc[:3].quantile(0.05),
        ) * 100_000

        self.assertAlmostEqual(
            result.iloc[0]["Estimated VaR ($)"],
            expected_var,
        )

    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            backtest_historical_var(
                self.returns, confidence=1.5, window=3
            )

    def test_insufficient_history(self):
        with self.assertRaises(ValueError):
            backtest_historical_var(
                self.returns, window=10
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
