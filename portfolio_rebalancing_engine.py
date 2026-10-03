"""
VITTANTRA
Day 63 — Constraint-Aware Scenario Rebalancing Engine

Corrected version:
- preserves the 25% maximum position limit
- redistributes excess weight instead of breaking the cap
- preserves approximately 100% total portfolio allocation
- applies turnover controls after concentration controls
- produces BUY / SELL / HOLD research proposals
- estimates transaction costs
- compares before/after scenario exposure

This is a research engine, not an automatic trading system
and not investment advice.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from multi_asset_risk import (
    AssetClass,
    Instrument,
    build_sample_instruments,
)

from unified_risk_engine import (
    calculate_asset_class_exposure,
    calculate_portfolio_value,
    enrich_sample_instruments,
)

from cross_asset_stress import (
    build_asset_class_stress,
    build_scenario_summary,
    run_cross_asset_stress,
)

from macro_scenario_engine import (
    MacroScenario,
    build_macro_scenario_library,
    classify_macro_regime,
    translate_macro_scenario,
)


# ==============================================================
# EXISTING RISK POLICY
# ==============================================================

try:
    from risk_engine import MAX_POSITION_WEIGHT

except Exception:
    MAX_POSITION_WEIGHT = 0.25


try:
    from risk_engine import MIN_CASH_RESERVE

except Exception:
    MIN_CASH_RESERVE = 1000.0


# ==============================================================
# OUTPUT FILES
# ==============================================================

OUTPUT_CURRENT_PORTFOLIO = Path(
    "day63_current_portfolio.csv"
)

OUTPUT_ASSET_CLASS_TARGETS = Path(
    "day63_asset_class_targets.csv"
)

OUTPUT_REBALANCE_ORDERS = Path(
    "day63_rebalance_orders.csv"
)

OUTPUT_REBALANCE_SUMMARY = Path(
    "day63_rebalance_summary.csv"
)

OUTPUT_BEFORE_AFTER = Path(
    "day63_before_after_risk.csv"
)

OUTPUT_SCENARIO_SELECTION = Path(
    "day63_scenario_selection.csv"
)

OUTPUT_VALIDATION = Path(
    "day63_validation_summary.csv"
)


# ==============================================================
# CONSTANTS
# ==============================================================

EPSILON = 1e-12

DEFAULT_TRANSACTION_COST_BPS = 10.0

DEFAULT_MIN_TRADE_WEIGHT = 0.0025

DEFAULT_MAX_ONE_WAY_TURNOVER = 0.35


# ==============================================================
# POLICY
# ==============================================================

@dataclass(frozen=True)
class RebalancingPolicy:

    transaction_cost_bps: float = (
        DEFAULT_TRANSACTION_COST_BPS
    )

    min_trade_weight: float = (
        DEFAULT_MIN_TRADE_WEIGHT
    )

    max_one_way_turnover: float = (
        DEFAULT_MAX_ONE_WAY_TURNOVER
    )

    max_position_weight: float = float(
        MAX_POSITION_WEIGHT
    )

    min_cash_reserve: float = float(
        MIN_CASH_RESERVE
    )

    downside_sensitivity: float = 3.0

    upside_sensitivity: float = 1.0


# ==============================================================
# ORDER OBJECT
# ==============================================================

@dataclass
class RebalanceOrder:

    instrument_id: str

    symbol: str

    asset_class: str

    current_market_value: float

    current_weight: float

    target_weight: float

    target_market_value: float

    trade_value: float

    trade_weight: float

    action: str

    approximate_unit_change: float

    estimated_transaction_cost: float

    scenario: str

    scenario_asset_class_return: float

    rationale: str


# ==============================================================
# UTILITIES
# ==============================================================

def safe_float(
    value,
) -> Optional[float]:

    if value is None:
        return None

    try:
        value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not np.isfinite(
        value
    ):
        return None

    return value


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

    print(
        "=" * 82
    )

    print(
        title
    )

    print(
        "=" * 82
    )


# ==============================================================
# ASSET CLASS CAPS
# ==============================================================

def asset_class_max_weights() -> Dict[str, float]:

    return {

        AssetClass.EQUITY.value:
            0.35,

        AssetClass.ETF_FUND.value:
            0.35,

        AssetClass.FIXED_INCOME.value:
            0.40,

        AssetClass.OPTION.value:
            0.08,

        AssetClass.FUTURE.value:
            0.10,

        AssetClass.FX.value:
            0.10,

        AssetClass.COMMODITY.value:
            0.15,

        AssetClass.CASH.value:
            0.30,

        AssetClass.CRYPTO.value:
            0.10,

        AssetClass.REAL_ESTATE.value:
            0.20,

        AssetClass.OTHER.value:
            0.15,
    }


# ==============================================================
# CURRENT PORTFOLIO
# ==============================================================

def build_current_portfolio(
    instruments: List[Instrument],
) -> pd.DataFrame:

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    rows = []

    for instrument in instruments:

        market_value = safe_float(
            instrument
            .calculate_market_value()
        )

        if market_value is None:
            continue

        current_weight = (
            market_value
            / portfolio_value
            if portfolio_value
            > EPSILON
            else np.nan
        )

        price = safe_float(
            getattr(
                instrument,
                "price",
                None,
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

        rows.append(
            {
                "instrument_id":
                    instrument.instrument_id,

                "symbol":
                    instrument.symbol,

                "asset_class":
                    instrument.asset_class.value,

                "quantity":
                    quantity,

                "price":
                    price,

                "contract_multiplier":
                    multiplier,

                "market_value":
                    market_value,

                "current_weight":
                    current_weight,
            }
        )

    return pd.DataFrame(
        rows
    )


# ==============================================================
# SCENARIO SELECTION
# ==============================================================

def select_macro_scenario(
    instruments: List[Instrument],
    scenarios: List[MacroScenario],
) -> Tuple[
    MacroScenario,
    pd.DataFrame,
]:

    requested = (
        os.getenv(
            "VITTANTRA_REBALANCE_SCENARIO",
            "",
        )
        .strip()
        .lower()
    )

    translated = [

        translate_macro_scenario(
            scenario
        )

        for scenario
        in scenarios
    ]

    stress_results = (
        run_cross_asset_stress(
            instruments=instruments,
            scenarios=translated,
        )
    )

    summary = (
        build_scenario_summary(
            stress_results
        )
    )

    if requested:

        for scenario in scenarios:

            if (
                scenario.name
                .strip()
                .lower()
                == requested
            ):

                return (
                    scenario,
                    summary,
                )

    if summary.empty:

        return (
            scenarios[0],
            summary,
        )

    worst_name = (
        summary
        .sort_values(
            "portfolio_return",
            ascending=True,
        )
        .iloc[0][
            "scenario"
        ]
    )

    selected = next(
        (
            scenario
            for scenario
            in scenarios
            if scenario.name
            == worst_name
        ),
        scenarios[0],
    )

    return (
        selected,
        summary,
    )


# ==============================================================
# SELECTED SCENARIO STRESS
# ==============================================================

def get_selected_asset_class_stress(
    instruments: List[Instrument],
    scenario: MacroScenario,
) -> pd.DataFrame:

    translated = (
        translate_macro_scenario(
            scenario
        )
    )

    stress_results = (
        run_cross_asset_stress(
            instruments=instruments,
            scenarios=[
                translated
            ],
        )
    )

    result = (
        build_asset_class_stress(
            stress_results
        )
    )

    if result.empty:
        return result

    return (
        result
        .rename(
            columns={
                "asset_class_return":
                    "scenario_return",
            }
        )
    )


# ==============================================================
# CAPPED WEIGHT PROJECTION
# ==============================================================

def project_weights_with_caps(
    raw_weights: Dict[str, float],
    caps: Dict[str, float],
    total_target: float = 1.0,
) -> Dict[str, float]:
    """
    Redistribute weight while enforcing caps.

    Unlike the previous Day 63 implementation,
    this does NOT cap and then blindly renormalize,
    because doing so can push capped positions
    above their limits again.
    """

    keys = list(
        raw_weights.keys()
    )

    if not keys:
        return {}

    cap_total = sum(
        caps.get(
            key,
            1.0,
        )
        for key
        in keys
    )

    if (
        cap_total
        + 1e-10
        < total_target
    ):

        raise ValueError(
            "Portfolio caps are infeasible."
        )

    raw = {

        key:
            max(
                0.0,
                float(
                    raw_weights[
                        key
                    ]
                ),
            )

        for key
        in keys
    }

    if (
        sum(
            raw.values()
        )
        <= EPSILON
    ):

        raw = {
            key:
                1.0
            for key
            in keys
        }

    weights = {
        key:
            0.0
        for key
        in keys
    }

    remaining_keys = set(
        keys
    )

    remaining_target = float(
        total_target
    )

    while remaining_keys:

        denominator = sum(
            raw[key]
            for key
            in remaining_keys
        )

        if denominator <= EPSILON:

            denominator = float(
                len(
                    remaining_keys
                )
            )

            proportional = {
                key:
                    1.0
                for key
                in remaining_keys
            }

        else:

            proportional = {
                key:
                    raw[key]
                for key
                in remaining_keys
            }

        proposed = {

            key:
                remaining_target
                * proportional[key]
                / denominator

            for key
            in remaining_keys
        }

        violations = [

            key

            for key
            in remaining_keys

            if (
                proposed[key]
                > caps.get(
                    key,
                    1.0,
                )
                + 1e-12
            )
        ]

        if not violations:

            for key in remaining_keys:

                weights[key] = (
                    proposed[
                        key
                    ]
                )

            break

        for key in violations:

            cap = float(
                caps.get(
                    key,
                    1.0,
                )
            )

            weights[
                key
            ] = cap

            remaining_target -= (
                cap
            )

            remaining_keys.remove(
                key
            )

        if (
            remaining_target
            < -1e-10
        ):

            raise ValueError(
                "Unable to satisfy weight caps."
            )

    residual = (
        total_target
        - sum(
            weights.values()
        )
    )

    if (
        abs(
            residual
        )
        > 1e-8
    ):

        eligible = [

            key

            for key
            in keys

            if (
                weights[key]
                < caps.get(
                    key,
                    1.0,
                )
                - 1e-10
            )
        ]

        while (
            abs(
                residual
            )
            > 1e-8
            and eligible
        ):

            if residual > 0:

                total_capacity = sum(

                    caps.get(
                        key,
                        1.0,
                    )
                    - weights[
                        key
                    ]

                    for key
                    in eligible
                )

                if (
                    total_capacity
                    <= EPSILON
                ):
                    break

                for key in list(
                    eligible
                ):

                    capacity = (
                        caps.get(
                            key,
                            1.0,
                        )
                        - weights[
                            key
                        ]
                    )

                    addition = min(
                        capacity,
                        residual
                        * capacity
                        / total_capacity,
                    )

                    weights[
                        key
                    ] += addition

                residual = (
                    total_target
                    - sum(
                        weights.values()
                    )
                )

            else:

                total_weight = sum(
                    weights[key]
                    for key
                    in eligible
                )

                if total_weight <= EPSILON:
                    break

                for key in list(
                    eligible
                ):

                    reduction = min(
                        weights[key],
                        (
                            -residual
                            * weights[key]
                            / total_weight
                        ),
                    )

                    weights[
                        key
                    ] -= reduction

                residual = (
                    total_target
                    - sum(
                        weights.values()
                    )
                )

            eligible = [

                key

                for key
                in keys

                if (
                    weights[key]
                    < caps.get(
                        key,
                        1.0,
                    )
                    - 1e-10
                )
            ]

    if (
        abs(
            sum(
                weights.values()
            )
            - total_target
        )
        > 1e-6
    ):

        raise ValueError(
            "Final portfolio weights "
            "do not sum to target."
        )

    for key in keys:

        if (
            weights[key]
            > caps.get(
                key,
                1.0,
            )
            + 1e-8
        ):

            raise ValueError(
                f"Position {key} violates cap."
            )

    return weights


# ==============================================================
# ASSET CLASS TARGETS
# ==============================================================

def build_asset_class_targets(
    instruments: List[Instrument],
    asset_stress: pd.DataFrame,
    policy: RebalancingPolicy,
) -> pd.DataFrame:

    exposure = (
        calculate_asset_class_exposure(
            instruments
        )
    )

    if exposure.empty:
        return pd.DataFrame()

    exposure = (
        exposure
        .rename(
            columns={
                "weight":
                    "current_weight",
            }
        )
    )

    stress_lookup = {}

    if not asset_stress.empty:

        stress_lookup = dict(
            zip(
                asset_stress[
                    "asset_class"
                ],
                asset_stress[
                    "scenario_return"
                ],
            )
        )

    raw_weights = {}

    rows = []

    for _, row in (
        exposure.iterrows()
    ):

        asset_class = str(
            row[
                "asset_class"
            ]
        )

        current_weight = float(
            row[
                "current_weight"
            ]
        )

        scenario_return = float(
            stress_lookup.get(
                asset_class,
                0.0,
            )
        )

        if (
            scenario_return
            < 0.0
        ):

            multiplier = np.exp(
                policy.downside_sensitivity
                * scenario_return
            )

        else:

            multiplier = np.exp(
                policy.upside_sensitivity
                * scenario_return
            )

        raw_target = (
            current_weight
            * multiplier
        )

        raw_weights[
            asset_class
        ] = raw_target

        rows.append(
            {
                "asset_class":
                    asset_class,

                "current_market_value":
                    float(
                        row[
                            "market_value"
                        ]
                    ),

                "current_weight":
                    current_weight,

                "scenario_return":
                    scenario_return,

                "scenario_multiplier":
                    multiplier,

                "raw_target_weight":
                    raw_target,
            }
        )

    target_weights = (
        project_weights_with_caps(
            raw_weights=raw_weights,
            caps=(
                asset_class_max_weights()
            ),
        )
    )

    result = pd.DataFrame(
        rows
    )

    result[
        "target_weight"
    ] = (
        result[
            "asset_class"
        ]
        .map(
            target_weights
        )
    )

    result[
        "weight_change"
    ] = (
        result[
            "target_weight"
        ]
        - result[
            "current_weight"
        ]
    )

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    result[
        "target_market_value"
    ] = (
        result[
            "target_weight"
        ]
        * portfolio_value
    )

    return result


# ==============================================================
# INSTRUMENT TARGETS
# ==============================================================

def build_instrument_targets(
    current_portfolio: pd.DataFrame,
    asset_targets: pd.DataFrame,
    policy: RebalancingPolicy,
) -> pd.DataFrame:

    portfolio_value = float(
        current_portfolio[
            "market_value"
        ]
        .sum()
    )

    target_lookup = dict(
        zip(
            asset_targets[
                "asset_class"
            ],
            asset_targets[
                "target_weight"
            ],
        )
    )

    rows = []

    for (
        asset_class,
        group,
    ) in (
        current_portfolio
        .groupby(
            "asset_class",
            sort=False,
        )
    ):

        current_class_value = float(
            group[
                "market_value"
            ]
            .sum()
        )

        class_target = float(
            target_lookup.get(
                asset_class,
                0.0,
            )
        )

        for _, row in (
            group.iterrows()
        ):

            if (
                current_class_value
                > EPSILON
            ):

                within_class = (
                    float(
                        row[
                            "market_value"
                        ]
                    )
                    / current_class_value
                )

            else:

                within_class = (
                    1.0
                    / len(
                        group
                    )
                )

            raw_target = (
                class_target
                * within_class
            )

            rows.append(
                {
                    **row.to_dict(),

                    "raw_target_weight":
                        raw_target,
                }
            )

    result = pd.DataFrame(
        rows
    )

    raw_weights = dict(
        zip(
            result[
                "instrument_id"
            ].astype(
                str
            ),

            result[
                "raw_target_weight"
            ].astype(
                float
            ),
        )
    )

    caps = {

        str(
            instrument_id
        ):
            policy.max_position_weight

        for instrument_id
        in result[
            "instrument_id"
        ]
    }

    capped = (
        project_weights_with_caps(
            raw_weights=raw_weights,
            caps=caps,
        )
    )

    result[
        "target_weight"
    ] = (
        result[
            "instrument_id"
        ]
        .astype(
            str
        )
        .map(
            capped
        )
    )

    return result


# ==============================================================
# TURNOVER LIMIT
# ==============================================================

def apply_turnover_limit(
    targets: pd.DataFrame,
    policy: RebalancingPolicy,
) -> pd.DataFrame:

    result = (
        targets.copy()
    )

    current_max = float(
        result[
            "current_weight"
        ]
        .max()
    )

    if (
        current_max
        > policy.max_position_weight
        + 1e-8
    ):

        raise ValueError(
            "Current portfolio already exceeds "
            "the configured position cap."
        )

    changes = (
        result[
            "target_weight"
        ]
        - result[
            "current_weight"
        ]
    )

    turnover = (
        0.5
        * changes
        .abs()
        .sum()
    )

    if (
        turnover
        > policy.max_one_way_turnover
    ):

        scale = (
            policy.max_one_way_turnover
            / turnover
        )

        result[
            "target_weight"
        ] = (

            result[
                "current_weight"
            ]

            + scale
            * changes
        )

        result[
            "turnover_scale"
        ] = scale

    else:

        result[
            "turnover_scale"
        ] = 1.0

    return result


# ==============================================================
# ORDER GENERATION
# ==============================================================

def build_rebalance_orders(
    instruments: List[Instrument],
    targets: pd.DataFrame,
    asset_stress: pd.DataFrame,
    scenario: MacroScenario,
    policy: RebalancingPolicy,
) -> pd.DataFrame:

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    stress_lookup = {}

    if not asset_stress.empty:

        stress_lookup = dict(
            zip(
                asset_stress[
                    "asset_class"
                ],
                asset_stress[
                    "scenario_return"
                ],
            )
        )

    instrument_lookup = {

        instrument.instrument_id:
            instrument

        for instrument
        in instruments
    }

    orders = []

    for _, row in (
        targets.iterrows()
    ):

        current_weight = float(
            row[
                "current_weight"
            ]
        )

        target_weight = float(
            row[
                "target_weight"
            ]
        )

        trade_weight = (
            target_weight
            - current_weight
        )

        if (
            abs(
                trade_weight
            )
            < policy.min_trade_weight
        ):

            target_weight = (
                current_weight
            )

            trade_weight = 0.0

            action = "HOLD"

        elif (
            trade_weight
            > 0.0
        ):

            action = "BUY"

        else:

            action = "SELL"

        current_value = float(
            row[
                "market_value"
            ]
        )

        target_value = (
            target_weight
            * portfolio_value
        )

        trade_value = (
            target_value
            - current_value
        )

        transaction_cost = (
            abs(
                trade_value
            )
            * policy.transaction_cost_bps
            / 10000.0
        )

        instrument_id = str(
            row[
                "instrument_id"
            ]
        )

        instrument = (
            instrument_lookup.get(
                instrument_id
            )
        )

        approximate_units = np.nan

        if instrument is not None:

            price = safe_float(
                getattr(
                    instrument,
                    "price",
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
                price is not None
                and price > EPSILON
                and instrument.asset_class
                not in {
                    AssetClass.OPTION,
                    AssetClass.FUTURE,
                }
            ):

                approximate_units = (
                    trade_value
                    / (
                        price
                        * multiplier
                    )
                )

        asset_class = str(
            row[
                "asset_class"
            ]
        )

        scenario_return = float(
            stress_lookup.get(
                asset_class,
                0.0,
            )
        )

        if action == "SELL":

            rationale = (
                "Reduce scenario vulnerability."
            )

        elif action == "BUY":

            rationale = (
                "Increase scenario-resilient exposure "
                "within portfolio constraints."
            )

        else:

            rationale = (
                "Change below rebalance threshold."
            )

        orders.append(
            asdict(
                RebalanceOrder(
                    instrument_id=(
                        instrument_id
                    ),

                    symbol=str(
                        row[
                            "symbol"
                        ]
                    ),

                    asset_class=(
                        asset_class
                    ),

                    current_market_value=(
                        current_value
                    ),

                    current_weight=(
                        current_weight
                    ),

                    target_weight=(
                        target_weight
                    ),

                    target_market_value=(
                        target_value
                    ),

                    trade_value=(
                        trade_value
                    ),

                    trade_weight=(
                        trade_weight
                    ),

                    action=(
                        action
                    ),

                    approximate_unit_change=(
                        float(
                            approximate_units
                        )
                        if np.isfinite(
                            approximate_units
                        )
                        else np.nan
                    ),

                    estimated_transaction_cost=(
                        transaction_cost
                    ),

                    scenario=(
                        scenario.name
                    ),

                    scenario_asset_class_return=(
                        scenario_return
                    ),

                    rationale=(
                        rationale
                    ),
                )
            )
        )

    orders = pd.DataFrame(
        orders
    )

    #
    # HOLD thresholding may create tiny residual weight.
    # Redistribute residual ONLY to positions below the cap.
    #

    residual = (
        1.0
        - orders[
            "target_weight"
        ]
        .sum()
    )

    if (
        abs(
            residual
        )
        > 1e-8
    ):

        if residual > 0:

            for _ in range(
                100
            ):

                eligible = (

                    orders[
                        "target_weight"
                    ]
                    < (
                        policy.max_position_weight
                        - 1e-10
                    )
                )

                if not eligible.any():
                    break

                capacity = (

                    policy.max_position_weight
                    - orders.loc[
                        eligible,
                        "target_weight",
                    ]
                )

                total_capacity = (
                    capacity.sum()
                )

                if (
                    total_capacity
                    <= EPSILON
                ):
                    break

                additions = (
                    residual
                    * capacity
                    / total_capacity
                )

                additions = np.minimum(
                    additions,
                    capacity,
                )

                orders.loc[
                    eligible,
                    "target_weight",
                ] += additions

                residual = (
                    1.0
                    - orders[
                        "target_weight"
                    ]
                    .sum()
                )

                if (
                    abs(
                        residual
                    )
                    < 1e-8
                ):
                    break

        else:

            positive = (
                orders[
                    "target_weight"
                ]
                > 1e-10
            )

            total_positive = (
                orders.loc[
                    positive,
                    "target_weight",
                ]
                .sum()
            )

            if (
                total_positive
                > EPSILON
            ):

                reductions = (

                    -residual

                    * orders.loc[
                        positive,
                        "target_weight",
                    ]

                    / total_positive
                )

                orders.loc[
                    positive,
                    "target_weight",
                ] -= reductions

    orders[
        "target_market_value"
    ] = (
        orders[
            "target_weight"
        ]
        * portfolio_value
    )

    orders[
        "trade_value"
    ] = (
        orders[
            "target_market_value"
        ]
        - orders[
            "current_market_value"
        ]
    )

    orders[
        "trade_weight"
    ] = (
        orders[
            "target_weight"
        ]
        - orders[
            "current_weight"
        ]
    )

    orders[
        "estimated_transaction_cost"
    ] = (
        orders[
            "trade_value"
        ]
        .abs()
        * policy.transaction_cost_bps
        / 10000.0
    )

    return orders


# ==============================================================
# BEFORE / AFTER
# ==============================================================

def build_before_after(
    orders: pd.DataFrame,
) -> pd.DataFrame:

    before_return = float(
        (
            orders[
                "current_weight"
            ]
            * orders[
                "scenario_asset_class_return"
            ]
        )
        .sum()
    )

    after_return = float(
        (
            orders[
                "target_weight"
            ]
            * orders[
                "scenario_asset_class_return"
            ]
        )
        .sum()
    )

    portfolio_value = float(
        orders[
            "current_market_value"
        ]
        .sum()
    )

    costs = float(
        orders[
            "estimated_transaction_cost"
        ]
        .sum()
    )

    before_pnl = (
        portfolio_value
        * before_return
    )

    after_pnl = (
        portfolio_value
        * after_return
        - costs
    )

    return pd.DataFrame(
        [
            {
                "metric":
                    "portfolio_value",

                "before":
                    portfolio_value,

                "after":
                    portfolio_value,

                "difference":
                    0.0,
            },

            {
                "metric":
                    "scenario_return",

                "before":
                    before_return,

                "after":
                    after_return,

                "difference":
                    after_return
                    - before_return,
            },

            {
                "metric":
                    "scenario_pnl",

                "before":
                    before_pnl,

                "after":
                    after_pnl,

                "difference":
                    after_pnl
                    - before_pnl,
            },

            {
                "metric":
                    "transaction_cost",

                "before":
                    0.0,

                "after":
                    costs,

                "difference":
                    costs,
            },
        ]
    )


# ==============================================================
# SUMMARY
# ==============================================================

def build_summary(
    orders: pd.DataFrame,
    scenario: MacroScenario,
    portfolio_value: float,
) -> pd.DataFrame:

    gross_trading = float(
        orders[
            "trade_value"
        ]
        .abs()
        .sum()
    )

    turnover = (
        0.5
        * gross_trading
        / portfolio_value
    )

    return pd.DataFrame(
        [
            {
                "scenario":
                    scenario.name,

                "macro_regime":
                    classify_macro_regime(
                        scenario
                    ),

                "portfolio_value":
                    portfolio_value,

                "gross_trading":
                    gross_trading,

                "one_way_turnover":
                    turnover,

                "transaction_cost":
                    float(
                        orders[
                            "estimated_transaction_cost"
                        ]
                        .sum()
                    ),

                "buy_orders":
                    int(
                        (
                            orders[
                                "action"
                            ]
                            == "BUY"
                        )
                        .sum()
                    ),

                "sell_orders":
                    int(
                        (
                            orders[
                                "action"
                            ]
                            == "SELL"
                        )
                        .sum()
                    ),

                "hold_orders":
                    int(
                        (
                            orders[
                                "action"
                            ]
                            == "HOLD"
                        )
                        .sum()
                    ),
            }
        ]
    )


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day63(
    portfolio: pd.DataFrame,
    asset_targets: pd.DataFrame,
    orders: pd.DataFrame,
    summary: pd.DataFrame,
    before_after: pd.DataFrame,
    policy: RebalancingPolicy,
) -> pd.DataFrame:

    checks = []

    def add(
        name,
        passed,
        details,
    ):

        checks.append(
            {
                "check":
                    name,

                "passed":
                    bool(
                        passed
                    ),

                "details":
                    details,
            }
        )

    add(
        "Current portfolio generated",

        not portfolio.empty,

        (
            f"Positions: "
            f"{len(portfolio)}"
        ),
    )

    add(
        "Asset-class targets generated",

        not asset_targets.empty,

        (
            f"Asset classes: "
            f"{len(asset_targets)}"
        ),
    )

    add(
        "Rebalance orders generated",

        not orders.empty,

        (
            f"Positions: "
            f"{len(orders)}"
        ),
    )

    target_sum = float(
        orders[
            "target_weight"
        ]
        .sum()
    )

    add(
        "Target weights approximately sum to one",

        abs(
            target_sum
            - 1.0
        )
        < 1e-6,

        (
            f"Target sum: "
            f"{target_sum:.8f}"
        ),
    )

    add(
        "No negative target weights",

        (
            orders[
                "target_weight"
            ]
            >= -EPSILON
        )
        .all(),

        "Long-only target portfolio.",
    )

    largest_weight = float(
        orders[
            "target_weight"
        ]
        .max()
    )

    add(
        "Position concentration within policy",

        largest_weight
        <= (
            policy.max_position_weight
            + 1e-6
        ),

        (
            f"Largest target weight: "
            f"{largest_weight:.4%}; "
            f"limit: "
            f"{policy.max_position_weight:.4%}"
        ),
    )

    finite = (

        orders[
            [
                "current_market_value",
                "current_weight",
                "target_weight",
                "target_market_value",
                "trade_value",
                "trade_weight",
                "estimated_transaction_cost",
            ]
        ]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
    )

    add(
        "Core order fields contain finite values",

        np.isfinite(
            finite.to_numpy(
                dtype=float
            )
        )
        .all(),

        "Allocation fields are finite.",
    )

    add(
        "All actions valid",

        orders[
            "action"
        ]
        .isin(
            [
                "BUY",
                "SELL",
                "HOLD",
            ]
        )
        .all(),

        "BUY / SELL / HOLD only.",
    )

    add(
        "Rebalance summary generated",

        not summary.empty,

        (
            f"Rows: "
            f"{len(summary)}"
        ),
    )

    add(
        "Before-after analysis generated",

        not before_after.empty,

        (
            f"Rows: "
            f"{len(before_after)}"
        ),
    )

    turnover = float(
        summary.iloc[0][
            "one_way_turnover"
        ]
    )

    add(
        "Turnover within policy",

        turnover
        <= (
            policy.max_one_way_turnover
            + 1e-6
        ),

        (
            f"Turnover: "
            f"{turnover:.4%}; "
            f"limit: "
            f"{policy.max_one_way_turnover:.4%}"
        ),
    )

    result = pd.DataFrame(
        checks
    )

    passed = int(
        result[
            "passed"
        ]
        .sum()
    )

    total = len(
        result
    )

    result[
        "passed_tests"
    ] = passed

    result[
        "total_tests"
    ] = total

    result[
        "pass_rate"
    ] = (
        passed
        / total
    )

    return result


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:

    print_section(
        "VITTANTRA — DAY 63 CONSTRAINT-AWARE REBALANCING"
    )

    instruments = (
        build_sample_instruments()
    )

    instruments = (
        enrich_sample_instruments(
            instruments
        )
    )

    policy = (
        RebalancingPolicy()
    )

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    current_portfolio = (
        build_current_portfolio(
            instruments
        )
    )

    scenarios = (
        build_macro_scenario_library()
    )

    (
        selected_scenario,
        scenario_summary,
    ) = (
        select_macro_scenario(
            instruments,
            scenarios,
        )
    )

    asset_stress = (
        get_selected_asset_class_stress(
            instruments,
            selected_scenario,
        )
    )

    asset_targets = (
        build_asset_class_targets(
            instruments,
            asset_stress,
            policy,
        )
    )

    instrument_targets = (
        build_instrument_targets(
            current_portfolio,
            asset_targets,
            policy,
        )
    )

    instrument_targets = (
        apply_turnover_limit(
            instrument_targets,
            policy,
        )
    )

    orders = (
        build_rebalance_orders(
            instruments,
            instrument_targets,
            asset_stress,
            selected_scenario,
            policy,
        )
    )

    before_after = (
        build_before_after(
            orders
        )
    )

    summary = (
        build_summary(
            orders,
            selected_scenario,
            portfolio_value,
        )
    )

    validation = (
        validate_day63(
            current_portfolio,
            asset_targets,
            orders,
            summary,
            before_after,
            policy,
        )
    )

    selected_scenario_table = (
        scenario_summary.copy()
    )

    if not selected_scenario_table.empty:

        selected_scenario_table[
            "selected"
        ] = (
            selected_scenario_table[
                "scenario"
            ]
            == selected_scenario.name
        )

    current_portfolio.to_csv(
        OUTPUT_CURRENT_PORTFOLIO,
        index=False,
    )

    asset_targets.to_csv(
        OUTPUT_ASSET_CLASS_TARGETS,
        index=False,
    )

    orders.to_csv(
        OUTPUT_REBALANCE_ORDERS,
        index=False,
    )

    summary.to_csv(
        OUTPUT_REBALANCE_SUMMARY,
        index=False,
    )

    before_after.to_csv(
        OUTPUT_BEFORE_AFTER,
        index=False,
    )

    selected_scenario_table.to_csv(
        OUTPUT_SCENARIO_SELECTION,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )

    print_section(
        "SELECTED SCENARIO"
    )

    print(
        selected_scenario.name
    )

    print(
        classify_macro_regime(
            selected_scenario
        )
    )

    print_section(
        "REBALANCE ORDERS"
    )

    print(
        orders[
            [
                "symbol",
                "asset_class",
                "action",
                "current_weight",
                "target_weight",
                "trade_value",
            ]
        ]
        .to_string(
            index=False
        )
    )

    print_section(
        "BEFORE / AFTER"
    )

    print(
        before_after
        .to_string(
            index=False
        )
    )

    print_section(
        "DAY 63 VALIDATION"
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

    passed = int(
        validation[
            "passed"
        ]
        .sum()
    )

    total = len(
        validation
    )

    print()

    print(
        f"Passed: "
        f"{passed}/{total}"
    )

    print(
        f"Pass rate: "
        f"{passed / total:.2%}"
    )

    print_section(
        "DAY 63 COMPLETE"
    )

    print(
        "The rebalancing engine now enforces "
        "the position-concentration limit during "
        "portfolio construction."
    )

    print()

    print(
        "Architecture:"
    )

    print(
        "Economic Data -> Macro Scenario -> Stress Testing -> "
        "Unified Risk -> Constraint-Aware Rebalancing -> Dashboard"
    )


if __name__ == "__main__":
    main()