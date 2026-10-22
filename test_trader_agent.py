"""Tests for the Day 92 trader agent: indicators, setups, sizing, backtest, blotter and the no-execution rule."""

import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import academy_desk as desk
import trader_agent as ta


def synthetic(n=300, drift=0.001, seed=1):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-06-02", periods=n)
    up = 100 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    down = 100 * np.exp(np.cumsum(-drift + 0.01 * rng.standard_normal(n)))
    flat = 100 * np.exp(np.cumsum(0.0001 * rng.standard_normal(n)))
    vix = 15 + rng.random(n)
    return pd.DataFrame({"UP": up, "DOWN": down, "CASH": flat, "SPY": up, "^VIX": vix}, index=days)


ANALYTICS = pd.DataFrame({"name": ["Up", "Down", "Cash", "S&P"], "asset_class": ["Equity", "Commodity", "Fixed Income",
                          "Equity"]}, index=["UP", "DOWN", "CASH", "SPY"])


class TraderAgentTests(unittest.TestCase):

    def test_trends_are_classified_by_direction(self):
        h = synthetic()
        self.assertEqual(ta.classify(ta.indicator_frame(h["UP"]).iloc[-1])[1] in ("Long", None), True)
        self.assertIn(ta.classify(ta.indicator_frame(h["DOWN"]).iloc[-1])[1], ("Short", None))
        self.assertEqual(ta.classify(ta.indicator_frame(h["CASH"]).iloc[-1])[0], "Cash-like — not traded")

    def test_indicators_use_only_past_data(self):
        h = synthetic()
        full = ta.indicator_frame(h["UP"])
        cut = ta.indicator_frame(h["UP"].iloc[:250])
        pd.testing.assert_series_equal(full.iloc[249], cut.iloc[-1], check_names=False)

    def test_trade_plan_risks_the_budget_and_respects_the_cap(self):
        plan = ta.trade_plan(50.0, 5.0, "Long")
        self.assertAlmostEqual(plan["stop"], 40.0)
        self.assertAlmostEqual(plan["target"], 65.0)
        self.assertAlmostEqual(plan["risk_at_stop"], ta.BOOK * ta.RISK_PER_TRADE)
        self.assertAlmostEqual(plan["reward_to_risk"], 1.5)
        capped = ta.trade_plan(50.0, 0.01, "Long")                 # tiny stop → huge size → capped
        self.assertLessEqual(capped["notional"], ta.BOOK * ta.MAX_POSITION + 1e-6)
        short = ta.trade_plan(50.0, 1.0, "Short")
        self.assertGreater(short["stop"], 50.0)
        self.assertLess(short["target"], 50.0)

    def test_scan_and_validation(self):
        h = synthetic()
        table = ta.scan(h, ANALYTICS)
        self.assertNotIn("^VIX", set(table["symbol"]))
        validation = ta.validate(table, ta.backtest_setups(h))
        self.assertTrue(validation["passed"].all())

    def test_risk_off_halves_long_risk_assets(self):
        h = synthetic(drift=-0.002)
        h["^VIX"] = 30.0
        reg = ta.regime(h)
        self.assertEqual(reg["state"], "Risk-off")
        self.assertEqual(reg["size_scale_risk_assets"], 0.5)

    def test_backtest_reports_setups(self):
        bt = ta.backtest_setups(synthetic(), step=5)
        self.assertTrue({"setup", "signals", "hit_rate", "avg_return", "avg_r"} <= set(bt.columns))
        self.assertTrue(((bt["hit_rate"] >= 0) & (bt["hit_rate"] <= 1)).all())

    def test_paper_blotter_marks_stops_and_targets(self):
        days = pd.bdate_range("2026-10-01", periods=4)
        h = pd.DataFrame({"X": [100.0, 101.0, 104.0, 104.0], "Y": [100.0, 99.0, 97.0, 96.0]}, index=days)
        progress = {}
        ta.open_paper_trade(progress, {"symbol": "X", "direction": "Long", "entry": 100, "stop": 98, "target": 103,
                                       "quantity": 10}, datetime(2026, 10, 1))
        ta.open_paper_trade(progress, {"symbol": "Y", "direction": "Long", "entry": 100, "stop": 98, "target": 103,
                                       "quantity": 10}, datetime(2026, 10, 1))
        marked = ta.mark_paper_trades(progress, h).set_index("symbol")
        self.assertEqual(marked.loc["X", "status"], "Target hit")
        self.assertAlmostEqual(marked.loc["X", "pnl"], 40.0)
        self.assertAlmostEqual(marked.loc["X", "r_multiple"], 2.0)
        self.assertEqual(marked.loc["Y", "status"], "Stopped out")
        self.assertFalse(any(t["executed"] for t in progress["paper_trades"]))
        summary = ta.blotter_summary(marked)
        self.assertEqual(summary["closed"], 2)
        self.assertAlmostEqual(summary["hit_rate"], 0.5)

    def test_live_snapshot_extends_history(self):
        h = synthetic(n=10)
        snap = pd.DataFrame({"symbol": ["UP"], "price": [123.0], "as_of": ["2030-01-02"]})
        out = ta.overlay_live(h, snap)
        self.assertEqual(out["UP"].dropna().iloc[-1], 123.0)

    def test_desk_grading(self):
        task = {"price": 50.0, "atr": 5.0, "direction": "Long", "budget": 5000.0, "max_notional": 100000.0}
        self.assertEqual(desk.grade_trade_plan(task, 40.0, 500)[0], 100)
        self.assertEqual(desk.grade_trade_plan(task, 60.0, 500)[0], 0)
        execution = {"side": "Buy", "arrival": 100.0, "avg_fill": 100.05, "is_bps": 5.0}
        self.assertEqual(desk.grade_execution(execution, 100.05, 5.0)[0], 100)
        self.assertEqual(desk.grade_execution(execution, 100.05, -5.0)[0], 50)

    def test_agent_never_sends_orders(self):
        text = Path(ta.__file__).read_text() + Path(ta.BASE_DIR / "vittantra_trading_page.py").read_text()
        for word in ("submit_order", "place_order", "broker", "alpaca", "requests.post"):
            self.assertNotIn(word, text.lower())


if __name__ == "__main__":
    unittest.main()
