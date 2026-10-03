"""
Vittantra
Day 66 — Portfolio Risk Budgeting

Purpose
-------
Convert Day 65 exposure-aware target allocations into an explicit
portfolio risk-budget framework.

The module:

1. Loads Day 65 target exposures.
2. Preserves capital, gross-notional, signed-notional and risk concepts.
3. Builds strategic risk budgets by asset class.
4. Allocates asset-class budgets to individual instruments.
5. Compares target risk exposure with assigned risk budget.
6. Calculates budget utilization and risk concentration.
7. Generates risk-budget-aware target weights.
8. Produces validation checks.
9. Writes Day 66 research outputs.

Important
---------
This is a research/risk-management engine.

Risk weights and risk budgets are analytical constructs. They are not
exchange margin requirements, regulatory capital requirements, or
automatic trade instructions.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("day65_target_exposures.csv")

OUTPUT_INSTRUMENT_BUDGETS = Path("day66_instrument_risk_budgets.csv")
OUTPUT_ASSET_CLASS_BUDGETS = Path("day66_asset_class_risk_budgets.csv")
OUTPUT_PORTFOLIO_SUMMARY = Path("day66_portfolio_risk_budget_summary.csv")
OUTPUT_BREACHES = Path("day66_risk_budget_breaches.csv")
OUTPUT_VALIDATION = Path("day66_validation_summary.csv")


EPSILON = 1e-12

# Maximum instrument-level share of total portfolio risk budget.
MAX_INSTRUMENT_RISK_BUDGET = 0.25

# Warn when an instrument consumes more than this fraction of its
# assigned risk budget.
WARNING_UTILIZATION = 0.90

# A hard breach occurs above this utilization.
BREACH_UTILIZATION = 1.00

# Small differences below this level are treated as immaterial.
MATERIALITY_THRESHOLD = 0.0001


# Strategic risk-budget assumptions.
#
# These are research assumptions rather than predictions.
# The engine automatically renormalizes the budgets across asset
# classes that actually exist in the Day 65 portfolio.
ASSET_CLASS_RISK_BUDGETS = {
    "Equity": 0.25,
    "ETF/Fund": 0.15,
    "Fixed Income": 0.12,
    "Commodity": 0.10,
    "Crypto": 0.08,
    "FX": 0.08,
    "Real Estate/REIT": 0.08,
    "Option": 0.05,
    "Future": 0.06,
    "Cash/Money Market": 0.03,
}


REQUIRED_COLUMNS = [
    "symbol",
    "asset_class",
    "instrument_type",
    "capital_weight",
    "target_capital_weight",
    "gross_exposure_weight",
    "target_gross_exposure_weight",
    "signed_notional_weight",
    "target_signed_notional_weight",
    "risk_weight",
    "target_risk_weight",
    "scale_factor",
    "constraint_reason",
]


NUMERIC_COLUMNS = [
    "capital_weight",
    "target_capital_weight",
    "gross_exposure_weight",
    "target_gross_exposure_weight",
    "signed_notional_weight",
    "target_signed_notional_weight",
    "risk_weight",
    "target_risk_weight",
    "scale_factor",
]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def safe_divide(
    numerator: pd.Series | float,
    denominator: pd.Series | float,
    default: float = 0.0,
):
    """
    Divide while protecting against zero or non-finite denominators.
    """

    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        numerator_series = pd.Series(numerator)
        denominator_series = pd.Series(denominator)

        result = np.where(
            np.abs(denominator_series) > EPSILON,
            numerator_series / denominator_series,
            default,
        )

        return pd.Series(
            result,
            index=numerator_series.index,
            dtype=float,
        )

    if not np.isfinite(denominator) or abs(denominator) <= EPSILON:
        return default

    return numerator / denominator


def normalize_positive(series: pd.Series) -> pd.Series:
    """
    Normalize non-negative values so that they sum to one.

    If all values are zero, use equal weights.
    """

    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    values = values.clip(lower=0.0)

    total = float(values.sum())

    if total > EPSILON:
        return values / total

    if len(values) == 0:
        return values

    return pd.Series(
        np.repeat(1.0 / len(values), len(values)),
        index=values.index,
        dtype=float,
    )


def classify_utilization(utilization: float) -> str:
    """
    Convert budget utilization into an interpretable status.
    """

    if not np.isfinite(utilization):
        return "UNKNOWN"

    if utilization > BREACH_UTILIZATION + EPSILON:
        return "BREACH"

    if utilization >= WARNING_UTILIZATION:
        return "WARNING"

    return "WITHIN_BUDGET"


def require_columns(df: pd.DataFrame) -> None:
    """
    Confirm that Day 65 has the schema required by Day 66.
    """

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]

    if missing:
        raise KeyError(
            "Day 66 cannot run because required Day 65 columns are missing.\n"
            f"Missing columns: {missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


def coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert known numerical fields safely.
    """

    result = df.copy()

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result


