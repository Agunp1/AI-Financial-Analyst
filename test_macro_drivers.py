"""Tests for the Day 76d macro drivers: planted sensitivities must be recovered."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import macro_drivers as md


def planted_market(n=320, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-10-02", periods=n)
    d10 = rng.normal(0, 0.06, n)            # daily 10Y yield change, pp
    dbe = rng.normal(0, 0.03, n)
    dhy = rng.normal(0, 0.05, n)
    spy = rng.normal(0.0004, 0.01, n)
    usd = rng.normal(0, 0.004, n)
    oil = rng.normal(0, 0.02, n)
    fred = pd.DataFrame({"DGS10": 4 + np.cumsum(d10), "T10YIE": 2.3 + np.cumsum(dbe),
                         "BAMLH0A0HYM2": 3 + np.cumsum(dhy)}, index=dates)
    def path(r):
        return 100 * np.cumprod(1 + r)
    # The first day's return is lost when prices are rebuilt, so shift factors by one.
    returns = {
        "SPY": spy, "DX-Y.NYB": usd, "CL=F": oil,
        "TLT": -17 * d10 + rng.normal(0, 0.001, n),
        "HYG": 0.3 * spy - 4 * dhy + rng.normal(0, 0.001, n),
        "GC=F": -0.9 * usd + 0.5 * dbe + rng.normal(0, 0.004, n),
    }
    prices = pd.DataFrame({k: path(v) for k, v in returns.items()}, index=dates)
    # Factor moves on day t are realised in prices from t-1 to t: align by construction
    fred = fred.shift(0)
    universe = pd.DataFrame({"symbol": list(returns), "name": list(returns),
                             "asset_class": ["Equity", "FX", "Commodity", "Fixed Income", "Fixed Income", "Commodity"],
                             "sub_class": ["x"] * 6})
    return prices, fred, universe


class MacroDriverTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        prices, fred, universe = planted_market()
        cls.betas, cls.attr, cls.moves, cls.stories, cls.validation = md.run_macro_drivers(
            prices, fred, universe, Path(cls.tmp.name), verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_recovers_duration_from_rate_beta(self):
        self.assertAlmostEqual(self.betas.loc["TLT", "beta_interest_rates"], -17, delta=0.5)

    def test_recovers_credit_and_equity_betas(self):
        self.assertAlmostEqual(self.betas.loc["HYG", "beta_credit_spreads"], -4, delta=0.2)
        self.assertAlmostEqual(self.betas.loc["HYG", "beta_equity_market"], 0.3, delta=0.05)

    def test_gold_dollar_relationship(self):
        self.assertAlmostEqual(self.betas.loc["GC=F", "beta_us_dollar"], -0.9, delta=0.2)

    def test_instrument_not_regressed_on_itself(self):
        self.assertTrue(pd.isna(self.betas.loc["SPY"].get("beta_equity_market", np.nan)))

    def test_attribution_adds_up(self):
        row = self.attr[(self.attr["symbol"] == "TLT") & (self.attr["window"] == "1 month")].iloc[0]
        parts = row.filter(like="contribution_").fillna(0).sum() + row["alpha"] + row["unexplained"]
        self.assertAlmostEqual(parts, row["actual"], places=10)

    def test_rates_explain_treasury_move(self):
        row = self.attr[(self.attr["symbol"] == "TLT") & (self.attr["window"] == "1 month")].iloc[0]
        self.assertLess(abs(row["unexplained"]), 0.01)

    def test_validation_passes(self):
        failed = self.validation[~self.validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())


class AlignmentTests(unittest.TestCase):

    def test_intraday_price_timestamps_do_not_shift_returns(self):
        prices, fred, _ = planted_market()
        stamped = prices.copy()
        stamped.index = stamped.index + pd.Timedelta(hours=5)
        returns, factors = md.build_daily_frame(stamped, fred)
        lags = md.alignment_lags(returns, factors)
        self.assertLess(lags[0], -0.9)
        betas = md.macro_betas(returns["TLT"], factors)
        self.assertAlmostEqual(betas["beta_interest_rates"], -17, delta=0.5)

    def test_misaligned_dates_are_flagged(self):
        prices, fred, universe = planted_market()
        with tempfile.TemporaryDirectory() as tmp:
            *_, validation = md.run_macro_drivers(prices, fred.shift(1), universe, Path(tmp), verbose=False)
        check = validation[validation["check"].str.startswith("Rates factor lines up")].iloc[0]
        self.assertFalse(check["passed"])


if __name__ == "__main__":
    unittest.main()
