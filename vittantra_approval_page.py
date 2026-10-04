"""
Human approval of the remediation sizing (Day 69b) for the demo risk book.

The owner reviews the proposed position sizes and approves or rejects them,
acting as both reviewers in this one-person demo. An approval writes
approved_positions.json (the demo book's new sizes) and records the decision;
the risk chain then re-runs. Nothing is traded: the book is a fictional model
portfolio and automatic execution stays 0.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

import vittantra_cloud as cloud


BASE_DIR = Path(__file__).resolve().parent
PROPOSAL = BASE_DIR / "day69_proposed_positions.csv"
SUMMARY = BASE_DIR / "day69_sizing_summary.csv"
APPROVED = BASE_DIR / "approved_positions.json"


def load_proposal() -> Optional[pd.DataFrame]:
    return pd.read_csv(PROPOSAL) if PROPOSAL.exists() else None


def load_summary() -> dict:
    return pd.read_csv(SUMMARY).iloc[0].to_dict() if SUMMARY.exists() else {}


def load_approved() -> dict:
    try:
        return json.loads(APPROVED.read_text())
    except Exception:
        return {}


def pending(proposal: Optional[pd.DataFrame] = None, summary: Optional[dict] = None) -> bool:
    """A fix is waiting when the sizing proposes reductions that have not been approved yet."""
    proposal = load_proposal() if proposal is None else proposal
    summary = load_summary() if summary is None else summary
    if proposal is None or summary.get("status") != "PENDING_HUMAN_APPROVAL":
        return False
    approved = load_approved().get("quantities", {})
    return not all(abs(approved.get(r.instrument_id, r.quantity) - r.proposed_quantity) < 1e-9
                   for r in proposal.itertuples())


def recalculating(proposal: Optional[pd.DataFrame] = None) -> bool:
    """Approved, but the risk chain has not re-run with the new sizes yet."""
    proposal = load_proposal() if proposal is None else proposal
    decision = (load_approved().get("history") or [{}])[-1]
    if decision.get("decision") != "APPROVED" or proposal is None:
        return False
    approved = load_approved().get("quantities", {})
    return any(abs(approved.get(r.instrument_id, r.quantity) - r.quantity) > 1e-9 for r in proposal.itertuples())


def record_decision(decision: str, proposal: pd.DataFrame, summary: dict, comment: str) -> dict:
    data = load_approved()
    history = list(data.get("history", []))
    entry = {
        "decision": decision, "decided_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decided_by": "owner (risk reviewer and portfolio reviewer)", "comment": comment.strip(),
        "max_utilization_before": summary.get("max_utilization_now"),
        "max_utilization_after_estimated": summary.get("max_utilization_after"),
        "changes": {r.instrument_id: {"from": r.quantity, "to": r.proposed_quantity}
                    for r in proposal.itertuples() if r.action == "REDUCE"},
        "automatic_execution_authorized": 0,
    }
    history.append(entry)
    quantities = dict(data.get("quantities", {}))
    if decision == "APPROVED":
        quantities.update({r.instrument_id: float(r.proposed_quantity) for r in proposal.itertuples()})
    data.update({"quantities": quantities, "history": history,
                 "note": "Demo multi-asset risk book (fictional). Sizes changed only by human approval."})
    APPROVED.write_text(json.dumps(data, indent=2))
    return entry


def render_pending_fix(where: str) -> None:
    proposal, summary = load_proposal(), load_summary()
    if recalculating(proposal):
        st.info("✅ Fix approved. The risk chain is re-running on GitHub with the new position sizes (about "
                "10 minutes); the status updates by itself when it finishes.")
        return
    if not pending(proposal, summary):
        return
    before, after = summary.get("max_utilization_now", 0), summary.get("max_utilization_after", 0)
    with st.container(border=True):
        st.markdown("#### ✅ Risk controls working — fix ready for approval")
        st.markdown(
            f"Vittantra's risk monitor caught {int(summary.get('positions_over_budget_now', 0))} position(s) in the "
            f"**demo risk book** (10 fictional positions) using more risk than their limit, and has already sized "
            f"the fix: reduce {int(summary.get('positions_reduced', 0))} position(s) so every position is comfortably "
            f"inside its limit (worst position: **{before:.0%} → {after:.0%}** of its limit). Only reductions — "
            f"total risk falls. A human signs off before anything changes.")
        shown = proposal[proposal["action"] == "REDUCE"].assign(
            change=lambda d: d["change"] * 100,
            current_utilization=lambda d: d["current_utilization"] * 100,
            proposed_utilization=lambda d: d["proposed_utilization"] * 100)
        st.dataframe(shown[["symbol", "quantity", "proposed_quantity", "change", "current_utilization",
                            "proposed_utilization", "reason"]].rename(columns={
            "symbol": "Position", "quantity": "Size now", "proposed_quantity": "Proposed size",
            "change": "Change %", "current_utilization": "% of limit now", "proposed_utilization": "% of limit after",
            "reason": "Why"}), hide_index=True, width="stretch",
            column_config={"Change %": st.column_config.NumberColumn(format="%.0f%%"),
                           "% of limit now": st.column_config.NumberColumn(format="%.0f%%"),
                           "% of limit after": st.column_config.NumberColumn(format="%.0f%%"),
                           "Proposed size": st.column_config.NumberColumn(format="%.4f")})
        if not cloud.is_owner():
            st.caption("Only the owner can approve or reject. Nothing changes until a human decides.")
            return
        risk_ok = st.checkbox("As risk reviewer: the fix lowers risk and brings every position within its limit",
                              key=f"fix-risk-{where}")
        pm_ok = st.checkbox("As portfolio reviewer: the new sizes are acceptable for the portfolio",
                            key=f"fix-pm-{where}")
        comment = st.text_input("Comment for the audit log", key=f"fix-comment-{where}",
                                placeholder="e.g. Approved: derivatives were far above their risk limits")
        approve, reject = st.columns(2)
        if approve.button("Approve fix", type="primary", key=f"fix-approve-{where}",
                          disabled=not (risk_ok and pm_ok and comment.strip())):
            record_decision("APPROVED", proposal, summary, comment)
            cloud.persist(APPROVED, "Risk fix approved by owner (demo book; nothing traded)")
            st.rerun()
        if reject.button("Reject", key=f"fix-reject-{where}", disabled=not comment.strip()):
            record_decision("REJECTED", proposal, summary, comment)
            cloud.persist(APPROVED, "Risk fix rejected by owner")
            st.rerun()
        st.caption("Dual approval: in this one-person demo you act as both reviewers. The decision is recorded "
                   "in approved_positions.json. The book is fictional — nothing is traded, automatic execution "
                   "stays 0.")


def sidebar_note() -> None:
    if recalculating():
        st.caption("✅ Fix approved · updating")
    elif pending():
        st.caption("✅ Issue caught · fix ready for approval (Command Center)")
