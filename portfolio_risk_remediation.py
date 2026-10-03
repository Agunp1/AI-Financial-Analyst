"""
Vittantra
Day 69 — Portfolio Risk Remediation Engine

Purpose
-------
Convert Day 68 portfolio-risk governance decisions into transparent,
human-reviewable remediation proposals.

This module DOES NOT:
    - place trades
    - generate broker orders
    - override human review
    - represent regulatory capital requirements

Pipeline
--------
Day 65 Exposure-Aware Targets
    ->
Day 66 Portfolio Risk Budgets
    ->
Day 67 Portfolio Risk Monitoring
    ->
Day 68 Portfolio Risk Governance
    ->
Day 69 Portfolio Risk Remediation
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

INPUT_FILE = Path("day68_instrument_governance_actions.csv")

OUTPUT_ACTIONS = Path("day69_instrument_remediation_actions.csv")
OUTPUT_PRIORITY = Path("day69_remediation_priority.csv")
OUTPUT_SUMMARY = Path("day69_portfolio_remediation_summary.csv")
OUTPUT_VALIDATION = Path("day69_validation_summary.csv")


REQUIRED_COLUMNS = [
    "symbol",
    "asset_class",
    "instrument_type",
    "risk_budget",
    "modeled_risk_contribution",
    "risk_budget_utilization",
    "risk_budget_excess",
    "day66_risk_budget_status",
    "governance_status",
    "governance_action",
    "governance_reason",
    "requires_review",
    "block_incremental_risk",
]


# Utilization levels used for remediation severity.
WATCH_THRESHOLD = 0.80
BREACH_THRESHOLD = 1.00
CRITICAL_THRESHOLD = 1.20


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize_bool(value) -> bool:
    """Convert common boolean representations to Python bool."""

    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
        "t",
    }


def clean_text(value) -> str:
    """Return a safe normalized uppercase text value."""

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def safe_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float."""

    try:
        number = float(value)

        if np.isfinite(number):
            return number

    except (TypeError, ValueError):
        pass

    return default


def validate_input_columns(df: pd.DataFrame) -> None:
    """Ensure Day 68 schema is present."""

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            "Day 69 could not locate required Day 68 columns.\n"
            f"Missing columns: {missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


# ---------------------------------------------------------------------
# Remediation logic
# ---------------------------------------------------------------------

def determine_severity(row: pd.Series) -> str:
    """
    Determine remediation severity from Day 68 governance state
    and risk-budget utilization.
    """

    governance_status = clean_text(row["governance_status"])
    governance_action = clean_text(row["governance_action"])

    utilization = safe_float(row["risk_budget_utilization"])

    requires_review = normalize_bool(row["requires_review"])
    block_incremental = normalize_bool(row["block_incremental_risk"])

    if (
        governance_status == "CRITICAL"
        or utilization >= CRITICAL_THRESHOLD
    ):
        return "CRITICAL"

    if (
        governance_status in {"BREACH", "HIGH"}
        or governance_action in {
            "REDUCE_RISK",
            "DE_RISK",
            "FREEZE_NEW_RISK",
        }
        or utilization >= BREACH_THRESHOLD
    ):
        return "HIGH"

    if (
        governance_status in {"WATCH", "WARNING"}
        or requires_review
        or block_incremental
        or utilization >= WATCH_THRESHOLD
    ):
        return "MEDIUM"

    return "LOW"


def determine_remediation_action(
    row: pd.Series,
    severity: str,
) -> str:
    """
    Translate governance state into a remediation recommendation.

    These are research recommendations only.
    """

    governance_action = clean_text(row["governance_action"])
    utilization = safe_float(row["risk_budget_utilization"])
    block_incremental = normalize_bool(row["block_incremental_risk"])

    if severity == "CRITICAL":
        return "REDUCE_AND_FREEZE"

    if severity == "HIGH":
        if block_incremental:
            return "REDUCE_AND_FREEZE"

        return "REDUCE_RISK"

    if severity == "MEDIUM":
        if block_incremental:
            return "FREEZE_INCREMENTAL_RISK"

        return "REVIEW_AND_MONITOR"

    if governance_action == "HOLD":
        return "HOLD"

    if utilization < WATCH_THRESHOLD:
        return "HOLD"

    return "MONITOR"


