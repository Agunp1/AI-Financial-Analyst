"""Tests for the Days 82–84 advisory engine."""

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import advisory_engine as ae

SLEEVES = list(ae.SLEEVES)


def toy_market():
    mu = pd.Series({"US equity": 0.09, "International developed equity": 0.095, "Emerging-market equity": 0.11,
                    "US Treasuries": 0.045, "Inflation-linked Treasuries": 0.045, "Investment-grade credit": 0.05,
                    "High-yield credit": 0.065, "US REITs": 0.08, "Gold": 0.025, "Cash (T-bills)": 0.04})
    vol = pd.Series(ae.LONG_RUN_VOL)
    corr = np.full((10, 10), 0.2)
    eq = [0, 1, 2, 7]
    for i in eq:
        for j in eq:
            corr[i, j] = 0.75
    np.fill_diagonal(corr, 1.0)
    cov = pd.DataFrame(corr * np.outer(vol[SLEEVES], vol[SLEEVES]), index=SLEEVES, columns=SLEEVES)
    return mu, cov


def retail(**overrides):
    client = {"client_id": "T", "type": "retail", "name": "Test", "horizon_years": 20, "goal": "Retirement",
              "wealth": 100000, "annual_contribution": 5000, "annual_withdrawal": 0, "goal_target_real": 300000,
              "income_stability": "Stable", "loss_reaction": "Would buy more", "experience": "Some",
              "liquidity_need_12m": 0}
    client.update(overrides)
    return client


class ProfileTests(unittest.TestCase):

    def test_profile_is_lower_of_willingness_and_capacity(self):
        p = ae.retail_profile(retail(horizon_years=2))       # keen, but money needed soon
        self.assertGreaterEqual(p["willingness"], 4)
        self.assertLessEqual(p["capacity"], 3)
        self.assertEqual(p["profile"], min(p["willingness"], p["capacity"]))
        self.assertIn("discuss", p["profile_note"])

    def test_cautious_client_gets_low_profile(self):
        p = ae.retail_profile(retail(loss_reaction="Would sell everything", experience="None"))
        self.assertEqual(p["profile"], 1)
        self.assertEqual(p["loss_tolerance"], 0.10)

    def test_institutional_required_return(self):
        client = {"type": "institutional", "ips": {"spending_rate": 0.045, "cost_rate": 0.005,
                                                   "max_volatility": 0.10, "max_bad_year_loss": 0.15}}
        p = ae.institutional_profile(client, inflation=0.025)
        self.assertAlmostEqual(p["required_return"], 0.075)
        self.assertEqual(p["profile"], 3)                    # 10% volatility → Moderate


class AllocationTests(unittest.TestCase):

    def setUp(self):
        self.mu, self.cov = toy_market()

    def test_allocation_respects_limits(self):
        for level, p in ae.PROFILES.items():
            w = ae.optimize_allocation(self.mu, self.cov, p["target_vol"], p["max_equity"], p["min_cash"])
            stats = ae.portfolio_stats(w, self.mu, self.cov)
            self.assertAlmostEqual(w.sum(), 1.0)
            self.assertLessEqual(stats["volatility"], p["target_vol"] + 1e-4)
            self.assertLessEqual(stats["equity_share"], p["max_equity"] + 1e-4)
            self.assertGreaterEqual(stats["cash_share"], p["min_cash"] - 1e-4)
            for sleeve, cap in ae.SLEEVE_MAX.items():
                self.assertLessEqual(w[sleeve], cap + 1e-4, sleeve)

    def test_more_risk_more_expected_return(self):
        returns = [ae.portfolio_stats(ae.optimize_allocation(self.mu, self.cov, p["target_vol"], p["max_equity"],
                                                             p["min_cash"]), self.mu, self.cov)["expected_return"]
                   for p in ae.PROFILES.values()]
        self.assertEqual(returns, sorted(returns))

    def test_inexperienced_retail_gets_no_complex_holdings(self):
        profile = ae.retail_profile(retail())
        w = ae.recommend(retail(), profile, self.mu, self.cov)
        self.assertEqual(w["High-yield credit"], 0.0)


