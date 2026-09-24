
import unittest

from risk_engine import evaluate_order


class TestRiskEngine(unittest.TestCase):

    def test_normal_buy_approved(self):
        result = evaluate_order(
            ticker="AAPL",
            side="BUY",
            quantity=1,
            price=200,
            cash_balance=50_000,
            current_position_quantity=0,
            current_position_value=0,
            total_equity=100_000,
        )
        self.assertTrue(result.approved)

    def test_insufficient_cash_rejected(self):
        result = evaluate_order(
            ticker="AAPL",
            side="BUY",
            quantity=10,
            price=200,
            cash_balance=1_500,
            current_position_quantity=0,
            current_position_value=0,
            total_equity=100_000,
        )
        self.assertFalse(result.approved)
        self.assertTrue(result.errors)

    def test_oversized_buy_rejected(self):
        result = evaluate_order(
            ticker="MSFT",
            side="BUY",
            quantity=100,
            price=200,
            cash_balance=50_000,
            current_position_quantity=0,
            current_position_value=0,
            total_equity=100_000,
        )
        self.assertFalse(result.approved)

    def test_concentration_limit(self):
        result = evaluate_order(
            ticker="AAPL",
            side="BUY",
            quantity=10,
            price=200,
            cash_balance=50_000,
            current_position_quantity=10,
            current_position_value=24_000,
            total_equity=100_000,
        )
        self.assertFalse(result.approved)

    def test_overselling_rejected(self):
        result = evaluate_order(
            ticker="AAPL",
            side="SELL",
            quantity=10,
            price=200,
            cash_balance=50_000,
            current_position_quantity=5,
            current_position_value=1_000,
            total_equity=100_000,
        )
        self.assertFalse(result.approved)

    def test_valid_sell_approved(self):
        result = evaluate_order(
            ticker="AAPL",
            side="SELL",
            quantity=2,
            price=200,
            cash_balance=50_000,
            current_position_quantity=5,
            current_position_value=1_000,
            total_equity=100_000,
        )
        self.assertTrue(result.approved)

    def test_invalid_price_rejected(self):
        result = evaluate_order(
            ticker="AAPL",
            side="BUY",
            quantity=1,
            price=-200,
            cash_balance=50_000,
            current_position_quantity=0,
            current_position_value=0,
            total_equity=100_000,
        )
        self.assertFalse(result.approved)


if __name__ == "__main__":
    unittest.main(verbosity=2)