# ============================================================
# DATA LOADING
# ============================================================

def load_day65_targets() -> pd.DataFrame:
    """
    Load Day 65 exposure-aware target exposures.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Required input file not found: {INPUT_FILE}\n"
            "Run Day 65 first."
        )

    df = pd.read_csv(INPUT_FILE)

    if df.empty:
        raise ValueError(
            f"{INPUT_FILE} exists but contains no rows."
        )

    require_columns(df)

    df = coerce_numeric_columns(df)

    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["asset_class"] = df["asset_class"].astype(str).str.strip()
    df["instrument_type"] = df["instrument_type"].astype(str).str.strip()

    if df["symbol"].duplicated().any():
        duplicates = (
            df.loc[df["symbol"].duplicated(keep=False), "symbol"]
            .astype(str)
            .tolist()
        )

        raise ValueError(
            "Duplicate symbols detected in Day 65 target exposures: "
            f"{duplicates}"
        )

    return df.reset_index(drop=True)


# ============================================================
# STRATEGIC ASSET-CLASS RISK BUDGETS
# ============================================================

def build_asset_class_budget_map(
    df: pd.DataFrame,
) -> dict[str, float]:
    """
    Build normalized strategic risk budgets for asset classes that
    actually appear in the portfolio.

    Known asset classes receive their configured strategic budget.
    Unknown asset classes receive a small fallback allocation.
    """

    asset_classes = sorted(
        df["asset_class"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not asset_classes:
        raise ValueError("No asset classes found in Day 65 data.")

    raw_budgets: dict[str, float] = {}

    known_values = list(ASSET_CLASS_RISK_BUDGETS.values())

    fallback = (
        min(known_values) if known_values else 0.05
    )

    for asset_class in asset_classes:
        raw_budgets[asset_class] = float(
            ASSET_CLASS_RISK_BUDGETS.get(
                asset_class,
                fallback,
            )
        )

    total = sum(raw_budgets.values())

    if total <= EPSILON:
        equal_budget = 1.0 / len(asset_classes)

        return {
            asset_class: equal_budget
            for asset_class in asset_classes
        }

    return {
        asset_class: budget / total
        for asset_class, budget in raw_budgets.items()
    }


# ============================================================
# INSTRUMENT RISK-BUDGET ALLOCATION
# ============================================================

def allocate_instrument_budgets(
    df: pd.DataFrame,
    asset_class_budget_map: dict[str, float],
) -> pd.DataFrame:
    """
    Allocate each asset-class risk budget across instruments.

    Within an asset class, allocation is based primarily on Day 65
    target risk weights.

    If target risk weights are unavailable or zero, the engine falls
    back to target gross exposure and then target capital weight.
    """

    result = df.copy()

    result["asset_class_risk_budget"] = (
        result["asset_class"]
        .map(asset_class_budget_map)
        .fillna(0.0)
        .astype(float)
    )

    result["risk_allocation_driver"] = 0.0

    for asset_class, group in result.groupby(
        "asset_class",
        sort=False,
    ):
        idx = group.index

        target_risk = (
            pd.to_numeric(
                group["target_risk_weight"],
                errors="coerce",
            )
            .fillna(0.0)
            .abs()
        )

        target_gross = (
            pd.to_numeric(
                group["target_gross_exposure_weight"],
                errors="coerce",
            )
            .fillna(0.0)
            .abs()
        )

        target_capital = (
            pd.to_numeric(
                group["target_capital_weight"],
                errors="coerce",
            )
            .fillna(0.0)
            .abs()
        )

        if target_risk.sum() > EPSILON:
            driver = normalize_positive(target_risk)

        elif target_gross.sum() > EPSILON:
            driver = normalize_positive(target_gross)

        else:
            driver = normalize_positive(target_capital)

        result.loc[idx, "risk_allocation_driver"] = driver.values

    result["raw_instrument_risk_budget"] = (
        result["asset_class_risk_budget"]
        * result["risk_allocation_driver"]
    )

    # Apply instrument-level budget ceiling.
    result["instrument_risk_budget"] = (
        result["raw_instrument_risk_budget"]
        .clip(
            lower=0.0,
            upper=MAX_INSTRUMENT_RISK_BUDGET,
        )
    )

    # If clipping removed budget capacity, redistribute residual risk
    # budget among instruments that still have capacity.
    result = redistribute_budget_residual(result)

    return result


def redistribute_budget_residual(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Redistribute any residual risk budget created by the instrument cap.

    The process is deterministic and stops when:
    - total risk budget reaches approximately 100%, or
    - all instruments reach the instrument cap.
    """

    result = df.copy()

    for _ in range(100):
        current_total = float(
            result["instrument_risk_budget"].sum()
        )

        residual = 1.0 - current_total

        if residual <= 1e-10:
            break

        capacity = (
            MAX_INSTRUMENT_RISK_BUDGET
            - result["instrument_risk_budget"]
        ).clip(lower=0.0)

        available_capacity = float(capacity.sum())

        if available_capacity <= EPSILON:
            break

        eligible = capacity > EPSILON

        if not eligible.any():
            break

        driver = result.loc[
            eligible,
            "raw_instrument_risk_budget",
        ].clip(lower=0.0)

        if driver.sum() <= EPSILON:
            driver = capacity.loc[eligible]

        allocation_weights = normalize_positive(driver)

        proposed = allocation_weights * residual

        proposed = np.minimum(
            proposed,
            capacity.loc[eligible],
        )

        result.loc[
            eligible,
            "instrument_risk_budget",
        ] += proposed.values

    return result