def calculate_target_risk_contribution(
    row: pd.Series,
    severity: str,
) -> float:
    """
    Calculate a research target for modeled risk contribution.

    Critical/high-risk positions are targeted back toward their
    risk budget. Medium-risk positions retain current risk unless
    they are already above budget.
    """

    budget = max(
        safe_float(row["risk_budget"]),
        0.0,
    )

    contribution = max(
        safe_float(row["modeled_risk_contribution"]),
        0.0,
    )

    if severity in {"CRITICAL", "HIGH"}:
        return min(contribution, budget)

    if severity == "MEDIUM":
        if contribution > budget:
            return budget

        return contribution

    return contribution


def calculate_required_risk_reduction(
    current_risk: float,
    target_risk: float,
) -> float:
    """Calculate absolute modeled-risk reduction required."""

    return max(
        current_risk - target_risk,
        0.0,
    )


def calculate_reduction_fraction(
    current_risk: float,
    required_reduction: float,
) -> float:
    """Calculate fraction of current modeled risk proposed for reduction."""

    if current_risk <= 0:
        return 0.0

    fraction = required_reduction / current_risk

    return float(
        np.clip(
            fraction,
            0.0,
            1.0,
        )
    )


def calculate_post_remediation_utilization(
    target_risk: float,
    risk_budget: float,
) -> float:
    """Calculate estimated utilization after proposed remediation."""

    if risk_budget <= 0:
        if target_risk <= 0:
            return 0.0

        return np.inf

    return target_risk / risk_budget


def determine_priority_score(
    row: pd.Series,
    severity: str,
    reduction_fraction: float,
) -> float:
    """
    Construct an interpretable remediation-priority score.

    This score is for workflow ordering only.
    It is NOT a trading signal.
    """

    severity_points = {
        "LOW": 0.0,
        "MEDIUM": 25.0,
        "HIGH": 60.0,
        "CRITICAL": 85.0,
    }

    score = severity_points.get(
        severity,
        0.0,
    )

    utilization = max(
        safe_float(row["risk_budget_utilization"]),
        0.0,
    )

    excess = max(
        safe_float(row["risk_budget_excess"]),
        0.0,
    )

    if utilization > 1.0:
        score += min(
            (utilization - 1.0) * 20.0,
            10.0,
        )

    if excess > 0:
        score += 2.0

    if normalize_bool(row["requires_review"]):
        score += 1.5

    if normalize_bool(row["block_incremental_risk"]):
        score += 1.5

    score += min(
        reduction_fraction * 10.0,
        10.0,
    )

    return float(
        np.clip(
            score,
            0.0,
            100.0,
        )
    )


def determine_priority_bucket(score: float) -> str:
    """Convert numerical priority score into workflow priority."""

    if score >= 80:
        return "P1_IMMEDIATE"

    if score >= 55:
        return "P2_HIGH"

    if score >= 25:
        return "P3_REVIEW"

    return "P4_MONITOR"


def build_remediation_reason(
    row: pd.Series,
    severity: str,
    action: str,
    reduction_fraction: float,
) -> str:
    """Generate transparent remediation explanation."""

    symbol = str(row["symbol"])

    utilization = safe_float(
        row["risk_budget_utilization"]
    )

    governance_reason = str(
        row["governance_reason"]
    ).strip()

    pieces = [
        f"{symbol} classified as {severity}.",
        (
            "Risk-budget utilization "
            f"is {utilization:.2%}."
        ),
        f"Proposed remediation: {action}.",
    ]

    if reduction_fraction > 0:
        pieces.append(
            "Estimated modeled-risk reduction "
            f"is {reduction_fraction:.2%}."
        )

    if governance_reason:
        pieces.append(
            f"Day 68 governance context: {governance_reason}"
        )

    return " | ".join(pieces)


