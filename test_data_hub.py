"""
Tests for the Day 75 data hub and live-input overlay.

Network calls are replaced with deterministic fake fetchers, so these
tests run offline.
"""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import vittantra_data_hub as hub
import vittantra_live_inputs as live
from multi_asset_risk import build_sample_instruments


TODAY = pd.Timestamp("2026-10-02")

FAKE_LEVELS = {
    "ES=F": 6700.0, "EURUSD=X": 1.17, "GC=F": 3800.0, "BTC-USD": 118000.0,
    "VNQ": 92.0, "LQD": 110.0, "SPY": 660.0, "AAPL": 250.0,
}

FAKE_MACRO = {
    "DGS3MO": 4.0, "DGS2": 3.6, "DGS5": 3.7, "DGS10": 4.1,
    "BAMLC0A4CBBB": 1.1, "VIXCLS": 16.0, "CPIAUCSL": 323.0,
    "UNRATE": 4.3, "FEDFUNDS": 4.1, "GDPC1": 23700.0,
}


def fake_price_history(tickers, start):
    dates = pd.bdate_range(end=TODAY, periods=400)
    rng = np.random.default_rng(7)
    frames = []
    for ticker in tickers:
        level = FAKE_LEVELS.get(ticker, 100.0)
        path = level * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
        path = path / path[-1] * level
        frames.append(pd.DataFrame({
            "ticker": ticker, "date": dates, "open": path, "high": path,
            "low": path, "close": path, "adj_close": path, "volume": 1e6,
        }))
    return pd.concat(frames, ignore_index=True)


def fake_latest_quotes(tickers):
    return pd.DataFrame({
        "ticker": tickers,
        "price": [FAKE_LEVELS.get(t, 100.0) * 1.01 for t in tickers],
        "quote_time_utc": TODAY.strftime("%Y-%m-%dT15:30:00Z"),
    })


def fake_fred(series_id):
    dates = pd.date_range(end=TODAY, periods=30, freq="D")
    return pd.DataFrame({"date": dates, "value": FAKE_MACRO[series_id]})


def failing_fetch(*args, **kwargs):
    raise ConnectionError("network unavailable")


FAKE = hub.DataFetchers(fake_price_history, fake_latest_quotes, fake_fred)


class DataHubTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "market.db"
        self.validation = hub.run_refresh(
            db_path=self.db, out_dir=self.dir, fetchers=FAKE,
            force=True, today=TODAY, verbose=False,
        )
        self.prices_file = self.dir / hub.OUTPUT_LIVE_PRICES

    def tearDown(self):
        os.environ.pop("VITTANTRA_DATA_MODE", None)
        self.tmp.cleanup()

    def test_all_validation_checks_pass(self):
        failed = self.validation[~self.validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())

    def test_outputs_written(self):
        for name in [hub.OUTPUT_MARKET_SNAPSHOT, hub.OUTPUT_MACRO_SNAPSHOT,
                     hub.OUTPUT_LIVE_PRICES, hub.OUTPUT_PRICE_HISTORY,
                     hub.OUTPUT_REFRESH_LOG, hub.OUTPUT_VALIDATION]:
            self.assertTrue((self.dir / name).exists(), name)

    def test_intraday_quote_preferred_over_close(self):
        prices = pd.read_csv(self.prices_file).set_index("symbol")
        self.assertAlmostEqual(prices.loc["ES", "price"], 6700.0 * 1.01)
        self.assertEqual(prices.loc["USD", "price"], 1.0)

    def test_model_prices_are_sensible(self):
        prices = pd.read_csv(self.prices_file).set_index("symbol")
        bond = prices.loc["CORP_BOND"]
        self.assertAlmostEqual(bond["model_yield"], 0.048)
        self.assertTrue(80 < bond["price"] < 110)
        option = prices.loc["AAPL_CALL", "price"]
        spot = 250.0 * 1.01
        self.assertGreater(option, spot - 210.0)   # above intrinsic value
        self.assertLess(option, spot)

    def test_rerun_does_not_duplicate_rows(self):
        conn = hub.connect(self.db)
        before = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        conn.close()
        hub.run_refresh(db_path=self.db, out_dir=self.dir, fetchers=FAKE,
                        force=True, today=TODAY, verbose=False)
        conn = hub.connect(self.db)
        after = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        conn.close()
        self.assertEqual(before, after)

    def test_network_failure_keeps_last_good_data(self):
        broken = hub.DataFetchers(failing_fetch, failing_fetch, failing_fetch)
        hub.run_refresh(db_path=self.db, out_dir=self.dir, fetchers=broken,
                        force=True, today=TODAY, verbose=False)
        prices = pd.read_csv(self.prices_file)
        self.assertTrue((prices["status"] != "MISSING").all())
        log = pd.read_csv(self.dir / hub.OUTPUT_REFRESH_LOG)
        self.assertIn("FAILED", set(log["status"]))

    def test_old_data_is_flagged_stale(self):
        later = TODAY + pd.Timedelta(days=30)
        conn = hub.connect(self.db)
        conn.execute("DELETE FROM latest_quotes")
        conn.commit()
        prices = hub.build_live_instrument_prices(
            conn, later, build_sample_instruments(use_live_data=False))
        conn.close()
        self.assertEqual(prices.set_index("symbol").loc["SPY", "status"], "STALE")

    def test_live_overlay_replaces_sample_prices(self):
        instruments = live.apply_live_prices(
            build_sample_instruments(use_live_data=False), self.prices_file)
        by_symbol = {i.symbol: i for i in instruments}
        self.assertAlmostEqual(by_symbol["BTC"].price, 118000.0 * 1.01)
        self.assertIn("DIRECT", by_symbol["BTC"].metadata["price_source"])
        self.assertAlmostEqual(by_symbol["CORP_BOND"].yield_to_maturity, 0.048)

    def test_sample_mode_ignores_live_data(self):
        os.environ["VITTANTRA_DATA_MODE"] = "sample"
        instruments = live.apply_live_prices(
            build_sample_instruments(use_live_data=False), self.prices_file)
        self.assertEqual({i.symbol: i for i in instruments}["BTC"].price, 100000.0)

    def test_price_history_aligned_for_risk_models(self):
        symbols = [i.symbol for i in build_sample_instruments(use_live_data=False)]
        history = live.load_price_history(
            symbols, history_file=self.dir / hub.OUTPUT_PRICE_HISTORY,
            prices_file=self.prices_file)
        self.assertIsNotNone(history)
        self.assertGreaterEqual(len(history), 250)
        self.assertIn(live.BENCHMARK_COLUMN, history.columns)


class PricingModelTests(unittest.TestCase):

    def test_bond_at_par_when_coupon_equals_yield(self):
        self.assertAlmostEqual(hub.bond_price(0.05, 0.05, 5), 100.0, places=6)

    def test_black_scholes_reference_value(self):
        # Standard textbook case: S=K=100, T=1, r=5%, vol=20% → 10.4506
        self.assertAlmostEqual(
            hub.black_scholes_price(100, 100, 1, 0.05, 0.20, "call"), 10.4506, places=3)

    def test_expired_option_is_intrinsic(self):
        self.assertEqual(hub.black_scholes_price(120, 100, 0, 0.05, 0.2, "call"), 20.0)


if __name__ == "__main__":
    unittest.main()
