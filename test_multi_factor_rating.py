"""Tests for the Day 77 multi-factor rating, focused on look-ahead safety."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import multi_factor_rating as mfr


def synthetic_prices():
    dates = pd.bdate_range("2023-01-02", "2026-09-30")
    rng = np.random.default_rng(5)
    data = {f"S{i}": 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012 + 0.001 * i, len(dates))))
            for i in range(15)}
    return pd.DataFrame(data, index=dates)


class LookAheadTests(unittest.TestCase):

    def test_price_features_ignore_future_prices(self):
        prices = synthetic_prices()
        date = pd.Timestamp("2025-06-30")
        before = mfr.price_features(prices, date, None)
        shocked = prices.copy()
        shocked.loc[shocked.index > date] *= 3.0
        after = mfr.price_features(shocked, date, None)
        pd.testing.assert_frame_equal(before, after)

    def test_ic_weights_use_only_past_outcomes(self):
        dates = pd.date_range("2024-01-31", periods=12, freq="ME")
        rng = np.random.default_rng(1)
        rows = []
        for d in dates:
            for t in range(12):
                rows.append({"date": d, "ticker": f"T{t}", **{p: rng.uniform(0, 100) for p in mfr.PILLARS},
                             "forward_return_20d": rng.normal(0, 0.05)})
        history = pd.DataFrame(rows)
        _, weights = mfr.add_ic_weighted_composite(history)
        altered = history.copy()
        altered.loc[altered["date"] == dates[-1], "forward_return_20d"] *= -10   # change the last outcome
        _, weights_altered = mfr.add_ic_weighted_composite(altered)
        pd.testing.assert_frame_equal(weights, weights_altered)                  # it was never used

    def test_equal_weights_until_enough_history(self):
        dates = pd.date_range("2024-01-31", periods=3, freq="ME")
        history = pd.DataFrame([{"date": d, "ticker": f"T{t}", **{p: float(t) for p in mfr.PILLARS},
                                 "forward_return_20d": 0.01 * t} for d in dates for t in range(12)])
        _, weights = mfr.add_ic_weighted_composite(history)
        self.assertTrue(np.allclose(weights[mfr.PILLARS].to_numpy(), 1 / len(mfr.PILLARS)))


class ScoringTests(unittest.TestCase):

    def test_ratings_30_40_30(self):
        ratings = mfr.ratings_from_scores(pd.Series(np.arange(100, dtype=float)))
        counts = ratings.value_counts()
        self.assertEqual(counts["Overweight"], 30)
        self.assertEqual(counts["Underweight"], 30)

    def test_spearman_matches_rank_correlation(self):
        a = pd.Series(np.arange(12, dtype=float))
        self.assertAlmostEqual(mfr.spearman(a, a ** 3), 1.0)
        self.assertAlmostEqual(mfr.spearman(a, -a), -1.0)

    def test_regime_needs_data(self):
        self.assertEqual(mfr.macro_regime({}, pd.Timestamp("2025-01-01")), "unknown")
        dates = pd.date_range("2024-01-01", "2025-01-01", freq="D")
        widening = pd.Series(np.linspace(3, 5, len(dates)), index=dates)
        self.assertEqual(mfr.macro_regime({"BAMLH0A0HYM2": widening}, dates[-1]), "risk_off")
        tightening = pd.Series(np.linspace(5, 3, len(dates)), index=dates)
        self.assertEqual(mfr.macro_regime({"BAMLH0A0HYM2": tightening}, dates[-1]), "risk_on")


class EndToEndTests(unittest.TestCase):

    def test_runs_on_committed_rankings(self):
        ranks = pd.read_csv(mfr.RANKINGS_FILE, parse_dates=["date"])
        prices = ranks.pivot(index="date", columns="ticker", values="close")
        with tempfile.TemporaryDirectory() as tmp:
            current, ic_sum, backtest, validation = mfr.run_multi_factor(
                Path(tmp), prices=prices, price_source="test", macro={}, facts={}, verbose=False)
            for name in (mfr.OUTPUT_RATINGS, mfr.OUTPUT_IC_SUMMARY, mfr.OUTPUT_BACKTEST, mfr.OUTPUT_VALIDATION):
                self.assertTrue((Path(tmp) / name).exists())
        self.assertEqual(len(current), 33)
        self.assertIn("composite_ic_weighted", set(ic_sum["signal"]))


class FreeDataLoaderTests(unittest.TestCase):
    """Yahoo and FRED loaders: cache, fallback, never overwrite with empty data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.saved = (mfr.PRICE_CACHE, mfr.MACRO_CACHE, mfr.MARKET_DB)
        mfr.PRICE_CACHE, mfr.MACRO_CACHE = base / "prices.csv", base / "macro.csv"
        mfr.MARKET_DB = base / "missing.db"

    def tearDown(self):
        mfr.PRICE_CACHE, mfr.MACRO_CACHE, mfr.MARKET_DB = self.saved
        self.tmp.cleanup()

    @staticmethod
    def fake_yahoo(tickers, start):
        dates = pd.bdate_range(start, periods=5)
        return pd.DataFrame([{"ticker": t, "date": d, "close": 10.0 + i, "adj_close": 9.0 + i}
                             for t in tickers for i, d in enumerate(dates)])

    def test_yahoo_prices_cached_and_adjusted(self):
        long = mfr.load_yahoo_prices(["AAA", "SPY"], fetch=self.fake_yahoo)
        self.assertEqual(set(long.columns), {"date", "ticker", "close"})
        self.assertEqual(set(long["ticker"]), {"AAA", "SPY"})
        self.assertEqual(long["close"].min(), 9.0)          # adjusted close used
        self.assertTrue(mfr.PRICE_CACHE.exists())

    def test_failed_download_keeps_saved_copy(self):
        mfr.load_yahoo_prices(["AAA"], fetch=self.fake_yahoo)
        os.utime(mfr.PRICE_CACHE, (0, 0))                  # make the cache stale
        def broken(tickers, start):
            raise ConnectionError("offline")
        long = mfr.load_yahoo_prices(["AAA"], fetch=broken)
        self.assertEqual(len(long), 5)
        long = mfr.load_yahoo_prices(["AAA"], fetch=lambda t, s: pd.DataFrame())
        self.assertEqual(len(long), 5)

    def test_macro_regime_from_fred(self):
        dates = pd.bdate_range(end="2026-10-01", periods=300)
        values = {"BAMLH0A0HYM2": np.linspace(3, 5, 300), "DGS10": np.full(300, 4.0), "DGS3MO": np.full(300, 3.5)}
        fake = lambda sid: pd.DataFrame({"date": dates, "value": values[sid]})
        macro = mfr.load_macro(fetch=fake)
        self.assertEqual(set(macro), set(mfr.REGIME_SERIES))
        self.assertEqual(mfr.macro_regime(macro, dates[-1]), "risk_off")   # spreads above 1y median


if __name__ == "__main__":
    unittest.main()
