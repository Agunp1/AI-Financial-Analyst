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


if __name__ == "__main__":
    unittest.main()
