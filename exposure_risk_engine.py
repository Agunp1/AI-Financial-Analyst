"""
Vittantra - Exposure Risk Engine

Purpose
-------
Build an exposure-aware risk layer on top of the Day 63 portfolio.

This module does NOT modify Day 63 files.

It separates:
1. Capital / market-value exposure
2. Derivative notional exposure
3. Gross and net economic exposure
4. Risk-adjusted exposure
5. Concentration-policy diagnostics

Important
---------
This is a research/risk analytics engine, not an execution engine.
Derivative assumptions are explicit and should eventually be replaced
with contract-level metadata.
"""

from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("day63_current_portfolio.csv")

OUTPUT_EXPOSURE_FILE = Path("day64_instrument_exposures.csv")
OUTPUT_ASSET_CLASS_FILE = Path("day64_asset_class_exposures.csv")
OUTPUT_PORTFOLIO_FILE = Path("day64_portfolio_exposure_summary.csv")
OUTPUT_LIMIT_FILE = Path("day64_concentration_checks.csv")
OUTPUT_VALIDATION_FILE = Path("day64_validation_summary.csv")


MAX_CAPITAL_WEIGHT = 0.25
MAX_SINGLE_NAME_NOTIONAL_WEIGHT = 0.75
MAX_SINGLE_NAME_RISK_WEIGHT = 0.35

EPSILON = 1e-12


# ============================================================
# DEFAULT INSTRUMENT ASSUMPTIONS
# ============================================================

# These are transparent research assumptions.
# Later we can replace them with contract/security master data.

DEFAULTS = {
    "Equity": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 1.00,
    },
    "ETF/Fund": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.90,
    },
    "Commodity": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.85,
    },
    "Fixed Income": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.35,
    },
    "Real Estate/REIT": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.90,
    },
    "Crypto": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 1.80,
    },
    "FX": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.55,
    },
    "Cash/Money Market": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 0.05,
    },

    # Futures are handled differently.
    #
    # The Day 63 market_value for a future is treated as economic
    # notional rather than fully funded cash capital.
    #
    # 10% is only a transparent research approximation for
    # capital/margin usage until contract-level margin metadata
    # is introduced.
    "Future": {
        "capital_factor": 0.10,
        "notional_factor": 1.00,
        "risk_multiplier": 1.00,
    },

    # Option market value is capital at risk for a long option,
    # while economic exposure may differ materially.
    # Until delta/contract multiplier information is available,
    # we retain a conservative placeholder notional relationship.
    "Option": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 1.25,
    },

    "Unknown": {
        "capital_factor": 1.00,
        "notional_factor": 1.00,
        "risk_multiplier": 1.00,
    },
}


# Symbol-specific overrides.
#
# ES is explicitly recognized as an equity-index future.
# We preserve the Day 63 $300,000 economic exposure but do not
# interpret all $300,000 as funded portfolio capital.

SYMBOL_OVERRIDES = {
    "ES": {
        "instrument_type": "Future",
        "capital_factor": 0.10,
        "notional_factor": 1.00,
        "risk_multiplier": 1.00,
    }
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def normalize_asset_class(value: str) -> str:
    raw = clean_text(value)

    if not raw:
        return "Unknown"

    mapping = {
        "equity": "Equity",
        "stock": "Equity",
        "stocks": "Equity",

        "etf": "ETF/Fund",
        "fund": "ETF/Fund",
        "etf/fund": "ETF/Fund",

        "commodity": "Commodity",
        "commodities": "Commodity",

        "fixed income": "Fixed Income",
        "bond": "Fixed Income",
        "bonds": "Fixed Income",

        "real estate": "Real Estate/REIT",
        "reit": "Real Estate/REIT",
        "real estate/reit": "Real Estate/REIT",

        "crypto": "Crypto",
        "cryptocurrency": "Crypto",

        "fx": "FX",
        "forex": "FX",
        "foreign exchange": "FX",

        "cash": "Cash/Money Market",
        "money market": "Cash/Money Market",
        "cash/money market": "Cash/Money Market",

        "future": "Future",
        "futures": "Future",

        "option": "Option",
        "options": "Option",
    }

    return mapping.get(raw.lower(), raw)


def required_columns_exist(
    df: pd.DataFrame,
    required_columns: list[str],
) -> None:

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            "Missing required columns: "
            + ", ".join(missing)
            + "\nAvailable columns: "
            + ", ".join(df.columns)
        )