# ============================================================
# RISK CONTRIBUTION ANALYSIS
# ============================================================

def calculate_risk_contributions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare Day 65 target risk weights with Day 66 risk budgets.

    Day 65 target_risk_weight is treated as the portfolio's modeled
    instrument risk exposure.

    Day 66 instrument_risk_budget is the allowed strategic share of
    portfolio risk.
    """

    result = df.copy()

    modeled_risk = (
        pd.to_numeric(
            result["target_risk_weight"],
            errors="coerce",
        )
        .fillna(0.0)
        .abs()
    )

    modeled_total = float(modeled_risk.sum())

    if modeled_total > EPSILON:
        result["modeled_risk_contribution"] = (
            modeled_risk / modeled_total
        )
    else:
        result["modeled_risk_contribution"] = 0.0

    result["risk_budget_utilization"] = safe_divide(
        result["modeled_risk_contribution"],
        result["instrument_risk_budget"],
        default=0.0,
    )

    result["risk_budget_gap"] = (
        result["instrument_risk_budget"]
        - result["modeled_risk_contribution"]
    )

    result["risk_budget_excess"] = (
        result["modeled_risk_contribution"]
        - result["instrument_risk_budget"]
    ).clip(lower=0.0)

    result["risk_budget_status"] = (
        result["risk_budget_utilization"]
        .apply(classify_utilization)
    )

    return result


# ============================================================
# RISK-BUDGET-AWARE TARGETS
# ============================================================

def calculate_budget_scalers(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate risk-budget scaling factors.

    Instruments exceeding their risk budget receive a scaler below 1.

    Instruments inside their budget are not automatically levered up.
    This makes Day 66 primarily a risk-control layer rather than a
    return-seeking leverage engine.
    """

    result = df.copy()

    utilization = pd.to_numeric(
        result["risk_budget_utilization"],
        errors="coerce",
    ).fillna(0.0)

    scaler = np.ones(len(result), dtype=float)

    over_budget = utilization > BREACH_UTILIZATION

    scaler[over_budget] = (
        1.0
        / utilization.loc[over_budget].values
    )

    scaler = np.clip(
        scaler,
        0.0,
        1.0,
    )

    result["risk_budget_scaler"] = scaler

    return result


