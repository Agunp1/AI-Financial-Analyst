"""
Vittantra
Day 70 — Portfolio Decision & Approval Workflow

Purpose
-------
Turn Day 69 remediation recommendations into a controlled,
auditable approval workflow.

Pipeline
--------
Day 65 Exposure-Aware Targets
    ->
Day 66 Portfolio Risk Budgets
    ->
Day 67 Risk Monitoring
    ->
Day 68 Governance
    ->
Day 69 Remediation
    ->
Day 70 Approval Workflow
    ->
Future Paper-Execution / Order-Control Layer

This module DOES NOT execute trades.

It creates:
- decision tickets
- approval requirements
- proposed action states
- human-review queues
- approval / rejection / hold states
- audit records
- portfolio-level workflow summary
- validation controls

Default behavior
----------------
No remediation action is automatically approved.

Any action requiring risk reduction or blocking incremental risk
enters a human-review state.

This is intentional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

import numpy as np
import pandas as pd


# =============================================================================
# FILES
# =============================================================================

DAY69_REMEDIATION_FILE = Path(
    "day69_instrument_remediation_actions.csv"
)

DAY69_PRIORITY_FILE = Path(
    "day69_remediation_priority.csv"
)

DAY69_SUMMARY_FILE = Path(
    "day69_portfolio_remediation_summary.csv"
)


OUTPUT_DECISION_TICKETS = Path(
    "day70_decision_tickets.csv"
)

OUTPUT_APPROVAL_QUEUE = Path(
    "day70_approval_queue.csv"
)

OUTPUT_AUDIT_LOG = Path(
    "day70_approval_audit_log.csv"
)

OUTPUT_PORTFOLIO_SUMMARY = Path(
    "day70_portfolio_approval_summary.csv"
)

OUTPUT_VALIDATION = Path(
    "day70_validation_summary.csv"
)


# =============================================================================
# CONFIGURATION
# =============================================================================

ALLOWED_DECISIONS = {
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    "HELD",
    "NO_ACTION_REQUIRED",
}

ALLOWED_WORKFLOW_STATUS = {
    "OPEN",
    "AWAITING_RISK_REVIEW",
    "AWAITING_PORTFOLIO_REVIEW",
    "AWAITING_DUAL_APPROVAL",
    "APPROVED",
    "REJECTED",
    "HELD",
    "CLOSED_NO_ACTION",
}

ALLOWED_REMEDIATION_ACTIONS = {
    "HOLD",
    "MONITOR",
    "REVIEW_AND_MONITOR",
    "FREEZE_INCREMENTAL_RISK",
    "REDUCE_RISK",
    "REDUCE_AND_FREEZE",
}

ALLOWED_PRIORITY_BUCKETS = {
    "P1_IMMEDIATE",
    "P2_HIGH",
    "P3_REVIEW",
    "P4_MONITOR",
}


# =============================================================================
# POLICY
# =============================================================================

@dataclass(frozen=True)
class ApprovalPolicy:
    """
    Research approval policy.

    These are workflow assumptions, not regulatory requirements.
    """

    dual_approval_for_critical: bool = True
    risk_review_for_high: bool = True
    portfolio_review_for_reduction: bool = True
    require_review_for_blocked_risk: bool = True

    auto_close_hold_positions: bool = True
    auto_close_monitor_only: bool = False


POLICY = ApprovalPolicy()


# =============================================================================
# HELPERS
# =============================================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        number = float(value)

        if np.isfinite(number):
            return number

    except (TypeError, ValueError):
        pass

    return default


def safe_bool(value: Any) -> bool:

    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    return (
        str(value)
        .strip()
        .lower()
        in {
            "true",
            "1",
            "yes",
            "y",
            "t",
        }
    )


def clean_text(value: Any) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip()


def uppercase_text(value: Any) -> str:
    return clean_text(value).upper()


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
            f"Available columns: "
            f"{df.columns.tolist()}"
        )


def current_utc_timestamp() -> str:

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def deterministic_ticket_id(
    symbol: str,
    remediation_action: str,
    priority_bucket: str,
) -> str:

    raw = (
        f"{symbol}|"
        f"{remediation_action}|"
        f"{priority_bucket}"
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:12].upper()

    return f"VIT-{digest}"


# =============================================================================
# LOAD DAY 69
# =============================================================================

def load_day69_remediation() -> pd.DataFrame:

    if not DAY69_REMEDIATION_FILE.exists():

        raise FileNotFoundError(
            f"Required input not found: "
            f"{DAY69_REMEDIATION_FILE}"
        )

    df = pd.read_csv(
        DAY69_REMEDIATION_FILE
    )

    required = [
        "symbol",
        "asset_class",
        "instrument_type",
        "risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_excess",
        "day66_risk_budget_status",
        "day68_governance_status",
        "day68_governance_action",
        "day68_requires_review",
        "day68_block_incremental_risk",
        "remediation_severity",
        "remediation_action",
        "target_modeled_risk_contribution",
        "required_modeled_risk_reduction",
        "proposed_risk_reduction_fraction",
        "estimated_post_remediation_utilization",
        "priority_score",
        "priority_bucket",
        "human_review_required",
        "proposed_block_incremental_risk",
        "remediation_reason",
    ]

    require_columns(
        df,
        required,
        "Day 69 remediation output",
    )

    if df.empty:

        raise ValueError(
            "Day 69 remediation output is empty."
        )

    return df


def load_optional_csv(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)

    except pd.errors.EmptyDataError:
        return pd.DataFrame()


# =============================================================================
# APPROVAL REQUIREMENTS
# =============================================================================

def determine_required_reviewers(
    row: pd.Series,
) -> list[str]:

    severity = uppercase_text(
        row["remediation_severity"]
    )

    action = uppercase_text(
        row["remediation_action"]
    )

    human_review = safe_bool(
        row["human_review_required"]
    )

    block_risk = safe_bool(
        row["proposed_block_incremental_risk"]
    )

    reviewers: list[str] = []

    if (
        severity == "CRITICAL"
        and POLICY.dual_approval_for_critical
    ):
        reviewers.extend(
            [
                "RISK_REVIEW",
                "PORTFOLIO_REVIEW",
            ]
        )

    elif (
        severity == "HIGH"
        and POLICY.risk_review_for_high
    ):
        reviewers.append(
            "RISK_REVIEW"
        )

    if (
        action in {
            "REDUCE_RISK",
            "REDUCE_AND_FREEZE",
        }
        and POLICY.portfolio_review_for_reduction
    ):
        reviewers.append(
            "PORTFOLIO_REVIEW"
        )

    if (
        block_risk
        and POLICY.require_review_for_blocked_risk
    ):
        reviewers.append(
            "RISK_REVIEW"
        )

    if (
        human_review
        and not reviewers
    ):
        reviewers.append(
            "RISK_REVIEW"
        )

    # Preserve order while removing duplicates
    reviewers = list(
        dict.fromkeys(reviewers)
    )

    return reviewers


def determine_workflow_status(
    reviewers: list[str],
    remediation_action: str,
) -> str:

    action = uppercase_text(
        remediation_action
    )

    if not reviewers:

        if (
            action == "HOLD"
            and POLICY.auto_close_hold_positions
        ):
            return "CLOSED_NO_ACTION"

        if (
            action == "MONITOR"
            and POLICY.auto_close_monitor_only
        ):
            return "CLOSED_NO_ACTION"

        return "OPEN"

    reviewer_set = set(reviewers)

    if reviewer_set == {
        "RISK_REVIEW",
        "PORTFOLIO_REVIEW",
    }:
        return "AWAITING_DUAL_APPROVAL"

    if "RISK_REVIEW" in reviewer_set:
        return "AWAITING_RISK_REVIEW"

    if "PORTFOLIO_REVIEW" in reviewer_set:
        return "AWAITING_PORTFOLIO_REVIEW"

    return "OPEN"


def determine_initial_decision(
    workflow_status: str,
) -> str:

    if workflow_status == "CLOSED_NO_ACTION":
        return "NO_ACTION_REQUIRED"

    return "PENDING_REVIEW"


# =============================================================================
# BUILD DECISION TICKETS
# =============================================================================

def build_decision_tickets(
    remediation: pd.DataFrame,
) -> pd.DataFrame:

    records: list[dict[str, Any]] = []

    timestamp = current_utc_timestamp()

    for _, row in remediation.iterrows():

        symbol = clean_text(
            row["symbol"]
        )

        severity = uppercase_text(
            row["remediation_severity"]
        )

        remediation_action = uppercase_text(
            row["remediation_action"]
        )

        priority_bucket = uppercase_text(
            row["priority_bucket"]
        )

        reviewers = determine_required_reviewers(
            row
        )

        workflow_status = determine_workflow_status(
            reviewers,
            remediation_action,
        )

        decision = determine_initial_decision(
            workflow_status
        )

        ticket_id = deterministic_ticket_id(
            symbol,
            remediation_action,
            priority_bucket,
        )

        requires_risk_review = (
            "RISK_REVIEW"
            in reviewers
        )

        requires_portfolio_review = (
            "PORTFOLIO_REVIEW"
            in reviewers
        )

        dual_approval_required = (
            requires_risk_review
            and requires_portfolio_review
        )

        proposed_reduction = safe_float(
            row[
                "proposed_risk_reduction_fraction"
            ]
        )

        target_utilization = safe_float(
            row[
                "estimated_post_remediation_utilization"
            ]
        )

        records.append(
            {
                "ticket_id":
                    ticket_id,

                "created_at_utc":
                    timestamp,

                "symbol":
                    symbol,

                "asset_class":
                    row["asset_class"],

                "instrument_type":
                    row["instrument_type"],

                "remediation_severity":
                    severity,

                "remediation_action":
                    remediation_action,

                "priority_score":
                    safe_float(
                        row["priority_score"]
                    ),

                "priority_bucket":
                    priority_bucket,

                "current_risk_budget_utilization":
                    safe_float(
                        row[
                            "risk_budget_utilization"
                        ]
                    ),

                "risk_budget":
                    safe_float(
                        row["risk_budget"]
                    ),

                "modeled_risk_contribution":
                    safe_float(
                        row[
                            "modeled_risk_contribution"
                        ]
                    ),

                "target_modeled_risk_contribution":
                    safe_float(
                        row[
                            "target_modeled_risk_contribution"
                        ]
                    ),

                "required_modeled_risk_reduction":
                    safe_float(
                        row[
                            "required_modeled_risk_reduction"
                        ]
                    ),

                "proposed_risk_reduction_fraction":
                    proposed_reduction,

                "estimated_post_remediation_utilization":
                    target_utilization,

                "proposed_block_incremental_risk":
                    safe_bool(
                        row[
                            "proposed_block_incremental_risk"
                        ]
                    ),

                "requires_risk_review":
                    requires_risk_review,

                "requires_portfolio_review":
                    requires_portfolio_review,

                "dual_approval_required":
                    dual_approval_required,

                "required_reviewers":
                    "|".join(reviewers),

                "workflow_status":
                    workflow_status,

                "decision":
                    decision,

                "risk_reviewer_decision":
                    "",

                "portfolio_reviewer_decision":
                    "",

                "final_approver":
                    "",

                "decision_timestamp_utc":
                    "",

                "decision_comment":
                    "",

                "remediation_reason":
                    row["remediation_reason"],

                "execution_authorized":
                    False,
            }
        )

    tickets = pd.DataFrame(
        records
    )

    priority_order = {
        "P1_IMMEDIATE": 1,
        "P2_HIGH": 2,
        "P3_REVIEW": 3,
        "P4_MONITOR": 4,
    }

    tickets["_priority_order"] = (
        tickets["priority_bucket"]
        .map(priority_order)
        .fillna(99)
    )

    tickets = (
        tickets
        .sort_values(
            [
                "_priority_order",
                "priority_score",
                "current_risk_budget_utilization",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )
        .drop(
            columns="_priority_order"
        )
        .reset_index(drop=True)
    )

    return tickets


# =============================================================================
# APPROVAL QUEUE
# =============================================================================

def build_approval_queue(
    tickets: pd.DataFrame,
) -> pd.DataFrame:

    queue = tickets[
        tickets["decision"]
        == "PENDING_REVIEW"
    ].copy()

    columns = [
        "ticket_id",
        "created_at_utc",
        "priority_bucket",
        "priority_score",
        "symbol",
        "asset_class",
        "instrument_type",
        "remediation_severity",
        "remediation_action",
        "current_risk_budget_utilization",
        "proposed_risk_reduction_fraction",
        "estimated_post_remediation_utilization",
        "proposed_block_incremental_risk",
        "requires_risk_review",
        "requires_portfolio_review",
        "dual_approval_required",
        "required_reviewers",
        "workflow_status",
        "decision",
        "remediation_reason",
    ]

    return (
        queue[columns]
        .reset_index(drop=True)
    )


# =============================================================================
# AUDIT LOG
# =============================================================================

def build_initial_audit_log(
    tickets: pd.DataFrame,
) -> pd.DataFrame:

    records: list[dict[str, Any]] = []

    for _, row in tickets.iterrows():

        payload = {
            "symbol":
                row["symbol"],

            "action":
                row["remediation_action"],

            "severity":
                row["remediation_severity"],

            "priority":
                row["priority_bucket"],

            "workflow_status":
                row["workflow_status"],

            "decision":
                row["decision"],
        }

        payload_json = json.dumps(
            payload,
            sort_keys=True,
        )

        audit_hash = hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()

        records.append(
            {
                "ticket_id":
                    row["ticket_id"],

                "event_timestamp_utc":
                    row["created_at_utc"],

                "event_type":
                    "TICKET_CREATED",

                "actor":
                    "VITTANTRA_SYSTEM",

                "previous_status":
                    "",

                "new_status":
                    row["workflow_status"],

                "decision":
                    row["decision"],

                "symbol":
                    row["symbol"],

                "remediation_action":
                    row["remediation_action"],

                "event_details":
                    (
                        "Day 70 decision ticket "
                        "created from Day 69 "
                        "remediation recommendation."
                    ),

                "audit_hash":
                    audit_hash,
            }
        )

    return pd.DataFrame(
        records
    )


# =============================================================================
# PORTFOLIO APPROVAL SUMMARY
# =============================================================================

def build_portfolio_summary(
    tickets: pd.DataFrame,
    approval_queue: pd.DataFrame,
) -> pd.DataFrame:

    total = len(tickets)

    pending = int(
        (
            tickets["decision"]
            == "PENDING_REVIEW"
        ).sum()
    )

    no_action = int(
        (
            tickets["decision"]
            == "NO_ACTION_REQUIRED"
        ).sum()
    )

    dual_approval = int(
        tickets[
            "dual_approval_required"
        ].sum()
    )

    risk_review = int(
        tickets[
            "requires_risk_review"
        ].sum()
    )

    portfolio_review = int(
        tickets[
            "requires_portfolio_review"
        ].sum()
    )

    blocked = int(
        tickets[
            "proposed_block_incremental_risk"
        ].sum()
    )

    immediate = int(
        (
            tickets["priority_bucket"]
            == "P1_IMMEDIATE"
        ).sum()
    )

    risk_reduction = int(
        (
            tickets[
                "proposed_risk_reduction_fraction"
            ]
            > 0
        ).sum()
    )

    max_utilization = safe_float(
        tickets[
            "current_risk_budget_utilization"
        ].max()
    )

    maximum_post_utilization = safe_float(
        tickets[
            "estimated_post_remediation_utilization"
        ]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .max()
    )

    if dual_approval > 0:
        portfolio_workflow_status = (
            "AWAITING_DUAL_APPROVAL"
        )

    elif pending > 0:
        portfolio_workflow_status = (
            "AWAITING_REVIEW"
        )

    else:
        portfolio_workflow_status = (
            "NO_ACTION_REQUIRED"
        )

    return pd.DataFrame(
        [
            {
                "portfolio_workflow_status":
                    portfolio_workflow_status,

                "decision_ticket_count":
                    total,

                "pending_review_count":
                    pending,

                "no_action_required_count":
                    no_action,

                "risk_review_required_count":
                    risk_review,

                "portfolio_review_required_count":
                    portfolio_review,

                "dual_approval_required_count":
                    dual_approval,

                "incremental_risk_block_count":
                    blocked,

                "risk_reduction_ticket_count":
                    risk_reduction,

                "immediate_priority_count":
                    immediate,

                "approval_queue_count":
                    len(approval_queue),

                "maximum_current_risk_budget_utilization":
                    max_utilization,

                "maximum_estimated_post_remediation_utilization":
                    maximum_post_utilization,

                "automatic_execution_authorized_count":
                    int(
                        tickets[
                            "execution_authorized"
                        ].sum()
                    ),
            }
        ]
    )


# =============================================================================
# VALIDATION
# =============================================================================

def validation_record(
    check: str,
    passed: bool,
    details: str,
) -> dict[str, Any]:

    return {
        "check":
            check,

        "passed":
            bool(passed),

        "details":
            details,
    }


def validate_workflow(
    remediation: pd.DataFrame,
    tickets: pd.DataFrame,
    queue: pd.DataFrame,
    audit: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:

    tests: list[
        dict[str, Any]
    ] = []


    # -----------------------------------------------------------------
    # Ticket coverage
    # -----------------------------------------------------------------

    tests.append(
        validation_record(
            "Every Day 69 instrument receives a Day 70 ticket",
            len(remediation) == len(tickets),
            (
                f"Day 69 rows: "
                f"{len(remediation)}; "
                f"Day 70 tickets: "
                f"{len(tickets)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Ticket uniqueness
    # -----------------------------------------------------------------

    unique_ticket_ids = (
        tickets["ticket_id"].nunique()
        == len(tickets)
    )

    tests.append(
        validation_record(
            "Decision ticket identifiers are unique",
            unique_ticket_ids,
            (
                f"Unique tickets: "
                f"{tickets['ticket_id'].nunique()}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Symbol coverage
    # -----------------------------------------------------------------

    symbol_coverage = (
        set(
            remediation["symbol"].astype(str)
        )
        ==
        set(
            tickets["symbol"].astype(str)
        )
    )

    tests.append(
        validation_record(
            "Instrument coverage reconciles with Day 69",
            symbol_coverage,
            (
                f"Instruments: "
                f"{tickets['symbol'].nunique()}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Valid decisions
    # -----------------------------------------------------------------

    decision_valid = (
        tickets["decision"]
        .isin(
            ALLOWED_DECISIONS
        )
        .all()
    )

    tests.append(
        validation_record(
            "Decision states use approved vocabulary",
            decision_valid,
            (
                "Observed: "
                + ", ".join(
                    sorted(
                        tickets[
                            "decision"
                        ].unique()
                    )
                )
            ),
        )
    )


    # -----------------------------------------------------------------
    # Workflow statuses
    # -----------------------------------------------------------------

    workflow_valid = (
        tickets["workflow_status"]
        .isin(
            ALLOWED_WORKFLOW_STATUS
        )
        .all()
    )

    tests.append(
        validation_record(
            "Workflow states use approved vocabulary",
            workflow_valid,
            (
                "Observed: "
                + ", ".join(
                    sorted(
                        tickets[
                            "workflow_status"
                        ].unique()
                    )
                )
            ),
        )
    )


    # -----------------------------------------------------------------
    # Remediation actions preserved
    # -----------------------------------------------------------------

    actions_valid = (
        tickets[
            "remediation_action"
        ]
        .isin(
            ALLOWED_REMEDIATION_ACTIONS
        )
        .all()
    )

    tests.append(
        validation_record(
            "Remediation actions remain within approved vocabulary",
            actions_valid,
            (
                "Observed: "
                + ", ".join(
                    sorted(
                        tickets[
                            "remediation_action"
                        ].unique()
                    )
                )
            ),
        )
    )


    # -----------------------------------------------------------------
    # Priority states
    # -----------------------------------------------------------------

    priority_valid = (
        tickets[
            "priority_bucket"
        ]
        .isin(
            ALLOWED_PRIORITY_BUCKETS
        )
        .all()
    )

    tests.append(
        validation_record(
            "Priority buckets remain valid",
            priority_valid,
            (
                "Observed: "
                + ", ".join(
                    sorted(
                        tickets[
                            "priority_bucket"
                        ].unique()
                    )
                )
            ),
        )
    )


    # -----------------------------------------------------------------
    # Human review gate
    # -----------------------------------------------------------------

    risk_actions = tickets[
        tickets[
            "remediation_action"
        ].isin(
            [
                "REDUCE_RISK",
                "REDUCE_AND_FREEZE",
                "FREEZE_INCREMENTAL_RISK",
            ]
        )
    ]

    risk_actions_pending = (
        risk_actions.empty
        or (
            risk_actions["decision"]
            == "PENDING_REVIEW"
        ).all()
    )

    tests.append(
        validation_record(
            "Risk-changing actions require review",
            risk_actions_pending,
            (
                f"Risk-changing tickets: "
                f"{len(risk_actions)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Critical requires dual approval
    # -----------------------------------------------------------------

    critical = tickets[
        tickets[
            "remediation_severity"
        ] == "CRITICAL"
    ]

    critical_dual_ok = (
        critical.empty
        or critical[
            "dual_approval_required"
        ].all()
    )

    tests.append(
        validation_record(
            "Critical remediation requires dual approval",
            critical_dual_ok,
            (
                f"Critical tickets: "
                f"{len(critical)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Execution remains disabled
    # -----------------------------------------------------------------

    execution_disabled = (
        tickets[
            "execution_authorized"
        ].eq(False)
        .all()
    )

    tests.append(
        validation_record(
            "Automatic execution remains disabled",
            execution_disabled,
            (
                "No Day 70 ticket authorizes "
                "automatic execution."
            ),
        )
    )


    # -----------------------------------------------------------------
    # Queue reconciliation
    # -----------------------------------------------------------------

    expected_queue = int(
        (
            tickets["decision"]
            == "PENDING_REVIEW"
        ).sum()
    )

    queue_reconciles = (
        len(queue)
        == expected_queue
    )

    tests.append(
        validation_record(
            "Approval queue reconciles with pending decisions",
            queue_reconciles,
            (
                f"Pending tickets: "
                f"{expected_queue}; "
                f"queue rows: "
                f"{len(queue)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Audit reconciliation
    # -----------------------------------------------------------------

    audit_reconciles = (
        len(audit)
        == len(tickets)
    )

    tests.append(
        validation_record(
            "Every decision ticket receives an audit event",
            audit_reconciles,
            (
                f"Tickets: "
                f"{len(tickets)}; "
                f"audit events: "
                f"{len(audit)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Audit hashes
    # -----------------------------------------------------------------

    valid_hashes = (
        audit["audit_hash"]
        .astype(str)
        .str.len()
        .eq(64)
        .all()
    )

    tests.append(
        validation_record(
            "Audit hashes are generated",
            valid_hashes,
            (
                f"Audit events checked: "
                f"{len(audit)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # Portfolio summary
    # -----------------------------------------------------------------

    summary_ok = (
        len(summary) == 1
        and int(
            summary.iloc[0][
                "decision_ticket_count"
            ]
        )
        == len(tickets)
    )

    tests.append(
        validation_record(
            "Portfolio approval summary generated",
            summary_ok,
            (
                f"Summary rows: "
                f"{len(summary)}"
            ),
        )
    )


    # -----------------------------------------------------------------
    # No automatic execution
    # -----------------------------------------------------------------

    execution_count = int(
        summary.iloc[0][
            "automatic_execution_authorized_count"
        ]
    )

    tests.append(
        validation_record(
            "Portfolio automatic-execution count remains zero",
            execution_count == 0,
            (
                f"Authorized execution tickets: "
                f"{execution_count}"
            ),
        )
    )


    validation = pd.DataFrame(
        tests
    )

    passed_tests = int(
        validation["passed"].sum()
    )

    total_tests = len(
        validation
    )

    validation["passed_tests"] = (
        passed_tests
    )

    validation["total_tests"] = (
        total_tests
    )

    validation["pass_rate"] = (
        passed_tests
        / total_tests
        if total_tests
        else 0.0
    )

    return validation


# =============================================================================
# REPORTING
# =============================================================================

def print_report(
    tickets: pd.DataFrame,
    queue: pd.DataFrame,
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:

    print()
    print("=" * 78)
    print(
        "VITTANTRA — DAY 70 "
        "PORTFOLIO DECISION & APPROVAL WORKFLOW"
    )
    print("=" * 78)


    print()
    print("WORKFLOW ARCHITECTURE")
    print("-" * 78)

    print(
        "Day 69 Remediation "
        "-> Decision Ticket "
        "-> Risk Review "
        "-> Portfolio Review "
        "-> Approval / Rejection / Hold "
        "-> Audit Trail "
        "-> Future Execution Layer"
    )


    print()
    print("PORTFOLIO APPROVAL SUMMARY")
    print("-" * 78)

    print(
        summary.to_string(
            index=False
        )
    )


    print()
    print("APPROVAL QUEUE")
    print("-" * 78)

    if queue.empty:

        print(
            "No approval tickets are pending."
        )

    else:

        columns = [
            "priority_bucket",
            "ticket_id",
            "symbol",
            "remediation_severity",
            "remediation_action",
            "current_risk_budget_utilization",
            "required_reviewers",
            "workflow_status",
        ]

        print(
            queue[
                columns
            ].to_string(
                index=False
            )
        )


    print()
    print("DECISION STATE COUNTS")
    print("-" * 78)

    decision_counts = (
        tickets[
            "decision"
        ]
        .value_counts()
        .rename_axis(
            "decision"
        )
        .reset_index(
            name="count"
        )
    )

    print(
        decision_counts.to_string(
            index=False
        )
    )


    print()
    print("WORKFLOW STATE COUNTS")
    print("-" * 78)

    workflow_counts = (
        tickets[
            "workflow_status"
        ]
        .value_counts()
        .rename_axis(
            "workflow_status"
        )
        .reset_index(
            name="count"
        )
    )

    print(
        workflow_counts.to_string(
            index=False
        )
    )


    print()
    print("AUDIT TRAIL")
    print("-" * 78)

    audit_display = [
        "ticket_id",
        "event_type",
        "actor",
        "new_status",
        "decision",
        "symbol",
    ]

    print(
        audit[
            audit_display
        ].to_string(
            index=False
        )
    )


    print()
    print("VALIDATION")
    print("-" * 78)

    print(
        validation[
            [
                "check",
                "passed",
                "details",
            ]
        ].to_string(
            index=False
        )
    )

    passed = int(
        validation[
            "passed_tests"
        ].iloc[0]
    )

    total = int(
        validation[
            "total_tests"
        ].iloc[0]
    )

    rate = safe_float(
        validation[
            "pass_rate"
        ].iloc[0]
    )

    print()

    print(
        f"Validation: "
        f"{passed}/{total} "
        f"passed "
        f"({rate:.2%})"
    )


    print()
    print("FILES GENERATED")
    print("-" * 78)

    for path in [
        OUTPUT_DECISION_TICKETS,
        OUTPUT_APPROVAL_QUEUE,
        OUTPUT_AUDIT_LOG,
        OUTPUT_PORTFOLIO_SUMMARY,
        OUTPUT_VALIDATION,
    ]:
        print(path)


    print()
    print(
        "Important: Day 70 creates decision and "
        "approval workflow records only. "
        "It does not submit, route, or execute trades."
    )

    print()
    print(
        "Day 70 portfolio approval workflow complete."
    )

    print("=" * 78)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    try:

        print()
        print("=" * 78)
        print(
            "VITTANTRA — DAY 70"
        )
        print(
            "Portfolio Decision & Approval Workflow"
        )
        print("=" * 78)


        remediation = (
            load_day69_remediation()
        )


        # Optional Day 69 artifacts
        _priority = load_optional_csv(
            DAY69_PRIORITY_FILE
        )

        _summary = load_optional_csv(
            DAY69_SUMMARY_FILE
        )


        tickets = build_decision_tickets(
            remediation
        )


        approval_queue = (
            build_approval_queue(
                tickets
            )
        )


        audit_log = (
            build_initial_audit_log(
                tickets
            )
        )


        portfolio_summary = (
            build_portfolio_summary(
                tickets,
                approval_queue,
            )
        )


        validation = (
            validate_workflow(
                remediation,
                tickets,
                approval_queue,
                audit_log,
                portfolio_summary,
            )
        )


        tickets.to_csv(
            OUTPUT_DECISION_TICKETS,
            index=False,
        )

        approval_queue.to_csv(
            OUTPUT_APPROVAL_QUEUE,
            index=False,
        )

        audit_log.to_csv(
            OUTPUT_AUDIT_LOG,
            index=False,
        )

        portfolio_summary.to_csv(
            OUTPUT_PORTFOLIO_SUMMARY,
            index=False,
        )

        validation.to_csv(
            OUTPUT_VALIDATION,
            index=False,
        )


        print_report(
            tickets,
            approval_queue,
            audit_log,
            portfolio_summary,
            validation,
        )


    except Exception as exc:

        print()
        print("=" * 78)
        print(
            "DAY 70 PORTFOLIO APPROVAL "
            "WORKFLOW FAILED"
        )
        print("=" * 78)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print()

        print(
            "No Day 70 conclusions should "
            "be drawn from an incomplete run."
        )

        print("=" * 78)

        raise


if __name__ == "__main__":
    main()