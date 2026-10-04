"""Tests for Day 69b remediation sizing and the human approval of the fix."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import multi_asset_risk as mar
import portfolio_risk_budgeting as prb
import remediation_sizing as rs
import vittantra_approval_page as ap


def proposal_frame():
    return pd.DataFrame([
        {"instrument_id": "OPT", "symbol": "OPT", "quantity": 5.0, "proposed_quantity": 1.0, "change": -0.8,
         "current_utilization": 3.5, "proposed_utilization": 0.79, "risk_budget": 0.1, "action": "REDUCE",
         "reason": "over its limit now"},
        {"instrument_id": "BOND", "symbol": "BOND", "quantity": 100.0, "proposed_quantity": 100.0, "change": 0.0,
         "current_utilization": 0.01, "proposed_utilization": 0.07, "risk_budget": 0.2, "action": "HOLD",
         "reason": ""},
    ])


SUMMARY = {"status": "PENDING_HUMAN_APPROVAL", "positions_over_budget_now": 1, "positions_over_budget_after": 0,
           "max_utilization_now": 3.5, "max_utilization_after": 0.79, "positions_reduced": 1, "rounds": 3,
           "automatic_execution_authorized_count": 0}


class SizingTests(unittest.TestCase):

    def test_limits_are_feasible_and_cash_has_none(self):
        limits = prb.ASSET_CLASS_RISK_BUDGETS
        self.assertEqual(limits["Cash/Money Market"], 0.0)
        risky = sum(v for k, v in limits.items() if k != "Cash/Money Market")
        self.assertGreater(risky, 1.0)        # limits of risky classes must be able to hold 100% of risk

    def test_validation_passes_for_a_good_proposal(self):
        out = rs.validate(proposal_frame(), SUMMARY)
        self.assertTrue(out["passed"].all(), out.to_string())

    def test_validation_catches_an_increase(self):
        bad = proposal_frame()
        bad.loc[1, "proposed_quantity"] = 150.0
        out = rs.validate(bad, SUMMARY).set_index("check")
        self.assertFalse(out.at["No position is increased", "passed"])

    def test_approved_quantities_override_the_example_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "approved.json"
            path.write_text(json.dumps({"quantities": {"OPT_AAPL_CALL": 0.5}}))
            instruments = mar.build_sample_instruments(use_live_data=False)
            mar.apply_approved_quantities(instruments, path)
            sizes = {i.instrument_id: i.quantity for i in instruments}
            self.assertEqual(sizes["OPT_AAPL_CALL"], 0.5)
            self.assertEqual(mar.approved_quantities(Path(tmp) / "missing.json"), {})


class ApprovalTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "approved_positions.json"
        self.patch = mock.patch.object(ap, "APPROVED", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_pending_until_approved_then_recalculating(self):
        proposal = proposal_frame()
        self.assertTrue(ap.pending(proposal, SUMMARY))
        entry = ap.record_decision("APPROVED", proposal, SUMMARY, "derivatives far above limits")
        self.assertEqual(entry["automatic_execution_authorized"], 0)
        self.assertFalse(ap.pending(proposal, SUMMARY))
        self.assertTrue(ap.recalculating(proposal))
        self.assertEqual(json.loads(self.path.read_text())["quantities"]["OPT"], 1.0)

    def test_reject_keeps_sizes_and_logs(self):
        proposal = proposal_frame()
        ap.record_decision("REJECTED", proposal, SUMMARY, "not now")
        data = json.loads(self.path.read_text())
        self.assertEqual(data["quantities"], {})
        self.assertEqual(data["history"][-1]["decision"], "REJECTED")
        self.assertTrue(ap.pending(proposal, SUMMARY))

    def test_nothing_pending_when_no_action_needed(self):
        self.assertFalse(ap.pending(proposal_frame(), {**SUMMARY, "status": "NO_ACTION_NEEDED"}))


if __name__ == "__main__":
    unittest.main()
