"""Tests for the personal welcome: greeting by time of day and briefing from the person's own data."""

import unittest
from datetime import datetime

import vittantra_welcome as w


class WelcomeTests(unittest.TestCase):

    def test_greeting_by_time_of_day(self):
        self.assertEqual(w.greeting(datetime(2026, 10, 5, 8)), "Good morning")
        self.assertEqual(w.greeting(datetime(2026, 10, 5, 14)), "Good afternoon")
        self.assertEqual(w.greeting(datetime(2026, 10, 5, 21)), "Good evening")
        self.assertEqual(w.greeting(datetime(2026, 10, 5, 2)), "Good evening")

    def test_names(self):
        self.assertEqual(w.display_name("owner"), "Arjun")          # default when no owner_name secret
        self.assertEqual(w.display_name("priya"), "priya")
        self.assertIsNone(w.display_name(None))

    def test_briefing_uses_real_market_data(self):
        line = w._market_line()
        if line is not None:
            self.assertIn("S&P 500", line)
            self.assertRegex(line, r"(rose|fell) \d+\.\d%")


if __name__ == "__main__":
    unittest.main()
