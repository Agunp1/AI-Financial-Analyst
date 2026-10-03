"""
Vittantra
Day 68 — Portfolio Risk Governance & Action Engine

Purpose
-------
Convert Day 67 portfolio-risk monitoring outputs into deterministic,
auditable governance decisions.

Architecture
------------
Day 65 Exposure-Aware Targets
        ->
Day 66 Portfolio Risk Budgets
        ->
Day 67 Portfolio Risk Monitoring
        ->
Day 68 Governance & Action Engine

This module does NOT execute trades.

It produces research/governance recommendations such as:

    HOLD
    MONITOR
    REVIEW
    REDUCE_RISK
    ESCALATE
    FREEZE_NEW_RISK

The design deliberately separates:
    monitoring
    governance
    execution

so that risk alerts never become automatic trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DAY67_PORTFOLIO_DASHBOARD = Path(
    "day67_portfolio_risk_dashboard.csv"
)

DAY66_INSTRUMENT_BUDGETS = Path(
    "day66_instrument_risk_budgets.csv"
)

DAY68_GOVERNANCE_ACTIONS = Path(
    "day68_governance_actions.csv"
)

DAY68_PORTFOLIO_DECISION = Path(
    "day68_portfolio_governance_decision.csv"
)

DAY68_INSTRUMENT_ACTIONS = Path(
    "day68_instrument_governance_actions.csv"
)

DAY68_VALIDATION = Path(
    "day68_validation_summary.csv"
)


# ============================================================
# GOVERNANCE POLICY
# ============================================================

@dataclass(frozen=True)
class GovernancePolicy:
    """
    Deterministic governance thresholds.

    These are research assumptions rather than regulatory,
    broker, exchange, or legal limits.
    """

    watch_utilization: float = 0.80
    review_utilization: float = 1.00
    breach_utilization: float = 1.10
    critical_utilization: float = 1.20

    concentration_watch: float = 0.35
    concentration_review: float = 0.45
    concentration_critical: float = 0.60


POLICY = GovernancePolicy()


# ============================================================
# PRIORITY SYSTEM
# ============================================================

ACTION_PRIORITY = {
    "HOLD": 0,
    "MONITOR": 1,
    "REVIEW": 2,
    "REDUCE_RISK": 3,
    "ESCALATE": 4,
    "FREEZE_NEW_RISK": 5,
}


STATUS_PRIORITY = {
    "NORMAL": 0,
    "WATCH": 1,
    "REVIEW": 2,
    "BREACH": 3,
    "CRITICAL": 4,
}


# ============================================================
# HELPERS
# ============================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)

        if np.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        value = float(value)

        if np.isfinite(value):
            return int(value)

    except (TypeError, ValueError):
        pass

    return default


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def highest_action(actions: list[str]) -> str:
    if not actions:
        return "HOLD"

    return max(
        actions,
        key=lambda x: ACTION_PRIORITY.get(x, -1),
    )


def highest_status(statuses: list[str]) -> str:
    if not statuses:
        return "NORMAL"

    return max(
        statuses,
        key=lambda x: STATUS_PRIORITY.get(x, -1),
    )


def require_columns(
    df: pd.DataFrame,
    required: list[str],
    dataset_name: str,
) -> None:

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            f"{dataset_name} is missing required columns: "
            f"{missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


# ============================================================
# LOAD INPUTS
# ============================================================

def load_day67_dashboard() -> pd.DataFrame:

    if not DAY67_PORTFOLIO_DASHBOARD.exists():
        raise FileNotFoundError(
            f"Missing required input: "
            f"{DAY67_PORTFOLIO_DASHBOARD}"
        )

    df = pd.read_csv(DAY67_PORTFOLIO_DASHBOARD)

    required = [
        "portfolio_status",
        "instrument_count",
        "normal_count",
        "watch_count",
        "warning_count",
        "breach_count",
        "critical_count",
        "requires_review_count",
        "mean_risk_budget_utilization",
        "maximum_risk_budget_utilization",
        "risk_budgeted_capital_weight_total",
        "risk_budgeted_gross_exposure_weight_total",
        "risk_budgeted_signed_notional_weight_total",
        "risk_budgeted_absolute_notional_weight_total",
        "risk_budgeted_risk_weight_total",
        "risk_budgeted_absolute_risk_weight_total",
        "largest_asset_class_risk_share",
        "largest_asset_class_by_risk",
    ]

    require_columns(
        df,
        required,
        "Day 67 portfolio risk dashboard",
    )

    if df.empty:
        raise ValueError(
            "Day 67 portfolio risk dashboard is empty."
        )

    return df


def load_day66_instrument_budgets() -> pd.DataFrame:

    if not DAY66_INSTRUMENT_BUDGETS.exists():
        raise FileNotFoundError(
            f"Missing required input: "
            f"{DAY66_INSTRUMENT_BUDGETS}"
        )

    df = pd.read_csv(DAY66_INSTRUMENT_BUDGETS)

    required = [
        "symbol",
        "asset_class",
        "instrument_type",
        "risk_weight",
        "target_risk_weight",
        "risk_budget_utilization",
        "risk_budget_gap",
        "risk_budget_excess",
        "risk_budget_status",
        "risk_budget_scaler",
        "risk_budgeted_capital_weight",
        "risk_budgeted_gross_exposure_weight",
        "risk_budgeted_signed_notional_weight",
        "risk_budgeted_risk_weight",
        "risk_budget_action",
    ]

    require_columns(
        df,
        required,
        "Day 66 instrument risk budgets",
    )

    if df.empty:
        raise ValueError(
            "Day 66 instrument risk budget file is empty."
        )

    return df


# ============================================================
# PORTFOLIO GOVERNANCE RULES
# ============================================================

def portfolio_governance_decision(
    row: pd.Series,
) -> dict[str, Any]:

    portfolio_status = normalize_text(
        row["portfolio_status"]
    ).upper()

    instrument_count = safe_int(
        row["instrument_count"]
    )

    watch_count = safe_int(
        row["watch_count"]
    )

    warning_count = safe_int(
        row["warning_count"]
    )

    breach_count = safe_int(
        row["breach_count"]
    )

    critical_count = safe_int(
        row["critical_count"]
    )

    review_count = safe_int(
        row["requires_review_count"]
    )

    mean_util = safe_float(
        row["mean_risk_budget_utilization"]
    )

    max_util = safe_float(
        row["maximum_risk_budget_utilization"]
    )

    largest_class_share = safe_float(
        row["largest_asset_class_risk_share"]
    )

    largest_class = normalize_text(
        row["largest_asset_class_by_risk"]
    )

    actions: list[str] = []
    reasons: list[str] = []


    # --------------------------------------------------------
    # Existing portfolio status
    # --------------------------------------------------------

    if portfolio_status == "CRITICAL":

        actions.append("FREEZE_NEW_RISK")

        reasons.append(
            "Day 67 portfolio status is CRITICAL."
        )

    elif portfolio_status == "BREACH":

        actions.append("REDUCE_RISK")

        reasons.append(
            "Day 67 portfolio status indicates a breach."
        )

    elif portfolio_status in {
        "WARNING",
        "REVIEW",
    }:

        actions.append("REVIEW")

        reasons.append(
            f"Day 67 portfolio status is "
            f"{portfolio_status}."
        )

    elif portfolio_status == "WATCH":

        actions.append("MONITOR")

        reasons.append(
            "Day 67 portfolio status is WATCH."
        )


    # --------------------------------------------------------
    # Critical positions
    # --------------------------------------------------------

    if critical_count > 0:

        actions.append("FREEZE_NEW_RISK")

        reasons.append(
            f"{critical_count} instrument(s) are "
            f"in critical risk state."
        )


    # --------------------------------------------------------
    # Breaches
    # --------------------------------------------------------

    if breach_count > 0:

        actions.append("REDUCE_RISK")

        reasons.append(
            f"{breach_count} risk-budget breach(es) "
            f"are present."
        )


    # --------------------------------------------------------
    # Review requirement
    # --------------------------------------------------------

    if review_count > 0:

        actions.append("REVIEW")

        reasons.append(
            f"{review_count} position(s) require "
            f"risk review."
        )


    # --------------------------------------------------------
    # Maximum utilization
    # --------------------------------------------------------

    if max_util >= POLICY.critical_utilization:

        actions.append("FREEZE_NEW_RISK")

        reasons.append(
            "Maximum risk-budget utilization is "
            f"{max_util:.2%}, at or above the "
            f"{POLICY.critical_utilization:.0%} "
            f"critical threshold."
        )

    elif max_util >= POLICY.breach_utilization:

        actions.append("REDUCE_RISK")

        reasons.append(
            "Maximum risk-budget utilization is "
            f"{max_util:.2%}, above the "
            f"{POLICY.breach_utilization:.0%} "
            f"breach threshold."
        )

    elif max_util >= POLICY.review_utilization:

        actions.append("REVIEW")

        reasons.append(
            "Maximum risk-budget utilization is "
            f"{max_util:.2%}, at or above "
            f"100% of budget."
        )

    elif max_util >= POLICY.watch_utilization:

        actions.append("MONITOR")

        reasons.append(
            "Maximum risk-budget utilization is "
            f"{max_util:.2%}, inside the watch zone."
        )


    # --------------------------------------------------------
    # Mean utilization
    # --------------------------------------------------------

    if mean_util >= POLICY.review_utilization:

        actions.append("REVIEW")

        reasons.append(
            "Average portfolio risk-budget "
            f"utilization is {mean_util:.2%}."
        )

    elif mean_util >= POLICY.watch_utilization:

        actions.append("MONITOR")

        reasons.append(
            "Average portfolio risk-budget "
            f"utilization is elevated at "
            f"{mean_util:.2%}."
        )


    # --------------------------------------------------------
    # Risk concentration
    # --------------------------------------------------------

    if (
        largest_class_share
        >= POLICY.concentration_critical
    ):

        actions.append("ESCALATE")

        reasons.append(
            f"{largest_class} represents "
            f"{largest_class_share:.2%} of "
            f"portfolio risk, above the "
            f"{POLICY.concentration_critical:.0%} "
            f"critical concentration threshold."
        )

    elif (
        largest_class_share
        >= POLICY.concentration_review
    ):

        actions.append("REVIEW")

        reasons.append(
            f"{largest_class} represents "
            f"{largest_class_share:.2%} of "
            f"portfolio risk."
        )

    elif (
        largest_class_share
        >= POLICY.concentration_watch
    ):

        actions.append("MONITOR")

        reasons.append(
            f"{largest_class} risk concentration "
            f"is {largest_class_share:.2%}."
        )


    # --------------------------------------------------------
    # Warning/watch populations
    # --------------------------------------------------------

    if warning_count > 0:

        actions.append("MONITOR")

        reasons.append(
            f"{warning_count} warning state(s) "
            f"are active."
        )

    if watch_count > 0:

        actions.append("MONITOR")

        reasons.append(
            f"{watch_count} instrument(s) are "
            f"in watch status."
        )


    # --------------------------------------------------------
    # No triggered governance rule
    # --------------------------------------------------------

    if not actions:

        actions.append("HOLD")

        reasons.append(
            "No portfolio governance threshold "
            "is currently breached."
        )


    action = highest_action(actions)


    # --------------------------------------------------------
    # Governance status
    # --------------------------------------------------------

    if action == "FREEZE_NEW_RISK":
        governance_status = "CRITICAL"

    elif action in {
        "ESCALATE",
        "REDUCE_RISK",
    }:
        governance_status = "BREACH"

    elif action == "REVIEW":
        governance_status = "REVIEW"

    elif action == "MONITOR":
        governance_status = "WATCH"

    else:
        governance_status = "NORMAL"


    return {
        "portfolio_status":
            portfolio_status,

        "governance_status":
            governance_status,

        "governance_action":
            action,

        "governance_reason":
            " | ".join(reasons),

        "instrument_count":
            instrument_count,

        "watch_count":
            watch_count,

        "warning_count":
            warning_count,

        "breach_count":
            breach_count,

        "critical_count":
            critical_count,

        "requires_review_count":
            review_count,

        "mean_risk_budget_utilization":
            mean_util,

        "maximum_risk_budget_utilization":
            max_util,

        "largest_asset_class_by_risk":
            largest_class,

        "largest_asset_class_risk_share":
            largest_class_share,

        "freeze_new_risk":
            action == "FREEZE_NEW_RISK",

        "portfolio_review_required":
            action != "HOLD",
    }


# ============================================================
# INSTRUMENT GOVERNANCE
# ============================================================

def classify_instrument(
    row: pd.Series,
) -> dict[str, Any]:

    symbol = normalize_text(
        row["symbol"]
    )

    asset_class = normalize_text(
        row["asset_class"]
    )

    instrument_type = normalize_text(
        row["instrument_type"]
    )

    utilization = safe_float(
        row["risk_budget_utilization"]
    )

    risk_budget = safe_float(
        row["instrument_risk_budget"]
    )

    modeled_risk = safe_float(
        row["modeled_risk_contribution"]
    )

    budget_excess = safe_float(
        row["risk_budget_excess"]
    )

    existing_status = normalize_text(
        row["risk_budget_status"]
    ).upper()

    existing_action = normalize_text(
        row["risk_budget_action"]
    )

    actions: list[str] = []
    reasons: list[str] = []


    # --------------------------------------------------------
    # Utilization rules
    # --------------------------------------------------------

    if utilization >= POLICY.critical_utilization:

        status = "CRITICAL"
        actions.append("FREEZE_NEW_RISK")

        reasons.append(
            f"Risk-budget utilization "
            f"{utilization:.2%} >= "
            f"{POLICY.critical_utilization:.0%}."
        )

    elif utilization >= POLICY.breach_utilization:

        status = "BREACH"
        actions.append("REDUCE_RISK")

        reasons.append(
            f"Risk-budget utilization "
            f"{utilization:.2%} >= "
            f"{POLICY.breach_utilization:.0%}."
        )

    elif utilization >= POLICY.review_utilization:

        status = "REVIEW"
        actions.append("REVIEW")

        reasons.append(
            f"Risk-budget utilization "
            f"{utilization:.2%} >= 100%."
        )

    elif utilization >= POLICY.watch_utilization:

        status = "WATCH"
        actions.append("MONITOR")

        reasons.append(
            f"Risk-budget utilization "
            f"{utilization:.2%} is elevated."
        )

    else:

        status = "NORMAL"
        actions.append("HOLD")

        reasons.append(
            f"Risk-budget utilization "
            f"{utilization:.2%} is within policy."
        )


    # --------------------------------------------------------
    # Preserve more severe Day 66 state
    # --------------------------------------------------------

    normalized_existing_status = (
        existing_status
        if existing_status in STATUS_PRIORITY
        else "NORMAL"
    )

    status = highest_status(
        [
            status,
            normalized_existing_status,
        ]
    )


    # --------------------------------------------------------
    # Budget excess
    # --------------------------------------------------------

    if budget_excess > 0:

        actions.append("REDUCE_RISK")

        reasons.append(
            f"Modeled risk exceeds budget by "
            f"{budget_excess:.6f}."
        )


    # --------------------------------------------------------
    # Existing Day 66 recommendation
    # --------------------------------------------------------

    if existing_action:

        reasons.append(
            f"Day 66 action: {existing_action}."
        )


    governance_action = highest_action(actions)


    if status == "CRITICAL":
        governance_action = highest_action(
            [
                governance_action,
                "FREEZE_NEW_RISK",
            ]
        )

    elif status == "BREACH":
        governance_action = highest_action(
            [
                governance_action,
                "REDUCE_RISK",
            ]
        )

    elif status == "REVIEW":
        governance_action = highest_action(
            [
                governance_action,
                "REVIEW",
            ]
        )

    elif status == "WATCH":
        governance_action = highest_action(
            [
                governance_action,
                "MONITOR",
            ]
        )


    return {
        "symbol":
            symbol,

        "asset_class":
            asset_class,

        "instrument_type":
            instrument_type,

        "risk_budget":
            risk_budget,

        "modeled_risk_contribution":
            modeled_risk,

        "risk_budget_utilization":
            utilization,

        "risk_budget_excess":
            budget_excess,

        "day66_risk_budget_status":
            existing_status,

        "governance_status":
            status,

        "governance_action":
            governance_action,

        "governance_reason":
            " | ".join(reasons),

        "requires_review":
            governance_action != "HOLD",

        "block_incremental_risk":
            governance_action
            == "FREEZE_NEW_RISK",
    }


def build_instrument_governance(
    budgets: pd.DataFrame,
) -> pd.DataFrame:

    records = []

    for _, row in budgets.iterrows():

        records.append(
            classify_instrument(row)
        )

    result = pd.DataFrame(records)

    if not result.empty:

        result["_priority"] = (
            result["governance_action"]
            .map(ACTION_PRIORITY)
            .fillna(-1)
        )

        result = (
            result
            .sort_values(
                [
                    "_priority",
                    "risk_budget_utilization",
                ],
                ascending=[
                    False,
                    False,
                ],
            )
            .drop(columns="_priority")
            .reset_index(drop=True)
        )

    return result


# ============================================================
# ACTION REGISTER
# ============================================================

def build_action_register(
    portfolio_decision: pd.DataFrame,
    instrument_actions: pd.DataFrame,
) -> pd.DataFrame:

    records: list[dict[str, Any]] = []


    # --------------------------------------------------------
    # Portfolio action
    # --------------------------------------------------------

    p = portfolio_decision.iloc[0]

    records.append(
        {
            "scope": "PORTFOLIO",
            "identifier": "TOTAL_PORTFOLIO",
            "governance_status":
                p["governance_status"],
            "governance_action":
                p["governance_action"],
            "requires_review":
                p["portfolio_review_required"],
            "block_incremental_risk":
                p["freeze_new_risk"],
            "reason":
                p["governance_reason"],
        }
    )


    # --------------------------------------------------------
    # Instrument actions
    # --------------------------------------------------------

    for _, row in instrument_actions.iterrows():

        if row["governance_action"] == "HOLD":
            continue

        records.append(
            {
                "scope": "INSTRUMENT",
                "identifier": row["symbol"],
                "governance_status":
                    row["governance_status"],
                "governance_action":
                    row["governance_action"],
                "requires_review":
                    row["requires_review"],
                "block_incremental_risk":
                    row["block_incremental_risk"],
                "reason":
                    row["governance_reason"],
            }
        )


    actions = pd.DataFrame(records)

    if not actions.empty:

        actions["_priority"] = (
            actions["governance_action"]
            .map(ACTION_PRIORITY)
            .fillna(-1)
        )

        actions = (
            actions
            .sort_values(
                "_priority",
                ascending=False,
            )
            .drop(columns="_priority")
            .reset_index(drop=True)
        )

    return actions


# ============================================================
# VALIDATION
# ============================================================

def validation_row(
    check: str,
    passed: bool,
    detail: str,
) -> dict[str, Any]:

    return {
        "check": check,
        "passed": bool(passed),
        "detail": detail,
    }


def validate_outputs(
    portfolio_decision: pd.DataFrame,
    instrument_actions: pd.DataFrame,
    action_register: pd.DataFrame,
    source_budgets: pd.DataFrame,
) -> pd.DataFrame:

    rows: list[dict[str, Any]] = []


    # --------------------------------------------------------
    # Portfolio decision generated
    # --------------------------------------------------------

    rows.append(
        validation_row(
            "Portfolio governance decision generated",
            len(portfolio_decision) == 1,
            f"Rows: {len(portfolio_decision)}",
        )
    )


    # --------------------------------------------------------
    # Instrument coverage
    # --------------------------------------------------------

    coverage_ok = (
        len(instrument_actions)
        == len(source_budgets)
    )

    rows.append(
        validation_row(
            "Every Day 66 instrument received governance classification",
            coverage_ok,
            (
                f"Source instruments: "
                f"{len(source_budgets)}; "
                f"governance instruments: "
                f"{len(instrument_actions)}"
            ),
        )
    )


    # --------------------------------------------------------
    # Unique symbols
    # --------------------------------------------------------

    unique_ok = (
        instrument_actions["symbol"]
        .nunique(dropna=False)
        == len(instrument_actions)
    )

    rows.append(
        validation_row(
            "Instrument identifiers remain unique",
            unique_ok,
            (
                f"Unique symbols: "
                f"{instrument_actions['symbol'].nunique(dropna=False)}"
            ),
        )
    )


    # --------------------------------------------------------
    # Finite utilization
    # --------------------------------------------------------

    utilization = pd.to_numeric(
        instrument_actions[
            "risk_budget_utilization"
        ],
        errors="coerce",
    )

    finite_ok = bool(
        np.isfinite(utilization).all()
    )

    rows.append(
        validation_row(
            "Risk-budget utilization values are finite",
            finite_ok,
            (
                f"Rows checked: "
                f"{len(utilization)}"
            ),
        )
    )


    # --------------------------------------------------------
    # Valid actions
    # --------------------------------------------------------

    valid_actions = set(
        ACTION_PRIORITY.keys()
    )

    actual_actions = set(
        instrument_actions[
            "governance_action"
        ].dropna()
    )

    action_ok = (
        actual_actions
        .issubset(valid_actions)
    )

    rows.append(
        validation_row(
            "Instrument governance actions use approved vocabulary",
            action_ok,
            (
                "Actions observed: "
                + ", ".join(
                    sorted(actual_actions)
                )
            ),
        )
    )


    # --------------------------------------------------------
    # Critical rule test
    # --------------------------------------------------------

    critical_test = pd.Series(
        {
            "symbol": "TEST_CRITICAL",
            "asset_class": "Test",
            "instrument_type": "Test",
            "risk_weight": 0.0,
            "target_risk_weight": 0.0,
            "risk_budget_utilization":
                POLICY.critical_utilization,
            "risk_budget_gap": 0.0,
            "risk_budget_excess": 0.01,
            "risk_budget_status": "CRITICAL",
            "risk_budget_scaler": 1.0,
            "risk_budgeted_capital_weight": 0.0,
            "risk_budgeted_gross_exposure_weight": 0.0,
            "risk_budgeted_signed_notional_weight": 0.0,
            "risk_budgeted_risk_weight": 0.0,
            "risk_budget_action": "TEST",
            "instrument_risk_budget": 0.05,
            "modeled_risk_contribution": 0.06,
        }
    )

    critical_result = classify_instrument(
        critical_test
    )

    critical_ok = (
        critical_result[
            "governance_action"
        ]
        == "FREEZE_NEW_RISK"
    )

    rows.append(
        validation_row(
            "Critical utilization freezes incremental risk",
            critical_ok,
            (
                f"Critical threshold: "
                f"{POLICY.critical_utilization:.0%}"
            ),
        )
    )


    # --------------------------------------------------------
    # Review rule test
    # --------------------------------------------------------

    review_test = critical_test.copy()

    review_test[
        "risk_budget_utilization"
    ] = POLICY.review_utilization

    review_test[
        "risk_budget_excess"
    ] = 0.0

    review_test[
        "risk_budget_status"
    ] = "REVIEW"

    review_result = classify_instrument(
        review_test
    )

    review_ok = (
        ACTION_PRIORITY[
            review_result["governance_action"]
        ]
        >= ACTION_PRIORITY["REVIEW"]
    )

    rows.append(
        validation_row(
            "Full risk-budget utilization requires review",
            review_ok,
            "100% utilization tested.",
        )
    )


    # --------------------------------------------------------
    # HOLD rule test
    # --------------------------------------------------------

    hold_test = critical_test.copy()

    hold_test[
        "risk_budget_utilization"
    ] = 0.50

    hold_test[
        "risk_budget_excess"
    ] = 0.0

    hold_test[
        "risk_budget_status"
    ] = "NORMAL"

    hold_test[
        "risk_budget_action"
    ] = "UNCHANGED"

    hold_result = classify_instrument(
        hold_test
    )

    hold_ok = (
        hold_result[
            "governance_action"
        ]
        == "HOLD"
    )

    rows.append(
        validation_row(
            "Comfortable utilization permits HOLD",
            hold_ok,
            "50% utilization tested.",
        )
    )


    # --------------------------------------------------------
    # Action register exists
    # --------------------------------------------------------

    rows.append(
        validation_row(
            "Governance action register generated",
            len(action_register) >= 1,
            f"Rows: {len(action_register)}",
        )
    )


    # --------------------------------------------------------
    # No automatic execution instruction
    # --------------------------------------------------------

    execution_columns = {
        "execute_trade",
        "submit_order",
        "send_order",
        "broker_order_id",
    }

    generated_columns = (
        set(portfolio_decision.columns)
        | set(instrument_actions.columns)
        | set(action_register.columns)
    )

    execution_safe = (
        len(
            execution_columns
            & generated_columns
        )
        == 0
    )

    rows.append(
        validation_row(
            "Governance layer remains separate from trade execution",
            execution_safe,
            (
                "No automatic execution fields "
                "are generated."
            ),
        )
    )


    validation = pd.DataFrame(rows)

    validation["passed_tests"] = int(
        validation["passed"].sum()
    )

    validation["total_tests"] = len(
        validation
    )

    validation["pass_rate"] = (
        validation["passed_tests"]
        / validation["total_tests"]
    )

    return validation


# ============================================================
# REPORTING
# ============================================================

def print_report(
    portfolio_decision: pd.DataFrame,
    instrument_actions: pd.DataFrame,
    action_register: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:

    p = portfolio_decision.iloc[0]

    print()
    print("=" * 78)
    print(
        "VITTANTRA — DAY 68 "
        "PORTFOLIO RISK GOVERNANCE"
    )
    print("=" * 78)

    print()
    print("PORTFOLIO GOVERNANCE")
    print("-" * 78)

    print(
        f"Day 67 status       : "
        f"{p['portfolio_status']}"
    )

    print(
        f"Governance status   : "
        f"{p['governance_status']}"
    )

    print(
        f"Governance action   : "
        f"{p['governance_action']}"
    )

    print(
        f"Mean utilization    : "
        f"{p['mean_risk_budget_utilization']:.2%}"
    )

    print(
        f"Maximum utilization : "
        f"{p['maximum_risk_budget_utilization']:.2%}"
    )

    print(
        f"Largest risk class  : "
        f"{p['largest_asset_class_by_risk']}"
    )

    print(
        f"Largest risk share  : "
        f"{p['largest_asset_class_risk_share']:.2%}"
    )

    print(
        f"Freeze new risk     : "
        f"{p['freeze_new_risk']}"
    )

    print()
    print("Reason:")
    print(
        p["governance_reason"]
    )


    print()
    print("INSTRUMENT GOVERNANCE SUMMARY")
    print("-" * 78)

    summary = (
        instrument_actions[
            "governance_action"
        ]
        .value_counts()
        .rename_axis(
            "governance_action"
        )
        .reset_index(
            name="instrument_count"
        )
    )

    print(
        summary.to_string(index=False)
    )


    print()
    print("HIGHEST-PRIORITY ACTIONS")
    print("-" * 78)

    if action_register.empty:

        print(
            "No governance actions generated."
        )

    else:

        display_columns = [
            "scope",
            "identifier",
            "governance_status",
            "governance_action",
        ]

        print(
            action_register[
                display_columns
            ]
            .head(15)
            .to_string(index=False)
        )


    print()
    print("VALIDATION")
    print("-" * 78)

    display_validation = validation[
        [
            "check",
            "passed",
            "detail",
        ]
    ]

    print(
        display_validation.to_string(
            index=False
        )
    )

    pass_rate = safe_float(
        validation["pass_rate"].iloc[0]
    )

    print()
    print(
        f"Validation pass rate: "
        f"{pass_rate:.2%}"
    )

    print()
    print("Generated files:")

    for path in [
        DAY68_GOVERNANCE_ACTIONS,
        DAY68_PORTFOLIO_DECISION,
        DAY68_INSTRUMENT_ACTIONS,
        DAY68_VALIDATION,
    ]:
        print(f"  {path}")

    print()
    print(
        "Architecture:"
    )

    print(
        "Day 65 Exposure-Aware Targets "
        "-> Day 66 Risk Budgets "
        "-> Day 67 Risk Monitoring "
        "-> Day 68 Governance "
        "-> Human Review / Future Execution Layer"
    )

    print()
    print(
        "Important: Day 68 governance decisions "
        "are research controls and recommendations. "
        "They are not automatic trade instructions, "
        "regulatory determinations, or broker/exchange "
        "risk limits."
    )

    print()
    print(
        "Day 68 portfolio risk governance complete."
    )

    print("=" * 78)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        # ----------------------------------------------------
        # Load Day 67
        # ----------------------------------------------------

        dashboard = load_day67_dashboard()

        # Day 67 dashboard is portfolio-level.
        # Current architecture expects one portfolio row.
        portfolio_row = dashboard.iloc[0]


        # ----------------------------------------------------
        # Load Day 66
        # ----------------------------------------------------

        budgets = load_day66_instrument_budgets()


        # ----------------------------------------------------
        # Additional exact Day 66 schema validation
        # ----------------------------------------------------

        additional_required = [
            "instrument_risk_budget",
            "modeled_risk_contribution",
        ]

        require_columns(
            budgets,
            additional_required,
            "Day 66 instrument risk budgets",
        )


        # ----------------------------------------------------
        # Portfolio governance
        # ----------------------------------------------------

        portfolio_result = (
            portfolio_governance_decision(
                portfolio_row
            )
        )

        portfolio_decision = pd.DataFrame(
            [portfolio_result]
        )


        # ----------------------------------------------------
        # Instrument governance
        # ----------------------------------------------------

        instrument_actions = (
            build_instrument_governance(
                budgets
            )
        )


        # ----------------------------------------------------
        # Action register
        # ----------------------------------------------------

        action_register = (
            build_action_register(
                portfolio_decision,
                instrument_actions,
            )
        )


        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        validation = validate_outputs(
            portfolio_decision,
            instrument_actions,
            action_register,
            budgets,
        )


        # ----------------------------------------------------
        # Save outputs
        # ----------------------------------------------------

        portfolio_decision.to_csv(
            DAY68_PORTFOLIO_DECISION,
            index=False,
        )

        instrument_actions.to_csv(
            DAY68_INSTRUMENT_ACTIONS,
            index=False,
        )

        action_register.to_csv(
            DAY68_GOVERNANCE_ACTIONS,
            index=False,
        )

        validation.to_csv(
            DAY68_VALIDATION,
            index=False,
        )


        # ----------------------------------------------------
        # Report
        # ----------------------------------------------------

        print_report(
            portfolio_decision,
            instrument_actions,
            action_register,
            validation,
        )


    except Exception as exc:

        print()
        print("=" * 78)

        print(
            "DAY 68 PORTFOLIO RISK GOVERNANCE "
            "FAILED"
        )

        print("=" * 78)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()

        print(
            "No Day 68 conclusions should be drawn "
            "from an incomplete run."
        )

        print("=" * 78)

        raise


if __name__ == "__main__":
    main()