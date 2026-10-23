"""Tests for the 4-week training coach: one day at a time, at most an hour, no pile-up after missed days."""

import unittest
from datetime import date

import vittantra_coach as coach


def finish_day(progress, day, when):
    for i in range(len(coach.TRAINING[day]["steps"])):
        coach.mark_done(progress, coach.step_id(day, i), when)


class CoachTests(unittest.TestCase):

    def test_four_weeks_each_within_an_hour_with_reasons(self):
        self.assertEqual(len(coach.TRAINING), 28)
        self.assertEqual({d["week"] for d in coach.TRAINING}, {1, 2, 3, 4})
        for day in range(28):
            self.assertLessEqual(coach.day_minutes(day) + 5, 60)
            for page, text, minutes, why in coach.TRAINING[day]["steps"]:
                self.assertTrue(text and why and minutes > 0)

    def test_steps_point_to_real_pages(self):
        import ast
        from pathlib import Path
        tree = ast.parse((Path(coach.__file__).parent / "vittantra_app.py").read_text())
        pages = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                     if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "NAV_PAGES")
        for d in coach.TRAINING:
            for page, *_ in d["steps"]:
                self.assertIn(page, pages)

    def test_one_day_at_a_time_and_no_pile_up(self):
        p = {}
        coach.start(p, date(2026, 11, 2))
        self.assertEqual(coach.current_day(p, date(2026, 11, 2)), 0)
        finish_day(p, 0, date(2026, 11, 2))
        self.assertIsNone(coach.current_day(p, date(2026, 11, 2)))      # day 2 waits until tomorrow
        # Missed 3 Nov and 4 Nov: on 5 Nov only day 2 is open, not three days of work
        self.assertEqual(coach.current_day(p, date(2026, 11, 5)), 1)
        finish_day(p, 1, date(2026, 11, 5))
        self.assertIsNone(coach.current_day(p, date(2026, 11, 5)))
        self.assertEqual(coach.current_day(p, date(2026, 11, 6)), 2)

    def test_next_step_and_finish(self):
        p = {}
        coach.start(p, date(2026, 11, 2))
        step = coach.next_step(p, date(2026, 11, 2))
        self.assertEqual((step["day"], step["index"], step["page"]), (0, 0, "Home"))
        self.assertTrue(step["why"])
        for d in range(28):
            finish_day(p, d, date(2026, 11, 2))
        self.assertTrue(coach.finished(p))
        self.assertIsNone(coach.next_step(p, date(2026, 12, 1)))


if __name__ == "__main__":
    unittest.main()
