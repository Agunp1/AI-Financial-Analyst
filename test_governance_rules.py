"""
Day 86 — Tests for every Vittantra rule, run against the committed outputs.

Each test is one non-negotiable rule from CLAUDE.md. If a module change ever
breaks a rule, this file fails — before anything reaches a user.
"""

import glob
import re
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent


def csv(name):
    path = BASE / name
    if not path.exists():
        raise unittest.SkipTest(f"{name} not generated yet")
    return pd.read_csv(path)


class NoAutomaticExecution(unittest.TestCase):
    """Rule: nothing may submit or execute trades."""

    def test_every_output_reports_zero_automatic_execution(self):
        checked = 0
        for path in glob.glob(str(BASE / "day*.csv")):
            df = pd.read_csv(path, nrows=5000)
            for column in [c for c in df.columns if "automatic_execution" in c.lower()]:
                values = pd.to_numeric(df[column], errors="coerce").fillna(0)
                self.assertTrue((values == 0).all(), f"{Path(path).name}:{column}")
                checked += 1
        self.assertGreater(checked, 0)

    def test_no_code_path_submits_orders(self):
        # actual calls or broker libraries, not the governance checks that look for such columns
        pattern = re.compile(r"(submit_order|place_order|create_order)\s*\(|import\s+(alpaca|ib_insync|ccxt)|"
                             r"from\s+(alpaca|ib_insync|ccxt)|\.buy\(|\.sell\(", re.IGNORECASE)
        offenders = [p for p in glob.glob(str(BASE / "*.py"))
                     if not Path(p).name.startswith("test_") and pattern.search(Path(p).read_text(errors="ignore"))]
        self.assertEqual(offenders, [])

    def test_proposals_wait_for_humans(self):
        self.assertEqual(csv("day79_portfolio_summary.csv")["approval_status"].iloc[0], "PENDING_HUMAN_APPROVAL")
        statuses = set(csv("day82_client_profiles.csv")["approval_status"])
        self.assertEqual(statuses, {"PENDING_CLIENT_AND_ADVISOR_APPROVAL"})
        proposals = BASE / "day81_whatif_proposals.csv"
        if proposals.exists():
            self.assertTrue((pd.read_csv(proposals)["status"] == "PENDING_HUMAN_APPROVAL").all())


class RemediationNeverIncreasesRisk(unittest.TestCase):
    """Rule: remediation must never increase modeled risk."""

    def test_instrument_level(self):
        actions = csv("day69_instrument_remediation_actions.csv")
        after = pd.to_numeric(actions["estimated_post_remediation_utilization"], errors="coerce")
        before = pd.to_numeric(actions["risk_budget_utilization"], errors="coerce")
        self.assertTrue((after <= before + 1e-9).all())
        self.assertTrue((pd.to_numeric(actions["required_modeled_risk_reduction"], errors="coerce").fillna(0) >= 0).all())

    def test_portfolio_level(self):
        s = csv("day69_portfolio_remediation_summary.csv").iloc[0]
        self.assertLessEqual(s["target_total_modeled_risk"], s["current_total_modeled_risk"] + 1e-9)
        self.assertLessEqual(s["maximum_estimated_post_remediation_utilization"],
                             s["maximum_current_risk_budget_utilization"] + 1e-9)


class RiskLimits(unittest.TestCase):
    """Rule: portfolio proposals respect the risk budget and limits."""

    def test_model_portfolio_limits(self):
        import portfolio_construction as pc
        p, s = csv("day79_model_portfolio.csv"), csv("day79_portfolio_summary.csv").iloc[0]
        self.assertAlmostEqual(p["weight"].sum(), 1.0, places=6)
        self.assertGreaterEqual(p["weight"].min(), 0)
        self.assertLessEqual(p["weight"].max(), pc.POLICY["max_weight"] + 1e-4)
        self.assertLessEqual(s["tracking_error"], s["tracking_error_budget"] + 1e-4)
        self.assertLessEqual(s["largest_risk_share"], pc.POLICY["max_risk_share"] + 1e-3)

    def test_model_allocations_within_target_volatility(self):
        import advisory_engine as ae
        a = csv("day82_model_allocations.csv")
        for row in a.itertuples():
            self.assertLessEqual(row.volatility, ae.PROFILES[row.profile]["target_vol"] + 1e-4)


