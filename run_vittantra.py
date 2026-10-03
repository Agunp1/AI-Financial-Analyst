"""
Day 75 — Vittantra One-Command Pipeline

Runs the whole risk-to-decision chain in order:

    Data hub (free live data)
      → Day 59 multi-asset risk      → Day 60 unified risk engine
      → Day 61 cross-asset stress    → Day 62 macro scenarios
      → Day 63 rebalancing           → Day 64 exposure risk
      → Day 65 exposure rebalancing  → Day 66 risk budgeting
      → Day 67 risk monitor          → Day 68 governance
      → Day 69 remediation           → Day 70 approval workflow
      → Day 73 AI Analyst
    plus research steps that do not block the chain: Day 76 fundamentals
    (SEC EDGAR), 76c multi-asset, 76d macro drivers, 77 ratings, 78 valuation
    and research reports

Usage
-----
python run_vittantra.py                # refresh data, then run the chain
python run_vittantra.py --skip-data    # run the chain on existing data
python run_vittantra.py --sample       # original illustrative sample data
python run_vittantra.py --loop 15      # repeat every 15 minutes
python run_vittantra.py --us-market    # also refresh all US-listed stocks (15-30 min)

If the data refresh fails (for example, no internet), the chain still
runs on the last successfully downloaded data.

No trades are submitted or executed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PIPELINE_LOG = BASE_DIR / "day75_pipeline_log.csv"

DATA_STEP = ("Data hub", "vittantra_data_hub.py")

# Research steps that do not feed the risk chain: a failure is reported
# but does not stop the pipeline.
RESEARCH_STEPS = [
    ("Day 76 fundamentals (SEC)", "fundamental_engine.py"),
    ("Day 76c multi-asset universe", "multi_asset_universe.py"),
    ("Day 76d macro drivers", "macro_drivers.py"),
    ("Day 78b world & markets brief", "world_brief.py"),
    ("Day 77 multi-factor rating", "multi_factor_rating.py"),
    ("Day 78 valuation", "valuation_engine.py"),
    ("Day 78 research reports", "research_report.py"),
    ("Day 79 model portfolio", "portfolio_construction.py"),
    ("Day 80 performance attribution", "performance_attribution.py"),
    ("Days 82-84 advisory", "advisory_engine.py"),
]

CHAIN_STEPS = [
    ("Day 59 multi-asset risk", "multi_asset_risk.py"),
    ("Day 60 unified risk engine", "unified_risk_engine.py"),
    ("Day 61 cross-asset stress", "cross_asset_stress.py"),
    ("Day 62 macro scenarios", "macro_scenario_engine.py"),
    ("Day 63 rebalancing", "portfolio_rebalancing_engine.py"),
    ("Day 64 exposure risk", "exposure_risk_engine.py"),
    ("Day 65 exposure-aware rebalancing", "exposure_aware_rebalancer.py"),
    ("Day 66 risk budgeting", "portfolio_risk_budgeting.py"),
    ("Day 67 risk monitor", "portfolio_risk_monitor.py"),
    ("Day 68 governance", "portfolio_risk_governance.py"),
    ("Day 69 remediation", "portfolio_risk_remediation.py"),
    ("Day 70 approval workflow", "portfolio_approval_workflow.py"),
    ("Day 73 AI Analyst", "vittantra_ai_analyst.py"),
]


def run_step(name: str, script: str, env: dict) -> dict:
    started = time.time()
    process = subprocess.run(
        [sys.executable, script],
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (process.stdout + process.stderr).strip().splitlines()
    return {
        "step": name,
        "script": script,
        "status": "OK" if process.returncode == 0 else "FAILED",
        "seconds": round(time.time() - started, 2),
        "last_output": output[-1][:300] if output else "",
        "error": "\n".join(output[-15:]) if process.returncode else "",
    }


def run_pipeline(skip_data: bool = False, sample: bool = False, us_market: bool = False) -> bool:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["VITTANTRA_DATA_MODE"] = "sample" if sample else "live"

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("=" * 78)
    print(f"VITTANTRA PIPELINE — {started_at}")
    print(f"Data mode requested: {'SAMPLE' if sample else 'LIVE (falls back to SAMPLE if no data)'}")
    print("=" * 78)

    results = []
    if not skip_data and not sample:
        result = run_step(*DATA_STEP, env)
        results.append(result)
        print(f"[{result['status']:>6}] {result['step']:<36} {result['seconds']:>6.1f}s")
        if result["status"] != "OK":
            print("         Data refresh failed; continuing with the last saved data.")
        steps = RESEARCH_STEPS + ([("Day 76b US market fundamentals", "us_fundamental_engine.py")]
                                  if us_market else [])
        for name, script in steps:
            result = run_step(name, script, env)
            results.append(result)
            print(f"[{result['status']:>6}] {result['step']:<36} {result['seconds']:>6.1f}s")
            if result["status"] != "OK":
                print("         " + result["error"].replace("\n", "\n         "))
                print("         Research step failed; the risk chain continues.")

    ok = True
    for name, script in CHAIN_STEPS:
        result = run_step(name, script, env)
        results.append(result)
        print(f"[{result['status']:>6}] {result['step']:<36} {result['seconds']:>6.1f}s")
        if result["status"] != "OK":
            ok = False
            print("\n" + result["error"])
            print(f"\nStopped at {name}. Later steps were not run.")
            break

    log = pd.DataFrame(results)
    log.insert(0, "run_started_utc", started_at)
    log.insert(1, "data_mode_requested", "SAMPLE" if sample else "LIVE")
    log.drop(columns=["error"]).to_csv(OUTPUT_PIPELINE_LOG, index=False)

    print("-" * 78)
    if ok:
        summary = pd.read_csv(BASE_DIR / "day67_portfolio_risk_dashboard.csv").iloc[0]
        approval = pd.read_csv(BASE_DIR / "day70_portfolio_approval_summary.csv").iloc[0]
        print(f"Portfolio status:             {summary['portfolio_status']}")
        print(f"Max risk-budget utilization:  {summary['maximum_risk_budget_utilization']:.1%}")
        print(f"Workflow:                     {approval['portfolio_workflow_status']}")
        print(f"Automatic execution:          {int(approval['automatic_execution_authorized_count'])}")
        print("\nPipeline complete. No trades were submitted or executed.")
    print("=" * 78)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Vittantra pipeline")
    parser.add_argument("--skip-data", action="store_true", help="do not refresh market data")
    parser.add_argument("--sample", action="store_true", help="use original illustrative sample data")
    parser.add_argument("--loop", type=float, metavar="MINUTES", help="repeat every N minutes")
    parser.add_argument("--us-market", action="store_true",
                        help="also refresh fundamentals for all US-listed stocks (slow)")
    args = parser.parse_args()

    if not args.loop:
        sys.exit(0 if run_pipeline(args.skip_data, args.sample, args.us_market) else 1)

    print(f"Running every {args.loop:g} minutes. Press Ctrl+C to stop.")
    try:
        while True:
            run_pipeline(args.skip_data, args.sample, args.us_market)
            time.sleep(max(args.loop, 1) * 60)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
