"""Offline tests for the Day 76c multi-asset universe."""

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import multi_asset_universe as mau


AS_OF = pd.Timestamp("2026-10-02")


def fake_history(tickers, start):
    business = pd.bdate_range(end=AS_OF, periods=700)
    calendar = pd.date_range(end=AS_OF, periods=980, freq="D")
    rng = np.random.default_rng(11)
    data = {}
    for ticker in tickers:
        crypto = ticker.endswith("-USD")
        dates = calendar if crypto else business
        vol = 0.04 if crypto else 0.01
        path = 100 * np.exp(np.cumsum(rng.normal(0.0002, vol, len(dates))))
        if ticker in ("USDT-USD", "USDC-USD"):
            path = np.full(len(dates), 1.0)
        data[ticker] = pd.Series(path, index=dates)
    return pd.DataFrame(data).sort_index()


def fake_fred(series_id):
    dates = pd.date_range(end=AS_OF, periods=800, freq="D")
    if series_id in mau.TREASURY_CURVE:
        level = 3.5 + 0.05 * mau.TREASURY_CURVE[series_id]          # upward-sloping curve
    elif series_id in mau.CREDIT_SPREADS:
        level = 1.0 if "C0A" in series_id else 3.5
    elif series_id == mau.SHORT_RATES["JPY"]:
        level = 0.5
    elif series_id == mau.SHORT_RATES["USD"]:
        level = 4.0
    elif series_id == mau.SHORT_RATES["EUR"]:
        level = 2.0
    else:
        level = 2.5
    values = np.linspace(level - 0.5, level, len(dates))
    return pd.Series(values, index=dates)


SOURCE = mau.MarketSource(history=fake_history, fred=fake_fred)


class AnalyticsTests(unittest.TestCase):

    def test_volatility_uses_each_instruments_trading_frequency(self):
        calendar = pd.date_range(end=AS_OF, periods=400, freq="D")
        rng = np.random.default_rng(1)
        returns = rng.normal(0, 0.02, len(calendar))
        series = pd.Series(100 * np.exp(np.cumsum(returns)), index=calendar)
        result = mau.instrument_analytics(series, None, AS_OF)
        self.assertGreater(result["observations_per_year"], 360)       # crypto: ~365, not 252
        simple = series.pct_change().dropna()
        last_year = simple[simple.index > calendar[-1] - pd.Timedelta(days=365)]
        self.assertAlmostEqual(result["volatility_1y"], last_year.std(ddof=1) * math.sqrt(len(last_year)))

    def test_returns_and_momentum(self):
        dates = pd.bdate_range(end=AS_OF, periods=300)
        series = pd.Series(np.linspace(100, 130, len(dates)), index=dates)
        result = mau.instrument_analytics(series, None, AS_OF)
        self.assertGreater(result["return_12m"], result["momentum_12_1"])  # 12-1 skips the last month
        self.assertEqual(result["max_drawdown_1y"], 0.0)
        self.assertGreater(result["trend_vs_200d"], 0)

    def test_beta_to_itself_is_one(self):
        dates = pd.bdate_range(end=AS_OF, periods=300)
        series = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.01, 300))), index=dates)
        result = mau.instrument_analytics(series, series, AS_OF)
        self.assertAlmostEqual(result["beta_to_spx"], 1.0)
        self.assertAlmostEqual(result["correlation_to_spx"], 1.0)


class EndToEndTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (self.analytics, self.curve, self.credit, self.fx, self.summary,
         self.validation) = mau.run_multi_asset(AS_OF, SOURCE, Path(self.tmp.name), verbose=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_asset_classes_present(self):
        self.assertEqual(set(self.analytics["asset_class"]),
                         {"Equity", "Fixed Income", "FX", "Commodity", "Digital Asset",
                          "Real Estate", "Alternative"})

    def test_validation_passes(self):
        failed = self.validation[~self.validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())

    def test_yield_curve_and_slope(self):
        self.assertEqual(len(self.curve), len(mau.TREASURY_CURVE))
        slope = self.curve["slope_2s10s_bp"].iloc[0]
        self.assertAlmostEqual(slope, (0.05 * 10 - 0.05 * 2) * 100)      # 40 bp
        self.assertFalse(self.curve["curve_inverted_3m10y"].iloc[0])

    def test_credit_spreads_in_basis_points(self):
        ig = self.credit.set_index("segment").loc["US investment grade"]
        self.assertAlmostEqual(ig["spread_bp"], 100.0)
        self.assertAlmostEqual(ig["percentile_in_history"], 100.0)       # widest in history

    def test_fx_carry_sign_follows_pair_direction(self):
        fx = self.fx.set_index("pair")
        self.assertAlmostEqual(fx.loc["USD/JPY", "carry_long_pair_pct"], 4.0 - 0.5)   # long USD earns more
        self.assertAlmostEqual(fx.loc["EUR/USD", "carry_long_pair_pct"], 2.0 - 4.0)   # long EUR pays

    def test_outputs_written(self):
        for name in (mau.OUTPUT_UNIVERSE, mau.OUTPUT_ANALYTICS, mau.OUTPUT_CURVE, mau.OUTPUT_CREDIT,
                     mau.OUTPUT_FX_CARRY, mau.OUTPUT_CLASS_SUMMARY, mau.OUTPUT_VALIDATION):
            self.assertTrue((Path(self.tmp.name) / name).exists(), name)

    def test_failed_download_keeps_previous_files(self):
        broken = mau.MarketSource(history=lambda t, s: pd.DataFrame(),
                                  fred=lambda s: (_ for _ in ()).throw(ConnectionError()))
        before = (Path(self.tmp.name) / mau.OUTPUT_ANALYTICS).read_text()
        mau.run_multi_asset(AS_OF, broken, Path(self.tmp.name), verbose=False)
        self.assertEqual((Path(self.tmp.name) / mau.OUTPUT_ANALYTICS).read_text(), before)


if __name__ == "__main__":
    unittest.main()
