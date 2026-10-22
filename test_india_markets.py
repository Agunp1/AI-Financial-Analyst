"""Tests for the Day 93 India market universe and the India trader book (fake data; no downloads)."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import india_markets as im
import trader_agent as ta
from multi_asset_universe import MarketSource


def fake_history(tickers, start):
    days = pd.bdate_range("2024-01-01", "2026-10-20")
    rng = np.random.default_rng(7)
    data = {}
    for i, t in enumerate(tickers):
        if t == "^INDIAVIX":
            data[t] = 14 + rng.random(len(days))
        else:
            drift = 0.0006 if i % 2 else -0.0003
            data[t] = 100 * np.exp(np.cumsum(drift + 0.012 * rng.standard_normal(len(days))))
    return pd.DataFrame(data, index=days)


def fake_fred(series_id):
    months = pd.date_range("2022-01-01", "2026-08-01", freq="MS")
    if series_id == "DEXINUS":
        return pd.Series(83 + np.linspace(0, 5, len(months)), index=months)
    if series_id in ("INDIRLTLT01STM", "INDIR3TIB01STM"):
        return pd.Series(np.linspace(7.4, 6.4, len(months)), index=months)
    return pd.Series(100 * 1.05 ** (np.arange(len(months)) / 12), index=months)      # index growing 5% a year


SOURCE = MarketSource(history=fake_history, fred=fake_fred)


class IndiaMarketTests(unittest.TestCase):

    def run_india(self, out):
        return im.run_india(pd.Timestamp("2026-10-20"), SOURCE, out_dir=out, verbose=False)

    def test_universe_is_indian_and_separate(self):
        master = im.instrument_master()
        self.assertTrue((master["market"] == "India").all())
        self.assertIn("^NSEI", set(master["symbol"]))
        self.assertGreaterEqual(len(im.NIFTY_50), 45)
        self.assertEqual(len(set(master["symbol"])), len(master))
        self.assertTrue(all(s.endswith(".NS") for s, _, _ in im.NIFTY_50))

    def test_pipeline_writes_india_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            analytics, macro, validation = self.run_india(tmp)
            files = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(files, sorted([im.OUTPUT_ANALYTICS, im.OUTPUT_HISTORY, im.OUTPUT_MACRO,
                                            im.OUTPUT_VALIDATION]))
            self.assertTrue(validation["passed"].all(), validation)
            self.assertIn("beta_to_nifty", analytics.columns)
            nifty = analytics.set_index("symbol").loc["^NSEI"]
            self.assertAlmostEqual(nifty["beta_to_nifty"], 1.0, places=6)

    def test_macro_yoy_and_levels(self):
        macro = im.macro_table({k: fake_fred(k) for k in im.MACRO_SERIES}).set_index("series")
        self.assertAlmostEqual(macro.loc["INDCPIALLMINMEI", "value"], 5.0, places=1)
        self.assertAlmostEqual(macro.loc["INDIRLTLT01STM", "value"], 6.4, places=2)
        self.assertLess(macro.loc["INDIRLTLT01STM", "change"], 0)
        old = {k: v[v.index < "2023-01-01"] for k, v in ((k, fake_fred(k)) for k in im.MACRO_SERIES)}
        self.assertTrue(im.macro_table(old)["status"].str.startswith("Stale").all())

    def test_failed_download_keeps_previous_files(self):
        empty = MarketSource(history=lambda t, s: pd.DataFrame(), fred=lambda s: pd.Series(dtype=float))
        with tempfile.TemporaryDirectory() as tmp:
            im.run_india(pd.Timestamp("2026-10-20"), empty, out_dir=tmp, verbose=False)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_india_trader_book_is_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_india(tmp)
            history = ta.load_history(Path(tmp), market="India")
            analytics = ta.load_analytics(Path(tmp), market="India")
            table = ta.scan(history, analytics, market="India")
            self.assertFalse(table["symbol"].str.startswith("^").any())       # indices and India VIX not traded
            reg = ta.regime(history, "India")
            self.assertEqual(reg["index_name"], "Nifty 50")
            ideas = table[table["direction"].isin(["Long", "Short"])]
            self.assertTrue((ideas["risk_at_stop"] <= ta.MARKETS["India"]["book"] * ta.RISK_PER_TRADE + 1e-6).all())
            self.assertTrue(ta.validate(table, ta.backtest_setups(history, market="India"), "India")["passed"].all())
            self.assertIn("₹", ta.agent_brief(table, reg))

    def test_paper_trades_stay_in_their_market(self):
        days = pd.bdate_range("2026-10-01", periods=3)
        us = pd.DataFrame({"SPY": [100.0, 101, 102]}, index=days)
        progress = {}
        ta.open_paper_trade(progress, {"symbol": "SPY", "direction": "Long", "entry": 100, "stop": 95, "target": 110,
                                       "quantity": 1})
        ta.open_paper_trade(progress, {"symbol": "TCS.NS", "direction": "Long", "entry": 4000, "stop": 3900,
                                       "target": 4200, "quantity": 1, "market": "India"})
        self.assertEqual(list(ta.mark_paper_trades(progress, us, "US")["symbol"]), ["SPY"])

    def test_rupee_formatting_uses_lakh_grouping(self):
        self.assertEqual(ta.money(10_000_000, "India"), "₹1,00,00,000")
        self.assertEqual(ta.money(-150_000, "India"), "−₹1,50,000")
        self.assertEqual(ta.money(1_234_567, "US"), "$1,234,567")

    def test_india_lesson_uses_india_data(self):
        import academy_live as live
        with tempfile.TemporaryDirectory() as tmp:
            self.run_india(tmp)
            old, live.BASE_DIR = live.BASE_DIR, Path(tmp)
            try:
                text = live.ia_india_market()
            finally:
                live.BASE_DIR = old
        self.assertIn("Nifty 50", text)
        self.assertIn("USD/INR", text)

    def test_india_pages_and_refresh(self):
        import run_vittantra as rv
        import vittantra_market as vm
        self.assertIn("india_markets.py", [s for _, s in rv.PRICE_STEPS])
        self.assertIsNone(vm.allowed_pages("US"))
        self.assertIn("Trading Desk", vm.allowed_pages("India"))
        flow = (Path(im.BASE_DIR) / ".github/workflows/refresh-prices.yml").read_text()
        self.assertIn("*/15 4-9 * * 1-5", flow)
        self.assertIn("day93_india_analytics.csv", flow)


if __name__ == "__main__":
    unittest.main()