# ============================================================
# LOAD DAY 63 PORTFOLIO
# ============================================================

def load_portfolio() -> pd.DataFrame:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Required input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns_exist(
        df,
        [
            "symbol",
            "asset_class",
            "market_value",
        ],
    )

    df = df.copy()

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["asset_class"] = (
        df["asset_class"]
        .apply(normalize_asset_class)
    )

    df["market_value"] = pd.to_numeric(
        df["market_value"],
        errors="coerce",
    ).fillna(0.0)

    if "current_weight" in df.columns:
        df["day63_current_weight"] = pd.to_numeric(
            df["current_weight"],
            errors="coerce",
        )
    else:
        df["day63_current_weight"] = np.nan

    return df


# ============================================================
# INSTRUMENT CLASSIFICATION
# ============================================================

def get_assumptions(
    symbol: str,
    asset_class: str,
) -> dict:

    symbol = clean_text(symbol).upper()
    asset_class = normalize_asset_class(asset_class)

    base = DEFAULTS.get(
        asset_class,
        DEFAULTS["Unknown"],
    ).copy()

    instrument_type = asset_class

    override = SYMBOL_OVERRIDES.get(symbol)

    if override:
        instrument_type = override.get(
            "instrument_type",
            instrument_type,
        )

        for key in [
            "capital_factor",
            "notional_factor",
            "risk_multiplier",
        ]:
            if key in override:
                base[key] = override[key]

    base["instrument_type"] = instrument_type

    return base


# ============================================================
# EXPOSURE CALCULATION
# ============================================================

def calculate_instrument_exposures(
    portfolio: pd.DataFrame,
) -> pd.DataFrame:

    df = portfolio.copy()

    instrument_types = []
    capital_factors = []
    notional_factors = []
    risk_multipliers = []

    for _, row in df.iterrows():

        assumptions = get_assumptions(
            row["symbol"],
            row["asset_class"],
        )

        instrument_types.append(
            assumptions["instrument_type"]
        )

        capital_factors.append(
            safe_float(
                assumptions["capital_factor"],
                1.0,
            )
        )

        notional_factors.append(
            safe_float(
                assumptions["notional_factor"],
                1.0,
            )
        )

        risk_multipliers.append(
            safe_float(
                assumptions["risk_multiplier"],
                1.0,
            )
        )

    df["instrument_type"] = instrument_types
    df["capital_factor"] = capital_factors
    df["notional_factor"] = notional_factors
    df["risk_multiplier"] = risk_multipliers

    # --------------------------------------------------------
    # CAPITAL EXPOSURE
    # --------------------------------------------------------

    df["capital_exposure"] = (
        df["market_value"].abs()
        * df["capital_factor"]
    )

    # --------------------------------------------------------
    # ECONOMIC / NOTIONAL EXPOSURE
    # --------------------------------------------------------

    df["signed_notional_exposure"] = (
        df["market_value"]
        * df["notional_factor"]
    )

    df["gross_notional_exposure"] = (
        df["signed_notional_exposure"].abs()
    )

    # --------------------------------------------------------
    # RISK-ADJUSTED EXPOSURE
    # --------------------------------------------------------

    df["risk_exposure"] = (
        df["gross_notional_exposure"]
        * df["risk_multiplier"]
    )

    total_capital = df["capital_exposure"].sum()
    total_gross = df["gross_notional_exposure"].sum()
    total_risk = df["risk_exposure"].sum()

    # --------------------------------------------------------
    # WEIGHTS
    # --------------------------------------------------------

    if total_capital > EPSILON:
        df["capital_weight"] = (
            df["capital_exposure"]
            / total_capital
        )
    else:
        df["capital_weight"] = 0.0

    if total_gross > EPSILON:
        df["gross_exposure_weight"] = (
            df["gross_notional_exposure"]
            / total_gross
        )

        df["signed_notional_weight"] = (
            df["signed_notional_exposure"]
            / total_gross
        )
    else:
        df["gross_exposure_weight"] = 0.0
        df["signed_notional_weight"] = 0.0

    if total_risk > EPSILON:
        df["risk_weight"] = (
            df["risk_exposure"]
            / total_risk
        )
    else:
        df["risk_weight"] = 0.0

    # Convenience alias requested by architecture.
    df["notional_weight"] = (
        df["gross_exposure_weight"]
    )

    # Difference between old Day 63 interpretation and
    # the new capital-based interpretation.

    df["capital_weight_minus_day63_weight"] = (
        df["capital_weight"]
        - df["day63_current_weight"].fillna(0.0)
    )

    return df


