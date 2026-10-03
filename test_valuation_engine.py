"""Tests for the Day 78 valuation engine."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import valuation_engine as ve
from vittantra_pricing import two_stage_value

MARKET = {"risk_free": 0.04, "risk_free_source": "test", "spreads_bp": dict(ve.DEFAULT_SPREADS_BP),
          "spread_source": "test"}


def company(**overrides):
    row = {"ticker": "AAA", "name": "Alpha", "sector": "Industrials", "price": 50.0,
           "shares_outstanding": 1e9, "total_debt": 10e9, "cash": 2e9, "interest_coverage": 10.0,
           "operating_cash_flow_ttm": 5e9, "capex_ttm": 1.5e9, "interest_expense_ttm": 0.5e9,
           "free_cash_flow_ttm": 3.5e9, "revenue_growth": 0.08, "roe": 0.18, "equity": 20e9,
           "net_income_ttm": 3.6e9, "dividends_ttm": 1.44e9, "as_of": "2026-10-01"}
    row.update(overrides)
    return row


class ValuationModelTests(unittest.TestCase):

    def test_dcf_matches_hand_calculation(self):
        out = ve.value_company(company(), 1.0, MARKET)
        a = ve.ASSUMPTIONS
        re = 0.04 + (2 / 3 * 1.0 + 1 / 3) * a["equity_risk_premium"]
        rd = 0.04 + ve.DEFAULT_SPREADS_BP["AAA"] / 10_000
        w = (50e9 * re + 10e9 * rd * (1 - a["tax_rate"])) / 60e9
        fcff = 5e9 + 0.5e9 * (1 - a["tax_rate"]) - 1.5e9
        g_t = min(a["max_terminal_growth"], 0.04)
        ev = two_stage_value(fcff, w, ve.three_stage_path(0.08, g_t), g_t)["value"]
        self.assertAlmostEqual(out["wacc"], w, places=12)
        self.assertAlmostEqual(out["dcf_value"], (ev - 10e9 + 2e9) / 1e9, places=6)

    def test_retention_from_dividends(self):
        out = ve.value_company(company(), 1.0, MARKET)
        self.assertAlmostEqual(out["retention"], 0.6)
        self.assertIsNotNone(out["ddm_value"])

    def test_reverse_dcf_reproduces_price(self):
        out = ve.value_company(company(), 1.0, MARKET)
        check = ve.dcf_per_share(out["fcff_ttm"], out["implied_growth"], out["terminal_growth"], out["wacc"],
                                 10e9, 2e9, 1e9)
        self.assertAlmostEqual(check["per_share"], 50.0, delta=0.01)

    def test_higher_wacc_lowers_value(self):
        low = ve.value_company(company(), 0.8, MARKET)["dcf_value"]
        high = ve.value_company(company(), 1.6, MARKET)["dcf_value"]
        self.assertGreater(low, high)

    def test_financials_use_residual_income(self):
        out = ve.value_company(company(sector="Financials"), 1.0, MARKET)
        self.assertNotIn("dcf_value", out)
        self.assertEqual(out["primary_model"], "RI")

    def test_utility_dividend_payer_uses_ddm(self):
        out = ve.value_company(company(sector="Utilities"), 1.0, MARKET)
        self.assertEqual(out["primary_model"], "DDM")

    def test_negative_free_cash_flow_skips_dcf(self):
        out = ve.value_company(company(operating_cash_flow_ttm=1e9, capex_ttm=3e9), 1.0, MARKET)
        self.assertNotIn("dcf_value", out)
        self.assertTrue(any("not positive" in n for n in out["notes"]))

    def test_cyclical_growth_capped(self):
        out = ve.value_company(company(sector="Energy", revenue_growth=0.40), 1.0, MARKET)
        self.assertEqual(out["dcf_initial_growth"], ve.ASSUMPTIONS["max_cyclical_growth"])

    def test_missing_beta_and_coverage_are_labelled(self):
        out = ve.value_company(company(interest_coverage=np.nan), None, MARKET)
        self.assertEqual(out["beta_adjusted"], 1.0)
        self.assertEqual(out["synthetic_rating"], "BBB")
        self.assertTrue(any("assumed" in n for n in out["notes"]))

    def test_missing_price_not_valued(self):
        out = ve.value_company(company(price=np.nan), 1.0, MARKET)
        self.assertNotIn("fair_value", out)

    def test_synthetic_rating_ladder(self):
        self.assertEqual(ve.synthetic_rating(12), "AAA")
        self.assertEqual(ve.synthetic_rating(3.5), "BBB")
        self.assertEqual(ve.synthetic_rating(0.5), "CCC & below")


class ValuationRunTests(unittest.TestCase):

    def test_end_to_end_outputs_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            rows = [company(ticker=t, sector=s, revenue_growth=g)
                    for t, s, g in [("AAA", "Industrials", 0.08), ("BBB", "Financials", 0.05),
                                    ("CCC", "Utilities", 0.03), ("DDD", "Information Technology", 0.25),
                                    ("EEE", "Energy", 0.30)]]
            pd.DataFrame(rows).to_csv(base / ve.METRICS_FILE, index=False)
            pd.DataFrame({"ticker": ["AAA", "DDD"], "beta": [1.1, 1.4]}).to_csv(base / ve.RATINGS_FILE, index=False)
            valuation, sensitivity, assumptions, validation = ve.run_valuation(base, verbose=False)
            self.assertTrue(validation["passed"].all(), validation.to_string())
            self.assertEqual(len(sensitivity[sensitivity["ticker"] == "AAA"]), 9)
            self.assertIn("risk_free_rate", set(assumptions["assumption"]))
            grid = sensitivity[sensitivity["ticker"] == "AAA"]
            # value falls as WACC rises, rises with terminal growth
            mid_g = grid[np.isclose(grid["terminal_growth"], grid["terminal_growth"].median())]
            self.assertTrue(mid_g.sort_values("wacc")["value_per_share"].is_monotonic_decreasing)


if __name__ == "__main__":
    unittest.main()
