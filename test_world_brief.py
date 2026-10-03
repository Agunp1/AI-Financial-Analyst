"""Tests for the Day 78b World & Markets Brief (no network: fake feeds)."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

import world_brief as wb

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Fed</title>
<item><title>Federal Reserve issues FOMC statement</title><link>https://fed/1</link>
<pubDate>Thu, 01 Oct 2026 18:00:00 GMT</pubDate><description>Interest rate decision</description></item>
<item><title>Old news from last year</title><link>https://fed/old</link>
<pubDate>Tue, 01 Oct 2025 18:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Oil jumps as OPEC cuts output; stocks slip</title><link href="https://news/2"/>
<updated>2026-10-02T09:30:00Z</updated><summary>Crude rallies</summary></entry>
<entry><title>Bitcoin hits record as crypto inflows grow</title><link href="https://news/3"/>
<updated>2026-10-02T10:00:00Z</updated></entry>
<entry><title>Federal Reserve issues FOMC statement</title><link href="https://news/dup"/>
<updated>2026-10-01T19:00:00Z</updated></entry>
</feed>"""


def fake_sources(fail_all=False, releases=None):
    pages = {"https://a/rss": RSS, "https://b/atom": ATOM, "https://c/bad": "<not xml"}

    def url(u):
        if fail_all or u == "https://d/down":
            raise ConnectionError("offline")
        return pages[u]

    def release_dates(start, end):
        return releases if releases is not None else pd.DataFrame(
            [{"date": "2026-10-14", "release": "Consumer Price Index"},
             {"date": "2026-10-09", "release": "Some Obscure Release"}])

    feeds = [("Fed", "Central bank", "https://a/rss"), ("News", "Markets", "https://b/atom"),
             ("Broken", "Markets", "https://c/bad"), ("Down", "Markets", "https://d/down")]
    return wb.BriefSources(url=url, release_dates=release_dates, feeds=feeds)


def write_data(base: Path):
    pd.DataFrame([{"factor": f, "window": "1 week", "move": m} for f, m in
                  [("interest_rates", 0.07), ("credit_spreads", 0.31), ("equity_market", -0.002),
                   ("us_dollar", 0.009), ("oil", -0.013), ("inflation_expectations", 0.02)]]
                 ).to_csv(base / "day76d_factor_moves.csv", index=False)
    dates = pd.bdate_range(end="2026-10-02", periods=15)
    pd.DataFrame({"BTC-USD": range(100, 115), "VNQ": range(50, 65), "^VIX": [20.0] * 15},
                 index=dates).to_csv(base / "day76c_price_history.csv", index_label="date")
    pd.DataFrame([{"series_id": "CPIAUCSL", "indicator": "CPI inflation", "latest": 3.35, "previous": 3.30,
                   "release_period": "2026-08-01"},
                  {"series_id": "FEDFUNDS", "indicator": "Fed funds", "latest": 3.75, "previous": 3.75,
                   "release_period": "2026-09-01"}]).to_csv(base / "day76c_economic_dashboard.csv", index=False)


class WorldBriefTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        write_data(self.base)
        self.now = pd.Timestamp("2026-10-03 08:00")

    def tearDown(self):
        self.tmp.cleanup()

    def run_brief(self, **kwargs):
        return wb.run_brief(fake_sources(**kwargs), base=self.base, now=self.now, verbose=False)

    def test_parses_rss_and_atom_and_drops_old_and_duplicates(self):
        headlines, *_ = self.run_brief()
        titles = list(headlines["title"])
        self.assertIn("Oil jumps as OPEC cuts output; stocks slip", titles)
        self.assertNotIn("Old news from last year", titles)
        self.assertEqual(titles.count("Federal Reserve issues FOMC statement"), 1)

    def test_theme_tagging(self):
        self.assertEqual(wb.tag_themes("Oil jumps as OPEC cuts output; stocks slip"), ["Equities", "Commodities"])
        self.assertIn("Rates", wb.tag_themes("Federal Reserve issues FOMC statement"))
        self.assertIn("Digital assets", wb.tag_themes("Bitcoin hits record"))
        self.assertEqual(wb.tag_themes("Local bakery wins award"), [])
        self.assertNotIn("FX", wb.tag_themes("Foxconn results"))   # word boundaries, not substrings

    def test_brief_links_data_to_headlines(self):
        _, _, brief, _ = self.run_brief()
        rates = brief.set_index("theme").loc["Rates"]
        self.assertEqual(rates["data_move"], "10Y Treasury yield change: +7 bp this week")
        self.assertIn("FOMC statement", rates["top_headlines"])
        crypto = brief.set_index("theme").loc["Digital assets"]
        self.assertIn("Bitcoin 1-week return", crypto["data_move"])

    def test_calendar_links_latest_values(self):
        _, calendar, _, _ = self.run_brief()
        cpi = calendar[calendar["event"] == "Consumer Price Index"].iloc[0]
        self.assertAlmostEqual(cpi["latest"], 3.35)
        self.assertNotIn("Some Obscure Release", set(calendar["event"]))
        fomc = calendar[calendar["event"] == "FOMC rate decision"]
        self.assertEqual(list(fomc["date"]), ["2026-10-28"])          # next meeting always shown

    def test_offline_keeps_saved_headlines(self):
        self.run_brief()
        headlines, _, _, validation = self.run_brief(fail_all=True)
        self.assertGreater(len(headlines), 0)
        feeds = validation.set_index("check").loc["News feeds reachable"]
        self.assertFalse(feeds["passed"])

    def test_calendar_without_fred_key(self):
        _, calendar, _, validation = self.run_brief(releases=pd.DataFrame(columns=["date", "release"]))
        self.assertEqual(list(calendar["event"]), ["FOMC rate decision"])
        self.assertIn("FRED_API_KEY", validation.set_index("check").loc["Calendar built", "details"])


if __name__ == "__main__":
    unittest.main()
