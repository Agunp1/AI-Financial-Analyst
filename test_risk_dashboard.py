
import unittest

import pandas as pd

from risk_dashboard import build_risk_report
from risk_engine import MAX_POSITION_WEIGHT, MIN_CASH_RESERVE


class TestRiskDashboard(unittest.TestCase):

    @staticmethod
    def make_data(cash, positions_data, prices_data):
        """Create sample data without accessing the real databases."""

        account = pd.DataFrame([
            {"account_id": 1, "cash_balance": cash}
        ])

        positions = pd.DataFrame(
            positions_data,
            columns=["ticker", "quantity", "average_cost"],
        )

        prices = pd.DataFrame(
            prices_data,
            columns=["ticker", "date", "close_price"],
        )

        return account, positions, prices

    def test_account_equity_and_unrealized_pnl(self):
        account, positions, prices = self.make_data(
            cash=90000,
            positions_data=[
                ("AAPL", 10, 150),
                ("MSFT", 5, 300),
            ],
            prices_data=[
                ("AAPL", "2026-09-21", 200),
                ("MSFT", "2026-09-21", 320),
            ],
        )

        report = build_risk_report(account, positions, prices)

        self.assertAlmostEqual(report["cash"], 90000)
        self.assertAlmostEqual(report["holdings_value"], 3600)
        self.assertAlmostEqual(report["equity"], 93600)
        self.assertAlmostEqual(report["unrealized_pnl"], 600)
        self.assertAlmostEqual(
            report["cash_weight"],
            90000 / 93600,
        )

    def test_no_risk_breaches(self):
        account, positions, prices = self.make_data(
            cash=90000,
            positions_data=[("AAPL", 10, 150)],
            prices_data=[("AAPL", "2026-09-21", 200)],
        )

        report = build_risk_report(account, positions, prices)

        self.assertEqual(report["alerts"], [])
        self.assertFalse(
            bool(report["holdings"].iloc[0]["limit_breached"])
        )

    def test_cash_reserve_breach(self):
        account, positions, prices = self.make_data(
            cash=MIN_CASH_RESERVE - 1,
            positions_data=[("AAPL", 10, 150)],
            prices_data=[("AAPL", "2026-09-21", 200)],
        )

        report = build_risk_report(account, positions, prices)

        self.assertTrue(
            any("Cash reserve below" in alert
                for alert in report["alerts"])
        )

    def test_position_concentration_breach(self):
        account, positions, prices = self.make_data(
            cash=1000,
            positions_data=[("AAPL", 100, 150)],
            prices_data=[("AAPL", "2026-09-21", 200)],
        )

        report = build_risk_report(account, positions, prices)

        self.assertGreater(
            report["holdings"].iloc[0]["portfolio_weight"],
            MAX_POSITION_WEIGHT,
        )
        self.assertTrue(
            bool(report["holdings"].iloc[0]["limit_breached"])
        )
        self.assertTrue(
            any("AAPL exceeds" in alert
                for alert in report["alerts"])
        )

    def test_no_open_positions(self):
        account, positions, prices = self.make_data(
            cash=100000,
            positions_data=[],
            prices_data=[],
        )

        report = build_risk_report(account, positions, prices)

        self.assertEqual(report["holdings_value"], 0)
        self.assertEqual(report["equity"], 100000)
        self.assertEqual(report["unrealized_pnl"], 0)
        self.assertTrue(report["holdings"].empty)
        self.assertEqual(report["alerts"], [])

    def test_missing_historical_price(self):
        account, positions, prices = self.make_data(
            cash=90000,
            positions_data=[("AAPL", 10, 150)],
            prices_data=[("MSFT", "2026-09-21", 320)],
        )

        with self.assertRaisesRegex(
            ValueError,
            "Missing historical prices for: AAPL",
        ):
            build_risk_report(account, positions, prices)

    def test_nonpositive_account_equity(self):
        account, positions, prices = self.make_data(
            cash=0,
            positions_data=[],
            prices_data=[],
        )

        with self.assertRaisesRegex(
            ValueError,
            "Estimated account equity must be positive",
        ):
            build_risk_report(account, positions, prices)

    def test_exact_position_limit_is_not_a_breach(self):
        # $25,000 position / $100,000 equity = exactly 25%.
        account, positions, prices = self.make_data(
            cash=75000,
            positions_data=[("AAPL", 100, 200)],
            prices_data=[("AAPL", "2026-09-21", 250)],
        )

        report = build_risk_report(account, positions, prices)

        self.assertAlmostEqual(
            report["holdings"].iloc[0]["portfolio_weight"],
            MAX_POSITION_WEIGHT,
        )
        self.assertFalse(
            bool(report["holdings"].iloc[0]["limit_breached"])
        )
        self.assertEqual(report["alerts"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)