
import unittest

import pandas as pd

from stress_engine import run_stress_tests


class TestStressEngine(unittest.TestCase):

    def setUp(self):
        # $80,000 cash + $20,000 in stocks.
        self.report = {
            "cash": 80000.0,
            "holdings_value": 20000.0,
            "equity": 100000.0,
            "holdings": pd.DataFrame({
                "ticker": ["AAPL", "MSFT"],
                "market_value": [12000.0, 8000.0],
            }),
        }

    def test_default_scenarios(self):
        result = run_stress_tests(self.report)

        self.assertEqual(len(result), 3)
        self.assertEqual(
            result["Scenario"].tolist(),
            [
                "Mild decline",
                "Market correction",
                "Severe decline",
            ],
        )

    def test_five_percent_decline(self):
        result = run_stress_tests(self.report)
        mild = result.iloc[0]

        self.assertAlmostEqual(
            mild["Stressed Equity ($)"], 99000
        )
        self.assertAlmostEqual(
            mild["Portfolio P&L ($)"], -1000
        )
        self.assertAlmostEqual(
            mild["Portfolio Return (%)"], -1.0
        )

    def test_twenty_percent_decline(self):
        result = run_stress_tests(self.report)
        severe = result.iloc[2]

        self.assertAlmostEqual(
            severe["Stressed Holdings ($)"], 16000
        )
        self.assertAlmostEqual(
            severe["Stressed Equity ($)"], 96000
        )
        self.assertAlmostEqual(
            severe["Portfolio P&L ($)"], -4000
        )

    def test_cash_only_portfolio(self):
        report = {
            "cash": 100000.0,
            "holdings_value": 0.0,
            "equity": 100000.0,
            "holdings": pd.DataFrame(
                columns=["ticker", "market_value"]
            ),
        }

        result = run_stress_tests(report)

        self.assertTrue(
            (result["Stressed Equity ($)"] == 100000).all()
        )
        self.assertTrue(
            (result["Portfolio P&L ($)"] == 0).all()
        )

    def test_largest_position_weight(self):
        result = run_stress_tests(
            self.report,
            {"Custom decline": -0.10},
        )

        # AAPL: $12,000 × 90% = $10,800
        # Equity: $80,000 + $18,000 = $98,000
        expected_weight = 10800 / 98000 * 100

        self.assertAlmostEqual(
            result.iloc[0]["Largest Position Weight (%)"],
            expected_weight,
        )

    def test_invalid_shock_rejected(self):
        with self.assertRaises(ValueError):
            run_stress_tests(
                self.report,
                {"Invalid": -1.5},
            )

    def test_nonpositive_equity_rejected(self):
        invalid_report = dict(self.report)
        invalid_report["equity"] = 0

        with self.assertRaises(ValueError):
            run_stress_tests(invalid_report)


if __name__ == "__main__":
    unittest.main(verbosity=2)