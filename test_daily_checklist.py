"""Tests for the Home daily checklist: within an hour, ticks, training, no pile-up."""

import unittest
from datetime import date

import daily_checklist as dc
import vittantra_coach as coach

TODAY = date(2026, 11, 3)


def rec(day, role, task, score=80):
    return {"time": f"{day}T09:00", "role": role, "task": task, "score": score, "xp": score,
            "answer": {"Q1": "A", "Q2": "B", "Q3": "C"}, "review": ""}


class ChecklistTests(unittest.TestCase):

    def test_plain_day_has_market_check_and_three_steps_within_an_hour(self):
        items = dc.checklist({}, TODAY)
        self.assertEqual([i["id"] for i in items], ["market", "desk", "cfa", "lesson"])
        self.assertLessEqual(dc.summary(items)["minutes"], 60)
        self.assertTrue(all(i["why"] for i in items))

    def test_items_tick_from_work_and_buttons(self):
        progress = {"records": [rec(TODAY, "trader", "Trade plan: SPY"),
                                rec(TODAY, "trader", "CFA L2 item set: Trade sizing and execution costs: SPY")]}
        dc.tick(progress, dc.MARKET_CHECK, TODAY)
        done = {i["id"]: i["done"] for i in dc.checklist(progress, TODAY)}     # 3 Nov 2026 is a Tuesday
        self.assertTrue(done["market"] and done["cfa"])
        self.assertFalse(done["lesson"])

    def test_training_replaces_the_tracker_steps_and_stays_within_an_hour(self):
        progress = {}
        coach.start(progress, TODAY)
        for day in range(len(coach.TRAINING)):
            progress["training"]["done"] = [coach.step_id(d, i) for d in range(day)
                                            for i in range(len(coach.TRAINING[d]["steps"]))]
            progress["training"]["completed_on"] = {}
            items = dc.checklist(progress, TODAY)
            self.assertEqual(items[0]["id"], "market")
            self.assertTrue(all(i.get("training") for i in items[1:]))
            self.assertLessEqual(dc.summary(items)["minutes"], 60, day)

    def test_finished_training_day_still_shows_ticked_today(self):
        progress = {}
        coach.start(progress, TODAY)
        for i in range(len(coach.TRAINING[0]["steps"])):
            coach.mark_done(progress, coach.step_id(0, i), TODAY)
        items = dc.checklist(progress, TODAY)
        self.assertTrue(all(i["done"] for i in items[1:]))

    def test_yesterday_is_reported_not_carried(self):
        progress = {"records": [rec("2026-11-01", "advisor", "x")], "daily_log": {"2026-11-01": ["market"]}}
        self.assertIn("Market & economy check", dc.yesterday_open(progress, TODAY))
        self.assertEqual(len(dc.checklist(progress, TODAY)), 4)              # today is still one day's work
        self.assertEqual(dc.yesterday_open({}, TODAY), [])                   # new user: nothing to report
        self.assertEqual(dc.yesterday_open({"records": [rec("2026-11-01", "advisor", "x")]}, TODAY), [])

    def test_market_snapshot_cites_sources(self):
        rows = dc.market_snapshot()
        self.assertGreater(len(rows), 4)
        for r in rows:
            if any(ch.isdigit() for ch in r["text"]):
                self.assertTrue(r["source"])


if __name__ == "__main__":
    unittest.main()
