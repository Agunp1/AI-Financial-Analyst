"""Tests for CFA Level II item sets built from live Vittantra data."""

import math
import unittest
from datetime import date

import academy_cfa as cfa
import academy_live as live
from academy_content import LESSONS


class ItemSetTests(unittest.TestCase):

    def item_sets(self):
        for key, build in cfa.ITEM_SETS.items():
            try:
                yield key, build(date(2026, 10, 3))
            except live.MissingData:
                continue

    def test_every_question_has_three_distinct_options_and_one_answer(self):
        seen = 0
        for key, item in self.item_sets():
            seen += 1
            self.assertIn(item["topic"], cfa.CFA_TOPICS)
            for q in item["questions"]:
                self.assertEqual(len(q["options"]), 3, key)
                self.assertEqual(len(set(q["options"])), 3, f"{key}: duplicate options {q['options']}")
                self.assertIn(q["answer"], (0, 1, 2))
                self.assertTrue(q["explanation"])
        self.assertGreater(seen, 0)

    def test_answers_are_stable_within_a_day(self):
        for key, build in cfa.ITEM_SETS.items():
            try:
                a, b = build(date(2026, 10, 3)), build(date(2026, 10, 3))
            except live.MissingData:
                continue
            self.assertEqual([q["options"] for q in a["questions"]], [q["options"] for q in b["questions"]])

    def test_fixed_income_answer_matches_formula(self):
        try:
            item = cfa.item_fixed_income(date(2026, 10, 3))
        except live.MissingData:
            self.skipTest("no data")
        d = live._risk_metric("CORP_BOND", "modified_duration")
        c = live._risk_metric("CORP_BOND", "convexity")
        q = item["questions"][0]
        self.assertEqual(q["options"][q["answer"]], f"{-d * 0.01 + 0.5 * c * 0.0001:.2%}")

    def test_grading(self):
        item = {"questions": [{"answer": 0}, {"answer": 2}, {"answer": 1}]}
        self.assertEqual(cfa.grade(item, [0, 2, 0]), (200 / 3, 2))

    def test_every_desk_gets_an_item_set_when_data_exists(self):
        for role in cfa.DESK_ITEM_SETS:
            item = cfa.todays_item_set(role, date(2026, 10, 3))
            if item is not None:
                self.assertIn(item["key"], cfa.DESK_ITEM_SETS[role])

    def test_every_lesson_has_a_cfa_topic(self):
        for lesson in LESSONS:
            self.assertIn(cfa.LESSON_CFA_TOPIC.get(lesson["id"]), cfa.CFA_TOPICS, lesson["id"])

    def test_record_cfa_accumulates(self):
        progress = {}
        cfa.record_cfa(progress, "Fixed Income", 2, 3)
        cfa.record_cfa(progress, "Fixed Income", 3, 3)
        self.assertEqual(progress["cfa"]["Fixed Income"], {"answered": 6, "correct": 5})


if __name__ == "__main__":
    unittest.main()