class Suitability(unittest.TestCase):
    """Rule: advice must pass suitability for the client."""

    def test_every_client_checked_and_no_blocking_failures(self):
        profiles = csv("day82_client_profiles.csv")
        rules = csv("day83_suitability_results.csv")
        self.assertEqual(set(profiles["client_id"]), set(rules["client_id"]))
        self.assertFalse((rules["severity"] == "block").any(), rules[rules["severity"] == "block"].to_string())
        self.assertNotIn("NOT SUITABLE", set(profiles["suitability"]))

    def test_sample_clients_are_labelled_fictional(self):
        import json
        data = json.loads((BASE / "advisory_clients.json").read_text())
        self.assertIn("Fictional", data["note"])
        self.assertTrue(all("Sample" in c["name"] or c["client_id"].startswith("U") for c in data["clients"]))


class NoInventedData(unittest.TestCase):
    """Rule: the AI layer must not invent data."""

    def test_every_research_claim_has_evidence(self):
        claims = csv("day78_research_claims.csv")
        self.assertTrue(claims[["source_file", "field", "value"]].notna().all().all())
        sources = set(claims["source_file"]) - {"—"}
        self.assertTrue(all((BASE / s).exists() for s in sources), sources)

    def test_claim_values_match_their_source(self):
        claims = csv("day78_research_claims.csv")
        valuation = csv("day78_valuation.csv").set_index("ticker")
        rows = claims[(claims["source_file"] == "day78_valuation.csv") & (claims["field"] == "fair_value")]
        for r in rows.itertuples():
            self.assertAlmostEqual(float(r.value), float(valuation.at[r.ticker, "fair_value"]), places=3)

    def test_copilot_refuses_unsupported_and_trades(self):
        import vittantra_copilot as vc
        bot = vc.Copilot(rewriter=None)
        self.assertEqual(bot.ask("What is the population of Mars?").mode, "no_data")
        self.assertEqual(bot.ask("Sell all my shares for me").mode, "refused")

    def test_copilot_numbers_come_from_evidence(self):
        import vittantra_copilot as vc
        bot = vc.Copilot(rewriter=None)
        for q in vc.Copilot.suggested_questions():
            a = bot.ask(q)
            if a.evidence:
                body = "\n".join(line for line in a.text.splitlines()[1:])
                self.assertTrue(vc.is_grounded(body, a.evidence), q)

    def test_reports_disclose_limits(self):
        reports = csv("day84_client_reports.csv")
        self.assertTrue(reports["report"].str.contains("not guarantees").all())
        self.assertTrue(reports["report"].str.contains("nothing is executed").all())


class NoLookAhead(unittest.TestCase):
    """Rule: research uses only information available at the time."""

    def test_ic_weights_start_equal_until_enough_history(self):
        import multi_factor_rating as mfr
        weights = csv("day77_ic_weights.csv")
        early = weights.head(mfr.MIN_IC_HISTORY)[mfr.PILLARS].astype(float)
        self.assertTrue(np.allclose(early.to_numpy(), 1 / len(mfr.PILLARS)))

    def test_fundamentals_point_in_time_flag(self):
        v = csv("day77_validation_summary.csv").set_index("check")
        self.assertTrue(bool(v.loc["Fundamentals point in time in backtest", "passed"]))


class FreeDataOnly(unittest.TestCase):
    """Rule: free data sources only."""

    def test_no_paid_providers_in_code(self):
        # paid data APIs or libraries actually used (mentions in lessons are fine)
        paid = re.compile(r"import\s+(blpapi|refinitiv|quandl|intrinio|polygon|alpha_vantage|openai|anthropic)|"
                          r"api\.polygon\.io|alphavantage\.co|data\.nasdaq\.com/api|api\.tiingo\.com|"
                          r"eodhistoricaldata\.com|api\.openai\.com|api\.anthropic\.com", re.IGNORECASE)
        offenders = [p for p in glob.glob(str(BASE / "*.py"))
                     if not Path(p).name.startswith("test_") and paid.search(Path(p).read_text(errors="ignore"))]
        self.assertEqual(offenders, [])


class BacktestsArePresentedAsHistory(unittest.TestCase):
    """Rule: backtests are historical research, not promised returns."""

    def test_pages_label_backtests(self):
        for page in ("vittantra_pm_page.py", "vittantra_research_page.py"):
            text = (BASE / page).read_text()
            self.assertRegex(text, r"(?i)historical research|not a promise|research labels")

    def test_no_promise_language_in_generated_text(self):
        banned = re.compile(r"(?i)guaranteed return|risk-free profit|will definitely|can't lose|cannot lose")
        for name in ("day78_research_claims.csv", "day84_client_reports.csv"):
            path = BASE / name
            if path.exists():
                self.assertIsNone(banned.search(path.read_text()), name)


if __name__ == "__main__":
    unittest.main()
