"""Tests for the Vittantra Academy: content integrity, grading and work-desk logic."""

import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

import academy_desk as desk
import academy_live as live
from academy_content import LESSONS, ROLES, SIMULATOR_TASKS

BASE = Path(__file__).resolve().parent


class ContentTests(unittest.TestCase):

    def test_every_role_has_handbook_tasks_and_five_lessons(self):
        for role in ROLES:
            for field in ("title", "mission", "framework", "duties", "outputs", "career", "credentials"):
                self.assertTrue(ROLES[role][field], f"{role}.{field}")
            self.assertIn(role, SIMULATOR_TASKS)
            self.assertGreaterEqual(sum(l["role"] == role for l in LESSONS), 5)

    def test_lessons_are_complete_and_ids_unique(self):
        ids = [l["id"] for l in LESSONS]
        self.assertEqual(len(ids), len(set(ids)))
        for lesson in LESSONS:
            for field in ("concept", "formulas", "live", "code", "on_the_job", "exercise", "interview"):
                self.assertTrue(lesson[field], f"{lesson['id']}.{field}")
            self.assertTrue(hasattr(live, lesson["live"]), lesson["live"])

    def test_code_references_point_to_real_files_and_functions(self):
        for lesson in LESSONS:
            for ref in lesson["code"]:
                match = re.match(r"([\w_]+\.py)(?: → ([\w_, ]+))?", ref)
                if not match:
                    continue
                path = BASE / match.group(1)
                self.assertTrue(path.exists(), ref)
                source = path.read_text(encoding="utf-8")
                for name in (match.group(2) or "").split(","):
                    name = name.strip().split(" ")[0]
                    if name:
                        self.assertRegex(source, rf"def {name}\b", ref)

    def test_live_examples_run_on_committed_data(self):
        for lesson in LESSONS:
            try:
                text = getattr(live, lesson["live"])()
            except live.MissingData:
                continue
            self.assertIsInstance(text, str)
            self.assertNotIn("nan%", text, lesson["id"])


class GradingTests(unittest.TestCase):

    def test_set_grading(self):
        score, _ = desk.grade_set(["A", "B"], ["A", "B"])
        self.assertEqual(score, 100)
        score, feedback = desk.grade_set(["A", "B"], ["A", "C"])
        self.assertAlmostEqual(score, 100 / 3)
        self.assertIn("Missed breaches: B", feedback)

    def test_tear_sheet_grading_gives_partial_credit(self):
        key = {"Valuation": "Strong", "Growth": "Weak"}
        score, _ = desk.grade_tear_sheet(key, {"Valuation": "Strong", "Growth": "Average"})
        self.assertEqual(score, 75)

    def test_score_bands(self):
        self.assertEqual(desk.score_band(10), "Weak")
        self.assertEqual(desk.score_band(50), "Average")
        self.assertEqual(desk.score_band(90), "Strong")

    def test_levels(self):
        self.assertEqual(desk.level_for(0)[0], "Junior")
        self.assertEqual(desk.level_for(350)[0], "Analyst")
        self.assertEqual(desk.level_for(350)[2], 650)
        self.assertEqual(desk.level_for(5000), ("Lead", None, None))


class AdvisorTests(unittest.TestCase):

    VOLS = {"Stocks": 0.16, "Bonds": 0.06, "Cash": 0.005, "Alternatives": 0.18}

    def test_short_horizon_client_fails_aggressive_allocation(self):
        client = desk.CLIENT_TEMPLATES[1]          # Robert, 2-year horizon, would sell everything
        result = desk.evaluate_allocation(client, {"Stocks": 0.8, "Bonds": 0.1, "Cash": 0.1, "Alternatives": 0.0},
                                          self.VOLS)
        failed = [name for name, ok, _ in result["checks"] if not ok]
        self.assertIn("Stock share fits the time horizon", failed)

    def test_reference_allocation_is_suitable(self):
        for client in desk.CLIENT_TEMPLATES:
            best = desk.reference_allocation(client, self.VOLS)
            self.assertIsNotNone(best)
            for name, ok, _ in best["checks"]:
                if not name.startswith("Plan"):
                    self.assertTrue(ok, f"{client['name']}: {name}")
            self.assertAlmostEqual(sum(best["weights"].values()), 1.0)

    def test_two_asset_volatility_formula(self):
        result = desk.evaluate_allocation(desk.CLIENT_TEMPLATES[2],
                                          {"Stocks": 0.5, "Bonds": 0.5, "Cash": 0.0, "Alternatives": 0.0}, self.VOLS)
        self.assertAlmostEqual(result["volatility"], (0.25 * 0.16 ** 2 + 0.25 * 0.06 ** 2) ** 0.5)


class DeskTests(unittest.TestCase):

    def test_tasks_build_from_live_data(self):
        for build in (desk.morning_brief_task, desk.tear_sheet_task, desk.risk_check_task, desk.stress_task):
            try:
                task = build()
            except live.MissingData:
                continue
            self.assertTrue(task["reference"])

    def test_daily_tasks_are_stable_within_a_day(self):
        try:
            a = desk.tear_sheet_task(day=date(2026, 10, 3))["ticker"]
            b = desk.tear_sheet_task(day=date(2026, 10, 3))["ticker"]
        except live.MissingData:
            self.skipTest("no fundamentals")
        self.assertEqual(a, b)

    def test_cutting_the_top_contributor_reduces_its_risk_share(self):
        try:
            inputs = desk.rebalance_inputs()
        except live.MissingData:
            self.skipTest("no exposures")
        top = max(inputs["risk_share"], key=inputs["risk_share"].get)
        before = desk.evaluate_rebalance(inputs, {})
        after = desk.evaluate_rebalance(inputs, {top: 0.6})
        self.assertLess(after["shares"][top], before["shares"][top])
        self.assertGreater(after["turnover"], 0)

    def test_progress_and_work_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            progress = desk.load_progress(path)
            desk.record_task(progress, "advisor", "Client meeting", 75, {"Stocks": "40%"}, "Good")
            desk.save_progress(progress, path)
            reloaded = desk.load_progress(path)
            self.assertEqual(reloaded["xp"]["advisor"], 75)
            self.assertIn("Client meeting", desk.work_record_markdown(reloaded))


if __name__ == "__main__":
    unittest.main()