class SuitabilityTests(unittest.TestCase):

    def setUp(self):
        self.mu, self.cov = toy_market()

    def test_recommendation_is_suitable(self):
        client = retail()
        profile = ae.retail_profile(client)
        w = ae.recommend(client, profile, self.mu, self.cov)
        self.assertEqual(ae.suitability_verdict(ae.suitability(client, profile, w, self.mu, self.cov)), "SUITABLE")

    def test_all_equity_for_cautious_client_is_blocked(self):
        client = retail(loss_reaction="Would sell everything")
        profile = ae.retail_profile(client)
        w = pd.Series(0.0, index=SLEEVES)
        w["US equity"], w["Emerging-market equity"] = 0.6, 0.4
        results = ae.suitability(client, profile, w, self.mu, self.cov)
        self.assertEqual(ae.suitability_verdict(results), "NOT SUITABLE")
        self.assertTrue(results["basis"].str.contains("III\\(C\\)").all())

    def test_ips_exclusion_blocks(self):
        client = {"client_id": "P", "type": "institutional", "name": "Plan", "horizon_years": 15, "goal": "x",
                  "wealth": 1e8, "ips": {"required_return": 0.06, "max_volatility": 0.10, "max_bad_year_loss": 0.15,
                                         "min_fixed_income": 0.3, "max_alternatives": 0.1,
                                         "excluded_sleeves": ["Emerging-market equity"], "liquidity_need_12m": 0}}
        profile = ae.institutional_profile(client, 0.025)
        w = pd.Series(0.0, index=SLEEVES)
        w["Emerging-market equity"], w["US Treasuries"] = 0.1, 0.9
        results = ae.suitability(client, profile, w, self.mu, self.cov).set_index("rule")
        self.assertFalse(results.loc["IPS exclusions respected", "passed"])
        self.assertFalse(results.loc["Expected return meets the return objective", "passed"])


class MonteCarloTests(unittest.TestCase):

    def test_zero_volatility_matches_compounding(self):
        paths = ae.simulate_wealth(100.0, 10.0, 0.0, 3, 0.05, 0.0, 0.0, paths=10)
        expected = ((100 * 1.05 + 10) * 1.05 + 10) * 1.05 + 10
        self.assertAlmostEqual(paths[0, -1], expected, places=8)

    def test_lognormal_mean_matches_assumption(self):
        paths = ae.simulate_wealth(1.0, 0.0, 0.0, 1, 0.07, 0.15, 0.0, paths=200_000, seed=1)
        self.assertAlmostEqual(paths[:, 1].mean(), 1.07, delta=0.002)
        self.assertAlmostEqual(paths[:, 1].std(), 0.15, delta=0.002)

    def test_real_terms_and_withdrawals(self):
        paths = ae.simulate_wealth(100.0, 0.0, 10.0, 20, 0.0, 0.0, 0.03, paths=5)
        self.assertEqual(ae.goal_probability(paths, 0, 10.0), 0.0)      # runs out with no growth
        self.assertTrue((paths >= 0).all())

    def test_required_contribution_reaches_target(self):
        client = retail(wealth=10000, horizon_years=15, goal_target_real=200000)
        c = ae.required_contribution(client, 0.07, 0.12, 0.02)
        paths = ae.simulate_wealth(10000, c, 0, 15, 0.07, 0.12, 0.02, 4000, ae.ASSUMPTIONS["seed"])
        self.assertGreaterEqual(ae.goal_probability(paths, 200000, 0), 0.80)


class RunTests(unittest.TestCase):

    def test_run_on_committed_data(self):
        base = Path(ae.BASE_DIR)
        if not (base / "day76c_price_history.csv").exists():
            self.skipTest("no Day 76c data")
        with tempfile.TemporaryDirectory() as tmp:
            out = ae.run_advisory(out_dir=Path(tmp), verbose=False)
        self.assertTrue(out["validation"]["passed"].all(), out["validation"].to_string())
        self.assertTrue(out["reports"]["report"].str.contains("not guarantees").all())


if __name__ == "__main__":
    unittest.main()
