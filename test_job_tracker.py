"""Tests for the Job Tracker: daily plan, readiness, CFA focus, streak and evidence pack."""

import unittest
from datetime import date, datetime

import academy_cfa as cfa
import academy_live as live
import job_tracker as jt
from academy_content import LESSONS, ROLES


def rec(day, role, task, score=80, answers=3):
    return {"time": f"{day}T09:00", "role": role, "task": task, "score": score, "xp": score,
            "answer": {f"Q{i + 1}": "A" for i in range(answers)}, "review": ""}


MONDAY = date(2026, 10, 19)


class JobTrackerTests(unittest.TestCase):

    def test_weekdays_cover_the_target_roles_and_weekend_catches_up(self):
        roles = [jt.role_of_the_day({}, date(2026, 10, 19 + i)) for i in range(5)]
        self.assertEqual(roles, jt.WEEKDAY_ROLES)
        self.assertEqual(roles[2], "trader")
        progress = {"records": [rec("2026-10-20", r, i["prefixes"][0]) for r in jt.ROLE_ORDER
                                for i in jt.RESPONSIBILITIES[r] if r != "trader"]}
        self.assertEqual(jt.role_of_the_day(progress, date(2026, 10, 24)), "private_markets_analyst")  # Saturday
        self.assertEqual(jt.role_of_the_day(progress, date(2026, 10, 25)), "trader")       # Sunday: weakest
        self.assertNotIn("advisor", jt.ROLE_ORDER)

    def test_every_role_has_desk_duties(self):
        self.assertEqual(set(jt.RESPONSIBILITIES), set(ROLES))
        for role, items in jt.RESPONSIBILITIES.items():
            self.assertTrue(any(i.get("desk") for i in items), role)

    def test_plan_has_three_steps_and_ticks_them(self):
        plan = jt.daily_plan({}, MONDAY)
        self.assertEqual([s["step"] for s in plan["steps"]], ["Desk duty", "CFA Level II", "Lesson"])
        self.assertEqual(plan["done"], 0)
        progress = {"records": [rec(MONDAY, "investment_analyst", "Morning market brief (08:00)"),
                                rec(MONDAY, "portfolio_analyst", "CFA L2 item set: Duration, convexity and the curve")],
                    "lesson_log": [{"id": "IA1", "date": f"{MONDAY}T10:00"}], "lessons_read": ["IA1"]}
        self.assertEqual(jt.daily_plan(progress, MONDAY)["done"], 3)

    def test_plan_does_not_move_while_working_today(self):
        before = jt.daily_plan({}, MONDAY)
        progress = {"records": [rec(MONDAY, "investment_analyst", "Morning market brief (08:00)", 100)],
                    "lessons_read": ["IA1"], "lesson_log": [{"id": "IA1", "date": f"{MONDAY}T10:00"}]}
        after = jt.daily_plan(progress, MONDAY)
        self.assertEqual([s["what"] for s in before["steps"]], [s["what"] for s in after["steps"]])

    def test_desk_duty_prefers_responsibilities_never_done(self):
        progress = {"records": [rec("2026-10-14", "private_markets_analyst", "Deal flow screen", 90)]}
        plan = jt.daily_plan(progress, date(2026, 10, 21))           # Wednesday: trader
        self.assertEqual(plan["role"], "trader")
        progress["records"].append(rec("2026-10-14", "trader", "Trade plan: SPY", 90))
        self.assertNotEqual(jt.daily_plan(progress, date(2026, 10, 21))["steps"][0]["what"], "Trade plan (stop and size)")

    def test_readiness_counts_only_passing_work(self):
        progress = {"records": [rec("2026-10-14", "portfolio_analyst", "Daily risk check (09:30)", 100),
                                rec("2026-10-14", "portfolio_analyst", "Stress question", 40)]}
        rows = {r["responsibility"]: r["status"] for r in jt.responsibility_status(progress, "portfolio_analyst")}
        self.assertEqual(rows["Daily risk check and escalation"], "Demonstrated")
        self.assertEqual(rows["Stress testing"], "In progress")
        self.assertAlmostEqual(jt.readiness(progress, "portfolio_analyst"), 1 / len(jt.RESPONSIBILITIES["portfolio_analyst"]))

    def test_desk_task_of_another_role_does_not_count(self):
        progress = {"records": [rec("2026-10-14", "advisor", "Daily risk check (09:30)", 100)]}
        self.assertEqual(jt.readiness(progress, "portfolio_analyst"), 0)

    def test_cfa_step_targets_the_weakest_topic(self):
        progress = {"records": [rec("2026-10-14", "portfolio_analyst",
                                    "CFA L2 item set: Duration, convexity and the curve", 100)]}
        key = jt.cfa_item_key(progress, MONDAY)
        self.assertNotEqual(jt.ITEM_SET_TOPIC[key], "Fixed Income")
        never = {t for t in jt.ITEM_SET_TOPIC.values() if t != "Fixed Income"}
        self.assertIn(jt.ITEM_SET_TOPIC[key], never)

    def test_item_set_topics_and_titles_match_the_item_sets(self):
        self.assertEqual(set(jt.ITEM_SET_TOPIC), set(cfa.ITEM_SETS))
        for key, build in cfa.ITEM_SETS.items():
            try:
                item = build(date(2026, 10, 3))
            except live.MissingData:
                continue
            self.assertEqual(item["topic"], jt.ITEM_SET_TOPIC[key], key)
            self.assertTrue(item["title"].startswith(jt._TITLE_PREFIX[key]), key)

    def test_responsibility_prefixes_match_real_item_set_titles(self):
        prefixes = [p[len(jt.CFA_TASK_PREFIX):] for items in jt.RESPONSIBILITIES.values() for i in items
                    for p in i["prefixes"] if p.startswith(jt.CFA_TASK_PREFIX)]
        titles = list(jt._TITLE_PREFIX.values())
        for p in prefixes:
            self.assertTrue(any(p.startswith(t) or t.startswith(p) for t in titles), p)

    def test_streak_counts_consecutive_days(self):
        progress = {"records": [rec("2026-10-17", "advisor", "Client meeting: X"),
                                rec("2026-10-18", "advisor", "Client meeting: Y")],
                    "lesson_log": [{"id": "AD1", "date": "2026-10-19T08:00"}]}
        self.assertEqual(jt.streak(progress, MONDAY), 3)
        self.assertEqual(jt.streak(progress, date(2026, 10, 20)), 3)     # nothing yet today
        self.assertEqual(jt.streak(progress, date(2026, 10, 22)), 0)

    def test_next_lesson_is_first_unread_for_the_role(self):
        first = next(l for l in LESSONS if l["role"] == "advisor")
        self.assertEqual(jt.next_lesson({}, "advisor", MONDAY)["id"], first["id"])

    def test_lesson_log_and_exam_countdown(self):
        progress = jt.log_lesson({}, "IA1", datetime(2026, 10, 19, 8))
        self.assertEqual(jt.lessons_on(progress, MONDAY), ["IA1"])
        self.assertEqual(jt.days_to_exam({"tracker": {"cfa_exam": "2026-11-18"}}, MONDAY), 30)
        self.assertIsNone(jt.days_to_exam({}, MONDAY))

    def test_evidence_pack_covers_every_role(self):
        text = jt.evidence_pack({"records": [rec("2026-10-14", "trader", "Trade plan: X", 90)]}, MONDAY)
        for key in jt.ROLE_ORDER:
            self.assertIn(ROLES[key]["title"], text)
        self.assertNotIn(ROLES["advisor"]["title"], text)
        self.assertIn("Trade plan: X", text)
        self.assertIn("no real money", text)


if __name__ == "__main__":
    unittest.main()