# ============================================================
# PORTFOLIO EXPOSURE SUMMARY
# ============================================================

def build_portfolio_summary(
    exposures: pd.DataFrame,
) -> pd.DataFrame:

    total_market_value = (
        exposures["market_value"].sum()
    )

    total_capital = (
        exposures["capital_exposure"].sum()
    )

    gross_exposure = (
        exposures["gross_notional_exposure"].sum()
    )

    net_exposure = (
        exposures["signed_notional_exposure"].sum()
    )

    total_risk_exposure = (
        exposures["risk_exposure"].sum()
    )

    leverage_on_capital = (
        gross_exposure / total_capital
        if total_capital > EPSILON
        else np.nan
    )

    net_to_gross = (
        net_exposure / gross_exposure
        if gross_exposure > EPSILON
        else np.nan
    )

    derivative_mask = (
        exposures["instrument_type"]
        .isin(["Future", "Option"])
    )

    derivative_gross = (
        exposures.loc[
            derivative_mask,
            "gross_notional_exposure",
        ].sum()
    )

    derivative_share_of_gross = (
        derivative_gross / gross_exposure
        if gross_exposure > EPSILON
        else np.nan
    )

    summary = pd.DataFrame(
        [
            {
                "portfolio_market_value_field_total":
                    total_market_value,

                "estimated_capital_exposure":
                    total_capital,

                "gross_notional_exposure":
                    gross_exposure,

                "net_notional_exposure":
                    net_exposure,

                "risk_adjusted_exposure":
                    total_risk_exposure,

                "gross_leverage_on_estimated_capital":
                    leverage_on_capital,

                "net_to_gross_ratio":
                    net_to_gross,

                "derivative_gross_exposure":
                    derivative_gross,

                "derivative_share_of_gross":
                    derivative_share_of_gross,

                "instrument_count":
                    len(exposures),
            }
        ]
    )

    return summary


# ============================================================
# ASSET-CLASS EXPOSURES
# ============================================================

def build_asset_class_summary(
    exposures: pd.DataFrame,
) -> pd.DataFrame:

    grouped = (
        exposures
        .groupby(
            "asset_class",
            as_index=False,
            dropna=False,
        )
        .agg(
            instrument_count=("symbol", "count"),
            raw_market_value=("market_value", "sum"),
            capital_exposure=("capital_exposure", "sum"),
            signed_notional_exposure=(
                "signed_notional_exposure",
                "sum",
            ),
            gross_notional_exposure=(
                "gross_notional_exposure",
                "sum",
            ),
            risk_exposure=("risk_exposure", "sum"),
        )
    )

    capital_total = grouped[
        "capital_exposure"
    ].sum()

    gross_total = grouped[
        "gross_notional_exposure"
    ].sum()

    risk_total = grouped[
        "risk_exposure"
    ].sum()

    grouped["capital_weight"] = (
        grouped["capital_exposure"]
        / capital_total
        if capital_total > EPSILON
        else 0.0
    )

    grouped["gross_exposure_weight"] = (
        grouped["gross_notional_exposure"]
        / gross_total
        if gross_total > EPSILON
        else 0.0
    )

    grouped["risk_weight"] = (
        grouped["risk_exposure"]
        / risk_total
        if risk_total > EPSILON
        else 0.0
    )

    grouped = grouped.sort_values(
        "gross_exposure_weight",
        ascending=False,
    ).reset_index(drop=True)

    return grouped


