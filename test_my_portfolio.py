"""Tests for My Portfolio: universe, valuation, risk-level status, checks, stress tests and saving."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import my_portfolio as mp
import whatif_engine as we
from test_whatif_engine import market


TABLE = pd.DataFrame([
    {"symbol": "SPY", "name": "S&P 500 ETF", "asset_class": "Equity", "sub_class": "US", "price": 100.0},
    {"symbol": "TLT", "name": "Treasuries", "asset_class": "Fixed Income", "sub_class": "UST", "price": 50.0},
    {"symbol": "HYG", "name": "High yield", "asset_class": "Fixed Income", "sub_class": "HY", "price": 80.0},
    {"symbol": "AAA", "name": "Alpha Inc", "asset_class": "Stock", "sub_class": "Tech", "price": 20.0},
    {"symbol": "BBB", "name": "Beta Inc", "asset_class": "Stock", "sub_class": "Retail", "price": 10.0},
])


class MyPortfolioTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        prices, fred = market()
        cls.model = we.RiskModel(prices, fred)

    def test_universe_is_investable_with_prices(self):
        u = mp.universe()
        self.assertGreater(len(u), 100)
        self.assertTrue(u["price"].gt(0).all())
        self.assertFalse(u["symbol"].str.startswith("DGS").any())        # FRED yields are not investable
        for template in mp.TEMPLATES.values():
            self.assertTrue(set(template["weights"]) <= set(u["symbol"]))
            self.assertAlmostEqual(sum(template["weights"].values()), 1.0)

    def test_valuation_and_weights(self):
        holdings = mp.from_weights({"SPY": 0.6, "TLT": 0.4}, 10_000, TABLE)
        pos = mp.valuation(holdings + [{"symbol": "ZZZ", "quantity": 5}], TABLE)
        self.assertAlmostEqual(pos["market_value"].sum(), 10_000, places=2)
        self.assertAlmostEqual(pos.set_index("symbol").at["SPY", "weight"], 0.6, places=4)
        self.assertNotIn("ZZZ", set(pos["symbol"]))                        # unknown symbols are not invented

    def test_analysis_status_checks_and_stress(self):
        holdings = mp.from_weights({"SPY": 0.6, "TLT": 0.4}, 100_000, TABLE)
        out = mp.analyse(holdings, self.model, TABLE, profile=3)
        self.assertIn(out["status"], ("ON TARGET", "SLIGHTLY ABOVE", "ABOVE RISK LEVEL"))
        self.assertAlmostEqual(out["positions"]["risk_share"].sum(), 1.0, places=6)
        crash = out["scenarios"]["Equity sell-off"]
        self.assertLess(crash, 0)
        self.assertAlmostEqual(crash, -0.6 * 0.20 * 100_000 + 0.4 * 100_000 * (-0.16) * -0.5, delta=1500)

    def test_concentrated_stock_is_flagged(self):
        holdings = mp.from_weights({"AAA": 0.5, "SPY": 0.5}, 100_000, TABLE)
        out = mp.analyse(holdings, self.model, TABLE, profile=3)
        checks = {name: ok for name, ok, _ in out["checks"]}
        self.assertFalse(checks["No single company above 20% of the portfolio"])
        self.assertTrue(any("20%" in tip for tip in out["tips"]))

    def test_risk_level_status(self):
        self.assertEqual(mp.risk_level_status(0.09, 0.10), "ON TARGET")
        self.assertEqual(mp.risk_level_status(0.11, 0.10), "SLIGHTLY ABOVE")
        self.assertEqual(mp.risk_level_status(0.15, 0.10), "ABOVE RISK LEVEL")

    def test_save_and_load_per_user(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mp, "PORTFOLIO_DIR", Path(tmp)):
            path = mp.save("Sam", [{"symbol": "spy", "quantity": 3}, {"symbol": "", "quantity": 1}], profile=4)
            data = json.loads(path.read_text())
            self.assertEqual(path.name, "sam.json")
            self.assertEqual(data["holdings"], [{"symbol": "SPY", "quantity": 3.0}])
            self.assertEqual(mp.load("sam")["profile"], 4)
            self.assertEqual(mp.load(None), {"holdings": []})


    def test_any_us_stock_can_be_held(self):
        u = mp.universe()
        self.assertGreater(len(u), 4000)
        self.assertTrue({"TSLA", "F"} <= set(u["symbol"]))
        self.assertEqual(u["symbol"].duplicated().sum(), 0)

    def test_fetched_history_feeds_the_model(self):
        prices, fred = market()
        def fake(tickers, start):
            rows = []
            for i, t in enumerate(tickers):
                px = prices["AAA"] * (1 + 0.1 * i)
                rows += [{"date": d, "ticker": t, "close": p, "adj_close": p} for d, p in px.items()]
            return pd.DataFrame(rows)
        extra = mp.fetch_history(["TSLA"], fetch=fake)
        self.assertEqual(list(extra.columns), ["TSLA"])
        model = mp.model_for(["TSLA", "SPY"], prices, fred, extra)
        self.assertIn("TSLA", model.cov.index)
        self.assertTrue(mp.fetch_history(["X"], fetch=lambda *a: (_ for _ in ()).throw(OSError())).empty)


    def test_performance_since_baseline_and_vs_spy(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mp, "PORTFOLIO_DIR", Path(tmp)):
            mp.save("sam", [{"symbol": "SPY", "quantity": 10}, {"symbol": "TLT", "quantity": 20}], table=TABLE)
            data = mp.load("sam")
            self.assertAlmostEqual(data["baseline"]["value"], 10 * 100 + 20 * 50)
            later = TABLE.assign(price=TABLE["price"] * [1.10, 0.95, 1, 1, 1])     # SPY +10%, TLT -5%
            perf = mp.performance(data, later)
            self.assertAlmostEqual(perf["portfolio_return"], (1100 + 950) / 2000 - 1)
            self.assertAlmostEqual(perf["spy_return"], 0.10)
            # saving the same holdings again keeps the baseline; changing them starts a new one
            mp.save("sam", [{"symbol": "SPY", "quantity": 10}, {"symbol": "TLT", "quantity": 20}], table=later)
            self.assertAlmostEqual(mp.load("sam")["baseline"]["value"], 2000)
            mp.save("sam", [{"symbol": "SPY", "quantity": 5}], table=later)
            self.assertAlmostEqual(mp.load("sam")["baseline"]["value"], 550)

    def test_watchlist_and_alerts(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mp, "PORTFOLIO_DIR", Path(tmp)):
            mp.save_watchlist("sam", [{"symbol": "aaa", "below": 25, "above": None, "move": float("nan")},
                                      {"symbol": "", "move": 5}])
            watch = mp.load("sam")["watchlist"]
            self.assertEqual(watch, [{"symbol": "AAA", "below": 25.0}])
            mp.save("sam", [{"symbol": "SPY", "quantity": 1}], table=TABLE)
            self.assertEqual(mp.load("sam")["watchlist"], watch)                  # saving holdings keeps the watchlist
        fired = mp.alerts([{"symbol": "AAA", "below": 25.0}, {"symbol": "BBB", "above": 50.0}], TABLE)
        self.assertEqual([a["symbol"] for a in fired], ["AAA"])                   # AAA at $20 is below $25
        u = mp.universe()
        moves = pd.read_csv(Path(mp.BASE_DIR) / mp.ANALYTICS).set_index("symbol")["return_1d"]
        big = moves.abs().idxmax()
        self.assertTrue(any(a["kind"] == "move" for a in mp.alerts([{"symbol": big, "move": 0.01}], u)))


if __name__ == "__main__":
    unittest.main()
