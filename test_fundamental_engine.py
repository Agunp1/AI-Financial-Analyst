"""
Tests for the Day 76 fundamental engine using synthetic SEC XBRL filings
(same structure as data.sec.gov companyfacts), so they run offline.
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import fundamental_engine as fe


def quarter_bounds(year, q):
    start = pd.Timestamp(year=year, month=3 * (q - 1) + 1, day=1)
    end = start + pd.offsets.QuarterEnd(0)
    return start, end


def build_company(quarterly_revenue, margin=0.2, equity=50_000.0, shares=1_000.0,
                  restate=None, share_classes=1, filing_lag_days=40):
    """
    Calendar fiscal year. quarterly_revenue: {(year, q): value}.
    10-Qs report 3-month and year-to-date values; 10-Ks report the year.
    restate: (year, q, new_ytd_value, filed_date) adds a later 10-Q/A.
    """
    flows = {"Revenues": [], "NetIncomeLoss": [], "OperatingIncomeLoss": [],
             "NetCashProvidedByUsedInOperatingActivities": [],
             "PaymentsToAcquirePropertyPlantAndEquipment": [], "GrossProfit": [],
             "EarningsPerShareDiluted": []}
    instants = {"Assets": [], "StockholdersEquity": [], "Liabilities": [],
                "AssetsCurrent": [], "LiabilitiesCurrent": [], "LongTermDebt": [],
                "CashAndCashEquivalentsAtCarryingValue": []}
    dei = []
    years = sorted({y for y, _ in quarterly_revenue})
    scale = {"Revenues": 1.0, "NetIncomeLoss": margin, "OperatingIncomeLoss": margin * 1.3,
             "NetCashProvidedByUsedInOperatingActivities": margin * 1.2,
             "PaymentsToAcquirePropertyPlantAndEquipment": 0.05, "GrossProfit": 0.45,
             "EarningsPerShareDiluted": margin / shares}

    def add_flow(concept, start, end, value, form, filed, fp):
        flows[concept].append({"start": str(start.date()), "end": str(end.date()), "val": value,
                               "form": form, "filed": str(filed.date()), "fp": fp})

    for year in years:
        ytd = 0.0
        for q in range(1, 5):
            if (year, q) not in quarterly_revenue:
                continue
            q_start, q_end = quarter_bounds(year, q)
            revenue = quarterly_revenue[(year, q)]
            ytd += revenue
            year_start = pd.Timestamp(year=year, month=1, day=1)
            if q < 4:
                filed = q_end + pd.Timedelta(days=filing_lag_days)
                for concept, factor in scale.items():
                    add_flow(concept, q_start, q_end, revenue * factor, "10-Q", filed, f"Q{q}")
                    if q > 1:
                        add_flow(concept, year_start, q_end, ytd * factor, "10-Q", filed, f"Q{q}")
            else:
                filed = q_end + pd.Timedelta(days=filing_lag_days + 20)
                for concept, factor in scale.items():
                    add_flow(concept, year_start, q_end, ytd * factor, "10-K", filed, "FY")
            for concept, value in [("Assets", equity * 3), ("StockholdersEquity", equity),
                                   ("Liabilities", equity * 2), ("AssetsCurrent", equity * 0.8),
                                   ("LiabilitiesCurrent", equity * 0.5), ("LongTermDebt", equity * 0.6),
                                   ("CashAndCashEquivalentsAtCarryingValue", equity * 0.2)]:
                instants[concept].append({"end": str(q_end.date()), "val": value,
                                          "form": "10-K" if q == 4 else "10-Q",
                                          "filed": str(filed.date())})
            for share_class in range(share_classes):
                dei.append({"end": str((filed - pd.Timedelta(days=5)).date()),
                            "val": shares / share_classes, "form": "10-K" if q == 4 else "10-Q",
                            "filed": str(filed.date())})
    if restate:
        year, q, value, filed = restate
        _, q_end = quarter_bounds(year, q)
        add_flow("Revenues", pd.Timestamp(year=year, month=1, day=1), q_end, value,
                 "10-Q/A", pd.Timestamp(filed), f"Q{q}")

    def wrap(series, unit):
        return {name: {"units": {unit if name != "EarningsPerShareDiluted" else "USD/shares": rows}}
                for name, rows in series.items()}

    return {"facts": {
        "us-gaap": {**wrap(flows, "USD"), **wrap(instants, "USD")},
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": dei}}},
    }}


QUARTERS_2024 = {(2024, q): 100.0 + 10 * q for q in range(1, 5)}   # 110,120,130,140
QUARTERS_2025 = {(2025, 1): 150.0, (2025, 2): 160.0}
REVENUE = {**QUARTERS_2024, **QUARTERS_2025}


class TrailingTwelveMonthTests(unittest.TestCase):

    def frame(self, company, as_of):
        return fe.concept_frame(company, "revenue", pd.Timestamp(as_of))

    def test_ttm_after_second_quarter(self):
        # FY2024 (500) + H1 2025 (310) − H1 2024 (230) = last four quarters 130+140+150+160
        df = self.frame(build_company(REVENUE), "2025-09-01")
        self.assertAlmostEqual(fe.ttm_value(df), 580.0)

    def test_ttm_at_fiscal_year_end_is_annual(self):
        df = self.frame(build_company(REVENUE), "2025-03-15")
        self.assertAlmostEqual(fe.ttm_value(df), 500.0)

    def test_point_in_time_ignores_unfiled_quarter(self):
        # Q2 2025 is filed 2025-08-09; on 2025-08-01 only Q1 is public.
        df = self.frame(build_company(REVENUE), "2025-08-01")
        self.assertEqual(df["end"].max(), pd.Timestamp("2025-03-31"))
        self.assertAlmostEqual(fe.ttm_value(df), 500.0 + 150.0 - 110.0)

    def test_restatement_used_only_after_it_is_filed(self):
        company = build_company(REVENUE, restate=(2025, 2, 330.0, "2025-11-01"))
        before = fe.ttm_value(self.frame(company, "2025-10-01"))
        after = fe.ttm_value(self.frame(company, "2025-11-02"))
        self.assertAlmostEqual(before, 580.0)
        self.assertAlmostEqual(after, 500.0 + 330.0 - 230.0)


class MetricTests(unittest.TestCase):

    def metrics(self, company, sector="Industrials", price=10.0, as_of="2025-09-01"):
        return fe.compute_company_metrics(company, pd.Timestamp(as_of), price, sector)

    def test_core_ratios(self):
        m = self.metrics(build_company(REVENUE))
        self.assertAlmostEqual(m["market_cap"], 10_000.0)
        self.assertAlmostEqual(m["revenue_ttm"], 580.0)
        self.assertAlmostEqual(m["net_margin"], 0.2)
        self.assertAlmostEqual(m["gross_margin"], 0.45)
        self.assertAlmostEqual(m["earnings_yield"], 116.0 / 10_000.0)
        self.assertAlmostEqual(m["debt_to_equity"], 0.6)
        self.assertAlmostEqual(m["current_ratio"], 1.6)
        # Revenue growth: TTM 580 vs TTM a year earlier (Q3'23–Q2'24 unavailable → None) handled
        self.assertIn("revenue_growth", m)

    def test_growth_uses_trailing_twelve_months(self):
        revenue = {**{(2023, q): 100.0 for q in range(1, 5)}, **REVENUE}
        m = self.metrics(build_company(revenue))
        # TTM Q3'24–Q2'25 = 580 vs TTM Q3'23–Q2'24 = 100+100+110+120 = 430
        self.assertAlmostEqual(m["revenue_growth"], 580.0 / 430.0 - 1)

    def test_negative_equity_flagged(self):
        m = self.metrics(build_company(REVENUE, equity=-5_000.0))
        self.assertTrue(m["negative_equity"])
        self.assertIsNone(m["roe"])
        self.assertIsNone(m["book_to_price"])
        self.assertIsNone(m["debt_to_equity"])

    def test_financials_exclude_industrial_ratios(self):
        m = self.metrics(build_company(REVENUE), sector="Financials")
        for metric in ("gross_margin", "current_ratio", "debt_to_equity", "fcf_yield", "ebit_to_ev"):
            self.assertIsNone(m[metric], metric)
        self.assertIsNotNone(m["roe"])

    def test_share_classes_are_summed(self):
        m = self.metrics(build_company(REVENUE, share_classes=3))
        self.assertAlmostEqual(m["shares_outstanding"], 1_000.0)


class EndToEndTests(unittest.TestCase):

    def test_scores_and_validation(self):
        universe, facts, prices = {}, {}, {}
        sectors = ["Industrials", "Health Care", "Financials", "Energy", "Utilities", "Materials"]
        for i, sector in enumerate(sectors):
            ticker = f"T{i}"
            universe[ticker] = {"name": f"Company {i}", "sector": sector}
            revenue = {k: v * (1 + 0.1 * i) for k, v in
                       {**{(2023, q): 100.0 for q in range(1, 5)}, **REVENUE}.items()}
            facts[1000 + i] = build_company(revenue, margin=0.05 + 0.03 * i, equity=40_000 + 5_000 * i)
            prices[ticker] = 10.0 + i
        source = fe.SecSource(
            ticker_map=lambda: {t: 1000 + i for i, t in enumerate(universe)},
            company_facts=lambda cik: facts[cik],
        )
        with tempfile.TemporaryDirectory() as tmp:
            metrics, scores, validation = fe.run_fundamentals(
                pd.Timestamp("2025-09-01"), source, universe, prices, Path(tmp), verbose=False)
            for name in (fe.OUTPUT_METRICS, fe.OUTPUT_SCORES, fe.OUTPUT_COVERAGE, fe.OUTPUT_VALIDATION):
                self.assertTrue((Path(tmp) / name).exists())
        failed = validation[~validation["passed"]]
        self.assertTrue(failed.empty, failed.to_string())
        self.assertTrue(scores["fundamental_score"].between(0, 100).all())
        # Higher margin → higher quality score
        self.assertGreater(scores.loc["T5", "quality_score"], scores.loc["T0", "quality_score"])

    def test_missing_company_is_reported_not_fatal(self):
        universe = {"AAA": {"name": "A", "sector": "Industrials"}}
        source = fe.SecSource(ticker_map=lambda: {}, company_facts=lambda cik: {})
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _, validation = fe.run_fundamentals(
                pd.Timestamp("2025-09-01"), source, universe, {}, Path(tmp), verbose=False)
        self.assertEqual(metrics.loc["AAA", "error"], "CIK not found")
        self.assertFalse(validation.set_index("check").loc["SEC filings loaded", "passed"])


if __name__ == "__main__":
    unittest.main()
