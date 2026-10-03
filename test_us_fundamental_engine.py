"""
Tests for the Day 76b US market engine. SEC frames are simulated by slicing
synthetic company filings by concept and calendar period, the way
data.sec.gov/api/xbrl/frames does, so the tests run offline.
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import us_fundamental_engine as us
from test_fundamental_engine import REVENUE, build_company as _build_company


def build_company(*args, shares=1_000.0, **kwargs):
    """Company facts plus quarterly diluted share counts (present in real 10-Qs)."""
    facts = _build_company(*args, shares=shares, **kwargs)
    revenue = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    facts["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"] = {"units": {"shares": [
        {"start": r["start"], "end": r["end"], "val": shares, "form": r["form"], "filed": r["filed"]}
        for r in revenue if (pd.Timestamp(r["end"]) - pd.Timestamp(r["start"])).days < 100
    ]}}
    return facts


AS_OF = pd.Timestamp("2025-09-01")


def frames_from_companies(companies):
    """Return a fake frame(concept, unit, period) over {cik: companyfacts}."""
    def frame(concept, unit, period):
        year = int(period[2:6])
        rows = []
        for cik, facts in companies.items():
            node = facts["facts"]["us-gaap"].get(concept)
            if not node:
                continue
            for fact in next(iter(node["units"].values())):
                end = pd.Timestamp(fact["end"])
                if period.endswith("I"):
                    q = int(period[7])
                    if "start" in fact or end.year != year or (end.month - 1) // 3 + 1 != q:
                        continue
                elif "Q" in period:
                    q = int(period[7])
                    if "start" not in fact:
                        continue
                    days = (end - pd.Timestamp(fact["start"])).days
                    if not 80 <= days <= 100 or end.year != year or (end.month - 1) // 3 + 1 != q:
                        continue
                else:
                    if "start" not in fact:
                        continue
                    days = (end - pd.Timestamp(fact["start"])).days
                    if not 350 <= days <= 380 or end.year != year:
                        continue
                row = {"cik": cik, "end": fact["end"], "val": fact["val"]}
                if "start" in fact:
                    row["start"] = fact["start"]
                rows.append(row)
        return rows
    return frame


def make_market():
    revenue_base = {**{(2023, q): 100.0 for q in range(1, 5)}, **REVENUE}
    rows, submissions, companies, prices = [], {}, {}, {}
    sectors = [("Information Technology", 7372), ("Health Care", 2834), ("Industrials", 3561)]
    cik = 100
    for sector, sic in sectors:
        for i in range(16):
            cik += 1
            ticker = f"{sector[:3].upper()}{i}"
            rows.append({"cik": cik, "name": f"{sector} {i}", "ticker": ticker, "exchange": "Nasdaq"})
            submissions[cik] = {"sic": str(sic), "entityType": "operating"}
            companies[cik] = build_company({k: v * (1 + 0.05 * i) for k, v in revenue_base.items()},
                                           margin=0.05 + 0.01 * i, equity=30_000 + 1_000 * i)
            prices[ticker] = 20.0 + i
    for i in range(4):
        cik += 1
        rows.append({"cik": cik, "name": f"Bank {i}", "ticker": f"BNK{i}", "exchange": "NYSE"})
        submissions[cik] = {"sic": "6022", "entityType": "operating"}
        companies[cik] = build_company(revenue_base, margin=0.25, equity=10_000 + 1_000 * i)
        prices[f"BNK{i}"] = 40.0
    # Excluded: SPAC, OTC listing, fund
    rows += [{"cik": 900, "name": "Blank Check", "ticker": "SPAC", "exchange": "Nasdaq"},
             {"cik": 901, "name": "OTC Co", "ticker": "OTCX", "exchange": "OTC"},
             {"cik": 902, "name": "Some Fund", "ticker": "FUND", "exchange": "NYSE"}]
    submissions[900] = {"sic": "6770", "entityType": "operating"}
    submissions[901] = {"sic": "7372", "entityType": "operating"}
    submissions[902] = {"sic": None, "entityType": "other"}
    source = us.UsSource(
        ticker_exchange=lambda: pd.DataFrame(rows),
        submission=lambda c: submissions[c],
        frame=frames_from_companies(companies),
        prices=lambda tickers: {t: prices[t] for t in tickers if t in prices},
    )
    return source


class SectorMappingTests(unittest.TestCase):

    def test_known_codes(self):
        self.assertEqual(us.sic_to_sector(7372), "Information Technology")   # software
        self.assertEqual(us.sic_to_sector(2834), "Health Care")              # pharma
        self.assertEqual(us.sic_to_sector(6798), "Real Estate")              # REIT
        self.assertEqual(us.sic_to_sector(6022), "Financials")               # bank
        self.assertEqual(us.sic_to_sector(4911), "Utilities")
        self.assertEqual(us.sic_to_sector(1311), "Energy")
        self.assertEqual(us.sic_to_sector(None), "Unclassified")


class PeriodTests(unittest.TestCase):

    def test_calendar_quarters_only_completed(self):
        self.assertEqual(us.calendar_quarters(pd.Timestamp("2025-09-01"), 3),
                         ["CY2025Q2", "CY2025Q1", "CY2024Q4"])
        self.assertEqual(us.calendar_quarters(pd.Timestamp("2025-09-30"), 1), ["CY2025Q3"])


class EndToEndTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.universe, self.metrics, self.scores, self.validation = us.run_us_fundamentals(
            AS_OF, make_market(), out_dir=Path(self.tmp.name), expected_size=40, verbose=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exclusions(self):
        self.assertNotIn("OTCX", set(self.universe["ticker"]))
        excluded = self.universe.set_index("ticker")
        self.assertFalse(excluded.loc["SPAC", "included"])
        self.assertFalse(excluded.loc["FUND", "included"])
        self.assertEqual(len(self.metrics), 52)

    def test_metrics_rebuilt_from_frames_match_company_engine(self):
        # Frames carry only quarters and years; TTM is rebuilt by deriving Q4.
        first = self.metrics.loc["INF0"]
        self.assertAlmostEqual(first["revenue_ttm"], 580.0)
        self.assertAlmostEqual(first["market_cap"], 20_000.0)

    def test_sector_relative_scores(self):
        it = self.scores[self.scores["sector"] == "Information Technology"]
        self.assertTrue((it["ranking_group"] == "sector").all())
        banks = self.scores[self.scores["sector"] == "Financials"]
        self.assertTrue((banks["ranking_group"] == "universe").all())   # only 4 banks
        self.assertEqual(it["sector_rank"].min(), 1)

    def test_validation_passes(self):
        failed = self.validation[~self.validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())

    def test_outputs_written(self):
        for name in (us.OUTPUT_UNIVERSE, us.OUTPUT_METRICS, us.OUTPUT_SCORES, us.OUTPUT_VALIDATION):
            self.assertTrue((Path(self.tmp.name) / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
