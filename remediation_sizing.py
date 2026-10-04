"""
Day 69b — Remediation sizing: turn the Day 69 'reduce risk' proposal into
concrete position sizes that bring every position within its risk budget.

Method: copy the project to a temporary folder, shrink only the positions
whose risk-budget utilization is above 100%, re-run the real risk chain
(Days 59–66) and repeat until every position is within budget. Positions that
are within budget are never increased, so modeled risk can only fall.

The result is a PROPOSAL (day69_proposed_positions.csv). Nothing changes until a
human approves it in the app (approved_positions.json); automatic execution
stays 0.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
CHAIN = ["multi_asset_risk.py", "unified_risk_engine.py", "cross_asset_stress.py", "macro_scenario_engine.py",
         "portfolio_rebalancing_engine.py", "exposure_risk_engine.py", "exposure_aware_rebalancer.py",
         "portfolio_risk_budgeting.py"]
BUDGETS = "day66_instrument_risk_budgets.csv"
APPROVED = "approved_positions.json"
OUTPUT = "day69_proposed_positions.csv"
OUTPUT_SUMMARY = "day69_sizing_summary.csv"
OUTPUT_VALIDATION = "day69b_validation_summary.csv"
TARGET = 0.75            # resize an over-limit position to 75% of its limit…
HEALTHY = 0.80           # …until every position is below 80% (the 'watch' level) of its limit
MAX_ROUNDS = 25


def current_book(base: Path = BASE_DIR) -> pd.DataFrame:
    """instrument_id, symbol and quantity of the demo book as it stands (approved sizes applied)."""
    sys.path.insert(0, str(base))
    import multi_asset_risk as mar
    instruments = mar.build_sample_instruments(use_live_data=False)
    return pd.DataFrame([{"instrument_id": i.instrument_id, "symbol": i.symbol, "quantity": float(i.quantity)}
                         for i in instruments])


def run_chain(folder: Path, quantities: Dict[str, float]) -> pd.DataFrame:
    """Re-run Days 59–66 in `folder` with the given quantities; return Day 66 utilization by symbol."""
    (folder / APPROVED).write_text(json.dumps({"quantities": quantities}))
    for script in CHAIN:
        done = subprocess.run([sys.executable, script], cwd=folder, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"{script} failed during sizing: {(done.stderr or done.stdout)[-300:]}")
    budgets = pd.read_csv(folder / BUDGETS)
    return budgets.set_index("symbol")[["risk_budget_utilization", "instrument_risk_budget",
                                        "modeled_risk_contribution"]]


def size_positions(base: Path = BASE_DIR) -> Tuple[pd.DataFrame, dict]:
    book = current_book(base)
    by_symbol = book.set_index("symbol")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for path in base.iterdir():
            if path.suffix in (".py", ".csv", ".json") and path.is_file():
                shutil.copy2(path, folder / path.name)
        quantities = dict(zip(book["instrument_id"], book["quantity"]))
        before = run_chain(folder, quantities)
        after, rounds, flagged = before, 0, set()
        while (after["risk_budget_utilization"] >= HEALTHY).any() and rounds < MAX_ROUNDS:
            rounds += 1
            for symbol, row in after.iterrows():
                if row["risk_budget_utilization"] >= HEALTHY and symbol in by_symbol.index:
                    iid = by_symbol.at[symbol, "instrument_id"]
                    quantities[iid] *= TARGET / row["risk_budget_utilization"]
                    flagged.add(symbol)
            after = run_chain(folder, quantities)
    proposal = book.copy()
    proposal["proposed_quantity"] = proposal["instrument_id"].map(quantities)
    proposal["change"] = proposal["proposed_quantity"] / proposal["quantity"] - 1
    proposal["current_utilization"] = proposal["symbol"].map(before["risk_budget_utilization"])
    proposal["proposed_utilization"] = proposal["symbol"].map(after["risk_budget_utilization"])
    proposal["risk_budget"] = proposal["symbol"].map(before["instrument_risk_budget"])
    proposal["action"] = proposal["change"].apply(lambda c: "REDUCE" if c < -1e-9 else "HOLD")
    proposal["reason"] = proposal["symbol"].map(
        lambda s: ("Over limit" if before.at[s, "risk_budget_utilization"] >= 1.0 else
                   "Above 80% of limit after other reductions") if s in flagged else "")
    summary = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "positions_over_budget_now": int((before["risk_budget_utilization"] > 1.0).sum()),
        "positions_over_budget_after": int((after["risk_budget_utilization"] > 1.0).sum()),
        "max_utilization_now": float(before["risk_budget_utilization"].max()),
        "max_utilization_after": float(after["risk_budget_utilization"].max()),
        "rounds": rounds, "positions_reduced": int((proposal["action"] == "REDUCE").sum()),
        "status": "PENDING_HUMAN_APPROVAL" if (proposal["action"] == "REDUCE").any() else "NO_ACTION_NEEDED",
        "automatic_execution_authorized_count": 0,
    }
    return proposal, summary


def validate(proposal: pd.DataFrame, summary: dict) -> pd.DataFrame:
    checks = [
        ("Every position below 80% of its limit after the fix", summary["max_utilization_after"] < HEALTHY,
         f"max utilization after: {summary['max_utilization_after']:.0%}"),
        ("No position is increased", bool((proposal["proposed_quantity"] <= proposal["quantity"] + 1e-9).all()),
         "only reductions; no position grows"),
        ("Only positions at or above 80% of their limit are reduced",
         bool((proposal.loc[proposal["action"] == "REDUCE", "reason"] != "").all()),
         f"{summary['positions_reduced']} reduced"),
        ("Nothing executed automatically", summary["automatic_execution_authorized_count"] == 0,
         "proposal waits for human approval"),
    ]
    out = pd.DataFrame(checks, columns=["check", "passed", "details"])
    out["passed_tests"], out["total_tests"] = int(out["passed"].sum()), len(out)
    return out


def main(base: Path = BASE_DIR, verbose: bool = True) -> Optional[pd.DataFrame]:
    proposal, summary = size_positions(base)
    validation = validate(proposal, summary)
    proposal.to_csv(base / OUTPUT, index=False)
    pd.DataFrame([summary]).to_csv(base / OUTPUT_SUMMARY, index=False)
    validation.to_csv(base / OUTPUT_VALIDATION, index=False)
    if verbose:
        print("VITTANTRA — DAY 69b REMEDIATION SIZING")
        print(proposal[["symbol", "quantity", "proposed_quantity", "current_utilization", "proposed_utilization",
                        "action"]].to_string(index=False))
        print(f"\nMax utilization now {summary['max_utilization_now']:.0%} → after fix "
              f"{summary['max_utilization_after']:.0%} ({summary['rounds']} rounds)")
        print(validation[["check", "passed", "details"]].to_string(index=False))
        print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
        print("Day 69b remediation sizing complete. Proposal pending human approval; nothing executed.")
    return validation


if __name__ == "__main__":
    main()
