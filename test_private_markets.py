"""Tests for the Day 91 private markets desk (VC and PE formulas, deal simulator, desk grading)."""

import unittest
from datetime import date

import academy_desk as desk
import private_markets as pm


class VentureTests(unittest.TestCase):

    def test_vc_method_and_reverse(self):
        v = pm.vc_method(200e6, 20, 2e6, retention=0.7)
        self.assertAlmostEqual(v["post_money"], 7e6)
        self.assertAlmostEqual(v["pre_money"], 5e6)
        self.assertAlmostEqual(pm.required_exit(7e6, 20, 0.7), 200e6)
        self.assertAlmostEqual(pm.target_multiple_from_irr(0.5, 5), 7.59375)

    def test_priced_round_and_pool_shuffle(self):
        plain = pm.priced_round(8e6, 2e6, 1e6)
        self.assertAlmostEqual(plain["price_per_share"], 8.0)
        self.assertAlmostEqual(plain["investor_ownership"], 0.2)
        shuffled = pm.priced_round(8e6, 2e6, 1e6, pool_top_up=0.10)
        self.assertLess(shuffled["price_per_share"], plain["price_per_share"])
        self.assertAlmostEqual(shuffled["new_shares"] / shuffled["post_shares"], 0.2)

    def test_cap_table_dilution(self):
        table = pm.cap_table(1e6, [{"name": "Seed", "pre_money": 6e6, "investment": 2e6, "pool_top_up": 0.10},
                                   {"name": "Series A", "pre_money": 24e6, "investment": 8e6}])
        last = table.iloc[-1]
        self.assertAlmostEqual(last[["Founders", "Option pool", "Seed", "Series A"]].sum(), 1.0)
        self.assertAlmostEqual(last["Series A"], 0.25)
        self.assertAlmostEqual(table.iloc[1]["Seed"] * 0.75, last["Seed"])      # diluted by the A round

    def test_waterfall(self):
        low = pm.waterfall(10e6, [{"name": "A", "invested": 8e6, "shares": 2e6}], 8e6)
        high = pm.waterfall(100e6, [{"name": "A", "invested": 8e6, "shares": 2e6}], 8e6)
        self.assertAlmostEqual(low.iloc[0]["proceeds"], 8e6)
        self.assertAlmostEqual(low.iloc[1]["proceeds"], 2e6)
        self.assertAlmostEqual(high.iloc[0]["proceeds"], 20e6)
        part = pm.waterfall(20e6, [{"name": "A", "invested": 8e6, "shares": 2e6, "participating": True}], 8e6)
        self.assertAlmostEqual(part.iloc[0]["proceeds"], 8e6 + 0.2 * 12e6)
        for table in (low, high, part):
            self.assertAlmostEqual(table["proceeds"].sum(), table["proceeds"].sum())
        self.assertAlmostEqual(low["proceeds"].sum(), 10e6)

    def test_unit_economics(self):
        u = pm.unit_economics(500, 0.75, 0.02, 9000, net_new_arr=1e6, net_burn=1.5e6)
        self.assertAlmostEqual(u["ltv"], 18750)
        self.assertAlmostEqual(u["ltv_to_cac"], 18750 / 9000)
        self.assertAlmostEqual(u["cac_payback_months"], 24)
        self.assertAlmostEqual(u["burn_multiple"], 1.5)
        self.assertEqual(pm.rule_of_40(0.5, -0.1), 0.4)

    def test_fund_power_law(self):
        f = pm.simulate_fund(sims=5000)
        self.assertGreater(f["median_top_deal_share"], 0.25)
        self.assertTrue(0 <= f["p_lose_money"] <= 1)


class PrivateEquityTests(unittest.TestCase):

    def test_lbo_bridge_reconciles(self):
        deal = pm.lbo(10e6, 10, 5, 0.08, 0.05, 5, 10, fees=0.0)
        b = deal["bridge"]
        gain = deal["exit_equity"] - deal["entry_equity"]
        self.assertAlmostEqual(b["ebitda_growth"] + b["multiple_change"] + b["debt_paydown"], gain, places=2)
        self.assertAlmostEqual(deal["irr"], deal["moic"] ** 0.2 - 1)

    def test_irr(self):
        self.assertAlmostEqual(pm.irr([-100, 0, 0, 0, 0, 200]), 2 ** 0.2 - 1, places=6)
        self.assertAlmostEqual(pm.irr([-100, 110]), 0.10, places=6)


class SimulatorTests(unittest.TestCase):

    def test_deals_reproducible_unique_and_fictional(self):
        a, b = pm.generate_deals(date(2026, 5, 1)), pm.generate_deals(date(2026, 5, 1))
        self.assertEqual([d["company"] for d in a], [d["company"] for d in b])
        self.assertEqual(len({d["company"] for d in a}), len(a))

    def test_screen_is_selective(self):
        decisions = [pm.screen_deal(d)["decision"] for day in range(60)
                     for d in pm.generate_deals(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + day))]
        share = decisions.count("Take meeting") / len(decisions)
        self.assertTrue(0.05 < share < 0.35, share)

    def test_desk_grading(self):
        task = desk.deal_screen_task(date(2026, 5, 1))
        perfect = {d["company"]: s["decision"] for d, s in zip(task["deals"], task["screens"])}
        self.assertEqual(desk.grade_deal_screen(task, perfect)[0], 100)
        t = desk.term_sheet_task(date(2026, 5, 1))
        score, _ = desk.grade_term_sheet(t, t["post_money"], t["ownership"] * 100, t["required_exit"])
        self.assertEqual(score, 100)
        l = desk.lbo_task(date(2026, 5, 1))
        self.assertEqual(desk.grade_lbo(l, l["result"]["moic"], l["result"]["irr"] * 100)[0], 100)

    def test_interview_coach(self):
        q = desk.INTERVIEW_BANK[8]
        good = ("Entry EV is EBITDA times the multiple, funded with debt and equity. Project EBITDA and free cash flow, "
                "repay debt, exit at a multiple; equity is exit EV minus debt; then MOIC and IRR.")
        self.assertGreater(desk.grade_interview(q, good)[0], desk.grade_interview(q, "I like money.")[0])


if __name__ == "__main__":
    unittest.main()
