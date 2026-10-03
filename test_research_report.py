"""Tests for the Day 78 evidence-linked research reports."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import research_report as rr


def write_inputs(base: Path):
    pd.DataFrame([
        {"ticker": "AAA", "name": "Alpha", "sector": "Industrials", "rating": "Overweight",
         "composite_ic_weighted": 80, "fundamental": 85, "technical": 75, "quant": 72, "economic": 50, "risk": 20,
         "strongest_pillar": "fundamental", "weakest_pillar": "risk", "regime": "risk_on", "as_of": "2026-10-01",
         "beta": 1.2, "volatility_1y": 0.45},
        {"ticker": "BBB", "name": "Beta Co", "sector": "Financials", "rating": "Underweight",
         "composite_ic_weighted": 20, "fundamental": 15, "technical": 25, "quant": 30, "economic": 60, "risk": 80,
         "strongest_pillar": "risk", "weakest_pillar": "fundamental", "regime": "risk_on", "as_of": "2026-10-01",
         "beta": np.nan, "volatility_1y": 0.2},
    ]).to_csv(base / rr.RATINGS, index=False)
    pd.DataFrame([
        {"signal": "fundamental", "mean_ic": 0.12, "ic_t_stat": 2.5},
        {"signal": "risk", "mean_ic": -0.1, "ic_t_stat": -2.6},
    ]).to_csv(base / rr.IC_SUMMARY, index=False)
    pd.DataFrame([
        {"ticker": "AAA", "revenue_growth": 0.15, "roe": 0.25, "debt_to_equity": 0.5, "pe_ratio": 45,
         "latest_filing_date": "2026-08-01", "fcf_yield": 0.01},
        {"ticker": "BBB", "revenue_growth": -0.02, "roe": np.nan, "debt_to_equity": 3.0,
         "latest_filing_date": "2026-07-15"},
    ]).to_csv(base / rr.METRICS, index=False)
    pd.DataFrame([{"ticker": "AAA"}, {"ticker": "BBB"}]).to_csv(base / rr.SCORES, index=False)
    pd.DataFrame([
        {"ticker": "AAA", "price": 100.0, "fair_value": 130.0, "upside": 0.30, "primary_model": "DCF",
         "valuation_signal": "Undervalued", "dcf_value": 130.0, "ri_value": 90.0, "models_used": "DCF, RI",
         "wacc": 0.09, "cost_of_equity": 0.10, "beta_adjusted": 1.13, "synthetic_rating": "A",
         "implied_growth": 0.02, "dcf_initial_growth": 0.12, "notes": "first note | second note"},
        {"ticker": "BBB", "price": 50.0, "notes": "price or shares missing: not valued"},
    ]).to_csv(base / rr.VALUATION, index=False)


class ResearchReportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        write_inputs(base)
        cls.claims, cls.summary, cls.validation = rr.run_reports(base, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def claims_for(self, ticker, section=None):
        c = self.claims[self.claims["ticker"] == ticker]
        return c if section is None else c[c["section"] == section]

    def test_every_claim_has_evidence(self):
        self.assertTrue(self.claims[["source_file", "field", "value"]].notna().all().all())

    def test_no_claims_about_missing_data(self):
        # BBB has no ROE and no fair value: nothing may be claimed about them
        fields = set(self.claims_for("BBB")["field"])
        self.assertNotIn("roe", fields)
        self.assertNotIn("fair_value", fields)
        missing = self.claims_for("BBB", "Risks and limits")
        self.assertTrue(missing["claim"].str.contains("Not available").any())

    def test_bull_and_bear_cases_from_evidence(self):
        bull = " ".join(self.claims_for("AAA", "Bull case")["claim"])
        bear = " ".join(self.claims_for("AAA", "Bear case")["claim"])
        self.assertIn("below its DCF value", bull)
        self.assertIn("Low expectations", bull)          # implied 2% vs 12% assumed
        self.assertIn("P/E", bear)
        self.assertIn("volatile", bear.lower())

    def test_notes_split_into_separate_risks(self):
        risks = self.claims_for("AAA", "Risks and limits")["claim"].tolist()
        self.assertIn("First note.", risks)
        self.assertIn("Second note.", risks)

    def test_predictive_pillars_cited_only_when_significant(self):
        thesis = " ".join(self.claims_for("AAA", "Thesis")["claim"])
        self.assertIn("fundamental (IC 0.12", thesis)
        self.assertNotIn("risk (IC", thesis)

    def test_markdown_numbers_evidence(self):
        md = rr.report_markdown("AAA", self.claims, self.summary.set_index("ticker").loc["AAA"])
        self.assertIn("## Evidence", md)
        self.assertIn("[1]", md)
        self.assertIn("Not a recommendation", md)
        self.assertEqual(md.count("→"), len(self.claims_for("AAA")))

    def test_validation_passes(self):
        failed = self.validation[~self.validation["passed"]]
        # Balanced check needs ≥70% of stocks with both cases; both stocks here have both
        self.assertTrue(failed.empty, failed.to_string())


if __name__ == "__main__":
    unittest.main()
