"""Tests for the Day 94 analyst agents: evidence, honesty about missing data, no execution."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import analyst_agents as aa


class AnalystAgentTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.runs = aa.morning_pack()

    def test_every_agent_delivers_with_steps(self):
        self.assertEqual(len(self.runs), len(aa.AGENTS))
        for run in self.runs:
            self.assertTrue(run.sections, run.agent)
            self.assertTrue(run.steps, run.agent)

    def test_numbers_cite_their_source(self):
        for run in self.runs:
            for f in run.findings():
                if any(ch.isdigit() for ch in f["text"]):
                    self.assertTrue(f["source"] and f["field"], f"{run.agent}: {f['text']}")
                    self.assertTrue((aa.BASE_DIR / f["source"]).exists(), f["source"])

    def test_cited_values_match_the_source(self):
        run = aa.investment_analyst()
        assets = pd.read_csv(aa.BASE_DIR / "day76c_asset_analytics.csv").set_index("symbol")
        for f in run.findings():
            if f["source"] == "day76c_asset_analytics.csv" and f["field"].endswith(".return_1d"):
                symbol = f["field"].split(".return_1d")[0]
                self.assertAlmostEqual(f["value"], float(assets.at[symbol, "return_1d"]), places=5)

    def test_human_judgment_and_limits_are_stated(self):
        for run in self.runs:
            self.assertTrue(run.judgment and run.limits, run.agent)

    def test_unknown_company_is_not_invented(self):
        run = aa.equity_research("ZZZZZQ")
        text = aa.to_markdown(run)
        self.assertIn("not in Vittantra", text)
        self.assertFalse(any(ch.isdigit() for ch in "".join(f.text for s in run.sections.values() for f in s)))

    def test_missing_data_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for fn in (aa.portfolio_construction, aa.portfolio_manager, aa.portfolio_analyst, aa.risk_analyst):
                run = fn(Path(tmp))
                self.assertIn("Result", run.sections, fn.__name__)

    def test_validation_and_no_execution(self):
        validation = aa.validate(self.runs)
        self.assertTrue(validation["passed"].all(), validation)
        text = Path(aa.__file__).read_text().lower()
        for word in ("submit_order", "place_order", "requests.post", "broker"):
            self.assertNotIn(word, text)

    def test_agent_reviews_count_in_the_job_tracker(self):
        import job_tracker as jt
        progress = {"records": [{"time": "2026-10-20T09:00", "role": "trader", "task": "Agent review: Trader",
                                 "score": 100, "xp": 100, "answer": {}, "review": ""}]}
        rows = {r["responsibility"]: r["status"] for r in jt.responsibility_status(progress, "trader")}
        self.assertEqual(rows["Review the agent's trading plan"], "Demonstrated")


if __name__ == "__main__":
    unittest.main()
