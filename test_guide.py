"""Tests for the in-app Guide: every page is covered, links point to real pages and lessons, live numbers are real."""

import unittest

import vittantra_guide as guide


class GuideTests(unittest.TestCase):

    def test_every_page_has_help(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(guide.BASE_DIR / "vittantra_app.py").read_text())
        pages = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                     if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "NAV_PAGES")
        self.assertEqual(set(pages), set(guide.PAGE_HELP))
        for page, help_ in guide.PAGE_HELP.items():
            self.assertTrue(help_["what"] and help_["steps"] and help_["tip"], page)
        for playbook in guide.PLAYBOOKS:
            for page, _ in playbook["steps"]:
                self.assertIn(page, pages, playbook["title"])

    def test_lessons_exist(self):
        from academy_content import LESSONS
        ids = {lesson["id"] for lesson in LESSONS}
        for asset in guide.ASSET_CLASSES:
            self.assertTrue(set(asset["lessons"]) <= ids, asset["name"])

    def test_asset_classes_cover_vittantra_data(self):
        import pandas as pd
        classes = set(pd.read_csv(guide.BASE_DIR / guide.ANALYTICS)["asset_class"])
        self.assertEqual(classes, {a["key"] for a in guide.ASSET_CLASSES})

    def test_live_numbers_come_from_data(self):
        snap = guide.asset_snapshot("Fixed Income")
        self.assertGreater(snap["instruments"], 0)
        self.assertIsNone(guide.asset_snapshot("Not an asset class"))

    def test_bonds_are_driven_by_rates(self):
        drivers = guide.macro_drivers("Fixed Income")
        self.assertEqual(drivers.iloc[0]["factor"], "Interest rates")

    def test_factor_verdicts_follow_t_stats(self):
        evidence = guide.factor_evidence()
        for row in evidence.itertuples():
            if row.t_stat >= 2 and row.mean_ic > 0:
                self.assertEqual(row.verdict, "Predictive so far")
            elif abs(row.t_stat) < 2:
                self.assertEqual(row.verdict, "Not proven yet")

    def test_glossary_search(self):
        self.assertIn("Duration", guide.search_glossary("duration"))
        self.assertEqual(guide.search_glossary("zzzz"), {})


if __name__ == "__main__":
    unittest.main()