def calculate_risk_budgeted_targets(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply risk-budget scalers to Day 65 target exposures.

    Capital, gross-notional and signed-notional concepts remain
    separate.
    """

    result = calculate_budget_scalers(df)

    result["risk_budgeted_capital_weight"] = (
        result["target_capital_weight"]
        * result["risk_budget_scaler"]
    )

    result["risk_budgeted_gross_exposure_weight"] = (
        result["target_gross_exposure_weight"]
        * result["risk_budget_scaler"]
    )

    result["risk_budgeted_signed_notional_weight"] = (
        result["target_signed_notional_weight"]
        * result["risk_budget_scaler"]
    )

    result["risk_budgeted_risk_weight"] = (
        result["target_risk_weight"]
        * result["risk_budget_scaler"]
    )

    result["capital_weight_adjustment"] = (
        result["risk_budgeted_capital_weight"]
        - result["target_capital_weight"]
    )

    result["gross_exposure_adjustment"] = (
        result["risk_budgeted_gross_exposure_weight"]
        - result["target_gross_exposure_weight"]
    )

    result["signed_notional_adjustment"] = (
        result["risk_budgeted_signed_notional_weight"]
        - result["target_signed_notional_weight"]
    )

    result["risk_weight_adjustment"] = (
        result["risk_budgeted_risk_weight"]
        - result["target_risk_weight"]
    )

    result["risk_budget_action"] = np.where(
        result["risk_budget_scaler"] < 1.0 - EPSILON,
        "REDUCE_RISK",
        "UNCHANGED",
    )

    return result


# ============================================================
# ASSET-CLASS SUMMARY
# ============================================================

def build_asset_class_summary(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate risk budgets and modeled risk by asset class.
    """

    summary = (
        df.groupby(
            "asset_class",
            dropna=False,
            as_index=False,
        )
        .agg(
            instruments=("symbol", "count"),
            asset_class_risk_budget=(
                "asset_class_risk_budget",
                "first",
            ),
            instrument_risk_budget=(
                "instrument_risk_budget",
                "sum",
            ),
            modeled_risk_contribution=(
                "modeled_risk_contribution",
                "sum",
            ),
            target_capital_weight=(
                "target_capital_weight",
                "sum",
            ),
            risk_budgeted_capital_weight=(
                "risk_budgeted_capital_weight",
                "sum",
            ),
            target_gross_exposure_weight=(
                "target_gross_exposure_weight",
                "sum",
            ),
            risk_budgeted_gross_exposure_weight=(
                "risk_budgeted_gross_exposure_weight",
                "sum",
            ),
            target_signed_notional_weight=(
                "target_signed_notional_weight",
                "sum",
            ),
            risk_budgeted_signed_notional_weight=(
                "risk_budgeted_signed_notional_weight",
                "sum",
            ),
            target_risk_weight=(
                "target_risk_weight",
                "sum",
            ),
            risk_budgeted_risk_weight=(
                "risk_budgeted_risk_weight",
                "sum",
            ),
        )
    )

    summary["risk_budget_utilization"] = safe_divide(
        summary["modeled_risk_contribution"],
        summary["instrument_risk_budget"],
        default=0.0,
    )

    summary["risk_budget_gap"] = (
        summary["instrument_risk_budget"]
        - summary["modeled_risk_contribution"]
    )

    summary["risk_budget_status"] = (
        summary["risk_budget_utilization"]
        .apply(classify_utilization)
    )

    return summary.sort_values(
        "modeled_risk_contribution",
        ascending=False,
    ).reset_index(drop=True)


# ============================================================
# PORTFOLIO SUMMARY
# ============================================================

def concentration_index(weights: pd.Series) -> float:
    """
    Herfindahl-style concentration index.
    """

    values = (
        pd.to_numeric(weights, errors="coerce")
        .fillna(0.0)
        .abs()
    )

    total = float(values.sum())

    if total <= EPSILON:
        return 0.0

    normalized = values / total

    return float(np.square(normalized).sum())


def effective_number_of_risk_positions(
    weights: pd.Series,
) -> float:
    """
    Convert the concentration index into an intuitive effective
    number of risk positions.
    """

    hhi = concentration_index(weights)

    if hhi <= EPSILON:
        return 0.0

    return 1.0 / hhi


def build_portfolio_summary(
    df: pd.DataFrame,
    asset_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one-row Day 66 portfolio risk-budget summary.
    """

    modeled = df["modeled_risk_contribution"].abs()
    budgets = df["instrument_risk_budget"].abs()

    largest_risk_idx = modeled.idxmax()
    largest_budget_idx = budgets.idxmax()

    breaches = int(
        (df["risk_budget_status"] == "BREACH").sum()
    )

    warnings = int(
        (df["risk_budget_status"] == "WARNING").sum()
    )

    summary = {
        "instruments": len(df),
        "asset_classes": df["asset_class"].nunique(),
        "total_instrument_risk_budget": float(
            df["instrument_risk_budget"].sum()
        ),
        "total_modeled_risk_contribution": float(
            df["modeled_risk_contribution"].sum()
        ),
        "largest_risk_contributor": str(
            df.loc[largest_risk_idx, "symbol"]
        ),
        "largest_risk_contribution": float(
            df.loc[
                largest_risk_idx,
                "modeled_risk_contribution",
            ]
        ),
        "largest_instrument_risk_budget_symbol": str(
            df.loc[largest_budget_idx, "symbol"]
        ),
        "largest_instrument_risk_budget": float(
            df.loc[
                largest_budget_idx,
                "instrument_risk_budget",
            ]
        ),
        "risk_budget_breaches": breaches,
        "risk_budget_warnings": warnings,
        "risk_concentration_index": concentration_index(
            modeled
        ),
        "effective_number_of_risk_positions": (
            effective_number_of_risk_positions(modeled)
        ),
        "budget_concentration_index": concentration_index(
            budgets
        ),
        "target_capital_weight_total": float(
            df["target_capital_weight"].sum()
        ),
        "risk_budgeted_capital_weight_total": float(
            df["risk_budgeted_capital_weight"].sum()
        ),
        "target_gross_exposure_weight_total": float(
            df["target_gross_exposure_weight"].sum()
        ),
        "risk_budgeted_gross_exposure_weight_total": float(
            df["risk_budgeted_gross_exposure_weight"].sum()
        ),
        "target_signed_notional_weight_total": float(
            df["target_signed_notional_weight"].sum()
        ),
        "risk_budgeted_signed_notional_weight_total": float(
            df["risk_budgeted_signed_notional_weight"].sum()
        ),
        "target_risk_weight_total": float(
            df["target_risk_weight"].sum()
        ),
        "risk_budgeted_risk_weight_total": float(
            df["risk_budgeted_risk_weight"].sum()
        ),
        "asset_classes_over_budget": int(
            (
                asset_summary["risk_budget_status"]
                == "BREACH"
            ).sum()
        ),
    }

    return pd.DataFrame([summary])


# ============================================================
# BREACH REPORT
# ============================================================

def build_breach_report(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create a dedicated report for warnings and breaches.
    """

    columns = [
        "symbol",
        "asset_class",
        "instrument_type",
        "instrument_risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_gap",
        "risk_budget_excess",
        "risk_budget_scaler",
        "risk_budget_action",
        "risk_budget_status",
    ]

    breaches = df.loc[
        df["risk_budget_status"].isin(
            ["WARNING", "BREACH"]
        ),
        columns,
    ].copy()

    if breaches.empty:
        return pd.DataFrame(columns=columns)

    return breaches.sort_values(
        [
            "risk_budget_status",
            "risk_budget_utilization",
        ],
        ascending=[True, False],
    ).reset_index(drop=True)


# ============================================================
# VALIDATION
# ============================================================

def validation_row(
    check: str,
    passed: bool,
    details: str,
) -> dict:
    return {
        "check": check,
        "passed": bool(passed),
        "details": details,
    }


def run_validation(
    df: pd.DataFrame,
    asset_summary: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validate the Day 66 risk-budget architecture.
    """

    checks: list[dict] = []

    finite_columns = [
        "instrument_risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_gap",
        "risk_budget_scaler",
        "risk_budgeted_capital_weight",
        "risk_budgeted_gross_exposure_weight",
        "risk_budgeted_signed_notional_weight",
        "risk_budgeted_risk_weight",
    ]

    finite_pass = True

    for column in finite_columns:
        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        if not np.isfinite(values).all():
            finite_pass = False
            break

    checks.append(
        validation_row(
            "Risk-budget outputs contain finite values",
            finite_pass,
            f"Columns checked: {len(finite_columns)}",
        )
    )

    total_budget = float(
        df["instrument_risk_budget"].sum()
    )

    budget_sum_pass = abs(total_budget - 1.0) <= 1e-6

    checks.append(
        validation_row(
            "Instrument risk budgets sum to 100%",
            budget_sum_pass,
            f"Total instrument risk budget: {total_budget:.6%}",
        )
    )

    max_budget = float(
        df["instrument_risk_budget"].max()
    )

    cap_pass = (
        max_budget
        <= MAX_INSTRUMENT_RISK_BUDGET + 1e-10
    )

    checks.append(
        validation_row(
            "Instrument risk budgets respect concentration cap",
            cap_pass,
            (
                f"Largest budget: {max_budget:.4%}; "
                f"limit: {MAX_INSTRUMENT_RISK_BUDGET:.4%}"
            ),
        )
    )

    modeled_total = float(
        df["modeled_risk_contribution"].sum()
    )

    modeled_pass = (
        abs(modeled_total - 1.0) <= 1e-6
        or abs(modeled_total) <= EPSILON
    )

    checks.append(
        validation_row(
            "Modeled risk contributions are normalized",
            modeled_pass,
            (
                "Total modeled risk contribution: "
                f"{modeled_total:.6%}"
            ),
        )
    )

    scaler_pass = bool(
        (
            (df["risk_budget_scaler"] >= -EPSILON)
            & (
                df["risk_budget_scaler"]
                <= 1.0 + EPSILON
            )
        ).all()
    )

    checks.append(
        validation_row(
            "Risk-budget scalers remain within policy",
            scaler_pass,
            "Required range: 0.0 to 1.0",
        )
    )

    # Day 66 should never increase capital through the risk-control
    # scaler.
    capital_increase = (
        df["risk_budgeted_capital_weight"].abs()
        - df["target_capital_weight"].abs()
    )

    no_leverage_pass = bool(
        (
            capital_increase
            <= MATERIALITY_THRESHOLD
        ).all()
    )

    checks.append(
        validation_row(
            "Risk budgeting does not increase capital exposure",
            no_leverage_pass,
            (
                "Largest absolute capital increase: "
                f"{max(float(capital_increase.max()), 0.0):.6%}"
            ),
        )
    )

    gross_increase = (
        df["risk_budgeted_gross_exposure_weight"].abs()
        - df["target_gross_exposure_weight"].abs()
    )

    gross_pass = bool(
        (
            gross_increase
            <= MATERIALITY_THRESHOLD
        ).all()
    )

    checks.append(
        validation_row(
            "Risk budgeting does not increase gross exposure",
            gross_pass,
            (
                "Largest absolute gross increase: "
                f"{max(float(gross_increase.max()), 0.0):.6%}"
            ),
        )
    )

    signed_direction_pass = True

    for _, row in df.iterrows():
        original = float(
            row["target_signed_notional_weight"]
        )

        adjusted = float(
            row["risk_budgeted_signed_notional_weight"]
        )

        if abs(original) <= EPSILON:
            continue

        if abs(adjusted) <= EPSILON:
            continue

        if np.sign(original) != np.sign(adjusted):
            signed_direction_pass = False
            break

    checks.append(
        validation_row(
            "Signed-notional direction is preserved",
            signed_direction_pass,
            (
                "Risk budgeting may reduce exposure but "
                "must not reverse long/short direction."
            ),
        )
    )

    asset_budget_total = float(
        asset_summary["instrument_risk_budget"].sum()
    )

    asset_pass = abs(
        asset_budget_total - total_budget
    ) <= 1e-8

    checks.append(
        validation_row(
            "Asset-class and instrument budgets reconcile",
            asset_pass,
            (
                f"Asset-class total: {asset_budget_total:.6%}; "
                f"instrument total: {total_budget:.6%}"
            ),
        )
    )

    symbol_unique_pass = not df["symbol"].duplicated().any()

    checks.append(
        validation_row(
            "Instrument identifiers remain unique",
            symbol_unique_pass,
            f"Instruments: {len(df)}",
        )
    )

    summary_pass = (
        len(portfolio_summary) == 1
    )

    checks.append(
        validation_row(
            "Portfolio risk-budget summary generated",
            summary_pass,
            f"Rows: {len(portfolio_summary)}",
        )
    )

    validation = pd.DataFrame(checks)

    validation["passed_tests"] = int(
        validation["passed"].sum()
    )

    validation["total_tests"] = len(validation)

    validation["pass_rate"] = (
        validation["passed_tests"]
        / validation["total_tests"]
    )

    return validation


# ============================================================
# OUTPUT
# ============================================================

def save_outputs(
    instrument_budgets: pd.DataFrame,
    asset_class_budgets: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    breaches: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    """
    Save all Day 66 outputs.
    """

    instrument_budgets.to_csv(
        OUTPUT_INSTRUMENT_BUDGETS,
        index=False,
    )

    asset_class_budgets.to_csv(
        OUTPUT_ASSET_CLASS_BUDGETS,
        index=False,
    )

    portfolio_summary.to_csv(
        OUTPUT_PORTFOLIO_SUMMARY,
        index=False,
    )

    breaches.to_csv(
        OUTPUT_BREACHES,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )


# ============================================================
# REPORTING
# ============================================================

def print_report(
    instrument_budgets: pd.DataFrame,
    asset_class_budgets: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    breaches: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    """
    Print a concise institutional-style Day 66 report.
    """

    print()
    print("=" * 78)
    print("VITTANTRA — DAY 66 PORTFOLIO RISK BUDGETING")
    print("=" * 78)

    print()
    print("Input:")
    print(f"  {INPUT_FILE}")

    print()
    print("Portfolio:")
    print(
        f"  Instruments: "
        f"{int(portfolio_summary.loc[0, 'instruments'])}"
    )
    print(
        f"  Asset classes: "
        f"{int(portfolio_summary.loc[0, 'asset_classes'])}"
    )
    print(
        "  Total instrument risk budget: "
        f"{portfolio_summary.loc[0, 'total_instrument_risk_budget']:.2%}"
    )
    print(
        "  Effective number of risk positions: "
        f"{portfolio_summary.loc[0, 'effective_number_of_risk_positions']:.2f}"
    )

    print()
    print("Largest modeled risk contributor:")
    print(
        "  "
        f"{portfolio_summary.loc[0, 'largest_risk_contributor']} "
        f"({portfolio_summary.loc[0, 'largest_risk_contribution']:.2%})"
    )

    print()
    print("Risk-budget status:")
    print(
        "  Breaches: "
        f"{int(portfolio_summary.loc[0, 'risk_budget_breaches'])}"
    )
    print(
        "  Warnings: "
        f"{int(portfolio_summary.loc[0, 'risk_budget_warnings'])}"
    )

    print()
    print("Top instrument risk contributions:")

    display_columns = [
        "symbol",
        "asset_class",
        "instrument_risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_status",
        "risk_budget_action",
    ]

    top = (
        instrument_budgets
        .sort_values(
            "modeled_risk_contribution",
            ascending=False,
        )
        .head(10)
    )

    print(
        top[display_columns]
        .to_string(index=False)
    )

    print()
    print("Asset-class risk budgets:")

    asset_display = [
        "asset_class",
        "instrument_risk_budget",
        "modeled_risk_contribution",
        "risk_budget_utilization",
        "risk_budget_status",
    ]

    print(
        asset_class_budgets[asset_display]
        .to_string(index=False)
    )

    print()
    print("Validation:")

    passed = int(validation["passed"].sum())
    total = len(validation)

    print(
        f"  Passed: {passed}/{total} "
        f"({passed / total:.2%})"
    )

    failed = validation.loc[
        ~validation["passed"]
    ]

    if failed.empty:
        print("  All Day 66 validation checks passed.")
    else:
        print()
        print("  Failed checks:")
        print(
            failed[
                ["check", "details"]
            ].to_string(index=False)
        )

    print()
    print("Outputs:")

    for output in [
        OUTPUT_INSTRUMENT_BUDGETS,
        OUTPUT_ASSET_CLASS_BUDGETS,
        OUTPUT_PORTFOLIO_SUMMARY,
        OUTPUT_BREACHES,
        OUTPUT_VALIDATION,
    ]:
        print(f"  {output}")

    print()
    print("Architecture:")
    print(
        "  Day 65 Exposure-Aware Targets"
        " -> Strategic Risk Budgets"
        " -> Instrument Risk Budgets"
        " -> Risk Contribution"
        " -> Budget Utilization"
        " -> Risk-Aware Scaling"
        " -> Validation"
    )

    print()
    print(
        "Important: Day 66 risk budgets are research assumptions. "
        "They are not regulatory capital, exchange margin, "
        "or automatic trade instructions."
    )

    print()
    print("Day 66 portfolio risk budgeting complete.")
    print("=" * 78)


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:
    """
    Execute Day 66.
    """

    try:
        # ----------------------------------------------------
        # 1. Load Day 65
        # ----------------------------------------------------

        targets = load_day65_targets()

        # ----------------------------------------------------
        # 2. Strategic asset-class risk budgets
        # ----------------------------------------------------

        asset_class_budget_map = (
            build_asset_class_budget_map(targets)
        )

        # ----------------------------------------------------
        # 3. Instrument risk budgets
        # ----------------------------------------------------

        instrument_budgets = (
            allocate_instrument_budgets(
                targets,
                asset_class_budget_map,
            )
        )

        # ----------------------------------------------------
        # 4. Modeled risk contributions
        # ----------------------------------------------------

        instrument_budgets = (
            calculate_risk_contributions(
                instrument_budgets
            )
        )

        # ----------------------------------------------------
        # 5. Risk-budget-aware targets
        # ----------------------------------------------------

        instrument_budgets = (
            calculate_risk_budgeted_targets(
                instrument_budgets
            )
        )

        # ----------------------------------------------------
        # 6. Asset-class aggregation
        # ----------------------------------------------------

        asset_class_budgets = (
            build_asset_class_summary(
                instrument_budgets
            )
        )

        # ----------------------------------------------------
        # 7. Portfolio summary
        # ----------------------------------------------------

        portfolio_summary = (
            build_portfolio_summary(
                instrument_budgets,
                asset_class_budgets,
            )
        )

        # ----------------------------------------------------
        # 8. Breaches
        # ----------------------------------------------------

        breaches = build_breach_report(
            instrument_budgets
        )

        # ----------------------------------------------------
        # 9. Validation
        # ----------------------------------------------------

        validation = run_validation(
            instrument_budgets,
            asset_class_budgets,
            portfolio_summary,
        )

        # ----------------------------------------------------
        # 10. Save
        # ----------------------------------------------------

        save_outputs(
            instrument_budgets,
            asset_class_budgets,
            portfolio_summary,
            breaches,
            validation,
        )

        # ----------------------------------------------------
        # 11. Report
        # ----------------------------------------------------

        print_report(
            instrument_budgets,
            asset_class_budgets,
            portfolio_summary,
            breaches,
            validation,
        )

    except Exception as exc:
        print()
        print("=" * 78)
        print("DAY 66 FAILED")
        print("=" * 78)
        print(f"{type(exc).__name__}: {exc}")
        print()
        print(
            "No Day 66 conclusions should be drawn "
            "from an incomplete run."
        )
        print("=" * 78)

        raise


if __name__ == "__main__":
    main()