# ============================================================
# CONCENTRATION POLICY
# ============================================================

def build_concentration_checks(
    exposures: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for _, row in exposures.iterrows():

        instrument_type = row["instrument_type"]

        capital_weight = safe_float(
            row["capital_weight"]
        )

        notional_weight = safe_float(
            row["notional_weight"]
        )

        risk_weight = safe_float(
            row["risk_weight"]
        )

        # ----------------------------------------------------
        # Capital concentration
        # ----------------------------------------------------
        #
        # For fully funded securities, the 25% policy applies.
        #
        # Derivatives are not judged solely by the raw Day 63
        # market-value weight because that confuses notional
        # exposure with funded capital.

        if instrument_type in ["Future", "Option"]:
            capital_policy_applicable = False
            capital_pass = True
            capital_reason = (
                "Derivative: capital concentration is "
                "reported separately from notional exposure."
            )
        else:
            capital_policy_applicable = True

            capital_pass = (
                capital_weight
                <= MAX_CAPITAL_WEIGHT + EPSILON
            )

            capital_reason = (
                f"Capital weight {capital_weight:.4%}; "
                f"limit {MAX_CAPITAL_WEIGHT:.4%}."
            )

        # ----------------------------------------------------
        # Notional concentration
        # ----------------------------------------------------

        notional_pass = (
            notional_weight
            <= MAX_SINGLE_NAME_NOTIONAL_WEIGHT
            + EPSILON
        )

        # ----------------------------------------------------
        # Risk concentration
        # ----------------------------------------------------

        risk_pass = (
            risk_weight
            <= MAX_SINGLE_NAME_RISK_WEIGHT
            + EPSILON
        )

        rows.append(
            {
                "symbol": row["symbol"],
                "asset_class": row["asset_class"],
                "instrument_type": instrument_type,

                "capital_weight":
                    capital_weight,

                "capital_limit":
                    MAX_CAPITAL_WEIGHT,

                "capital_policy_applicable":
                    capital_policy_applicable,

                "capital_limit_passed":
                    capital_pass,

                "capital_policy_details":
                    capital_reason,

                "notional_weight":
                    notional_weight,

                "notional_limit":
                    MAX_SINGLE_NAME_NOTIONAL_WEIGHT,

                "notional_limit_passed":
                    notional_pass,

                "risk_weight":
                    risk_weight,

                "risk_limit":
                    MAX_SINGLE_NAME_RISK_WEIGHT,

                "risk_limit_passed":
                    risk_pass,

                "overall_passed":
                    bool(
                        capital_pass
                        and notional_pass
                        and risk_pass
                    ),
            }
        )

    return pd.DataFrame(rows)


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


def build_validation_summary(
    exposures: pd.DataFrame,
    asset_classes: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    concentration: pd.DataFrame,
) -> pd.DataFrame:

    checks = []

    # --------------------------------------------------------
    # 1. Instrument rows generated
    # --------------------------------------------------------

    checks.append(
        validation_row(
            "Instrument exposure rows generated",
            len(exposures) > 0,
            f"Rows: {len(exposures)}",
        )
    )

    # --------------------------------------------------------
    # 2. Finite core calculations
    # --------------------------------------------------------

    numeric_columns = [
        "capital_exposure",
        "signed_notional_exposure",
        "gross_notional_exposure",
        "risk_exposure",
        "capital_weight",
        "gross_exposure_weight",
        "risk_weight",
    ]

    numeric_matrix = (
        exposures[numeric_columns]
        .apply(pd.to_numeric, errors="coerce")
        .to_numpy(dtype=float)
    )

    finite = np.isfinite(numeric_matrix).all()

    checks.append(
        validation_row(
            "Exposure calculations finite",
            finite,
            "Core exposure fields must contain finite values.",
        )
    )

    # --------------------------------------------------------
    # 3. Capital weights sum to 1
    # --------------------------------------------------------

    capital_sum = exposures[
        "capital_weight"
    ].sum()

    checks.append(
        validation_row(
            "Capital weights sum to one",
            np.isclose(
                capital_sum,
                1.0,
                atol=1e-8,
            ),
            f"Capital weight sum: {capital_sum:.8f}",
        )
    )

    # --------------------------------------------------------
    # 4. Gross weights sum to 1
    # --------------------------------------------------------

    gross_sum = exposures[
        "gross_exposure_weight"
    ].sum()

    checks.append(
        validation_row(
            "Gross exposure weights sum to one",
            np.isclose(
                gross_sum,
                1.0,
                atol=1e-8,
            ),
            f"Gross exposure weight sum: {gross_sum:.8f}",
        )
    )

    # --------------------------------------------------------
    # 5. Risk weights sum to 1
    # --------------------------------------------------------

    risk_sum = exposures[
        "risk_weight"
    ].sum()

    checks.append(
        validation_row(
            "Risk weights sum to one",
            np.isclose(
                risk_sum,
                1.0,
                atol=1e-8,
            ),
            f"Risk weight sum: {risk_sum:.8f}",
        )
    )

    # --------------------------------------------------------
    # 6. ES classified correctly
    # --------------------------------------------------------

    es = exposures[
        exposures["symbol"] == "ES"
    ]

    es_classified = (
        not es.empty
        and (
            es.iloc[0]["instrument_type"]
            == "Future"
        )
    )

    checks.append(
        validation_row(
            "ES recognized as future",
            es_classified,
            (
                "ES must be treated as derivative exposure "
                "rather than ordinary fully funded equity."
            ),
        )
    )

    # --------------------------------------------------------
    # 7. ES capital differs from notional
    # --------------------------------------------------------

    if not es.empty:

        es_capital = safe_float(
            es.iloc[0]["capital_exposure"]
        )

        es_notional = safe_float(
            es.iloc[0]["gross_notional_exposure"]
        )

        separated = (
            es_capital
            < es_notional
        )

        detail = (
            f"ES capital exposure: "
            f"${es_capital:,.2f}; "
            f"ES gross notional: "
            f"${es_notional:,.2f}"
        )

    else:
        separated = False
        detail = "ES not found."

    checks.append(
        validation_row(
            "Derivative capital and notional separated",
            separated,
            detail,
        )
    )

    # --------------------------------------------------------
    # 8. Asset-class summary generated
    # --------------------------------------------------------

    checks.append(
        validation_row(
            "Asset-class exposure summary generated",
            len(asset_classes) > 0,
            f"Rows: {len(asset_classes)}",
        )
    )

    # --------------------------------------------------------
    # 9. Portfolio summary generated
    # --------------------------------------------------------

    checks.append(
        validation_row(
            "Portfolio exposure summary generated",
            len(portfolio_summary) == 1,
            f"Rows: {len(portfolio_summary)}",
        )
    )

    # --------------------------------------------------------
    # 10. Concentration diagnostics generated
    # --------------------------------------------------------

    checks.append(
        validation_row(
            "Concentration diagnostics generated",
            len(concentration) == len(exposures),
            (
                f"Checks: {len(concentration)}; "
                f"instruments: {len(exposures)}"
            ),
        )
    )

    # --------------------------------------------------------
    # 11. Fully funded capital policy
    # --------------------------------------------------------

    applicable = concentration[
        concentration[
            "capital_policy_applicable"
        ]
    ]

    capital_policy_pass = (
        applicable["capital_limit_passed"].all()
        if not applicable.empty
        else True
    )

    if applicable.empty:
        max_capital = 0.0
    else:
        max_capital = applicable[
            "capital_weight"
        ].max()

    checks.append(
        validation_row(
            "Fully funded positions within capital policy",
            capital_policy_pass,
            (
                f"Largest applicable capital weight: "
                f"{max_capital:.4%}; "
                f"limit: {MAX_CAPITAL_WEIGHT:.4%}"
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


# ============================================================
# DISPLAY
# ============================================================

def print_key_results(
    exposures: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    concentration: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:

    print()
    print("=" * 76)
    print("VITTANTRA - EXPOSURE RISK ENGINE")
    print("=" * 76)

    print()
    print("Largest positions by gross economic exposure:")
    print()

    display_columns = [
        "symbol",
        "asset_class",
        "instrument_type",
        "market_value",
        "capital_exposure",
        "gross_notional_exposure",
        "capital_weight",
        "gross_exposure_weight",
        "risk_weight",
    ]

    print(
        exposures
        .sort_values(
            "gross_exposure_weight",
            ascending=False,
        )[display_columns]
        .head(10)
        .to_string(index=False)
    )

    print()
    print("Portfolio exposure summary:")
    print()

    print(
        portfolio_summary
        .to_string(index=False)
    )

    print()
    print("Concentration exceptions:")
    print()

    exceptions = concentration[
        ~concentration["overall_passed"]
    ]

    if exceptions.empty:
        print("No exposure-policy exceptions detected.")
    else:
        print(
            exceptions[
                [
                    "symbol",
                    "instrument_type",
                    "capital_weight",
                    "notional_weight",
                    "risk_weight",
                    "capital_limit_passed",
                    "notional_limit_passed",
                    "risk_limit_passed",
                ]
            ].to_string(index=False)
        )

    print()
    print("Validation:")
    print()

    print(
        validation[
            [
                "check",
                "passed",
                "details",
            ]
        ].to_string(index=False)
    )

    passed = int(
        validation["passed"].sum()
    )

    total = len(validation)

    print()
    print(
        f"Validation result: "
        f"{passed}/{total} passed "
        f"({passed / total:.2%})"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("Loading Day 63 portfolio...")

    portfolio = load_portfolio()

    print(
        f"Loaded {len(portfolio)} instruments "
        f"from {INPUT_FILE}."
    )

    exposures = (
        calculate_instrument_exposures(
            portfolio
        )
    )

    asset_classes = (
        build_asset_class_summary(
            exposures
        )
    )

    portfolio_summary = (
        build_portfolio_summary(
            exposures
        )
    )

    concentration = (
        build_concentration_checks(
            exposures
        )
    )

    validation = (
        build_validation_summary(
            exposures,
            asset_classes,
            portfolio_summary,
            concentration,
        )
    )

    # --------------------------------------------------------
    # SAVE OUTPUTS
    # --------------------------------------------------------

    exposures.to_csv(
        OUTPUT_EXPOSURE_FILE,
        index=False,
    )

    asset_classes.to_csv(
        OUTPUT_ASSET_CLASS_FILE,
        index=False,
    )

    portfolio_summary.to_csv(
        OUTPUT_PORTFOLIO_FILE,
        index=False,
    )

    concentration.to_csv(
        OUTPUT_LIMIT_FILE,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION_FILE,
        index=False,
    )

    print_key_results(
        exposures,
        portfolio_summary,
        concentration,
        validation,
    )

    print()
    print("Generated:")
    print(f"  {OUTPUT_EXPOSURE_FILE}")
    print(f"  {OUTPUT_ASSET_CLASS_FILE}")
    print(f"  {OUTPUT_PORTFOLIO_FILE}")
    print(f"  {OUTPUT_LIMIT_FILE}")
    print(f"  {OUTPUT_VALIDATION_FILE}")

    print()
    print("Architecture:")
    print(
        "Positions -> Instrument Classification -> "
        "Capital Exposure -> Notional Exposure -> "
        "Risk Exposure -> Concentration Controls -> "
        "Rebalancing"
    )

    print()
    print(
        "Important: derivative capital factors and risk "
        "multipliers are explicit research assumptions. "
        "They are not exchange margin requirements."
    )


if __name__ == "__main__":
    main()