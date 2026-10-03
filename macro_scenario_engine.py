"""
VITTANTRA
Day 62 — Configurable Macro Scenario Engine

Purpose
-------
Translate configurable macroeconomic assumptions into cross-asset
stress scenarios, reuse the validated Day 61 stress engine, and
measure portfolio impact by macro regime.

Important
---------
This is a deterministic scenario-analysis framework.

It does NOT:
    - forecast future markets
    - claim causal certainty
    - provide investment advice

Days 1–61 remain unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from multi_asset_risk import (
    build_sample_instruments,
)

from unified_risk_engine import (
    calculate_asset_class_exposure,
    calculate_portfolio_value,
    enrich_sample_instruments,
)

from cross_asset_stress import (
    StressScenario,
    build_asset_class_stress,
    build_loss_concentration,
    build_scenario_ranking,
    build_scenario_summary,
    run_cross_asset_stress,
)


# ==============================================================
# OUTPUT FILES
# ==============================================================

OUTPUT_MACRO_INPUTS = Path(
    "day62_macro_inputs.csv"
)

OUTPUT_TRANSLATED_SCENARIOS = Path(
    "day62_translated_scenarios.csv"
)

OUTPUT_PORTFOLIO_RESULTS = Path(
    "day62_macro_portfolio_results.csv"
)

OUTPUT_ASSET_CLASS_RESULTS = Path(
    "day62_macro_asset_class_results.csv"
)

OUTPUT_INSTRUMENT_RESULTS = Path(
    "day62_macro_instrument_results.csv"
)

OUTPUT_REGIME_SUMMARY = Path(
    "day62_macro_regime_summary.csv"
)

OUTPUT_VALIDATION = Path(
    "day62_validation_summary.csv"
)


EPSILON = 1e-12


# ==============================================================
# MACRO SCENARIO OBJECT
# ==============================================================

@dataclass(frozen=True)
class MacroScenario:

    name: str
    description: str

    gdp_growth_change_pct: float = 0.0
    inflation_change_pct: float = 0.0

    policy_rate_change_bps: float = 0.0
    long_rate_change_bps: float = 0.0

    credit_spread_change_bps: float = 0.0

    oil_change_pct: float = 0.0
    usd_change_pct: float = 0.0
    volatility_change_pct: float = 0.0

    unemployment_change_pct: float = 0.0
    liquidity_change_pct: float = 0.0

    housing_change_pct: float = 0.0
    earnings_change_pct: float = 0.0


# ==============================================================
# UTILITIES
# ==============================================================

def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    return float(
        max(
            minimum,
            min(
                maximum,
                value,
            ),
        )
    )


def print_section(
    title: str,
) -> None:

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ==============================================================
# MACRO REGIME CLASSIFICATION
# ==============================================================

def classify_macro_regime(
    scenario: MacroScenario,
) -> str:

    growth = (
        scenario
        .gdp_growth_change_pct
    )

    inflation = (
        scenario
        .inflation_change_pct
    )

    spreads = (
        scenario
        .credit_spread_change_bps
    )

    unemployment = (
        scenario
        .unemployment_change_pct
    )

    liquidity = (
        scenario
        .liquidity_change_pct
    )

    if (
        growth <= -2.0
        and inflation <= 0.5
    ):
        return (
            "Recession / Deflationary Slowdown"
        )

    if (
        growth <= -1.0
        and inflation >= 1.0
    ):
        return "Stagflation"

    if (
        inflation >= 1.5
        and growth > -1.0
    ):
        return "Inflationary Expansion"

    if (
        growth >= 1.0
        and inflation < 1.5
    ):
        return "Growth Expansion"

    if (
        spreads >= 150.0
        or liquidity <= -0.15
        or unemployment >= 1.5
    ):
        return "Financial Stress"

    return "Mixed / Transitional"


# ==============================================================
# MACRO → ASSET SHOCK TRANSLATION
# ==============================================================

def calculate_equity_shock(
    scenario: MacroScenario,
) -> float:

    value = (
        0.04
        * scenario.gdp_growth_change_pct

        + 0.55
        * scenario.earnings_change_pct

        - 0.00035
        * scenario.policy_rate_change_bps

        - 0.00020
        * scenario.long_rate_change_bps

        - 0.00030
        * scenario.credit_spread_change_bps

        - 0.025
        * scenario.unemployment_change_pct

        + 0.25
        * scenario.liquidity_change_pct

        - 0.12
        * max(
            0.0,
            scenario.volatility_change_pct,
        )
    )

    return clamp(
        value,
        -0.60,
        0.45,
    )


def calculate_fixed_income_shock(
    scenario: MacroScenario,
) -> float:

    risk_off_bonus = 0.0

    if (
        scenario.gdp_growth_change_pct
        < -1.0
        and scenario.policy_rate_change_bps
        < 0.0
    ):
        risk_off_bonus = 0.02

    value = (
        risk_off_bonus
        + 0.05
        * scenario.liquidity_change_pct
    )

    return clamp(
        value,
        -0.12,
        0.12,
    )


def calculate_crypto_shock(
    scenario: MacroScenario,
) -> float:

    value = (
        0.06
        * scenario.gdp_growth_change_pct

        + 0.75
        * scenario.liquidity_change_pct

        - 0.00055
        * scenario.policy_rate_change_bps

        - 0.30
        * max(
            0.0,
            scenario.volatility_change_pct,
        )

        - 0.00025
        * scenario.credit_spread_change_bps
    )

    return clamp(
        value,
        -0.80,
        0.70,
    )


def calculate_real_estate_shock(
    scenario: MacroScenario,
) -> float:

    value = (
        0.60
        * scenario.housing_change_pct

        - 0.00040
        * scenario.long_rate_change_bps

        + 0.03
        * scenario.gdp_growth_change_pct

        - 0.025
        * scenario.unemployment_change_pct

        + 0.20
        * scenario.liquidity_change_pct
    )

    return clamp(
        value,
        -0.60,
        0.40,
    )


def calculate_commodity_shock(
    scenario: MacroScenario,
) -> float:

    value = (
        0.035
        * scenario.gdp_growth_change_pct

        + 0.04
        * scenario.inflation_change_pct

        + 0.65
        * scenario.oil_change_pct

        - 0.30
        * scenario.usd_change_pct
    )

    return clamp(
        value,
        -0.60,
        0.70,
    )


def calculate_fx_shock(
    scenario: MacroScenario,
) -> float:

    return clamp(
        -scenario.usd_change_pct,
        -0.30,
        0.30,
    )


def calculate_etf_shock(
    equity_shock: float,
    fixed_income_shock: float,
) -> float:

    value = (
        0.75
        * equity_shock

        + 0.25
        * fixed_income_shock
    )

    return clamp(
        value,
        -0.60,
        0.45,
    )


def calculate_future_shock(
    equity_shock: float,
    commodity_shock: float,
) -> float:

    value = (
        0.40
        * equity_shock

        + 0.60
        * commodity_shock
    )

    return clamp(
        value,
        -0.70,
        0.70,
    )


def calculate_option_shock(
    equity_shock: float,
    volatility_change: float,
) -> float:

    value = (
        1.20
        * equity_shock

        + 0.15
        * volatility_change
    )

    return clamp(
        value,
        -0.90,
        0.90,
    )


# ==============================================================
# MACRO → DAY 61 StressScenario
# ==============================================================

def translate_macro_scenario(
    scenario: MacroScenario,
) -> StressScenario:

    equity_shock = (
        calculate_equity_shock(
            scenario
        )
    )

    fixed_income_shock = (
        calculate_fixed_income_shock(
            scenario
        )
    )

    commodity_shock = (
        calculate_commodity_shock(
            scenario
        )
    )

    crypto_shock = (
        calculate_crypto_shock(
            scenario
        )
    )

    real_estate_shock = (
        calculate_real_estate_shock(
            scenario
        )
    )

    fx_shock = (
        calculate_fx_shock(
            scenario
        )
    )

    etf_shock = (
        calculate_etf_shock(
            equity_shock,
            fixed_income_shock,
        )
    )

    future_shock = (
        calculate_future_shock(
            equity_shock,
            commodity_shock,
        )
    )

    option_shock = (
        calculate_option_shock(
            equity_shock,
            scenario.volatility_change_pct,
        )
    )

    volatility_multiplier = max(
        0.10,
        1.0
        + scenario.volatility_change_pct,
    )

    interest_rate_shock_bps = (
        0.40
        * scenario.policy_rate_change_bps

        + 0.60
        * scenario.long_rate_change_bps
    )

    return StressScenario(
        name=scenario.name,

        description=(
            scenario.description
        ),

        equity_shock=(
            equity_shock
        ),

        etf_fund_shock=(
            etf_shock
        ),

        fixed_income_shock=(
            fixed_income_shock
        ),

        option_shock=(
            option_shock
        ),

        future_shock=(
            future_shock
        ),

        fx_shock=(
            fx_shock
        ),

        commodity_shock=(
            commodity_shock
        ),

        cash_shock=0.0,

        crypto_shock=(
            crypto_shock
        ),

        real_estate_shock=(
            real_estate_shock
        ),

        other_shock=(
            0.50
            * equity_shock
        ),

        volatility_multiplier=(
            volatility_multiplier
        ),

        interest_rate_shock_bps=(
            interest_rate_shock_bps
        ),

        credit_spread_shock_bps=(
            scenario
            .credit_spread_change_bps
        ),
    )


# ==============================================================
# MACRO SCENARIO LIBRARY
# ==============================================================

def build_macro_scenario_library() -> List[MacroScenario]:

    return [

        MacroScenario(
            name="Macro Baseline",

            description=(
                "Control scenario with no macro changes."
            ),
        ),

        MacroScenario(
            name="Hard Landing",

            description=(
                "Sharp economic slowdown, wider credit "
                "spreads and higher volatility."
            ),

            gdp_growth_change_pct=-3.0,

            inflation_change_pct=-1.0,

            policy_rate_change_bps=-150.0,

            long_rate_change_bps=-100.0,

            credit_spread_change_bps=220.0,

            oil_change_pct=-0.20,

            usd_change_pct=0.05,

            volatility_change_pct=0.80,

            unemployment_change_pct=2.0,

            liquidity_change_pct=-0.12,

            housing_change_pct=-0.15,

            earnings_change_pct=-0.20,
        ),

        MacroScenario(
            name="Stagflation",

            description=(
                "Weak growth with accelerating inflation "
                "and higher rates."
            ),

            gdp_growth_change_pct=-1.5,

            inflation_change_pct=2.0,

            policy_rate_change_bps=150.0,

            long_rate_change_bps=175.0,

            credit_spread_change_bps=120.0,

            oil_change_pct=0.30,

            usd_change_pct=0.06,

            volatility_change_pct=0.45,

            unemployment_change_pct=1.0,

            liquidity_change_pct=-0.10,

            housing_change_pct=-0.12,

            earnings_change_pct=-0.12,
        ),

        MacroScenario(
            name="Soft Landing",

            description=(
                "Moderate growth with easing inflation "
                "and modest rate cuts."
            ),

            gdp_growth_change_pct=0.4,

            inflation_change_pct=-0.7,

            policy_rate_change_bps=-75.0,

            long_rate_change_bps=-40.0,

            credit_spread_change_bps=-35.0,

            oil_change_pct=0.02,

            usd_change_pct=-0.02,

            volatility_change_pct=-0.20,

            unemployment_change_pct=0.1,

            liquidity_change_pct=0.06,

            housing_change_pct=0.05,

            earnings_change_pct=0.08,
        ),

        MacroScenario(
            name="Growth Boom",

            description=(
                "Strong growth, earnings improvement "
                "and supportive liquidity."
            ),

            gdp_growth_change_pct=2.0,

            inflation_change_pct=0.6,

            policy_rate_change_bps=50.0,

            long_rate_change_bps=75.0,

            credit_spread_change_bps=-60.0,

            oil_change_pct=0.15,

            usd_change_pct=0.01,

            volatility_change_pct=-0.25,

            unemployment_change_pct=-0.8,

            liquidity_change_pct=0.12,

            housing_change_pct=0.10,

            earnings_change_pct=0.18,
        ),

        MacroScenario(
            name="Inflation Reacceleration",

            description=(
                "Inflation rises materially while "
                "monetary policy tightens."
            ),

            gdp_growth_change_pct=-0.4,

            inflation_change_pct=2.5,

            policy_rate_change_bps=200.0,

            long_rate_change_bps=175.0,

            credit_spread_change_bps=80.0,

            oil_change_pct=0.25,

            usd_change_pct=0.07,

            volatility_change_pct=0.35,

            unemployment_change_pct=0.4,

            liquidity_change_pct=-0.08,

            housing_change_pct=-0.10,

            earnings_change_pct=-0.08,
        ),

        MacroScenario(
            name="Credit Event",

            description=(
                "Credit spreads widen sharply while "
                "financial liquidity contracts."
            ),

            gdp_growth_change_pct=-1.8,

            inflation_change_pct=-0.3,

            policy_rate_change_bps=-100.0,

            long_rate_change_bps=-75.0,

            credit_spread_change_bps=350.0,

            oil_change_pct=-0.15,

            usd_change_pct=0.06,

            volatility_change_pct=0.90,

            unemployment_change_pct=1.5,

            liquidity_change_pct=-0.20,

            housing_change_pct=-0.18,

            earnings_change_pct=-0.18,
        ),

        MacroScenario(
            name="Liquidity Expansion",

            description=(
                "Financial liquidity improves and "
                "credit conditions ease."
            ),

            gdp_growth_change_pct=1.0,

            inflation_change_pct=0.3,

            policy_rate_change_bps=-50.0,

            long_rate_change_bps=-25.0,

            credit_spread_change_bps=-75.0,

            oil_change_pct=0.08,

            usd_change_pct=-0.05,

            volatility_change_pct=-0.30,

            unemployment_change_pct=-0.4,

            liquidity_change_pct=0.20,

            housing_change_pct=0.08,

            earnings_change_pct=0.12,
        ),
    ]


# ==============================================================
# DATA TABLE BUILDERS
# ==============================================================

def build_macro_input_table(
    scenarios: List[MacroScenario],
) -> pd.DataFrame:

    rows = []

    for scenario in scenarios:

        row = asdict(
            scenario
        )

        row[
            "macro_regime"
        ] = classify_macro_regime(
            scenario
        )

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def build_translated_scenario_table(
    macro_scenarios: List[MacroScenario],
    stress_scenarios: List[StressScenario],
) -> pd.DataFrame:

    rows = []

    for macro, stress in zip(
        macro_scenarios,
        stress_scenarios,
    ):

        rows.append(
            {
                "scenario":
                    macro.name,

                "macro_regime":
                    classify_macro_regime(
                        macro
                    ),

                "equity_shock":
                    stress.equity_shock,

                "etf_fund_shock":
                    stress.etf_fund_shock,

                "fixed_income_shock":
                    stress.fixed_income_shock,

                "option_shock":
                    stress.option_shock,

                "future_shock":
                    stress.future_shock,

                "fx_shock":
                    stress.fx_shock,

                "commodity_shock":
                    stress.commodity_shock,

                "crypto_shock":
                    stress.crypto_shock,

                "real_estate_shock":
                    stress.real_estate_shock,

                "interest_rate_shock_bps":
                    stress.interest_rate_shock_bps,

                "credit_spread_shock_bps":
                    stress.credit_spread_shock_bps,

                "volatility_multiplier":
                    stress.volatility_multiplier,
            }
        )

    return pd.DataFrame(
        rows
    )


# ==============================================================
# CORRECTED REGIME SUMMARY
# ==============================================================

def build_regime_summary(
    scenario_results: pd.DataFrame,
    macro_inputs: pd.DataFrame,
) -> pd.DataFrame:

    if (
        scenario_results.empty
        or macro_inputs.empty
    ):
        return pd.DataFrame()

    working = (
        scenario_results.copy()
    )

    # ----------------------------------------------------------
    # IMPORTANT DAY 62 FIX
    #
    # If macro_regime is already attached by main(), do NOT
    # merge it again. Re-merging creates macro_regime_x and
    # macro_regime_y and causes:
    #
    # KeyError: 'macro_regime'
    # ----------------------------------------------------------

    if (
        "macro_regime"
        not in working.columns
    ):

        regime_map = (
            macro_inputs[
                [
                    "name",
                    "macro_regime",
                ]
            ]
            .rename(
                columns={
                    "name":
                        "scenario",
                }
            )
        )

        working = (
            working
            .merge(
                regime_map,
                on="scenario",
                how="left",
                validate="many_to_one",
            )
        )

    if (
        "macro_regime"
        not in working.columns
    ):

        raise KeyError(
            "macro_regime could not be attached "
            "to scenario results."
        )

    result = (
        working
        .groupby(
            "macro_regime",
            as_index=False,
            dropna=False,
        )
        .agg(
            scenarios=(
                "scenario",
                "count",
            ),

            average_portfolio_return=(
                "portfolio_return",
                "mean",
            ),

            worst_portfolio_return=(
                "portfolio_return",
                "min",
            ),

            best_portfolio_return=(
                "portfolio_return",
                "max",
            ),

            average_portfolio_pnl=(
                "portfolio_pnl",
                "mean",
            ),
        )
    )

    return result


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day62(
    macro_scenarios,
    stress_scenarios,
    macro_inputs,
    translated,
    instrument_results,
    portfolio_results,
    asset_results,
    regime_summary,
) -> pd.DataFrame:

    checks = []

    def add(
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

    add(
        "Macro scenario library generated",

        len(macro_scenarios) > 0,

        (
            f"Macro scenarios: "
            f"{len(macro_scenarios)}"
        ),
    )

    add(
        "Every macro scenario translated",

        (
            len(macro_scenarios)
            == len(stress_scenarios)
        ),

        (
            f"Macro={len(macro_scenarios)}, "
            f"translated={len(stress_scenarios)}"
        ),
    )

    add(
        "Macro input table generated",

        not macro_inputs.empty,

        (
            f"Rows: "
            f"{len(macro_inputs)}"
        ),
    )

    add(
        "Translated scenario table generated",

        not translated.empty,

        (
            f"Rows: "
            f"{len(translated)}"
        ),
    )

    add(
        "Instrument stress results generated",

        not instrument_results.empty,

        (
            f"Rows: "
            f"{len(instrument_results)}"
        ),
    )

    add(
        "Portfolio results generated",

        not portfolio_results.empty,

        (
            f"Rows: "
            f"{len(portfolio_results)}"
        ),
    )

    add(
        "Asset-class attribution generated",

        not asset_results.empty,

        (
            f"Rows: "
            f"{len(asset_results)}"
        ),
    )

    add(
        "Macro regime summary generated",

        not regime_summary.empty,

        (
            f"Rows: "
            f"{len(regime_summary)}"
        ),
    )

    finite_pass = True

    if not portfolio_results.empty:

        numeric = (
            portfolio_results[
                [
                    "base_portfolio_value",
                    "stressed_portfolio_value",
                    "portfolio_pnl",
                    "portfolio_return",
                ]
            ]
            .apply(
                pd.to_numeric,
                errors="coerce",
            )
        )

        finite_pass = bool(
            np.isfinite(
                numeric.to_numpy(
                    dtype=float
                )
            ).all()
        )

    add(
        "Portfolio results contain finite values",

        finite_pass,

        (
            "Core portfolio stress outputs "
            "must contain finite values."
        ),
    )

    baseline_pass = False

    if not portfolio_results.empty:

        baseline = (
            portfolio_results.loc[
                portfolio_results[
                    "scenario"
                ]
                == "Macro Baseline"
            ]
        )

        if not baseline.empty:

            baseline_return = float(
                baseline.iloc[0][
                    "portfolio_return"
                ]
            )

            baseline_pass = (
                abs(
                    baseline_return
                )
                < 1e-10
            )

    add(
        "Macro baseline approximately zero",

        baseline_pass,

        (
            "Control scenario should produce "
            "approximately zero portfolio change."
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
# MAIN
# ==============================================================

def main() -> None:

    print_section(
        "VITTANTRA — DAY 62 CONFIGURABLE MACRO SCENARIO ENGINE"
    )

    print(
        "Translating macroeconomic assumptions "
        "into cross-asset portfolio stresses."
    )

    print()

    print(
        "Important:"
    )

    print(
        "Macro-to-market relationships are transparent "
        "scenario assumptions."
    )

    print(
        "They are not forecasts or claims of future "
        "market behavior."
    )

    # ----------------------------------------------------------
    # Portfolio foundation
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

    # ----------------------------------------------------------
    # Macro scenarios
    # ----------------------------------------------------------

    macro_scenarios = (
        build_macro_scenario_library()
    )

    macro_inputs = (
        build_macro_input_table(
            macro_scenarios
        )
    )

    print_section(
        "MACRO SCENARIOS"
    )

    print(
        macro_inputs[
            [
                "name",
                "macro_regime",
                "gdp_growth_change_pct",
                "inflation_change_pct",
                "policy_rate_change_bps",
                "credit_spread_change_bps",
                "volatility_change_pct",
            ]
        ]
        .to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Translate to Day 61 stress scenarios
    # ----------------------------------------------------------

    stress_scenarios = [

        translate_macro_scenario(
            scenario
        )

        for scenario
        in macro_scenarios
    ]

    translated = (
        build_translated_scenario_table(
            macro_scenarios,
            stress_scenarios,
        )
    )

    print_section(
        "TRANSLATED CROSS-ASSET SHOCKS"
    )

    print(
        translated[
            [
                "scenario",
                "macro_regime",
                "equity_shock",
                "fixed_income_shock",
                "commodity_shock",
                "crypto_shock",
                "real_estate_shock",
                "interest_rate_shock_bps",
                "credit_spread_shock_bps",
            ]
        ]
        .to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Run Day 61 stress engine
    # ----------------------------------------------------------

    instrument_results = (
        run_cross_asset_stress(
            instruments=instruments,
            scenarios=stress_scenarios,
        )
    )

    portfolio_results = (
        build_scenario_summary(
            instrument_results
        )
    )

    asset_results = (
        build_asset_class_stress(
            instrument_results
        )
    )

    # ----------------------------------------------------------
    # Attach macro regime ONCE
    # ----------------------------------------------------------

    regime_map = (
        macro_inputs[
            [
                "name",
                "macro_regime",
            ]
        ]
        .rename(
            columns={
                "name":
                    "scenario",
            }
        )
    )

    portfolio_results = (
        portfolio_results
        .merge(
            regime_map,
            on="scenario",
            how="left",
            validate="one_to_one",
        )
    )

    asset_results = (
        asset_results
        .merge(
            regime_map,
            on="scenario",
            how="left",
            validate="many_to_one",
        )
    )

    instrument_results = (
        instrument_results
        .merge(
            regime_map,
            on="scenario",
            how="left",
            validate="many_to_one",
        )
    )

    # ----------------------------------------------------------
    # Scenario ranking and loss concentration
    # ----------------------------------------------------------

    ranking = (
        build_scenario_ranking(
            portfolio_results
        )
    )

    concentration = (
        build_loss_concentration(
            instrument_results
        )
    )

    if not ranking.empty:

        ranking = (
            ranking
            .merge(
                concentration,
                on="scenario",
                how="left",
            )
        )

    # ----------------------------------------------------------
    # Macro regime summary
    # ----------------------------------------------------------

    regime_summary = (
        build_regime_summary(
            scenario_results=portfolio_results,
            macro_inputs=macro_inputs,
        )
    )

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    validation = (
        validate_day62(
            macro_scenarios=macro_scenarios,
            stress_scenarios=stress_scenarios,
            macro_inputs=macro_inputs,
            translated=translated,
            instrument_results=instrument_results,
            portfolio_results=portfolio_results,
            asset_results=asset_results,
            regime_summary=regime_summary,
        )
    )

    # ----------------------------------------------------------
    # Save
    # ----------------------------------------------------------

    macro_inputs.to_csv(
        OUTPUT_MACRO_INPUTS,
        index=False,
    )

    translated.to_csv(
        OUTPUT_TRANSLATED_SCENARIOS,
        index=False,
    )

    portfolio_results.to_csv(
        OUTPUT_PORTFOLIO_RESULTS,
        index=False,
    )

    asset_results.to_csv(
        OUTPUT_ASSET_CLASS_RESULTS,
        index=False,
    )

    instrument_results.to_csv(
        OUTPUT_INSTRUMENT_RESULTS,
        index=False,
    )

    regime_summary.to_csv(
        OUTPUT_REGIME_SUMMARY,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )

    # ----------------------------------------------------------
    # Portfolio output
    # ----------------------------------------------------------

    print_section(
        "MACRO PORTFOLIO RESULTS"
    )

    ranked_results = (
        portfolio_results
        .sort_values(
            "portfolio_return",
            ascending=True,
        )
        .reset_index(
            drop=True
        )
    )

    print(
        ranked_results[
            [
                "scenario",
                "macro_regime",
                "portfolio_pnl",
                "portfolio_return",
            ]
        ]
        .to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Worst macro scenario
    # ----------------------------------------------------------

    if not ranked_results.empty:

        worst = (
            ranked_results.iloc[0]
        )

        print_section(
            "WORST MACRO SCENARIO"
        )

        print(
            f"Scenario: "
            f"{worst['scenario']}"
        )

        print(
            f"Regime: "
            f"{worst['macro_regime']}"
        )

        print(
            f"Portfolio P&L: "
            f"${worst['portfolio_pnl']:,.2f}"
        )

        print(
            f"Portfolio return: "
            f"{worst['portfolio_return']:.2%}"
        )

    # ----------------------------------------------------------
    # Regime output
    # ----------------------------------------------------------

    print_section(
        "MACRO REGIME SUMMARY"
    )

    print(
        regime_summary
        .to_string(
            index=False
        )
    )

    # ----------------------------------------------------------
    # Validation output
    # ----------------------------------------------------------

    print_section(
        "DAY 62 VALIDATION"
    )

    print(
        validation[
            [
                "check",
                "passed",
                "details",
            ]
        ]
        .to_string(
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
        "DAY 62 OUTPUTS"
    )

    for output in [

        OUTPUT_MACRO_INPUTS,

        OUTPUT_TRANSLATED_SCENARIOS,

        OUTPUT_PORTFOLIO_RESULTS,

        OUTPUT_ASSET_CLASS_RESULTS,

        OUTPUT_INSTRUMENT_RESULTS,

        OUTPUT_REGIME_SUMMARY,

        OUTPUT_VALIDATION,

    ]:

        print(
            output
        )

    # ----------------------------------------------------------
    # Complete
    # ----------------------------------------------------------

    print_section(
        "DAY 62 COMPLETE"
    )

    print(
        "Configurable macro scenario engine completed."
    )

    print()

    print(
        "Vittantra can now:"
    )

    print(
        "• accept configurable macro assumptions"
    )

    print(
        "• classify economic regimes"
    )

    print(
        "• translate GDP assumptions into market shocks"
    )

    print(
        "• translate inflation and rate assumptions"
    )

    print(
        "• translate credit-spread changes"
    )

    print(
        "• translate oil and commodity assumptions"
    )

    print(
        "• translate USD / FX changes"
    )

    print(
        "• translate volatility conditions"
    )

    print(
        "• incorporate liquidity and unemployment"
    )

    print(
        "• incorporate housing and earnings assumptions"
    )

    print(
        "• feed those shocks directly into Day 61"
    )

    print(
        "• calculate portfolio and asset-class consequences"
    )

    print(
        "• summarize risk by macro regime"
    )

    print()

    print(
        "Architecture:"
    )

    print(
        "Economic Data -> Macro Scenario -> Cross-Asset Translation "
        "-> Stress Engine -> Portfolio Risk -> Rebalancing -> Dashboard"
    )


if __name__ == "__main__":
    main()