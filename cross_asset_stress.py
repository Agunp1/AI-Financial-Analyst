"""
VITTANTRA
Day 61 — Cross-Asset Stress Testing Engine

Purpose
-------
Build a scenario-based stress-testing layer on top of the existing
Day 59 multi-asset architecture and Day 60 unified risk engine.

Architecture
------------
Instrument
    ↓
Multi-Asset Classification
    ↓
Unified Risk Engine
    ↓
Cross-Asset Stress Testing
    ↓
Scenario Engine
    ↓
Rebalancing
    ↓
Dashboard

Important
---------
The scenarios in this module are deterministic research/engineering
assumptions. They are NOT forecasts and are NOT investment advice.

Day 61 does not modify:
    multi_asset_risk.py
    unified_risk_engine.py
    var_engine.py
    risk_engine.py
    stress_engine.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from vittantra_live_inputs import load_price_history
from multi_asset_risk import AssetClass, Instrument, build_sample_instruments

from unified_risk_engine import (
    build_validation_price_history,
    calculate_asset_class_exposure,
    calculate_portfolio_value,
    enrich_sample_instruments,
)


# ==============================================================
# OUTPUT FILES
# ==============================================================

OUTPUT_SCENARIO_SUMMARY = Path(
    "day61_scenario_summary.csv"
)

OUTPUT_INSTRUMENT_STRESS = Path(
    "day61_instrument_stress_results.csv"
)

OUTPUT_ASSET_CLASS_STRESS = Path(
    "day61_asset_class_stress.csv"
)

OUTPUT_SCENARIO_RANKING = Path(
    "day61_scenario_ranking.csv"
)

OUTPUT_VALIDATION = Path(
    "day61_validation_summary.csv"
)


# ==============================================================
# CONSTANTS
# ==============================================================

EPSILON = 1e-12


# ==============================================================
# DATA OBJECTS
# ==============================================================

@dataclass(frozen=True)
class StressScenario:
    """
    Cross-asset deterministic stress scenario.

    Shocks are expressed as decimal returns.

    Example:
        -0.20 = -20%
         0.10 = +10%
    """

    name: str
    description: str

    equity_shock: float = 0.0
    etf_fund_shock: float = 0.0
    fixed_income_shock: float = 0.0
    option_shock: float = 0.0
    future_shock: float = 0.0
    fx_shock: float = 0.0
    commodity_shock: float = 0.0
    cash_shock: float = 0.0
    crypto_shock: float = 0.0
    real_estate_shock: float = 0.0
    other_shock: float = 0.0

    volatility_multiplier: float = 1.0
    interest_rate_shock_bps: float = 0.0
    credit_spread_shock_bps: float = 0.0


@dataclass
class StressResult:
    scenario: str
    instrument_id: str
    symbol: str
    asset_class: str

    base_market_value: float
    direct_shock: float

    rate_effect: float
    credit_effect: float
    volatility_effect: float

    total_stress_return: float

    stressed_market_value: float
    pnl: float
    pnl_pct_of_portfolio: float

    method: str


# ==============================================================
# GENERAL UTILITIES
# ==============================================================

def safe_float(
    value,
) -> Optional[float]:

    if value is None:
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not np.isfinite(number):
        return None

    return number


def get_metadata(
    instrument: Instrument,
    key: str,
    default=None,
):

    metadata = getattr(
        instrument,
        "metadata",
        None,
    )

    if not isinstance(
        metadata,
        dict,
    ):
        return default

    return metadata.get(
        key,
        default,
    )


def instrument_market_value(
    instrument: Instrument,
) -> Optional[float]:

    try:
        value = (
            instrument
            .calculate_market_value()
        )

    except Exception:
        return None

    return safe_float(
        value
    )


# ==============================================================
# SCENARIO LIBRARY
# ==============================================================

def build_scenario_library() -> List[StressScenario]:
    """
    Day 61 deterministic scenario library.

    These numbers are scenario assumptions only.
    They are not estimates of future market behavior.
    """

    return [

        StressScenario(
            name="Baseline",
            description=(
                "No stress. Used as a control scenario."
            ),
        ),

        StressScenario(
            name="Equity Crash",
            description=(
                "Severe global risk-off equity selloff."
            ),
            equity_shock=-0.30,
            etf_fund_shock=-0.22,
            fixed_income_shock=0.04,
            option_shock=-0.35,
            future_shock=-0.18,
            fx_shock=0.03,
            commodity_shock=-0.10,
            cash_shock=0.00,
            crypto_shock=-0.45,
            real_estate_shock=-0.20,
            other_shock=-0.15,
            volatility_multiplier=1.80,
            credit_spread_shock_bps=175.0,
        ),

        StressScenario(
            name="Inflation Shock",
            description=(
                "Inflation resurgence with higher rates "
                "and commodity pressure."
            ),
            equity_shock=-0.12,
            etf_fund_shock=-0.10,
            fixed_income_shock=-0.08,
            option_shock=-0.12,
            future_shock=0.08,
            fx_shock=0.03,
            commodity_shock=0.20,
            cash_shock=0.00,
            crypto_shock=-0.15,
            real_estate_shock=-0.10,
            other_shock=-0.08,
            volatility_multiplier=1.35,
            interest_rate_shock_bps=200.0,
            credit_spread_shock_bps=75.0,
        ),

        StressScenario(
            name="Rates Up 200bp",
            description=(
                "Parallel upward interest-rate shock "
                "of approximately 200 basis points."
            ),
            equity_shock=-0.08,
            etf_fund_shock=-0.06,
            fixed_income_shock=0.0,
            option_shock=-0.06,
            future_shock=-0.04,
            fx_shock=0.04,
            commodity_shock=-0.04,
            cash_shock=0.00,
            crypto_shock=-0.12,
            real_estate_shock=-0.15,
            other_shock=-0.05,
            volatility_multiplier=1.20,
            interest_rate_shock_bps=200.0,
            credit_spread_shock_bps=50.0,
        ),

        StressScenario(
            name="Credit Crisis",
            description=(
                "Large widening in credit spreads "
                "combined with risk-asset weakness."
            ),
            equity_shock=-0.22,
            etf_fund_shock=-0.17,
            fixed_income_shock=0.0,
            option_shock=-0.25,
            future_shock=-0.12,
            fx_shock=0.02,
            commodity_shock=-0.08,
            cash_shock=0.00,
            crypto_shock=-0.35,
            real_estate_shock=-0.18,
            other_shock=-0.12,
            volatility_multiplier=1.60,
            interest_rate_shock_bps=-75.0,
            credit_spread_shock_bps=300.0,
        ),

        StressScenario(
            name="Crypto Crash",
            description=(
                "Digital-asset crash with moderate "
                "spillover into broader risk assets."
            ),
            equity_shock=-0.07,
            etf_fund_shock=-0.05,
            fixed_income_shock=0.01,
            option_shock=-0.10,
            future_shock=-0.04,
            fx_shock=0.01,
            commodity_shock=-0.02,
            cash_shock=0.00,
            crypto_shock=-0.60,
            real_estate_shock=-0.03,
            other_shock=-0.05,
            volatility_multiplier=1.40,
            credit_spread_shock_bps=35.0,
        ),

        StressScenario(
            name="Liquidity Crisis",
            description=(
                "Broad cross-asset deleveraging and "
                "liquidity contraction."
            ),
            equity_shock=-0.25,
            etf_fund_shock=-0.20,
            fixed_income_shock=-0.07,
            option_shock=-0.30,
            future_shock=-0.18,
            fx_shock=0.05,
            commodity_shock=-0.15,
            cash_shock=0.00,
            crypto_shock=-0.50,
            real_estate_shock=-0.22,
            other_shock=-0.15,
            volatility_multiplier=2.00,
            interest_rate_shock_bps=50.0,
            credit_spread_shock_bps=250.0,
        ),

        StressScenario(
            name="Risk Asset Rally",
            description=(
                "Positive risk-on scenario used to test "
                "portfolio upside participation."
            ),
            equity_shock=0.15,
            etf_fund_shock=0.12,
            fixed_income_shock=-0.02,
            option_shock=0.20,
            future_shock=0.10,
            fx_shock=-0.02,
            commodity_shock=0.08,
            cash_shock=0.00,
            crypto_shock=0.30,
            real_estate_shock=0.10,
            other_shock=0.08,
            volatility_multiplier=0.80,
            interest_rate_shock_bps=75.0,
            credit_spread_shock_bps=-50.0,
        ),
    ]


# ==============================================================
# ASSET-CLASS SHOCK ROUTING
# ==============================================================

def get_direct_asset_shock(
    asset_class: AssetClass,
    scenario: StressScenario,
) -> float:

    mapping = {

        AssetClass.EQUITY:
            scenario.equity_shock,

        AssetClass.ETF_FUND:
            scenario.etf_fund_shock,

        AssetClass.FIXED_INCOME:
            scenario.fixed_income_shock,

        AssetClass.OPTION:
            scenario.option_shock,

        AssetClass.FUTURE:
            scenario.future_shock,

        AssetClass.FX:
            scenario.fx_shock,

        AssetClass.COMMODITY:
            scenario.commodity_shock,

        AssetClass.CASH:
            scenario.cash_shock,

        AssetClass.CRYPTO:
            scenario.crypto_shock,

        AssetClass.REAL_ESTATE:
            scenario.real_estate_shock,

        AssetClass.OTHER:
            scenario.other_shock,
    }

    return float(
        mapping.get(
            asset_class,
            scenario.other_shock,
        )
    )


# ==============================================================
# FIXED-INCOME STRESS
# ==============================================================

def calculate_rate_effect(
    instrument: Instrument,
    scenario: StressScenario,
) -> float:
    """
    Approximate bond price effect:

        ΔP/P ≈ -Duration × Δy
                + 0.5 × Convexity × Δy²

    If duration data are unavailable, no fabricated duration
    exposure is inserted.
    """

    if (
        instrument.asset_class
        != AssetClass.FIXED_INCOME
    ):
        return 0.0

    duration = safe_float(
        getattr(
            instrument,
            "duration",
            None,
        )
    )

    if duration is None:
        duration = safe_float(
            get_metadata(
                instrument,
                "duration",
            )
        )

    if duration is None:
        duration = safe_float(
            get_metadata(
                instrument,
                "modified_duration",
            )
        )

    if duration is None:
        return 0.0

    convexity = safe_float(
        getattr(
            instrument,
            "convexity",
            None,
        )
    )

    if convexity is None:
        convexity = safe_float(
            get_metadata(
                instrument,
                "convexity",
                0.0,
            )
        )

    if convexity is None:
        convexity = 0.0

    delta_yield = (
        scenario.interest_rate_shock_bps
        / 10000.0
    )

    effect = (
        -duration
        * delta_yield
        + 0.5
        * convexity
        * delta_yield ** 2
    )

    return float(
        effect
    )


def calculate_credit_effect(
    instrument: Instrument,
    scenario: StressScenario,
) -> float:
    """
    Approximate credit-spread price impact using duration.

        ΔP/P ≈ -Duration × ΔSpread
    """

    if (
        instrument.asset_class
        != AssetClass.FIXED_INCOME
    ):
        return 0.0

    duration = safe_float(
        getattr(
            instrument,
            "duration",
            None,
        )
    )

    if duration is None:
        duration = safe_float(
            get_metadata(
                instrument,
                "duration",
            )
        )

    if duration is None:
        duration = safe_float(
            get_metadata(
                instrument,
                "modified_duration",
            )
        )

    if duration is None:
        return 0.0

    spread_change = (
        scenario.credit_spread_shock_bps
        / 10000.0
    )

    return float(
        -duration
        * spread_change
    )


# ==============================================================
# OPTION VOLATILITY STRESS
# ==============================================================

def calculate_option_volatility_effect(
    instrument: Instrument,
    scenario: StressScenario,
) -> float:
    """
    Uses Day 60-style metadata if option vega and implied
    volatility information exist.

    The result is expressed as an approximate return effect on
    the option position.

    If the required data are unavailable, zero is returned rather
    than inventing option sensitivity.
    """

    if (
        instrument.asset_class
        != AssetClass.OPTION
    ):
        return 0.0

    vega = safe_float(
        get_metadata(
            instrument,
            "vega",
        )
    )

    implied_volatility = safe_float(
        get_metadata(
            instrument,
            "implied_volatility",
        )
    )

    market_value = (
        instrument_market_value(
            instrument
        )
    )

    quantity = safe_float(
        getattr(
            instrument,
            "quantity",
            None,
        )
    )

    multiplier = safe_float(
        getattr(
            instrument,
            "contract_multiplier",
            None,
        )
    )

    if multiplier is None:
        multiplier = 1.0

    if (
        vega is None
        or implied_volatility is None
        or market_value is None
        or quantity is None
        or abs(market_value) < EPSILON
    ):
        return 0.0

    vol_change_decimal = (
        implied_volatility
        * (
            scenario.volatility_multiplier
            - 1.0
        )
    )

    vol_change_points = (
        vol_change_decimal
        * 100.0
    )

    pnl = (
        vega
        * vol_change_points
        * quantity
        * multiplier
    )

    return float(
        pnl
        / abs(market_value)
    )


# ==============================================================
# STRESS CALCULATOR
# ==============================================================

def stress_instrument(
    instrument: Instrument,
    scenario: StressScenario,
    portfolio_value: float,
) -> Optional[StressResult]:

    market_value = (
        instrument_market_value(
            instrument
        )
    )

    if market_value is None:
        return None

    direct_shock = (
        get_direct_asset_shock(
            instrument.asset_class,
            scenario,
        )
    )

    rate_effect = (
        calculate_rate_effect(
            instrument,
            scenario,
        )
    )

    credit_effect = (
        calculate_credit_effect(
            instrument,
            scenario,
        )
    )

    volatility_effect = (
        calculate_option_volatility_effect(
            instrument,
            scenario,
        )
    )

    total_stress_return = (
        direct_shock
        + rate_effect
        + credit_effect
        + volatility_effect
    )

    # Prevent a linear approximation from producing a market
    # value below zero for ordinary long positions.
    total_stress_return = max(
        total_stress_return,
        -1.0,
    )

    stressed_market_value = (
        market_value
        * (
            1.0
            + total_stress_return
        )
    )

    pnl = (
        stressed_market_value
        - market_value
    )

    if (
        portfolio_value is None
        or abs(portfolio_value) < EPSILON
    ):
        pnl_pct_of_portfolio = np.nan

    else:
        pnl_pct_of_portfolio = (
            pnl
            / portfolio_value
        )

    return StressResult(
        scenario=scenario.name,
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        asset_class=instrument.asset_class.value,
        base_market_value=float(
            market_value
        ),
        direct_shock=float(
            direct_shock
        ),
        rate_effect=float(
            rate_effect
        ),
        credit_effect=float(
            credit_effect
        ),
        volatility_effect=float(
            volatility_effect
        ),
        total_stress_return=float(
            total_stress_return
        ),
        stressed_market_value=float(
            stressed_market_value
        ),
        pnl=float(
            pnl
        ),
        pnl_pct_of_portfolio=float(
            pnl_pct_of_portfolio
        ) if np.isfinite(
            pnl_pct_of_portfolio
        ) else np.nan,
        method=(
            "Direct asset-class shock"
            " + rate sensitivity"
            " + credit sensitivity"
            " + option volatility sensitivity"
        ),
    )


# ==============================================================
# PORTFOLIO STRESS ENGINE
# ==============================================================

def run_cross_asset_stress(
    instruments: Iterable[Instrument],
    scenarios: Iterable[StressScenario],
) -> pd.DataFrame:

    instruments = list(
        instruments
    )

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    results: List[StressResult] = []

    for scenario in scenarios:

        for instrument in instruments:

            result = stress_instrument(
                instrument=instrument,
                scenario=scenario,
                portfolio_value=portfolio_value,
            )

            if result is not None:
                results.append(
                    result
                )

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            asdict(result)
            for result
            in results
        ]
    )


# ==============================================================
# SCENARIO SUMMARY
# ==============================================================

def build_scenario_summary(
    stress_results: pd.DataFrame,
) -> pd.DataFrame:

    if stress_results.empty:
        return pd.DataFrame()

    summary = (
        stress_results
        .groupby(
            "scenario",
            as_index=False,
        )
        .agg(
            base_portfolio_value=(
                "base_market_value",
                "sum",
            ),
            stressed_portfolio_value=(
                "stressed_market_value",
                "sum",
            ),
            portfolio_pnl=(
                "pnl",
                "sum",
            ),
            instrument_count=(
                "symbol",
                "count",
            ),
        )
    )

    summary[
        "portfolio_return"
    ] = np.where(
        summary[
            "base_portfolio_value"
        ].abs() > EPSILON,
        summary[
            "portfolio_pnl"
        ]
        / summary[
            "base_portfolio_value"
        ],
        np.nan,
    )

    summary[
        "loss_amount"
    ] = (
        -summary[
            "portfolio_pnl"
        ]
    ).clip(
        lower=0.0
    )

    return summary


# ==============================================================
# ASSET-CLASS STRESS ATTRIBUTION
# ==============================================================

def build_asset_class_stress(
    stress_results: pd.DataFrame,
) -> pd.DataFrame:

    if stress_results.empty:
        return pd.DataFrame()

    result = (
        stress_results
        .groupby(
            [
                "scenario",
                "asset_class",
            ],
            as_index=False,
        )
        .agg(
            base_market_value=(
                "base_market_value",
                "sum",
            ),
            stressed_market_value=(
                "stressed_market_value",
                "sum",
            ),
            pnl=(
                "pnl",
                "sum",
            ),
            instrument_count=(
                "symbol",
                "count",
            ),
        )
    )

    result[
        "asset_class_return"
    ] = np.where(
        result[
            "base_market_value"
        ].abs() > EPSILON,
        result[
            "pnl"
        ]
        / result[
            "base_market_value"
        ],
        np.nan,
    )

    return result


# ==============================================================
# SCENARIO RANKING
# ==============================================================

def build_scenario_ranking(
    scenario_summary: pd.DataFrame,
) -> pd.DataFrame:

    if scenario_summary.empty:
        return pd.DataFrame()

    ranking = (
        scenario_summary
        .copy()
        .sort_values(
            "portfolio_return",
            ascending=True,
        )
        .reset_index(
            drop=True
        )
    )

    ranking[
        "severity_rank"
    ] = np.arange(
        1,
        len(ranking) + 1,
    )

    ranking[
        "severity"
    ] = pd.cut(
        ranking[
            "portfolio_return"
        ],
        bins=[
            -np.inf,
            -0.20,
            -0.10,
            -0.05,
            0.0,
            np.inf,
        ],
        labels=[
            "Extreme",
            "Severe",
            "Moderate",
            "Mild",
            "Positive / Neutral",
        ],
        right=False,
    )

    columns = [
        "severity_rank",
        "scenario",
        "severity",
        "base_portfolio_value",
        "stressed_portfolio_value",
        "portfolio_pnl",
        "portfolio_return",
        "loss_amount",
        "instrument_count",
    ]

    return ranking[
        columns
    ]


# ==============================================================
# CONCENTRATION DIAGNOSTICS
# ==============================================================

def build_loss_concentration(
    stress_results: pd.DataFrame,
) -> pd.DataFrame:

    if stress_results.empty:
        return pd.DataFrame()

    rows = []

    for scenario, group in (
        stress_results.groupby(
            "scenario"
        )
    ):

        losses = (
            group.loc[
                group[
                    "pnl"
                ] < 0
            ]
            .copy()
        )

        total_loss = (
            -losses[
                "pnl"
            ].sum()
        )

        if (
            losses.empty
            or total_loss <= EPSILON
        ):

            rows.append(
                {
                    "scenario":
                        scenario,

                    "largest_loss_symbol":
                        None,

                    "largest_loss":
                        0.0,

                    "largest_loss_share":
                        0.0,

                    "top_3_loss_share":
                        0.0,
                }
            )

            continue

        losses[
            "loss"
        ] = (
            -losses[
                "pnl"
            ]
        )

        losses = (
            losses
            .sort_values(
                "loss",
                ascending=False,
            )
        )

        largest = (
            losses.iloc[0]
        )

        top_3_loss = (
            losses[
                "loss"
            ]
            .head(3)
            .sum()
        )

        rows.append(
            {
                "scenario":
                    scenario,

                "largest_loss_symbol":
                    largest[
                        "symbol"
                    ],

                "largest_loss":
                    float(
                        largest[
                            "loss"
                        ]
                    ),

                "largest_loss_share":
                    float(
                        largest[
                            "loss"
                        ]
                        / total_loss
                    ),

                "top_3_loss_share":
                    float(
                        top_3_loss
                        / total_loss
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day61(
    instruments: List[Instrument],
    scenarios: List[StressScenario],
    stress_results: pd.DataFrame,
    scenario_summary: pd.DataFrame,
    asset_class_stress: pd.DataFrame,
) -> pd.DataFrame:

    checks = []

    def add_check(
        check: str,
        passed: bool,
        details: str,
    ) -> None:

        checks.append(
            {
                "check":
                    check,

                "passed":
                    bool(passed),

                "details":
                    details,
            }
        )

    expected_rows = (
        len(instruments)
        * len(scenarios)
    )

    add_check(
        "Stress result table generated",
        not stress_results.empty,
        (
            f"Rows generated: "
            f"{len(stress_results)}"
        ),
    )

    add_check(
        "Every scenario-instrument combination evaluated",
        (
            len(stress_results)
            == expected_rows
        ),
        (
            f"Expected {expected_rows}; "
            f"received {len(stress_results)}."
        ),
    )

    scenario_names = {
        scenario.name
        for scenario
        in scenarios
    }

    output_scenarios = set(
        stress_results[
            "scenario"
        ].unique()
    ) if not stress_results.empty else set()

    add_check(
        "All scenarios represented",
        (
            scenario_names
            == output_scenarios
        ),
        (
            f"Expected {len(scenario_names)} scenarios; "
            f"received {len(output_scenarios)}."
        ),
    )

    baseline = (
        scenario_summary.loc[
            scenario_summary[
                "scenario"
            ]
            == "Baseline"
        ]
    )

    baseline_passed = False

    if not baseline.empty:

        baseline_return = safe_float(
            baseline.iloc[0][
                "portfolio_return"
            ]
        )

        baseline_passed = (
            baseline_return is not None
            and abs(
                baseline_return
            ) < 1e-10
        )

    add_check(
        "Baseline scenario approximately zero",
        baseline_passed,
        (
            "Baseline should not change "
            "portfolio value."
        ),
    )

    finite_values = True

    if not stress_results.empty:

        numeric_columns = [
            "base_market_value",
            "direct_shock",
            "rate_effect",
            "credit_effect",
            "volatility_effect",
            "total_stress_return",
            "stressed_market_value",
            "pnl",
        ]

        numeric_data = (
            stress_results[
                numeric_columns
            ]
            .apply(
                pd.to_numeric,
                errors="coerce",
            )
        )

        finite_values = bool(
            np.isfinite(
                numeric_data
                .to_numpy(
                    dtype=float
                )
            ).all()
        )

    add_check(
        "Stress calculations contain finite values",
        finite_values,
        (
            "Core stress-result numeric fields "
            "must be finite."
        ),
    )

    nonnegative_values = True

    if not stress_results.empty:

        nonnegative_values = bool(
            (
                stress_results[
                    "stressed_market_value"
                ]
                >= -EPSILON
            ).all()
        )

    add_check(
        "No stressed long market value below zero",
        nonnegative_values,
        (
            "Linear stress returns are floored "
            "at -100%."
        ),
    )

    add_check(
        "Scenario summary generated",
        not scenario_summary.empty,
        (
            f"Scenario summary rows: "
            f"{len(scenario_summary)}"
        ),
    )

    add_check(
        "Asset-class stress attribution generated",
        not asset_class_stress.empty,
        (
            f"Asset-class stress rows: "
            f"{len(asset_class_stress)}"
        ),
    )

    validation = pd.DataFrame(
        checks
    )

    passed_tests = int(
        validation[
            "passed"
        ].sum()
    )

    total_tests = len(
        validation
    )

    validation[
        "passed_tests"
    ] = passed_tests

    validation[
        "total_tests"
    ] = total_tests

    validation[
        "pass_rate"
    ] = (
        passed_tests
        / total_tests
        if total_tests
        else np.nan
    )

    return validation


# ==============================================================
# TERMINAL DISPLAY
# ==============================================================

def print_section(
    title: str,
) -> None:

    print()
    print(
        "=" * 72
    )
    print(
        title
    )
    print(
        "=" * 72
    )


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:

    print_section(
        "VITTANTRA — DAY 61 CROSS-ASSET STRESS TESTING"
    )

    print(
        "Building deterministic cross-asset stress scenarios."
    )

    print()
    print(
        "Important:"
    )

    print(
        "Scenario shocks are engineering assumptions used to test "
        "portfolio-risk plumbing."
    )

    print(
        "They are NOT forecasts, live market estimates, "
        "or investment recommendations."
    )

    # ----------------------------------------------------------
    # Reuse Day 59/60 portfolio architecture
    # ----------------------------------------------------------

    instruments = (
        build_sample_instruments()
    )

    instruments = (
        enrich_sample_instruments(
            instruments
        )
    )

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    asset_exposure = (
        calculate_asset_class_exposure(
            instruments
        )
    )

    # Build the same deterministic price-history object used by
    # Day 60. Day 61 does not require historical prices for the
    # deterministic shock itself, but constructing it verifies
    # compatibility with the existing unified-risk architecture.
    price_history = load_price_history(
        [instrument.symbol for instrument in instruments]
    )

    if price_history is None:
        price_history = (
            build_validation_price_history(
                instruments=instruments,
                observations=320,
                seed=60,
            )
        )

    print_section(
        "PORTFOLIO FOUNDATION"
    )

    print(
        f"Instruments: "
        f"{len(instruments)}"
    )

    print(
        f"Portfolio value: "
        f"${portfolio_value:,.2f}"
    )

    print(
        f"Asset classes: "
        f"{len(asset_exposure)}"
    )

    print(
        f"Validation price observations: "
        f"{len(price_history)}"
    )

    # ----------------------------------------------------------
    # Scenario library
    # ----------------------------------------------------------

    scenarios = (
        build_scenario_library()
    )

    print_section(
        "STRESS SCENARIO LIBRARY"
    )

    scenario_table = pd.DataFrame(
        [
            {
                "scenario":
                    scenario.name,

                "description":
                    scenario.description,

                "rate_shock_bps":
                    scenario.interest_rate_shock_bps,

                "credit_spread_shock_bps":
                    scenario.credit_spread_shock_bps,

                "volatility_multiplier":
                    scenario.volatility_multiplier,
            }
            for scenario
            in scenarios
        ]
    )

    print(
        scenario_table.to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Run stress engine
    # ----------------------------------------------------------

    stress_results = (
        run_cross_asset_stress(
            instruments=instruments,
            scenarios=scenarios,
        )
    )

    # ----------------------------------------------------------
    # Scenario aggregation
    # ----------------------------------------------------------

    scenario_summary = (
        build_scenario_summary(
            stress_results
        )
    )

    # ----------------------------------------------------------
    # Asset-class attribution
    # ----------------------------------------------------------

    asset_class_stress = (
        build_asset_class_stress(
            stress_results
        )
    )

    # ----------------------------------------------------------
    # Scenario ranking
    # ----------------------------------------------------------

    scenario_ranking = (
        build_scenario_ranking(
            scenario_summary
        )
    )

    # ----------------------------------------------------------
    # Loss concentration
    # ----------------------------------------------------------

    loss_concentration = (
        build_loss_concentration(
            stress_results
        )
    )

    if not scenario_ranking.empty:

        scenario_ranking = (
            scenario_ranking
            .merge(
                loss_concentration,
                on="scenario",
                how="left",
            )
        )

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    validation = (
        validate_day61(
            instruments=instruments,
            scenarios=scenarios,
            stress_results=stress_results,
            scenario_summary=scenario_summary,
            asset_class_stress=asset_class_stress,
        )
    )

    # ----------------------------------------------------------
    # Save files
    # ----------------------------------------------------------

    stress_results.to_csv(
        OUTPUT_INSTRUMENT_STRESS,
        index=False,
    )

    scenario_summary.to_csv(
        OUTPUT_SCENARIO_SUMMARY,
        index=False,
    )

    asset_class_stress.to_csv(
        OUTPUT_ASSET_CLASS_STRESS,
        index=False,
    )

    scenario_ranking.to_csv(
        OUTPUT_SCENARIO_RANKING,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )

    # ----------------------------------------------------------
    # Display scenario ranking
    # ----------------------------------------------------------

    print_section(
        "PORTFOLIO STRESS RESULTS"
    )

    display_columns = [
        "severity_rank",
        "scenario",
        "severity",
        "portfolio_pnl",
        "portfolio_return",
    ]

    print(
        scenario_ranking[
            display_columns
        ].to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Worst scenario
    # ----------------------------------------------------------

    if not scenario_ranking.empty:

        worst = (
            scenario_ranking
            .iloc[0]
        )

        print_section(
            "WORST SCENARIO"
        )

        print(
            f"Scenario: "
            f"{worst['scenario']}"
        )

        print(
            f"Portfolio P&L: "
            f"${worst['portfolio_pnl']:,.2f}"
        )

        print(
            f"Portfolio return: "
            f"{worst['portfolio_return']:.2%}"
        )

        print(
            f"Severity: "
            f"{worst['severity']}"
        )

        if pd.notna(
            worst[
                "largest_loss_symbol"
            ]
        ):

            print(
                f"Largest loss contributor: "
                f"{worst['largest_loss_symbol']}"
            )

            print(
                f"Largest loss share: "
                f"{worst['largest_loss_share']:.2%}"
            )

            print(
                f"Top-3 loss concentration: "
                f"{worst['top_3_loss_share']:.2%}"
            )

    # ----------------------------------------------------------
    # Asset-class attribution for worst scenario
    # ----------------------------------------------------------

    if not scenario_ranking.empty:

        worst_name = (
            scenario_ranking
            .iloc[0][
                "scenario"
            ]
        )

        worst_asset_classes = (
            asset_class_stress.loc[
                asset_class_stress[
                    "scenario"
                ]
                == worst_name
            ]
            .sort_values(
                "pnl",
                ascending=True,
            )
        )

        print_section(
            f"ASSET-CLASS ATTRIBUTION — {worst_name}"
        )

        print(
            worst_asset_classes[
                [
                    "asset_class",
                    "base_market_value",
                    "pnl",
                    "asset_class_return",
                ]
            ].to_string(
                index=False
            )
        )

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    print_section(
        "DAY 61 VALIDATION"
    )

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

    passed_tests = int(
        validation[
            "passed"
        ].sum()
    )

    total_tests = len(
        validation
    )

    print()

    print(
        f"Passed: "
        f"{passed_tests}/{total_tests}"
    )

    print(
        f"Pass rate: "
        f"{passed_tests / total_tests:.2%}"
    )

    # ----------------------------------------------------------
    # Outputs
    # ----------------------------------------------------------

    print_section(
        "DAY 61 OUTPUTS"
    )

    outputs = [
        OUTPUT_INSTRUMENT_STRESS,
        OUTPUT_SCENARIO_SUMMARY,
        OUTPUT_ASSET_CLASS_STRESS,
        OUTPUT_SCENARIO_RANKING,
        OUTPUT_VALIDATION,
    ]

    for output in outputs:

        print(
            output
        )

    # ----------------------------------------------------------
    # Completion
    # ----------------------------------------------------------

    print_section(
        "DAY 61 COMPLETE"
    )

    print(
        "Cross-asset stress-testing layer completed."
    )

    print()

    print(
        "Vittantra can now:"
    )

    print(
        "• apply common scenarios across multiple asset classes"
    )

    print(
        "• estimate instrument-level stressed P&L"
    )

    print(
        "• aggregate stressed portfolio value and return"
    )

    print(
        "• model duration and convexity rate sensitivity "
        "when data exist"
    )

    print(
        "• model credit-spread sensitivity when duration exists"
    )

    print(
        "• incorporate option volatility sensitivity "
        "when inputs exist"
    )

    print(
        "• attribute stress losses by asset class"
    )

    print(
        "• identify loss concentration"
    )

    print(
        "• rank scenarios by portfolio impact"
    )

    print(
        "• avoid fabricating sensitivities when required "
        "inputs are unavailable"
    )

    print()

    print(
        "Next architecture layer:"
    )

    print(
        "Unified Risk -> Cross-Asset Stress Testing -> "
        "Scenario Engine -> Rebalancing -> Dashboard"
    )


if __name__ == "__main__":
    main()