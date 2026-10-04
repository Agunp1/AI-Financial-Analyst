"""Tests for hover explanations and the 'day on the desk' guide."""

import unittest

import pandas as pd

import vittantra_guide as guide
import vittantra_tooltips as tt


class TooltipTests(unittest.TestCase):

    def test_common_labels_have_explanations(self):
        for label in ["Tracking error", "1-day 99% VaR", "Information ratio", "Beta to S&P 500", "Revenue (TTM)",
                      "Intrinsic value (DCF)", "Volatility (a year)", "Goal probability", "10Y Treasury",
                      "Max Risk Utilization", "risk_budget_utilization", "Bad year (1 in 20)"]:
            self.assertTrue(tt.tip(label), label)

    def test_every_explanation_says_why(self):
        for key, text in tt.TIPS.items():
            self.assertGreater(len(text), 25, key)

    def test_no_false_matches(self):
        self.assertIsNone(tt.tip("Economic"))          # 'ic' must not match inside words
        self.assertIsNone(tt.tip(""))
        self.assertIsNone(tt.tip("Name"))

    def test_table_columns_get_help_without_overriding(self):
        frame = pd.DataFrame({"tracking_error": [0.04], "Name": ["x"], "Beta": [1.1]})
        config = tt._column_help(frame, {"Beta": {"help": "custom"}})
        self.assertIn("tracking_error", config)
        self.assertNotIn("Name", config)
        self.assertEqual(config["Beta"]["help"], "custom")

    def test_day_on_the_desk_points_to_real_pages(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(guide.BASE_DIR / "vittantra_app.py").read_text())
        pages = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                     if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "NAV_PAGES")
        self.assertGreaterEqual(len(guide.DAY_ON_THE_DESK), 6)
        for role, info in guide.DAY_ON_THE_DESK.items():
            self.assertTrue(info["who"])
            for time, task, page, why in info["day"]:
                self.assertIn(page, pages, f"{role}: {task}")
                self.assertTrue(why)


class PriceRefreshTests(unittest.TestCase):

    def test_fast_mode_runs_only_quick_price_steps(self):
        import run_vittantra as rv
        from pathlib import Path
        scripts = [s for _, s in rv.PRICE_STEPS]
        for script in scripts:
            self.assertTrue((Path(rv.BASE_DIR) / script).exists(), script)
        self.assertNotIn("fundamental_engine.py", scripts)        # SEC filings stay daily
        self.assertNotIn("multi_factor_rating.py", scripts)

    def test_price_workflow_schedules_market_hours_and_weekends(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        from pathlib import Path
        flow = yaml.safe_load((Path(guide.BASE_DIR) / ".github/workflows/refresh-prices.yml").read_text())
        crons = [c["cron"] for c in flow[True]["schedule"]]
        self.assertIn("*/15 13-21 * * 1-5", crons)
        self.assertTrue(any(c.endswith("0,6") for c in crons))
        self.assertIn("--prices", str(flow["jobs"]))


if __name__ == "__main__":
    unittest.main()
