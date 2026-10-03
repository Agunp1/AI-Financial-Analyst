"""
VITTANTRA
Day 67 — Portfolio Risk Monitoring & Alert Engine

Purpose
-------
Convert Day 66 portfolio risk-budget outputs into a monitoring layer.

The monitor:
1. Loads Day 66 instrument risk budgets.
2. Measures risk-budget utilization.
3. Detects budget breaches and near-breaches.
4. Detects unusually large portfolio adjustments.
5. Detects concentration in asset classes.
6. Generates instrument-level alerts.
7. Generates asset-class monitoring statistics.
8. Produces a portfolio-level risk dashboard.
9. Generates validation checks.

Important
---------
This module is a research / monitoring system.

It does NOT:
- execute trades,
- send orders,
- guarantee investment performance,
- replace independent risk review,
- represent regulatory capital calculations.

Day 67 architecture:

Day 65 Exposure-Aware Portfolio
        ↓
Day 66 Portfolio Risk Budgeting
        ↓
Day 67 Portfolio Risk Monitor
        ↓
Risk Utilization
        ↓
Breach Detection
        ↓
Alert Severity
        ↓
Portfolio Risk Dashboard
        ↓
Validation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

DAY66_INSTRUMENT_FILE = Path("day66_instrument_risk_budgets.csv")
DAY66_ASSET_CLASS_FILE = Path("day66_asset_class_risk_budgets.csv")
DAY66_PORTFOLIO_FILE = Path("day66_portfolio_risk_budget_summary.csv")
DAY66_BREACH_FILE = Path("day66_risk_budget_breaches.csv")

OUTPUT_INSTRUMENT_MONITOR = Path("day67_instrument_risk_monitor.csv")
OUTPUT_ASSET_CLASS_MONITOR = Path("day67_asset_class_risk_monitor.csv")
OUTPUT_ALERTS = Path("day67_risk_alerts.csv")
OUTPUT_PORTFOLIO_DASHBOARD = Path("day67_portfolio_risk_dashboard.csv")
OUTPUT_VALIDATION = Path("day67_validation_summary.csv")


# Monitoring thresholds
WATCH_UTILIZATION = 0.80
WARNING_UTILIZATION = 0.95
BREACH_UTILIZATION = 1.00
CRITICAL_UTILIZATION = 1.20

LARGE_CAPITAL_ADJUSTMENT = 0.05
LARGE_GROSS_ADJUSTMENT = 0.05
LARGE_NOTIONAL_ADJUSTMENT = 0.05
LARGE_RISK_ADJUSTMENT = 0.05

HIGH_ASSET_CLASS_SHARE = 0.35

EPSILON = 1e-12


# =============================================================================
# HELPERS
# =============================================================================

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in result.columns
    ]
    return result


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)

        if np.isfinite(number):
            return number

    except (TypeError, ValueError):
        pass

    return default


def first_existing_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> str | None:

    for column in candidates:
        if column in df.columns:
            return column

    return None


def require_columns(
    df: pd.DataFrame,
    columns: list[str],
    dataset_name: str,
) -> None:

    missing = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            f"{dataset_name} is missing required columns: {missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


def bool_text(value: bool) -> str:
    return "PASS" if value else "FAIL"


def normalized_abs(series: pd.Series) -> pd.Series:
    values = safe_numeric(series).fillna(0.0).abs()

    total = values.sum()

    if total <= EPSILON:
        return pd.Series(
            np.zeros(len(values)),
            index=values.index,
            dtype=float,
        )

    return values / total


# =============================================================================
# LOAD DAY 66
# =============================================================================

def load_day66_instrument_budgets() -> pd.DataFrame:

    if not DAY66_INSTRUMENT_FILE.exists():
        raise FileNotFoundError(
            f"Required Day 66 file not found: "
            f"{DAY66_INSTRUMENT_FILE}"
        )

    df = pd.read_csv(DAY66_INSTRUMENT_FILE)
    df = clean_column_names(df)

    require_columns(
        df,
        [
            "risk_budget_utilization",
            "risk_budget_gap",
            "risk_budget_excess",
            "risk_budget_status",
            "risk_budget_scaler",
            "risk_budgeted_capital_weight",
            "risk_budgeted_gross_exposure_weight",
            "risk_budgeted_signed_notional_weight",
            "risk_budgeted_risk_weight",
            "capital_weight_adjustment",
            "gross_exposure_adjustment",
            "signed_notional_adjustment",
            "risk_weight_adjustment",
            "risk_budget_action",
        ],
        "Day 66 instrument risk budgets",
    )

    return df


def load_optional_csv(path: Path) -> pd.DataFrame:

    if not path.exists():
        return pd.DataFrame()

    try:
        return clean_column_names(pd.read_csv(path))

    except pd.errors.EmptyDataError:
        return pd.DataFrame()


# =============================================================================
# IDENTIFIERS
# =============================================================================

def add_monitor_identifiers(df: pd.DataFrame) -> pd.DataFrame:

    result = df.copy()

    symbol_col = first_existing_column(
        result,
        [
            "symbol",
            "ticker",
            "security",
            "instrument",
            "asset",
        ],
    )

    asset_class_col = first_existing_column(
        result,
        [
            "asset_class",
            "assetclass",
            "class",
        ],
    )

    instrument_type_col = first_existing_column(
        result,
        [
            "instrument_type",
            "security_type",
            "type",
        ],
    )

    if symbol_col is None:
        result["monitor_symbol"] = [
            f"INSTRUMENT_{i + 1}"
            for i in range(len(result))
        ]
    else:
        result["monitor_symbol"] = (
            result[symbol_col]
            .astype(str)
            .str.strip()
        )

    if asset_class_col is None:
        result["monitor_asset_class"] = "Unknown"
    else:
        result["monitor_asset_class"] = (
            result[asset_class_col]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

    if instrument_type_col is None:
        result["monitor_instrument_type"] = "Unknown"
    else:
        result["monitor_instrument_type"] = (
            result[instrument_type_col]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

    return result


# =============================================================================
# MONITORING METRICS
# =============================================================================

def prepare_monitor_metrics(df: pd.DataFrame) -> pd.DataFrame:

    result = add_monitor_identifiers(df)

    numeric_columns = [
        "risk_budget_utilization",
        "risk_budget_gap",
        "risk_budget_excess",
        "risk_budget_scaler",
        "risk_budgeted_capital_weight",
        "risk_budgeted_gross_exposure_weight",
        "risk_budgeted_signed_notional_weight",
        "risk_budgeted_risk_weight",
        "capital_weight_adjustment",
        "gross_exposure_adjustment",
        "signed_notional_adjustment",
        "risk_weight_adjustment",
    ]

    optional_numeric = [
        "capital_weight",
        "target_capital_weight",
        "gross_exposure_weight",
        "target_gross_exposure_weight",
        "signed_notional_weight",
        "target_signed_notional_weight",
        "risk_weight",
        "target_risk_weight",
        "asset_class_risk_budget",
        "raw_instrument_risk_budget",
        "instrument_risk_budget",
        "modeled_risk_contribution",
    ]

    for column in numeric_columns + optional_numeric:

        if column in result.columns:
            result[column] = safe_numeric(result[column])

    utilization = (
        result["risk_budget_utilization"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    result["monitor_utilization"] = utilization

    result["utilization_percent"] = (
        result["monitor_utilization"] * 100.0
    )

    result["absolute_risk_gap"] = (
        result["risk_budget_gap"]
        .fillna(0.0)
        .abs()
    )

    result["absolute_risk_excess"] = (
        result["risk_budget_excess"]
        .fillna(0.0)
        .abs()
    )

    result["absolute_capital_adjustment"] = (
        result["capital_weight_adjustment"]
        .fillna(0.0)
        .abs()
    )

    result["absolute_gross_adjustment"] = (
        result["gross_exposure_adjustment"]
        .fillna(0.0)
        .abs()
    )

    result["absolute_notional_adjustment"] = (
        result["signed_notional_adjustment"]
        .fillna(0.0)
        .abs()
    )

    result["absolute_risk_adjustment"] = (
        result["risk_weight_adjustment"]
        .fillna(0.0)
        .abs()
    )

    result["risk_budgeted_abs_notional"] = (
        result["risk_budgeted_signed_notional_weight"]
        .fillna(0.0)
        .abs()
    )

    result["risk_budgeted_abs_risk"] = (
        result["risk_budgeted_risk_weight"]
        .fillna(0.0)
        .abs()
    )

    return result


# =============================================================================
# ALERT CLASSIFICATION
# =============================================================================

def utilization_severity(utilization: float) -> str:

    if not np.isfinite(utilization):
        return "WARNING"

    if utilization >= CRITICAL_UTILIZATION:
        return "CRITICAL"

    if utilization > BREACH_UTILIZATION:
        return "BREACH"

    if utilization >= WARNING_UTILIZATION:
        return "WARNING"

    if utilization >= WATCH_UTILIZATION:
        return "WATCH"

    return "NORMAL"


def severity_rank(severity: str) -> int:

    mapping = {
        "NORMAL": 0,
        "WATCH": 1,
        "WARNING": 2,
        "BREACH": 3,
        "CRITICAL": 4,
    }

    return mapping.get(str(severity).upper(), 1)


def adjustment_severity(row: pd.Series) -> str:

    capital = safe_float(
        row.get("absolute_capital_adjustment")
    )

    gross = safe_float(
        row.get("absolute_gross_adjustment")
    )

    notional = safe_float(
        row.get("absolute_notional_adjustment")
    )

    risk = safe_float(
        row.get("absolute_risk_adjustment")
    )

    ratios = [
        capital / LARGE_CAPITAL_ADJUSTMENT,
        gross / LARGE_GROSS_ADJUSTMENT,
        notional / LARGE_NOTIONAL_ADJUSTMENT,
        risk / LARGE_RISK_ADJUSTMENT,
    ]

    maximum = max(ratios)

    if maximum >= 2.0:
        return "CRITICAL"

    if maximum >= 1.5:
        return "BREACH"

    if maximum >= 1.0:
        return "WARNING"

    if maximum >= 0.75:
        return "WATCH"

    return "NORMAL"


def determine_overall_severity(row: pd.Series) -> str:

    utilization_level = utilization_severity(
        safe_float(row["monitor_utilization"])
    )

    adjustment_level = adjustment_severity(row)

    day66_status = str(
        row.get("risk_budget_status", "")
    ).upper()

    day66_action = str(
        row.get("risk_budget_action", "")
    ).upper()

    levels = [
        utilization_level,
        adjustment_level,
    ]

    if (
        "BREACH" in day66_status
        or "EXCEEDED" in day66_status
        or "OVER" in day66_status
    ):
        levels.append("BREACH")

    if (
        "REDUCE" in day66_action
        or "SCALE" in day66_action
    ):
        levels.append("WARNING")

    return max(
        levels,
        key=severity_rank,
    )


# =============================================================================
# ALERT REASONS
# =============================================================================

def build_alert_reason(row: pd.Series) -> str:

    reasons: list[str] = []

    utilization = safe_float(
        row["monitor_utilization"]
    )

    if utilization >= CRITICAL_UTILIZATION:
        reasons.append(
            "risk budget utilization >= 120%"
        )

    elif utilization > BREACH_UTILIZATION:
        reasons.append(
            "risk budget exceeded"
        )

    elif utilization >= WARNING_UTILIZATION:
        reasons.append(
            "risk budget near limit"
        )

    elif utilization >= WATCH_UTILIZATION:
        reasons.append(
            "risk budget utilization elevated"
        )

    if (
        safe_float(row["absolute_capital_adjustment"])
        >= LARGE_CAPITAL_ADJUSTMENT
    ):
        reasons.append(
            "large capital-weight adjustment"
        )

    if (
        safe_float(row["absolute_gross_adjustment"])
        >= LARGE_GROSS_ADJUSTMENT
    ):
        reasons.append(
            "large gross-exposure adjustment"
        )

    if (
        safe_float(row["absolute_notional_adjustment"])
        >= LARGE_NOTIONAL_ADJUSTMENT
    ):
        reasons.append(
            "large signed-notional adjustment"
        )

    if (
        safe_float(row["absolute_risk_adjustment"])
        >= LARGE_RISK_ADJUSTMENT
    ):
        reasons.append(
            "large risk-weight adjustment"
        )

    status = str(
        row.get("risk_budget_status", "")
    ).strip()

    action = str(
        row.get("risk_budget_action", "")
    ).strip()

    if (
        status
        and status.upper()
        not in {
            "WITHIN_BUDGET",
            "UNCHANGED",
            "OK",
            "NORMAL",
        }
    ):
        reasons.append(
            f"Day 66 status: {status}"
        )

    if (
        action
        and action.upper()
        not in {
            "UNCHANGED",
            "NONE",
            "NO_ACTION",
        }
    ):
        reasons.append(
            f"Day 66 action: {action}"
        )

    if not reasons:
        return "Within monitoring thresholds"

    return "; ".join(dict.fromkeys(reasons))


# =============================================================================
# INSTRUMENT MONITOR
# =============================================================================

def build_instrument_monitor(
    df: pd.DataFrame,
) -> pd.DataFrame:

    monitor = prepare_monitor_metrics(df)

    monitor["alert_severity"] = monitor.apply(
        determine_overall_severity,
        axis=1,
    )

    monitor["alert_rank"] = (
        monitor["alert_severity"]
        .map(severity_rank)
        .fillna(0)
        .astype(int)
    )

    monitor["alert_reason"] = monitor.apply(
        build_alert_reason,
        axis=1,
    )

    monitor["requires_review"] = (
        monitor["alert_rank"] >= 2
    )

    monitor["budget_breach_flag"] = (
        monitor["monitor_utilization"]
        > BREACH_UTILIZATION
    )

    monitor["near_budget_flag"] = (
        (
            monitor["monitor_utilization"]
            >= WARNING_UTILIZATION
        )
        &
        (
            monitor["monitor_utilization"]
            <= BREACH_UTILIZATION
        )
    )

    monitor["watch_flag"] = (
        (
            monitor["monitor_utilization"]
            >= WATCH_UTILIZATION
        )
        &
        (
            monitor["monitor_utilization"]
            < WARNING_UTILIZATION
        )
    )

    monitor["large_adjustment_flag"] = (
        (
            monitor["absolute_capital_adjustment"]
            >= LARGE_CAPITAL_ADJUSTMENT
        )
        |
        (
            monitor["absolute_gross_adjustment"]
            >= LARGE_GROSS_ADJUSTMENT
        )
        |
        (
            monitor["absolute_notional_adjustment"]
            >= LARGE_NOTIONAL_ADJUSTMENT
        )
        |
        (
            monitor["absolute_risk_adjustment"]
            >= LARGE_RISK_ADJUSTMENT
        )
    )

    monitor = monitor.sort_values(
        [
            "alert_rank",
            "monitor_utilization",
            "risk_budgeted_abs_risk",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    ).reset_index(drop=True)

    return monitor


# =============================================================================
# ALERT TABLE
# =============================================================================

def build_alert_table(
    monitor: pd.DataFrame,
) -> pd.DataFrame:

    alerts = monitor.loc[
        monitor["alert_severity"] != "NORMAL"
    ].copy()

    desired_columns = [
        "monitor_symbol",
        "monitor_asset_class",
        "monitor_instrument_type",
        "alert_severity",
        "alert_rank",
        "alert_reason",
        "monitor_utilization",
        "utilization_percent",
        "risk_budget_gap",
        "risk_budget_excess",
        "risk_budget_scaler",
        "risk_budgeted_capital_weight",
        "risk_budgeted_gross_exposure_weight",
        "risk_budgeted_signed_notional_weight",
        "risk_budgeted_risk_weight",
        "capital_weight_adjustment",
        "gross_exposure_adjustment",
        "signed_notional_adjustment",
        "risk_weight_adjustment",
        "risk_budget_status",
        "risk_budget_action",
        "requires_review",
    ]

    available = [
        column
        for column in desired_columns
        if column in alerts.columns
    ]

    alerts = alerts[available]

    return alerts.reset_index(drop=True)


# =============================================================================
# ASSET-CLASS MONITOR
# =============================================================================

def build_asset_class_monitor(
    monitor: pd.DataFrame,
) -> pd.DataFrame:

    records: list[dict[str, Any]] = []

    grouped = monitor.groupby(
        "monitor_asset_class",
        dropna=False,
    )

    for asset_class, group in grouped:

        instrument_count = len(group)

        capital_weight = (
            group["risk_budgeted_capital_weight"]
            .fillna(0.0)
            .sum()
        )

        gross_weight = (
            group["risk_budgeted_gross_exposure_weight"]
            .fillna(0.0)
            .sum()
        )

        signed_notional = (
            group["risk_budgeted_signed_notional_weight"]
            .fillna(0.0)
            .sum()
        )

        absolute_notional = (
            group["risk_budgeted_signed_notional_weight"]
            .fillna(0.0)
            .abs()
            .sum()
        )

        risk_weight = (
            group["risk_budgeted_risk_weight"]
            .fillna(0.0)
            .sum()
        )

        absolute_risk = (
            group["risk_budgeted_risk_weight"]
            .fillna(0.0)
            .abs()
            .sum()
        )

        maximum_utilization = (
            group["monitor_utilization"]
            .replace(
                [np.inf, -np.inf],
                np.nan,
            )
            .max()
        )

        mean_utilization = (
            group["monitor_utilization"]
            .replace(
                [np.inf, -np.inf],
                np.nan,
            )
            .mean()
        )

        alerts = (
            group["alert_severity"] != "NORMAL"
        ).sum()

        warnings = (
            group["alert_severity"]
            .isin(
                [
                    "WARNING",
                    "BREACH",
                    "CRITICAL",
                ]
            )
        ).sum()

        breaches = (
            group["alert_severity"]
            .isin(
                [
                    "BREACH",
                    "CRITICAL",
                ]
            )
        ).sum()

        highest_rank = (
            group["alert_rank"].max()
            if len(group)
            else 0
        )

        reverse_map = {
            0: "NORMAL",
            1: "WATCH",
            2: "WARNING",
            3: "BREACH",
            4: "CRITICAL",
        }

        records.append(
            {
                "asset_class": asset_class,
                "instrument_count": instrument_count,
                "risk_budgeted_capital_weight": capital_weight,
                "risk_budgeted_gross_exposure_weight": gross_weight,
                "risk_budgeted_signed_notional_weight": signed_notional,
                "risk_budgeted_absolute_notional_weight": absolute_notional,
                "risk_budgeted_risk_weight": risk_weight,
                "risk_budgeted_absolute_risk_weight": absolute_risk,
                "mean_risk_budget_utilization": mean_utilization,
                "maximum_risk_budget_utilization": maximum_utilization,
                "alert_count": int(alerts),
                "warning_or_higher_count": int(warnings),
                "breach_or_higher_count": int(breaches),
                "highest_alert_severity": reverse_map.get(
                    int(highest_rank),
                    "WATCH",
                ),
            }
        )

    result = pd.DataFrame(records)

    if result.empty:
        return result

    total_abs_risk = (
        result[
            "risk_budgeted_absolute_risk_weight"
        ].sum()
    )

    if total_abs_risk > EPSILON:
        result["portfolio_risk_share"] = (
            result[
                "risk_budgeted_absolute_risk_weight"
            ]
            / total_abs_risk
        )
    else:
        result["portfolio_risk_share"] = 0.0

    result["concentration_flag"] = (
        result["portfolio_risk_share"]
        > HIGH_ASSET_CLASS_SHARE
    )

    result = result.sort_values(
        [
            "breach_or_higher_count",
            "portfolio_risk_share",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)

    return result


# =============================================================================
# PORTFOLIO DASHBOARD
# =============================================================================

def build_portfolio_dashboard(
    monitor: pd.DataFrame,
    asset_monitor: pd.DataFrame,
) -> pd.DataFrame:

    total_instruments = len(monitor)

    normal_count = int(
        (
            monitor["alert_severity"]
            == "NORMAL"
        ).sum()
    )

    watch_count = int(
        (
            monitor["alert_severity"]
            == "WATCH"
        ).sum()
    )

    warning_count = int(
        (
            monitor["alert_severity"]
            == "WARNING"
        ).sum()
    )

    breach_count = int(
        (
            monitor["alert_severity"]
            == "BREACH"
        ).sum()
    )

    critical_count = int(
        (
            monitor["alert_severity"]
            == "CRITICAL"
        ).sum()
    )

    review_count = int(
        monitor["requires_review"].sum()
    )

    maximum_utilization = safe_float(
        monitor["monitor_utilization"].max()
    )

    mean_utilization = safe_float(
        monitor["monitor_utilization"].mean()
    )

    capital_total = safe_float(
        monitor[
            "risk_budgeted_capital_weight"
        ].sum()
    )

    gross_total = safe_float(
        monitor[
            "risk_budgeted_gross_exposure_weight"
        ].sum()
    )

    signed_notional_total = safe_float(
        monitor[
            "risk_budgeted_signed_notional_weight"
        ].sum()
    )

    absolute_notional_total = safe_float(
        monitor[
            "risk_budgeted_signed_notional_weight"
        ].abs().sum()
    )

    risk_total = safe_float(
        monitor[
            "risk_budgeted_risk_weight"
        ].sum()
    )

    absolute_risk_total = safe_float(
        monitor[
            "risk_budgeted_risk_weight"
        ].abs().sum()
    )

    largest_risk_share = 0.0
    largest_risk_asset_class = ""

    if not asset_monitor.empty:

        idx = (
            asset_monitor["portfolio_risk_share"]
            .idxmax()
        )

        largest_risk_share = safe_float(
            asset_monitor.loc[
                idx,
                "portfolio_risk_share",
            ]
        )

        largest_risk_asset_class = str(
            asset_monitor.loc[
                idx,
                "asset_class",
            ]
        )

    if critical_count > 0:
        portfolio_status = "CRITICAL"

    elif breach_count > 0:
        portfolio_status = "BREACH"

    elif warning_count > 0:
        portfolio_status = "WARNING"

    elif watch_count > 0:
        portfolio_status = "WATCH"

    else:
        portfolio_status = "NORMAL"

    dashboard = pd.DataFrame(
        [
            {
                "portfolio_status": portfolio_status,
                "instrument_count": total_instruments,
                "normal_count": normal_count,
                "watch_count": watch_count,
                "warning_count": warning_count,
                "breach_count": breach_count,
                "critical_count": critical_count,
                "requires_review_count": review_count,
                "mean_risk_budget_utilization": mean_utilization,
                "maximum_risk_budget_utilization": maximum_utilization,
                "risk_budgeted_capital_weight_total": capital_total,
                "risk_budgeted_gross_exposure_weight_total": gross_total,
                "risk_budgeted_signed_notional_weight_total": signed_notional_total,
                "risk_budgeted_absolute_notional_weight_total": absolute_notional_total,
                "risk_budgeted_risk_weight_total": risk_total,
                "risk_budgeted_absolute_risk_weight_total": absolute_risk_total,
                "largest_asset_class_risk_share": largest_risk_share,
                "largest_asset_class_by_risk": largest_risk_asset_class,
            }
        ]
    )

    return dashboard


# =============================================================================
# VALIDATION
# =============================================================================

def validation_record(
    check: str,
    passed: bool,
    detail: str,
) -> dict[str, Any]:

    return {
        "check": check,
        "passed": bool(passed),
        "detail": detail,
    }


def run_validation(
    source: pd.DataFrame,
    monitor: pd.DataFrame,
    asset_monitor: pd.DataFrame,
    alerts: pd.DataFrame,
    dashboard: pd.DataFrame,
) -> pd.DataFrame:

    checks: list[dict[str, Any]] = []

    checks.append(
        validation_record(
            "Day 66 source loaded",
            len(source) > 0,
            f"Rows: {len(source)}",
        )
    )

    checks.append(
        validation_record(
            "Instrument count preserved",
            len(source) == len(monitor),
            (
                f"Day 66 rows: {len(source)}; "
                f"Day 67 rows: {len(monitor)}"
            ),
        )
    )

    unique_symbols = (
        monitor["monitor_symbol"]
        .astype(str)
        .nunique()
    )

    checks.append(
        validation_record(
            "Instrument identifiers remain unique",
            unique_symbols == len(monitor),
            (
                f"Unique identifiers: "
                f"{unique_symbols}; "
                f"rows: {len(monitor)}"
            ),
        )
    )

    finite_utilization = np.isfinite(
        monitor["monitor_utilization"]
        .fillna(0.0)
        .to_numpy(dtype=float)
    ).all()

    checks.append(
        validation_record(
            "Risk utilization values are finite",
            bool(finite_utilization),
            "Instrument utilization checked.",
        )
    )

    valid_severities = {
        "NORMAL",
        "WATCH",
        "WARNING",
        "BREACH",
        "CRITICAL",
    }

    severity_ok = (
        monitor["alert_severity"]
        .isin(valid_severities)
        .all()
    )

    checks.append(
        validation_record(
            "Alert severities are valid",
            bool(severity_ok),
            (
                "Allowed: NORMAL, WATCH, "
                "WARNING, BREACH, CRITICAL."
            ),
        )
    )

    alert_reconciliation = (
        len(alerts)
        ==
        int(
            (
                monitor["alert_severity"]
                != "NORMAL"
            ).sum()
        )
    )

    checks.append(
        validation_record(
            "Alert table reconciles",
            alert_reconciliation,
            (
                f"Alert rows: {len(alerts)}"
            ),
        )
    )

    asset_count = (
        monitor["monitor_asset_class"]
        .nunique(dropna=False)
    )

    checks.append(
        validation_record(
            "Asset-class monitor generated",
            (
                len(asset_monitor)
                == asset_count
            ),
            (
                f"Asset classes: {asset_count}; "
                f"monitor rows: {len(asset_monitor)}"
            ),
        )
    )

    dashboard_ok = len(dashboard) == 1

    checks.append(
        validation_record(
            "Portfolio dashboard generated",
            dashboard_ok,
            f"Rows: {len(dashboard)}",
        )
    )

    if len(monitor):

        severity_consistency = (
            (
                monitor[
                    "monitor_utilization"
                ]
                >= CRITICAL_UTILIZATION
            )
            <=
            (
                monitor[
                    "alert_severity"
                ]
                == "CRITICAL"
            )
        ).all()

    else:
        severity_consistency = True

    checks.append(
        validation_record(
            "Critical utilization produces critical alert",
            bool(severity_consistency),
            (
                f"Critical threshold: "
                f"{CRITICAL_UTILIZATION:.0%}"
            ),
        )
    )

    finite_budgeted_weights = True

    for column in [
        "risk_budgeted_capital_weight",
        "risk_budgeted_gross_exposure_weight",
        "risk_budgeted_signed_notional_weight",
        "risk_budgeted_risk_weight",
    ]:

        values = (
            monitor[column]
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        if not np.isfinite(values).all():
            finite_budgeted_weights = False

    checks.append(
        validation_record(
            "Risk-budgeted portfolio weights are finite",
            finite_budgeted_weights,
            (
                "Capital, gross, signed-notional "
                "and risk weights checked."
            ),
        )
    )

    validation = pd.DataFrame(checks)

    passed_tests = int(
        validation["passed"].sum()
    )

    total_tests = len(validation)

    pass_rate = (
        passed_tests / total_tests
        if total_tests
        else 0.0
    )

    validation["passed_tests"] = passed_tests
    validation["total_tests"] = total_tests
    validation["pass_rate"] = pass_rate

    return validation


# =============================================================================
# REPORTING
# =============================================================================

def print_report(
    monitor: pd.DataFrame,
    asset_monitor: pd.DataFrame,
    alerts: pd.DataFrame,
    dashboard: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:

    print()
    print("=" * 78)
    print("VITTANTRA — DAY 67 PORTFOLIO RISK MONITOR")
    print("=" * 78)

    print()
    print("Architecture:")
    print(
        "Day 65 Exposure-Aware Portfolio "
        "-> Day 66 Risk Budgeting "
        "-> Day 67 Risk Monitoring "
        "-> Alerts -> Dashboard -> Validation"
    )

    print()
    print("PORTFOLIO STATUS")
    print("-" * 78)

    if not dashboard.empty:

        row = dashboard.iloc[0]

        print(
            f"Status: "
            f"{row['portfolio_status']}"
        )

        print(
            f"Instruments monitored: "
            f"{int(row['instrument_count'])}"
        )

        print(
            f"Normal: {int(row['normal_count'])} | "
            f"Watch: {int(row['watch_count'])} | "
            f"Warning: {int(row['warning_count'])} | "
            f"Breach: {int(row['breach_count'])} | "
            f"Critical: {int(row['critical_count'])}"
        )

        print(
            f"Mean budget utilization: "
            f"{row['mean_risk_budget_utilization']:.2%}"
        )

        print(
            f"Maximum budget utilization: "
            f"{row['maximum_risk_budget_utilization']:.2%}"
        )

        print(
            f"Risk-budgeted capital total: "
            f"{row['risk_budgeted_capital_weight_total']:.2%}"
        )

        print(
            f"Risk-budgeted gross exposure: "
            f"{row['risk_budgeted_gross_exposure_weight_total']:.2%}"
        )

        print(
            f"Absolute notional exposure: "
            f"{row['risk_budgeted_absolute_notional_weight_total']:.2%}"
        )

        print(
            f"Largest asset-class risk share: "
            f"{row['largest_asset_class_risk_share']:.2%} "
            f"({row['largest_asset_class_by_risk']})"
        )

    print()
    print("INSTRUMENT MONITOR")
    print("-" * 78)

    display_columns = [
        "monitor_symbol",
        "monitor_asset_class",
        "monitor_utilization",
        "alert_severity",
        "risk_budget_action",
        "alert_reason",
    ]

    available = [
        column
        for column in display_columns
        if column in monitor.columns
    ]

    if monitor.empty:
        print("No instruments.")

    else:
        print(
            monitor[available]
            .to_string(index=False)
        )

    print()
    print("ASSET-CLASS RISK MONITOR")
    print("-" * 78)

    asset_display = [
        "asset_class",
        "instrument_count",
        "portfolio_risk_share",
        "mean_risk_budget_utilization",
        "maximum_risk_budget_utilization",
        "alert_count",
        "highest_alert_severity",
        "concentration_flag",
    ]

    asset_available = [
        column
        for column in asset_display
        if column in asset_monitor.columns
    ]

    if asset_monitor.empty:
        print("No asset-class data.")

    else:
        print(
            asset_monitor[asset_available]
            .to_string(index=False)
        )

    print()
    print("ACTIVE ALERTS")
    print("-" * 78)

    if alerts.empty:
        print(
            "No WATCH/WARNING/BREACH/CRITICAL "
            "alerts generated."
        )

    else:

        alert_display = [
            "monitor_symbol",
            "monitor_asset_class",
            "alert_severity",
            "utilization_percent",
            "alert_reason",
        ]

        alert_available = [
            column
            for column in alert_display
            if column in alerts.columns
        ]

        print(
            alerts[alert_available]
            .to_string(index=False)
        )

    print()
    print("VALIDATION")
    print("-" * 78)

    for _, row in validation.iterrows():

        print(
            f"{bool_text(bool(row['passed'])):4} | "
            f"{row['check']} | "
            f"{row['detail']}"
        )

    if not validation.empty:

        passed = int(
            validation["passed_tests"].iloc[0]
        )

        total = int(
            validation["total_tests"].iloc[0]
        )

        rate = safe_float(
            validation["pass_rate"].iloc[0]
        )

        print()
        print(
            f"Validation: "
            f"{passed}/{total} passed "
            f"({rate:.2%})"
        )

    print()
    print("Files generated:")
    print(f"  {OUTPUT_INSTRUMENT_MONITOR}")
    print(f"  {OUTPUT_ASSET_CLASS_MONITOR}")
    print(f"  {OUTPUT_ALERTS}")
    print(f"  {OUTPUT_PORTFOLIO_DASHBOARD}")
    print(f"  {OUTPUT_VALIDATION}")

    print()
    print(
        "Important: Day 67 alerts are research "
        "monitoring outputs. They are not automatic "
        "trade instructions."
    )

    print()
    print(
        "Day 67 portfolio risk monitoring complete."
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
            "VITTANTRA — DAY 67 "
            "PORTFOLIO RISK MONITORING & ALERT ENGINE"
        )
        print("=" * 78)

        print()
        print(
            f"Loading: {DAY66_INSTRUMENT_FILE}"
        )

        source = load_day66_instrument_budgets()

        # Optional Day 66 files are loaded so that the
        # monitoring architecture can later be expanded
        # without modifying the Day 66 engine.
        _asset_source = load_optional_csv(
            DAY66_ASSET_CLASS_FILE
        )

        _portfolio_source = load_optional_csv(
            DAY66_PORTFOLIO_FILE
        )

        _breach_source = load_optional_csv(
            DAY66_BREACH_FILE
        )

        monitor = build_instrument_monitor(
            source
        )

        alerts = build_alert_table(
            monitor
        )

        asset_monitor = build_asset_class_monitor(
            monitor
        )

        dashboard = build_portfolio_dashboard(
            monitor,
            asset_monitor,
        )

        validation = run_validation(
            source,
            monitor,
            asset_monitor,
            alerts,
            dashboard,
        )

        monitor.to_csv(
            OUTPUT_INSTRUMENT_MONITOR,
            index=False,
        )

        asset_monitor.to_csv(
            OUTPUT_ASSET_CLASS_MONITOR,
            index=False,
        )

        alerts.to_csv(
            OUTPUT_ALERTS,
            index=False,
        )

        dashboard.to_csv(
            OUTPUT_PORTFOLIO_DASHBOARD,
            index=False,
        )

        validation.to_csv(
            OUTPUT_VALIDATION,
            index=False,
        )

        print_report(
            monitor,
            asset_monitor,
            alerts,
            dashboard,
            validation,
        )

    except Exception as exc:

        print()
        print("=" * 78)
        print("DAY 67 FAILED")
        print("=" * 78)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "No Day 67 conclusions should be drawn "
            "from an incomplete run."
        )

        print("=" * 78)

        raise


if __name__ == "__main__":
    main()