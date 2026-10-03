"""Tests for the Day 85 copilot: grounding, refusals, no invented numbers."""

import unittest

import vittantra_copilot as vc


def kb():
    base = vc.KnowledgeBase.__new__(vc.KnowledgeBase)
    base.records, base.entities, base.sources = [], {}, ["test"]
    base.alias("NVDA", "NVIDIA")
    base.alias("R2", "Sample client B — family")
    base.add("Research", "NVDA", "NVDA: DCF intrinsic value $204.80 vs price $233.99 (-12%), Fairly valued.",
             "day78_valuation.csv", "fair_value", 204.8, "valuation")
    base.add("Research", "NVDA", "NVDA (Bear case): Trades 12% above its DCF value.", "day78_research_claims.csv",
             "upside", -0.12, "bear")
    base.add("Research", "NVDA", "NVDA (Bull case): Revenue growing 20% a year.", "day78_research_claims.csv",
             "revenue_growth", 0.2, "bull")
    base.add("Advisory", "R2", "Sample client B (R2): profile Moderate, suitability SUITABLE.",
             "day82_client_profiles.csv", "suitability", "SUITABLE", "advisory")
    return base


class CopilotTests(unittest.TestCase):

    def setUp(self):
        self.bot = vc.Copilot(kb(), rewriter=None)

    def test_answers_with_citations(self):
        a = self.bot.ask("What is NVIDIA worth?")
        self.assertEqual(a.mode, "template")
        self.assertIn("204.80", a.text)
        self.assertIn("[1]", a.text)
        self.assertTrue(a.citations()[0].startswith("[1] day78_valuation.csv"))

    def test_bear_case_excludes_bull_points(self):
        a = self.bot.ask("What is the bear case for NVDA?")
        self.assertIn("Bear case", a.text)
        self.assertNotIn("Bull case", a.text)

    def test_refuses_to_trade(self):
        for q in ("Buy 100 shares of NVDA for me", "Please execute the trade now", "submit the order"):
            a = self.bot.ask(q)
            self.assertEqual(a.mode, "refused", q)
            self.assertIn("does not place", a.text)

    def test_no_data_means_no_guess(self):
        a = self.bot.ask("What is the weather in Paris?")
        self.assertEqual(a.mode, "no_data")
        self.assertIn("won't guess", a.text)
        self.assertEqual(a.evidence, [])

    def test_should_i_buy_gets_research_view_not_instruction(self):
        a = self.bot.ask("Should I buy NVDA?")
        self.assertIn("not personal trade instructions", a.text)

    def test_llm_answer_with_invented_number_is_rejected(self):
        liar = vc.Copilot(kb(), rewriter=lambda q, d: "NVDA is worth $300 per share [1].")
        a = liar.ask("What is NVIDIA worth?")
        self.assertEqual(a.mode, "template")
        self.assertNotIn("$300", a.text)

    def test_grounded_llm_answer_is_used(self):
        honest = vc.Copilot(kb(), rewriter=lambda q, d: "Vittantra's DCF puts NVDA at $204.80, 12% below the "
                                                         "$233.99 price — fairly valued [1].")
        a = honest.ask("What is NVIDIA worth?")
        self.assertEqual(a.mode, "llm")

    def test_entity_filter(self):
        a = self.bot.ask("Is sample client B suitable?")
        self.assertTrue(all(e.entity == "R2" for e in a.evidence))

    def test_grounding_check(self):
        ev = kb().records[:1]
        self.assertTrue(vc.is_grounded("Value $204.80 vs $233.99 [1]", ev))
        self.assertFalse(vc.is_grounded("Value $250 [1]", ev))

    def test_real_knowledge_base_loads(self):
        real = vc.KnowledgeBase()
        if not real.records:
            self.skipTest("no outputs")
        self.assertGreater(len({e.desk for e in real.records}), 2)


if __name__ == "__main__":
    unittest.main()
