"""Tests for Day 80 performance attribution."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import performance_attribution as pa


class BrinsonTests(unittest.TestCase):

    def test_textbook_two_sector_example(self):
        # Portfolio 70% Tech / 30% Energy; benchmark 50/50.
        # Tech: portfolio stock +12%, benchmark stocks +10% avg; Energy: +2% vs +4%.
        wb = pd.Series({"T1": 0.25, "T2": 0.25, "E1": 0.25, "E2": 0.25})
        wp = pd.Series({"T1": 0.70, "E1": 0.30})
        r = pd.Series({"T1": 0.12, "T2": 0.08, "E1": 0.02, "E2": 0.06})
        sectors = pd.Series({"T1": "Tech", "T2": "Tech", "E1": "Energy", "E2": "Energy"})
        bf = pa.brinson_fachler(wp, wb, r, sectors).set_index("sector")
        rb = 0.07
        self.assertAlmostEqual(bf.loc["Tech", "allocation"], 0.20 * (0.10 - rb))
        self.assertAlmostEqual(bf.loc["Tech", "selection"], 0.50 * (0.12 - 0.10))
        self.assertAlmostEqual(bf.loc["Energy", "interaction"], -0.20 * (0.02 - 0.04))
        active = 0.70 * 0.12 + 0.30 * 0.02 - rb
        self.assertAlmostEqual(bf[["allocation", "selection", "interaction"]].sum().sum(), active)

    def test_sector_not_held_has_no_selection(self):
        wb = pd.Series({"A": 0.5, "B": 0.5})
        wp = pd.Series({"A": 1.0})
        bf = pa.brinson_fachler(wp, wb, pd.Series({"A": 0.1, "B": -0.1}),
                                pd.Series({"A": "X", "B": "Y"})).set_index("sector")
        self.assertEqual(bf.loc["Y", "selection"], 0.0)
        self.assertEqual(bf.loc["Y", "interaction"], 0.0)

    def test_carino_linking_adds_to_compounded_active(self):
        rp = pd.Series([0.05, -0.02, 0.03])
        rb = pd.Series([0.03, -0.01, 0.01])
        scale = pa.carino_factors(rp, rb)
        linked = ((rp - rb) * scale).sum()
        self.assertAlmostEqual(linked, np.prod(1 + rp) - np.prod(1 + rb), places=12)


class RunTests(unittest.TestCase):

    def test_end_to_end_with_planted_signal(self):
        rng = np.random.default_rng(5)
        tickers = [f"S{i:02d}" for i in range(30)]
        sectors = {t: ["A", "B", "C"][i % 3] for i, t in enumerate(tickers)}
        rows = []
        for date in pd.date_range("2024-01-01", periods=30, freq="28D"):
            scores = rng.uniform(0, 100, 30)
            for t, s in zip(tickers, scores):
                rows.append({"date": date, "ticker": t, "composite_ic_weighted": s,
                             "fundamental": s, "technical": rng.uniform(0, 100), "quant": rng.uniform(0, 100),
                             "economic": rng.uniform(0, 100), "risk": rng.uniform(0, 100),
                             "forward_return_20d": 0.0004 * (s - 50) + rng.normal(0, 0.02)})
        with tempfile.TemporaryDirectory() as tmp:
            periods, sectors_table, factors, summary, validation = pa.run_attribution(
                pd.DataFrame(rows), sectors, out_dir=Path(tmp), verbose=False)
        self.assertTrue(validation["passed"].all(), validation.to_string())
        self.assertGreater(summary["active_cumulative"], 0)
        self.assertGreater(summary["selection_linked"], 0)          # the signal picks stocks, not sectors
        self.assertGreater(summary["factor_fundamental_sum"], 0)    # planted on the fundamental pillar
        self.assertLess(summary["costs_linked"], 0)


if __name__ == "__main__":
    unittest.main()
