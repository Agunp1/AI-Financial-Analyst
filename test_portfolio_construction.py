"""Tests for Day 79 portfolio construction and the shrinkage covariance."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import portfolio_construction as pc
from vittantra_risk_model import constant_correlation_shrinkage

SECTORS = ["Tech", "Health", "Energy", "Financials", "Utilities"]


def synthetic(n=25, days=300, seed=4):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-10-02", periods=days)
    market = rng.normal(0.0004, 0.01, days)
    tickers = [f"S{i:02d}" for i in range(n)]
    betas = rng.uniform(0.6, 1.4, n)
    rets = np.outer(market, betas) + rng.normal(0, 0.012, (days, n))
    prices = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=dates, columns=tickers)
    ratings = pd.DataFrame({
        "name": tickers, "sector": [SECTORS[i % len(SECTORS)] for i in range(n)],
        "rating": "Neutral", "composite_ic_weighted": np.linspace(10, 90, n),
    }, index=pd.Index(tickers, name="ticker"))
    return ratings, prices


class ShrinkageTests(unittest.TestCase):

    def test_intensity_between_zero_and_one_and_psd(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=(60, 30)) @ np.diag(rng.uniform(0.5, 2, 30))
        cov, delta = constant_correlation_shrinkage(x)
        self.assertTrue(0 <= delta <= 1)
        self.assertGreater(np.linalg.eigvalsh(cov).min(), 0)
        np.testing.assert_allclose(np.diag(cov), x.var(axis=0), rtol=1e-10)   # variances kept

    def test_less_shrinkage_with_more_data(self):
        rng = np.random.default_rng(2)
        common = rng.normal(size=(5000, 1))
        loadings = np.linspace(0.0, 1.5, 10)            # correlations differ across pairs
        x = common * loadings + rng.normal(size=(5000, 10))
        _, short = constant_correlation_shrinkage(x[:40])
        _, long = constant_correlation_shrinkage(x)
        self.assertLess(long, short)

    def test_keeps_average_correlation(self):
        rng = np.random.default_rng(3)
        common = rng.normal(size=(40, 1))
        x = common + rng.normal(size=(40, 30))           # average correlation ≈ 0.5
        cov, _ = constant_correlation_shrinkage(x)
        sd = np.sqrt(np.diag(cov))
        corr = cov / np.outer(sd, sd)
        self.assertGreater(corr[np.triu_indices(30, 1)].mean(), 0.35)


class PortfolioTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ratings, cls.prices = synthetic()
        cls.result = pc.build_portfolio(cls.ratings, cls.prices, ic=0.07)
        cls.validation = pc.validate_portfolio(cls.result)

    def test_all_constraints_hold(self):
        failed = self.validation[~self.validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())

    def test_higher_scores_get_more_weight(self):
        t = self.result["portfolio"].set_index("ticker")
        top = t.loc[t["score"] >= 70, "active_weight"].mean()
        bottom = t.loc[t["score"] <= 30, "active_weight"].mean()
        self.assertGreater(top, 0)
        self.assertLess(bottom, 0)

    def test_grinold_alpha(self):
        score = pd.Series([0.0, 50.0, 100.0])
        alpha = pc.grinold_alpha(score, pd.Series([0.2, 0.2, 0.2]), ic=0.05)
        z = (score - 50) / score.std(ddof=0)
        expected = 0.05 * 0.2 / np.sqrt(12.6) * z * 12.6
        np.testing.assert_allclose(alpha, expected)
        self.assertTrue((pc.grinold_alpha(score, pd.Series([0.2] * 3), ic=-0.02) == 0).all())

    def test_no_signal_means_close_to_benchmark(self):
        result = pc.build_portfolio(self.ratings, self.prices, ic=None)
        self.assertLess(result["summary"]["tracking_error"], 0.01)
        self.assertAlmostEqual(result["summary"]["expected_active_return"], 0.0, places=6)

    def test_tighter_budget_lowers_tracking_error(self):
        tight = pc.build_portfolio(self.ratings, self.prices, ic=0.07, policy={"tracking_error_budget": 0.02})
        self.assertLessEqual(tight["summary"]["tracking_error"], 0.0201)

    def test_staggered_price_rows_still_work(self):
        # Free Yahoo data can leave tickers missing on alternate rows; the
        # optimizer must align calendars instead of dropping every stock.
        staggered = self.prices.copy()
        staggered.iloc[::2, ::2] = np.nan
        result = pc.build_portfolio(self.ratings, staggered, ic=0.07)
        self.assertEqual(len(result["portfolio"]), len(self.ratings))
        self.assertAlmostEqual(result["summary"]["tracking_error"], self.result["summary"]["tracking_error"], places=2)

    def test_no_usable_prices_gives_clear_error(self):
        with self.assertRaisesRegex(ValueError, "overlapping price history"):
            pc.build_portfolio(self.ratings, self.prices.iloc[:, :1], ic=0.07)

    def test_never_executes(self):
        s = self.result["summary"]
        self.assertEqual(s["automatic_execution_authorized_count"], 0)
        self.assertEqual(s["approval_status"], "PENDING_HUMAN_APPROVAL")

    def test_run_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.ratings.reset_index().to_csv(base / pc.RATINGS, index=False)
            pd.DataFrame({"signal": ["composite_ic_weighted"], "mean_ic": [0.07]}).to_csv(base / pc.IC_SUMMARY,
                                                                                        index=False)
            result, validation = pc.run_portfolio(base, prices=self.prices, verbose=False)
            self.assertTrue((base / pc.OUTPUT_PORTFOLIO).exists())
            # second run measures turnover against the first proposal
            again, _ = pc.run_portfolio(base, prices=self.prices, verbose=False)
            self.assertLess(again["summary"]["turnover_traded"], 0.01)


if __name__ == "__main__":
    unittest.main()