# ---------------------------------------------------------------------
# Build instrument remediation table
# ---------------------------------------------------------------------

def build_instrument_remediation(
    source: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for _, row in source.iterrows():

        severity = determine_severity(row)

        remediation_action = determine_remediation_action(
            row,
            severity,
        )

        current_risk = max(
            safe_float(row["modeled_risk_contribution"]),
            0.0,
        )

        risk_budget = max(
            safe_float(row["risk_budget"]),
            0.0,
        )

        target_risk = calculate_target_risk_contribution(
            row,
            severity,
        )

        required_reduction = (
            calculate_required_risk_reduction(
                current_risk,
                target_risk,
            )
        )

        reduction_fraction = (
            calculate_reduction_fraction(
                current_risk,
                required_reduction,
            )
        )

        post_utilization = (
            calculate_post_remediation_utilization(
                target_risk,
                risk_budget,
            )
        )

        priority_score = determine_priority_score(
            row,
            severity,
            reduction_fraction,
        )

        priority_bucket = determine_priority_bucket(
            priority_score
        )

        human_review_required = (
            severity in {"HIGH", "CRITICAL"}
            or normalize_bool(row["requires_review"])
        )

        proposed_block_incremental_risk = (
            normalize_bool(row["block_incremental_risk"])
            or severity in {"HIGH", "CRITICAL"}
        )

        reason = build_remediation_reason(
            row,
            severity,
            remediation_action,
            reduction_fraction,
        )

        rows.append(
            {
                "symbol": row["symbol"],
                "asset_class": row["asset_class"],
                "instrument_type": row["instrument_type"],

                "risk_budget": risk_budget,
                "modeled_risk_contribution": current_risk,
                "risk_budget_utilization": safe_float(
                    row["risk_budget_utilization"]
                ),
                "risk_budget_excess": safe_float(
                    row["risk_budget_excess"]
                ),

                "day66_risk_budget_status":
                    row["day66_risk_budget_status"],

                "day68_governance_status":
                    row["governance_status"],

                "day68_governance_action":
                    row["governance_action"],

                "day68_requires_review":
                    normalize_bool(row["requires_review"]),

                "day68_block_incremental_risk":
                    normalize_bool(
                        row["block_incremental_risk"]
                    ),

                "remediation_severity":
                    severity,

                "remediation_action":
                    remediation_action,

                "target_modeled_risk_contribution":
                    target_risk,

                "required_modeled_risk_reduction":
                    required_reduction,

                "proposed_risk_reduction_fraction":
                    reduction_fraction,

                "estimated_post_remediation_utilization":
                    post_utilization,

                "priority_score":
                    priority_score,

                "priority_bucket":
                    priority_bucket,

                "human_review_required":
                    human_review_required,

                "proposed_block_incremental_risk":
                    proposed_block_incremental_risk,

                "remediation_reason":
                    reason,
            }
        )

    result = pd.DataFrame(rows)

    priority_order = {
        "P1_IMMEDIATE": 1,
        "P2_HIGH": 2,
        "P3_REVIEW": 3,
        "P4_MONITOR": 4,
    }

    result["_priority_order"] = (
        result["priority_bucket"]
        .map(priority_order)
        .fillna(99)
    )

    result = (
        result
        .sort_values(
            [
                "_priority_order",
                "priority_score",
                "risk_budget_utilization",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )
        .drop(columns="_priority_order")
        .reset_index(drop=True)
    )

    return result


# ---------------------------------------------------------------------
# Priority queue
# ---------------------------------------------------------------------

def build_priority_queue(
    remediation: pd.DataFrame,
) -> pd.DataFrame:

    queue = remediation[
        (
            remediation["human_review_required"]
        )
        |
        (
            remediation[
                "proposed_risk_reduction_fraction"
            ] > 0
        )
        |
        (
            remediation[
                "proposed_block_incremental_risk"
            ]
        )
    ].copy()

    columns = [
        "priority_bucket",
        "priority_score",
        "symbol",
        "asset_class",
        "instrument_type",
        "remediation_severity",
        "remediation_action",
        "risk_budget_utilization",
        "risk_budget_excess",
        "required_modeled_risk_reduction",
        "proposed_risk_reduction_fraction",
        "human_review_required",
        "proposed_block_incremental_risk",
        "remediation_reason",
    ]

    return queue[columns].reset_index(drop=True)


# ---------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------

def build_portfolio_summary(
    remediation: pd.DataFrame,
) -> pd.DataFrame:

    total_current_risk = (
        remediation[
            "modeled_risk_contribution"
        ].sum()
    )

    total_target_risk = (
        remediation[
            "target_modeled_risk_contribution"
        ].sum()
    )

    total_reduction = (
        remediation[
            "required_modeled_risk_reduction"
        ].sum()
    )

    if total_current_risk > 0:
        portfolio_reduction_fraction = (
            total_reduction
            / total_current_risk
        )
    else:
        portfolio_reduction_fraction = 0.0

    critical_count = int(
        (
            remediation[
                "remediation_severity"
            ] == "CRITICAL"
        ).sum()
    )

    high_count = int(
        (
            remediation[
                "remediation_severity"
            ] == "HIGH"
        ).sum()
    )

    medium_count = int(
        (
            remediation[
                "remediation_severity"
            ] == "MEDIUM"
        ).sum()
    )

    low_count = int(
        (
            remediation[
                "remediation_severity"
            ] == "LOW"
        ).sum()
    )

    review_count = int(
        remediation[
            "human_review_required"
        ].sum()
    )

    blocked_count = int(
        remediation[
            "proposed_block_incremental_risk"
        ].sum()
    )

    reduction_count = int(
        (
            remediation[
                "required_modeled_risk_reduction"
            ] > 0
        ).sum()
    )

    immediate_count = int(
        (
            remediation[
                "priority_bucket"
            ] == "P1_IMMEDIATE"
        ).sum()
    )

    if critical_count > 0:
        portfolio_status = "CRITICAL"

    elif high_count > 0:
        portfolio_status = "HIGH"

    elif medium_count > 0:
        portfolio_status = "REVIEW"

    else:
        portfolio_status = "NORMAL"

    summary = pd.DataFrame(
        [
            {
                "portfolio_remediation_status":
                    portfolio_status,

                "instrument_count":
                    len(remediation),

                "critical_count":
                    critical_count,

                "high_count":
                    high_count,

                "medium_count":
                    medium_count,

                "low_count":
                    low_count,

                "requires_review_count":
                    review_count,

                "incremental_risk_block_count":
                    blocked_count,

                "risk_reduction_action_count":
                    reduction_count,

                "immediate_priority_count":
                    immediate_count,

                "current_total_modeled_risk":
                    total_current_risk,

                "target_total_modeled_risk":
                    total_target_risk,

                "required_total_modeled_risk_reduction":
                    total_reduction,

                "portfolio_modeled_risk_reduction_fraction":
                    portfolio_reduction_fraction,

                "maximum_current_risk_budget_utilization":
                    remediation[
                        "risk_budget_utilization"
                    ].max(),

                "maximum_estimated_post_remediation_utilization":
                    remediation[
                        "estimated_post_remediation_utilization"
                    ].replace(
                        [np.inf, -np.inf],
                        np.nan,
                    ).max(),
            }
        ]
    )

    return summary


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------

def validation_row(
    test_name: str,
    passed: bool,
    details: str,
    rows_checked: int,
) -> dict:

    return {
        "validation_test": test_name,
        "passed": bool(passed),
        "details": details,
        "rows_checked": int(rows_checked),
    }


def build_validation_summary(
    source: pd.DataFrame,
    remediation: pd.DataFrame,
    priority: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:

    tests = []

    n = len(remediation)

    # 1
    tests.append(
        validation_row(
            "All Day 68 instruments preserved",
            len(source) == len(remediation),
            (
                f"Day 68 rows: {len(source)}; "
                f"Day 69 rows: {len(remediation)}"
            ),
            n,
        )
    )

    # 2
    unique_symbols = (
        remediation["symbol"].nunique()
        == len(remediation)
    )

    tests.append(
        validation_row(
            "Instrument identifiers remain unique",
            unique_symbols,
            (
                f"Unique symbols: "
                f"{remediation['symbol'].nunique()}"
            ),
            n,
        )
    )

    # 3
    finite_fields = [
        "risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_excess",
        "target_modeled_risk_contribution",
        "required_modeled_risk_reduction",
        "proposed_risk_reduction_fraction",
        "priority_score",
    ]

    finite_ok = True

    for column in finite_fields:
        values = pd.to_numeric(
            remediation[column],
            errors="coerce",
        )

        if not np.isfinite(values).all():
            finite_ok = False
            break

    tests.append(
        validation_row(
            "Core remediation metrics are finite",
            finite_ok,
            "Core numerical remediation fields checked.",
            n,
        )
    )

    # 4
    fraction_ok = (
        remediation[
            "proposed_risk_reduction_fraction"
        ]
        .between(
            0.0,
            1.0,
            inclusive="both",
        )
        .all()
    )

    tests.append(
        validation_row(
            "Risk reduction fractions are bounded",
            fraction_ok,
            "Expected range: 0% to 100%.",
            n,
        )
    )

    # 5
    critical = remediation[
        remediation[
            "remediation_severity"
        ] == "CRITICAL"
    ]

    critical_review_ok = (
        critical.empty
        or critical[
            "human_review_required"
        ].all()
    )

    tests.append(
        validation_row(
            "Critical instruments require human review",
            critical_review_ok,
            (
                f"Critical instruments: "
                f"{len(critical)}"
            ),
            len(critical),
        )
    )

    # 6
    critical_block_ok = (
        critical.empty
        or critical[
            "proposed_block_incremental_risk"
        ].all()
    )

    tests.append(
        validation_row(
            "Critical instruments block incremental risk",
            critical_block_ok,
            (
                f"Critical instruments: "
                f"{len(critical)}"
            ),
            len(critical),
        )
    )

    # 7
    reductions = remediation[
        remediation[
            "required_modeled_risk_reduction"
        ] > 0
    ]

    reduction_direction_ok = (
        reductions.empty
        or (
            reductions[
                "target_modeled_risk_contribution"
            ]
            <=
            reductions[
                "modeled_risk_contribution"
            ]
        ).all()
    )

    tests.append(
        validation_row(
            "Remediation never increases modeled risk",
            reduction_direction_ok,
            (
                f"Reduction candidates: "
                f"{len(reductions)}"
            ),
            len(reductions),
        )
    )

    # 8
    high_critical = remediation[
        remediation[
            "remediation_severity"
        ].isin(
            ["HIGH", "CRITICAL"]
        )
    ]

    budget_target_ok = (
        high_critical.empty
        or (
            high_critical[
                "target_modeled_risk_contribution"
            ]
            <=
            high_critical["risk_budget"]
            + 1e-12
        ).all()
    )

    tests.append(
        validation_row(
            "High and critical targets do not exceed risk budget",
            budget_target_ok,
            (
                f"High/Critical instruments: "
                f"{len(high_critical)}"
            ),
            len(high_critical),
        )
    )

    # 9
    priority_valid = (
        priority["priority_bucket"]
        .isin(
            [
                "P1_IMMEDIATE",
                "P2_HIGH",
                "P3_REVIEW",
                "P4_MONITOR",
            ]
        )
        .all()
        if not priority.empty
        else True
    )

    tests.append(
        validation_row(
            "Priority queue contains valid workflow states",
            priority_valid,
            f"Priority rows: {len(priority)}",
            len(priority),
        )
    )

    # 10
    summary_ok = (
        len(summary) == 1
        and int(
            summary.iloc[0][
                "instrument_count"
            ]
        ) == n
    )

    tests.append(
        validation_row(
            "Portfolio remediation summary generated",
            summary_ok,
            f"Summary rows: {len(summary)}",
            n,
        )
    )

    validation = pd.DataFrame(tests)

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


# ---------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------

def print_console_report(
    remediation: pd.DataFrame,
    priority: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:

    print("=" * 78)
    print("VITTANTRA — DAY 69 PORTFOLIO RISK REMEDIATION")
    print("=" * 78)

    print()
    print(
        "Day 68 Governance -> Day 69 Remediation "
        "-> Human Review -> Future Execution Layer"
    )

    print()
    print("PORTFOLIO REMEDIATION SUMMARY")
    print("-" * 78)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("REMEDIATION PRIORITY")
    print("-" * 78)

    display_columns = [
        "symbol",
        "asset_class",
        "risk_budget_utilization",
        "remediation_severity",
        "remediation_action",
        "proposed_risk_reduction_fraction",
        "priority_bucket",
        "human_review_required",
    ]

    print(
        remediation[
            display_columns
        ].to_string(
            index=False
        )
    )

    print()
    print("HUMAN-REVIEW QUEUE")
    print("-" * 78)

    if priority.empty:
        print(
            "No instruments currently require "
            "risk remediation review."
        )
    else:
        print(
            priority[
                [
                    "priority_bucket",
                    "symbol",
                    "remediation_severity",
                    "remediation_action",
                    "risk_budget_utilization",
                    "proposed_risk_reduction_fraction",
                ]
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
                "validation_test",
                "passed",
                "details",
            ]
        ].to_string(
            index=False
        )
    )

    passed = int(
        validation["passed"].sum()
    )

    total = len(validation)

    print()
    print(
        f"Validation: {passed}/{total} "
        f"tests passed."
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 78)
    print("VITTANTRA — DAY 69")
    print("Portfolio Risk Remediation Engine")
    print("=" * 78)

    try:

        if not INPUT_FILE.exists():
            raise FileNotFoundError(
                f"Required Day 68 input not found: "
                f"{INPUT_FILE}"
            )

        source = pd.read_csv(
            INPUT_FILE
        )

        validate_input_columns(
            source
        )

        if source.empty:
            raise ValueError(
                "Day 68 governance file contains no rows."
            )

        remediation = (
            build_instrument_remediation(
                source
            )
        )

        priority = build_priority_queue(
            remediation
        )

        summary = build_portfolio_summary(
            remediation
        )

        validation = (
            build_validation_summary(
                source,
                remediation,
                priority,
                summary,
            )
        )

        remediation.to_csv(
            OUTPUT_ACTIONS,
            index=False,
        )

        priority.to_csv(
            OUTPUT_PRIORITY,
            index=False,
        )

        summary.to_csv(
            OUTPUT_SUMMARY,
            index=False,
        )

        validation.to_csv(
            OUTPUT_VALIDATION,
            index=False,
        )

        print_console_report(
            remediation,
            priority,
            summary,
            validation,
        )

        print()
        print("OUTPUT FILES")
        print("-" * 78)
        print(OUTPUT_ACTIONS)
        print(OUTPUT_PRIORITY)
        print(OUTPUT_SUMMARY)
        print(OUTPUT_VALIDATION)

        print()
        print(
            "Important: Day 69 remediation outputs are "
            "research controls and human-review recommendations. "
            "They are not automatic trade instructions, "
            "regulatory determinations, or broker/exchange limits."
        )

        print()
        print(
            "Day 69 portfolio risk remediation complete."
        )

        print("=" * 78)

    except Exception as exc:

        print()
        print("=" * 78)
        print("DAY 69 FAILED")
        print("=" * 78)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "No Day 69 conclusions should be drawn "
            "from an incomplete run."
        )

        print("=" * 78)

        raise


if __name__ == "__main__":
    main()