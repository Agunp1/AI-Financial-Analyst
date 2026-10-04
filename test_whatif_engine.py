"""Tests for the Day 81 what-if engine (synthetic daily market with planted sensitivities)."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import whatif_engine as we


def market(days=400, seed=8):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-10-02", periods=days)
    spy = rng.normal(0.0004, 0.01, days)
    d10 = rng.normal(0, 0.06, days)
    dhy = rng.normal(0, 0.04, days)
    rets = {
        "SPY": spy,
        "TLT": -0.16 * d10 + rng.normal(0, 0.002, days),
        "HYG": 0.3 * spy - 0.03 * dhy + rng.normal(0, 0.002, days),
        "AAA": 1.3 * spy + rng.normal(0, 0.012, days),
        "BBB": 0.7 * spy + rng.normal(0, 0.008, days),
    }
    prices = pd.DataFrame({k: 100 * np.cumprod(1 + v) for k, v in rets.items()}, index=dates)
    fred = pd.DataFrame({"DGS10": 4 + np.cumsum(d10), "BAMLH0A0HYM2": 3 + np.cumsum(dhy)}, index=dates)
    # the first change is lost when differencing, so prices start one day later in effect
    return prices, fred


class WhatIfTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        prices, fred = market()
        cls.model = we.RiskModel(prices, fred)

    def test_recovers_planted_betas(self):
        b = self.model.betas
        self.assertAlmostEqual(b.loc["TLT", "interest_rates"], -0.16, delta=0.01)
        self.assertAlmostEqual(b.loc["AAA", "equity_market"], 1.3, delta=0.1)
        self.assertAlmostEqual(b.loc["SPY", "equity_market"], 1.0)        # its own factor

    def test_factor_instrument_is_not_double_counted(self):
        # SPY is the equity factor: in a scenario it moves exactly with the equity shock, nothing more
        pnl = we.scenario_pnl(self.model, {"SPY": 1.0}, {"equity_market": -0.2, "interest_rates": 2.0,
                                                          "credit_spreads": 1.5}, 1.0)
        self.assertAlmostEqual(float(pnl["scenario_return"].iloc[0]), -0.2, places=9)

    def test_scenario_pnl_is_linear_in_shocks(self):
        weights = {"AAA": 0.6, "TLT": 0.4}
        shock = {"equity_market": -0.20, "interest_rates": -0.5}
        pnl = we.scenario_pnl(self.model, weights, shock).set_index("symbol")
        b = self.model.betas
        expected_aaa = 0.6 * (b.loc["AAA", "equity_market"] * -0.20 + b.loc["AAA", "interest_rates"] * -0.5) * 1e6
        self.assertAlmostEqual(pnl.loc["AAA", "pnl"], expected_aaa, places=4)
        self.assertGreater(pnl.loc["TLT", "pnl"], 0)            # bonds gain when yields fall

    def test_parametric_var_and_es(self):
        risk = we.portfolio_risk(self.model, {"AAA": 1.0})
        sigma_day = risk["volatility_annual"] / np.sqrt(252)
        self.assertAlmostEqual(risk["var99_1d_parametric"], 2.326347874 * sigma_day * 1e6, delta=1)
        self.assertGreater(risk["es99_1d_parametric"], risk["var99_1d_parametric"])
        self.assertAlmostEqual(risk["risk_shares"].sum(), 1.0)

    def test_adding_treasuries_lowers_equity_crash_loss(self):
        before = {"AAA": 0.5, "BBB": 0.5}
        after = {"AAA": 0.4, "BBB": 0.4, "TLT": 0.2}
        table = we.compare(self.model, before, after, we.SCENARIOS["Equity sell-off"])
        self.assertGreater(table.loc["What-if", "scenario_pnl"], table.loc["Current", "scenario_pnl"])
        self.assertLess(table.loc["What-if", "volatility_annual"], table.loc["Current", "volatility_annual"])

    def test_unknown_holdings_reported_not_invented(self):
        risk = we.portfolio_risk(self.model, {"AAA": 0.5, "ZZZ": 0.5})
        self.assertEqual(risk["missing"], ["ZZZ"])
        pnl = we.scenario_pnl(self.model, {"ZZZ": 1.0}, {"equity_market": -0.1})
        self.assertTrue(np.isnan(pnl.loc[0, "pnl"]))

    def test_proposal_goes_to_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proposals.csv"
            we.save_proposal({"AAA": 0.5, "TLT": 0.5}, "hedge", "Equity sell-off", {"vol": 0.1}, path)
            table = we.save_proposal({"AAA": 1.0}, "undo", "none", {}, path)
            self.assertEqual(list(table["proposal_id"]), ["WI-0001", "WI-0002"])
            self.assertTrue((table["status"] == "PENDING_HUMAN_APPROVAL").all())
            self.assertTrue((table["automatic_execution_authorized"] == 0).all())

    def test_align_prices_uses_coarsest_calendar(self):
        daily = pd.DataFrame({"A": range(100)}, index=pd.bdate_range("2026-01-01", periods=100))
        coarse = daily.iloc[::20].rename(columns={"A": "B"})
        aligned = we.align_prices([daily, coarse])
        self.assertEqual(len(aligned), len(coarse))
        self.assertEqual(list(aligned.columns), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
