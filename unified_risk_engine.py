"""
VITTANTRA
Day 60 — Unified Multi-Asset Risk Engine

Purpose
-------
Create the calculation layer that sits on top of Day 59's
multi-asset classification and risk-routing architecture.

Architecture
------------
Instrument
    ↓
Day 59 asset classification / routing
    ↓
Day 60 unified calculation engine
    ↓
Portfolio aggregation
    ↓
Stress testing
    ↓
Rebalancing
    ↓
Dashboard

Design principles
-----------------
1. Reuse existing Vittantra modules where appropriate.
2. Never manufacture unavailable risk metrics.
3. Explicitly report insufficient data.
4. Keep asset-specific risk logic separate.
5. Produce machine-readable outputs for later dashboard use.

Existing modules preserved
--------------------------
multi_asset_risk.py
risk_engine.py
var_engine.py
stress_engine.py
risk_dashboard.py

Day 60 does NOT modify those modules.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from vittantra_live_inputs import (
    live_valuation_date,
    load_price_history,
)

from multi_asset_risk import (
    AssetClass,
    Instrument,
    MetricStatus,
    RISK_METRICS,
    RiskCategory,
    build_sample_instruments,
    get_risk_requirements,
)

# --------------------------------------------------------------
# Optional integration with existing Vittantra VaR engine
# --------------------------------------------------------------

try:
    from var_engine import calculate_historical_var

    EXISTING_VAR_ENGINE_AVAILABLE = True

except Exception:
    calculate_historical_var = None
    EXISTING_VAR_ENGINE_AVAILABLE = False


# ==============================================================
# OUTPUT FILES
# ==============================================================

OUTPUT_INSTRUMENT_RISK = Path(
    "day60_instrument_risk_results.csv"
)

OUTPUT_PORTFOLIO_RISK = Path(
    "day60_portfolio_risk_summary.csv"
)

OUTPUT_ASSET_CLASS = Path(
    "day60_asset_class_exposure.csv"
)

OUTPUT_RISK_COVERAGE = Path(
    "day60_risk_coverage.csv"
)

OUTPUT_VALIDATION = Path(
    "day60_validation_summary.csv"
)

OUTPUT_DATA_REQUIREMENTS = Path(
    "day60_missing_data_requirements.csv"
)


# ==============================================================
# CONSTANTS
# ==============================================================

TRADING_DAYS = 252

DEFAULT_VAR_CONFIDENCE = 0.95

DEFAULT_CVAR_CONFIDENCE = 0.95

EPSILON = 1e-12

NA_REASON = "N/A / insufficient data"


# ==============================================================
# RESULT OBJECT
# ==============================================================

@dataclass
class UnifiedRiskResult:

    instrument_id: str

    symbol: str

    asset_class: str

    metric: str

    category: str

    requirement: str

    value: Any

    unit: str

    status: str

    method: str

    reason: str


# ==============================================================
# GENERAL UTILITIES
# ==============================================================

def finite_number(
    value: Any,
) -> bool:

    try:

        return bool(
            np.isfinite(
                float(value)
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return False


def safe_float(
    value: Any,
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


def normalize_price_series(
    prices: Optional[pd.Series],
) -> Optional[pd.Series]:

    if prices is None:

        return None

    if not isinstance(
        prices,
        pd.Series,
    ):

        try:

            prices = pd.Series(
                prices
            )

        except Exception:

            return None

    prices = pd.to_numeric(
        prices,
        errors="coerce",
    )

    prices = prices.replace(
        [
            np.inf,
            -np.inf,
        ],
        np.nan,
    )

    prices = prices.dropna()

    prices = prices[
        prices > 0
    ]

    if len(prices) < 2:

        return None

    return prices.astype(
        float
    )


def price_to_returns(
    prices: Optional[pd.Series],
) -> Optional[pd.Series]:

    prices = normalize_price_series(
        prices
    )

    if prices is None:

        return None

    returns = (
        prices
        .pct_change()
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .dropna()
    )

    if len(returns) < 2:

        return None

    return returns.astype(
        float
    )


def unavailable_result(
    instrument: Instrument,
    metric: str,
    requirement: MetricStatus,
    reason: str = NA_REASON,
) -> UnifiedRiskResult:

    metric_definition = (
        RISK_METRICS.get(
            metric
        )
    )

    if metric_definition is None:

        category = "Unclassified"

        unit = "unknown"

    else:

        category = (
            metric_definition
            .category
            .value
        )

        unit = (
            metric_definition
            .unit
        )

    return UnifiedRiskResult(
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        asset_class=instrument.asset_class.value,
        metric=metric,
        category=category,
        requirement=requirement.value,
        value=np.nan,
        unit=unit,
        status="Unavailable",
        method="Not calculated",
        reason=reason,
    )


def calculated_result(
    instrument: Instrument,
    metric: str,
    requirement: MetricStatus,
    value: Any,
    method: str,
    reason: str,
) -> UnifiedRiskResult:

    metric_definition = (
        RISK_METRICS.get(
            metric
        )
    )

    if metric_definition is None:

        category = "Unclassified"

        unit = "unknown"

    else:

        category = (
            metric_definition
            .category
            .value
        )

        unit = (
            metric_definition
            .unit
        )

    return UnifiedRiskResult(
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        asset_class=instrument.asset_class.value,
        metric=metric,
        category=category,
        requirement=requirement.value,
        value=value,
        unit=unit,
        status="Calculated",
        method=method,
        reason=reason,
    )


# ==============================================================
# GENERIC RETURN-BASED RISK
# ==============================================================

def annualized_volatility(
    returns: pd.Series,
    periods_per_year: int = TRADING_DAYS,
) -> Optional[float]:

    returns = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()

    if len(returns) < 2:

        return None

    volatility = (
        returns.std(
            ddof=1
        )
        * math.sqrt(
            periods_per_year
        )
    )

    return safe_float(
        volatility
    )


def historical_var_return(
    returns: pd.Series,
    confidence: float = DEFAULT_VAR_CONFIDENCE,
) -> Optional[float]:

    returns = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()

    if returns.empty:

        return None

    tail_probability = (
        1.0
        - confidence
    )

    quantile = returns.quantile(
        tail_probability
    )

    value = max(
        0.0,
        -float(
            quantile
        ),
    )

    return value


def historical_cvar_return(
    returns: pd.Series,
    confidence: float = DEFAULT_CVAR_CONFIDENCE,
) -> Optional[float]:

    returns = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()

    if returns.empty:

        return None

    threshold = returns.quantile(
        1.0 - confidence
    )

    tail = returns[
        returns <= threshold
    ]

    if tail.empty:

        return None

    cvar = max(
        0.0,
        -float(
            tail.mean()
        ),
    )

    return cvar


def maximum_drawdown(
    prices: pd.Series,
) -> Optional[float]:

    prices = normalize_price_series(
        prices
    )

    if prices is None:

        return None

    running_max = prices.cummax()

    drawdown = (
        prices
        / running_max
        - 1.0
    )

    return safe_float(
        drawdown.min()
    )


def calculate_beta(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> Optional[float]:

    aligned = pd.concat(
        [
            pd.to_numeric(
                asset_returns,
                errors="coerce",
            ).rename(
                "asset"
            ),
            pd.to_numeric(
                benchmark_returns,
                errors="coerce",
            ).rename(
                "benchmark"
            ),
        ],
        axis=1,
    ).dropna()

    if len(aligned) < 3:

        return None

    benchmark_variance = (
        aligned[
            "benchmark"
        ]
        .var(
            ddof=1
        )
    )

    if (
        not np.isfinite(
            benchmark_variance
        )
        or abs(
            benchmark_variance
        ) < EPSILON
    ):

        return None

    covariance = (
        aligned[
            [
                "asset",
                "benchmark",
            ]
        ]
        .cov()
        .iloc[
            0,
            1,
        ]
    )

    beta = (
        covariance
        / benchmark_variance
    )

    return safe_float(
        beta
    )


def calculate_correlation(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> Optional[float]:

    aligned = pd.concat(
        [
            pd.to_numeric(
                asset_returns,
                errors="coerce",
            ).rename(
                "asset"
            ),
            pd.to_numeric(
                benchmark_returns,
                errors="coerce",
            ).rename(
                "benchmark"
            ),
        ],
        axis=1,
    ).dropna()

    if len(aligned) < 3:

        return None

    correlation = (
        aligned[
            "asset"
        ]
        .corr(
            aligned[
                "benchmark"
            ]
        )
    )

    return safe_float(
        correlation
    )


# ==============================================================
# FIXED-INCOME ANALYTICS
# ==============================================================

def years_until_maturity(
    maturity_date: Optional[str],
    valuation_date: Optional[pd.Timestamp] = None,
) -> Optional[float]:

    if maturity_date is None:

        return None

    try:

        maturity = pd.Timestamp(
            maturity_date
        )

    except Exception:

        return None

    if valuation_date is None:

        valuation_date = pd.Timestamp.today()

    valuation_date = pd.Timestamp(
        valuation_date
    )

    years = (
        maturity
        - valuation_date
    ).days / 365.25

    if years <= 0:

        return None

    return float(
        years
    )


def bond_cashflows(
    face_value: float,
    coupon_rate: float,
    years: float,
    frequency: int = 2,
) -> Tuple[np.ndarray, np.ndarray]:

    periods = max(
        1,
        int(
            round(
                years
                * frequency
            )
        ),
    )

    times = (
        np.arange(
            1,
            periods + 1,
        )
        / frequency
    )

    coupon = (
        face_value
        * coupon_rate
        / frequency
    )

    cashflows = np.full(
        periods,
        coupon,
        dtype=float,
    )

    cashflows[
        -1
    ] += face_value

    return (
        times,
        cashflows,
    )


def calculate_bond_analytics(
    instrument: Instrument,
    valuation_date: Optional[pd.Timestamp] = None,
    face_value: float = 100.0,
    frequency: int = 2,
) -> Dict[str, Optional[float]]:

    years = years_until_maturity(
        instrument.maturity_date,
        valuation_date=valuation_date,
    )

    coupon_rate = safe_float(
        instrument.coupon_rate
    )

    ytm = safe_float(
        instrument.yield_to_maturity
    )

    market_value = (
        instrument
        .calculate_market_value()
    )

    output = {
        "duration": None,
        "modified_duration": None,
        "convexity": None,
        "dv01": None,
    }

    if (
        years is None
        or coupon_rate is None
        or ytm is None
        or ytm <= -1
    ):

        return output

    times, cashflows = bond_cashflows(
        face_value=face_value,
        coupon_rate=coupon_rate,
        years=years,
        frequency=frequency,
    )

    discount = (
        1.0
        + ytm
        / frequency
    ) ** (
        frequency
        * times
    )

    present_values = (
        cashflows
        / discount
    )

    theoretical_price = (
        present_values.sum()
    )

    if (
        not np.isfinite(
            theoretical_price
        )
        or theoretical_price <= 0
    ):

        return output

    macaulay_duration = (
        (
            times
            * present_values
        ).sum()
        / theoretical_price
    )

    modified_duration = (
        macaulay_duration
        / (
            1.0
            + ytm
            / frequency
        )
    )

    periods = (
        times
        * frequency
    )

    convexity_numerator = (
        (
            cashflows
            * periods
            * (
                periods
                + 1.0
            )
        )
        / (
            (
                1.0
                + ytm
                / frequency
            )
            ** (
                periods
                + 2.0
            )
        )
    ).sum()

    convexity = (
        convexity_numerator
        / (
            theoretical_price
            * frequency
            * frequency
        )
    )

    dv01 = None

    if (
        market_value is not None
        and finite_number(
            market_value
        )
    ):

        dv01 = (
            abs(
                float(
                    market_value
                )
            )
            * modified_duration
            * 0.0001
        )

    output[
        "duration"
    ] = safe_float(
        macaulay_duration
    )

    output[
        "modified_duration"
    ] = safe_float(
        modified_duration
    )

    output[
        "convexity"
    ] = safe_float(
        convexity
    )

    output[
        "dv01"
    ] = safe_float(
        dv01
    )

    return output


# ==============================================================
# BLACK-SCHOLES OPTION ANALYTICS
# ==============================================================

def normal_cdf(
    x: float,
) -> float:

    return (
        0.5
        * (
            1.0
            + math.erf(
                x
                / math.sqrt(
                    2.0
                )
            )
        )
    )


def normal_pdf(
    x: float,
) -> float:

    return (
        math.exp(
            -0.5
            * x
            * x
        )
        / math.sqrt(
            2.0
            * math.pi
        )
    )


def black_scholes_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: str,
) -> Dict[str, Optional[float]]:

    output = {
        "delta": None,
        "gamma": None,
        "vega": None,
        "theta": None,
        "rho": None,
    }

    if (
        spot <= 0
        or strike <= 0
        or time_to_expiry <= 0
        or volatility <= 0
    ):

        return output

    sqrt_t = math.sqrt(
        time_to_expiry
    )

    d1 = (
        math.log(
            spot
            / strike
        )
        + (
            risk_free_rate
            + 0.5
            * volatility
            * volatility
        )
        * time_to_expiry
    ) / (
        volatility
        * sqrt_t
    )

    d2 = (
        d1
        - volatility
        * sqrt_t
    )

    option_type_normalized = (
        str(
            option_type
        )
        .strip()
        .lower()
    )

    pdf_d1 = normal_pdf(
        d1
    )

    discount = math.exp(
        -risk_free_rate
        * time_to_expiry
    )

    gamma = (
        pdf_d1
        / (
            spot
            * volatility
            * sqrt_t
        )
    )

    vega = (
        spot
        * pdf_d1
        * sqrt_t
        / 100.0
    )

    if option_type_normalized in {
        "call",
        "c",
    }:

        delta = normal_cdf(
            d1
        )

        theta_annual = (
            -spot
            * pdf_d1
            * volatility
            / (
                2.0
                * sqrt_t
            )
            - risk_free_rate
            * strike
            * discount
            * normal_cdf(
                d2
            )
        )

        rho = (
            strike
            * time_to_expiry
            * discount
            * normal_cdf(
                d2
            )
            / 100.0
        )

    elif option_type_normalized in {
        "put",
        "p",
    }:

        delta = (
            normal_cdf(
                d1
            )
            - 1.0
        )

        theta_annual = (
            -spot
            * pdf_d1
            * volatility
            / (
                2.0
                * sqrt_t
            )
            + risk_free_rate
            * strike
            * discount
            * normal_cdf(
                -d2
            )
        )

        rho = (
            -strike
            * time_to_expiry
            * discount
            * normal_cdf(
                -d2
            )
            / 100.0
        )

    else:

        return output

    theta_daily = (
        theta_annual
        / 365.0
    )

    output[
        "delta"
    ] = safe_float(
        delta
    )

    output[
        "gamma"
    ] = safe_float(
        gamma
    )

    output[
        "vega"
    ] = safe_float(
        vega
    )

    output[
        "theta"
    ] = safe_float(
        theta_daily
    )

    output[
        "rho"
    ] = safe_float(
        rho
    )

    return output


# ==============================================================
# EXPOSURE ANALYTICS
# ==============================================================

def calculate_notional_exposure(
    instrument: Instrument,
) -> Optional[float]:

    price = safe_float(
        instrument.price
    )

    quantity = safe_float(
        instrument.quantity
    )

    if (
        price is None
        or quantity is None
    ):

        return None

    multiplier = safe_float(
        instrument.contract_multiplier
    )

    if multiplier is None:

        multiplier = 1.0

    return float(
        quantity
        * price
        * multiplier
    )


def calculate_leverage(
    instrument: Instrument,
) -> Optional[float]:

    notional = (
        calculate_notional_exposure(
            instrument
        )
    )

    market_value = (
        instrument
        .calculate_market_value()
    )

    if (
        notional is None
        or market_value is None
        or abs(
            market_value
        ) < EPSILON
    ):

        return None

    return safe_float(
        abs(
            notional
        )
        / abs(
            market_value
        )
    )


# ==============================================================
# DATA ACCESS HELPERS
# ==============================================================

def get_price_series(
    symbol: str,
    price_history: Optional[pd.DataFrame],
) -> Optional[pd.Series]:

    if price_history is None:

        return None

    if not isinstance(
        price_history,
        pd.DataFrame,
    ):

        return None

    if symbol not in price_history.columns:

        return None

    return normalize_price_series(
        price_history[
            symbol
        ]
    )


def get_metadata_value(
    instrument: Instrument,
    key: str,
) -> Any:

    if instrument.metadata is None:

        return None

    return instrument.metadata.get(
        key
    )


# ==============================================================
# METRIC CALCULATOR
# ==============================================================

def calculate_metric(
    instrument: Instrument,
    metric: str,
    requirement: MetricStatus,
    portfolio_value: Optional[float],
    price_history: Optional[pd.DataFrame],
    benchmark_symbol: Optional[str],
    valuation_date: Optional[pd.Timestamp],
) -> UnifiedRiskResult:

    prices = get_price_series(
        instrument.symbol,
        price_history,
    )

    returns = price_to_returns(
        prices
    )

    market_value = (
        instrument
        .calculate_market_value()
    )

    # ----------------------------------------------------------
    # Market value
    # ----------------------------------------------------------

    if metric == "market_value":

        if market_value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            float(
                market_value
            ),
            "Position valuation",
            "quantity × price × contract multiplier",
        )

    # ----------------------------------------------------------
    # Portfolio weight
    # ----------------------------------------------------------

    if metric == "portfolio_weight":

        if (
            market_value is None
            or portfolio_value is None
            or abs(
                portfolio_value
            ) < EPSILON
        ):

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        weight = (
            market_value
            / portfolio_value
        )

        return calculated_result(
            instrument,
            metric,
            requirement,
            weight,
            "Portfolio aggregation",
            "position market value / total portfolio market value",
        )

    # ----------------------------------------------------------
    # Volatility
    # ----------------------------------------------------------

    if metric == "volatility":

        if returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Historical price series required.",
            )

        value = annualized_volatility(
            returns
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical returns",
            "Annualized standard deviation of periodic returns.",
        )

    # ----------------------------------------------------------
    # Historical VaR
    # ----------------------------------------------------------

    if metric == "var":

        if returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Historical price series required.",
            )

        value = historical_var_return(
            returns,
            confidence=DEFAULT_VAR_CONFIDENCE,
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical simulation",
            "95% one-period historical return VaR.",
        )

    # ----------------------------------------------------------
    # Historical CVaR
    # ----------------------------------------------------------

    if metric == "cvar":

        if returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Historical price series required.",
            )

        value = historical_cvar_return(
            returns,
            confidence=DEFAULT_CVAR_CONFIDENCE,
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical tail average",
            "Average loss beyond the 95% historical VaR threshold.",
        )

    # ----------------------------------------------------------
    # Maximum drawdown
    # ----------------------------------------------------------

    if metric == "maximum_drawdown":

        if prices is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Historical price series required.",
            )

        value = maximum_drawdown(
            prices
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical peak-to-trough",
            "Maximum observed peak-to-trough price decline.",
        )

    # ----------------------------------------------------------
    # Beta
    # ----------------------------------------------------------

    if metric == "beta":

        if (
            returns is None
            or benchmark_symbol is None
        ):

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Asset and benchmark price histories required.",
            )

        benchmark_prices = get_price_series(
            benchmark_symbol,
            price_history,
        )

        benchmark_returns = price_to_returns(
            benchmark_prices
        )

        if benchmark_returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Benchmark history unavailable.",
            )

        value = calculate_beta(
            returns,
            benchmark_returns,
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical covariance beta",
            f"Relative to benchmark {benchmark_symbol}.",
        )

    # ----------------------------------------------------------
    # Correlation
    # ----------------------------------------------------------

    if metric == "correlation":

        if (
            returns is None
            or benchmark_symbol is None
        ):

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Asset and benchmark price histories required.",
            )

        benchmark_prices = get_price_series(
            benchmark_symbol,
            price_history,
        )

        benchmark_returns = price_to_returns(
            benchmark_prices
        )

        if benchmark_returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        value = calculate_correlation(
            returns,
            benchmark_returns,
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Historical Pearson correlation",
            f"Relative to benchmark {benchmark_symbol}.",
        )

    # ----------------------------------------------------------
    # Fixed-income analytics
    # ----------------------------------------------------------

    if metric in {
        "duration",
        "modified_duration",
        "convexity",
        "dv01",
    }:

        analytics = calculate_bond_analytics(
            instrument,
            valuation_date=valuation_date,
        )

        value = analytics.get(
            metric
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                (
                    "Bond maturity, coupon and yield-to-maturity "
                    "are required."
                ),
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Cash-flow fixed-income approximation",
            (
                "Calculated from coupon, maturity and "
                "yield-to-maturity."
            ),
        )

    # ----------------------------------------------------------
    # Credit spread
    # ----------------------------------------------------------

    if metric == "credit_spread":

        value = safe_float(
            get_metadata_value(
                instrument,
                "credit_spread_bps",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Reference credit spread data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Instrument metadata",
            "Credit spread supplied in basis points.",
        )

    # ----------------------------------------------------------
    # Credit risk
    # ----------------------------------------------------------

    if metric == "credit_risk":

        if instrument.credit_rating is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Credit rating or credit model data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            instrument.credit_rating,
            "Credit rating",
            "Issuer/instrument credit rating.",
        )

    # ----------------------------------------------------------
    # Yield curve exposure
    # ----------------------------------------------------------

    if metric == "yield_curve_exposure":

        analytics = calculate_bond_analytics(
            instrument,
            valuation_date=valuation_date,
        )

        modified_duration = analytics.get(
            "modified_duration"
        )

        if modified_duration is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Duration inputs required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            modified_duration,
            "Duration proxy",
            (
                "Modified duration used as first-order "
                "parallel-rate sensitivity proxy."
            ),
        )

    # ----------------------------------------------------------
    # Generic interest-rate exposure
    # ----------------------------------------------------------

    if metric == "interest_rate_risk":

        value = safe_float(
            get_metadata_value(
                instrument,
                "interest_rate_exposure",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Instrument-specific rate exposure data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Instrument metadata",
            "User/data-provider supplied interest-rate exposure.",
        )

    # ----------------------------------------------------------
    # Option Greeks
    # ----------------------------------------------------------

    if metric in {
        "delta",
        "gamma",
        "vega",
        "theta",
        "rho",
    }:

        spot = safe_float(
            get_metadata_value(
                instrument,
                "underlying_price",
            )
        )

        strike = safe_float(
            instrument.strike
        )

        volatility = safe_float(
            get_metadata_value(
                instrument,
                "implied_volatility",
            )
        )

        risk_free_rate = safe_float(
            get_metadata_value(
                instrument,
                "risk_free_rate",
            )
        )

        if risk_free_rate is None:

            risk_free_rate = 0.0

        if (
            instrument.expiration_date
            is None
        ):

            time_to_expiry = None

        else:

            try:

                expiry = pd.Timestamp(
                    instrument.expiration_date
                )

                valuation = (
                    pd.Timestamp(
                        valuation_date
                    )
                    if valuation_date
                    is not None
                    else pd.Timestamp.today()
                )

                time_to_expiry = (
                    expiry
                    - valuation
                ).days / 365.25

            except Exception:

                time_to_expiry = None

        if (
            spot is None
            or strike is None
            or volatility is None
            or time_to_expiry is None
            or time_to_expiry <= 0
            or instrument.option_type is None
        ):

            return unavailable_result(
                instrument,
                metric,
                requirement,
                (
                    "Underlying price, strike, expiry, "
                    "option type and implied volatility required."
                ),
            )

        greeks = black_scholes_greeks(
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            risk_free_rate=risk_free_rate,
            volatility=volatility,
            option_type=instrument.option_type,
        )

        value = greeks.get(
            metric
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Black-Scholes approximation",
            (
                "European-option Greek using supplied "
                "market assumptions."
            ),
        )

    # ----------------------------------------------------------
    # Implied volatility
    # ----------------------------------------------------------

    if metric == "implied_volatility":

        value = safe_float(
            get_metadata_value(
                instrument,
                "implied_volatility",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Option implied volatility data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Market input",
            "Implied volatility supplied by market-data layer.",
        )

    # ----------------------------------------------------------
    # Leverage
    # ----------------------------------------------------------

    if metric == "leverage":

        metadata_leverage = safe_float(
            get_metadata_value(
                instrument,
                "leverage",
            )
        )

        if metadata_leverage is not None:

            return calculated_result(
                instrument,
                metric,
                requirement,
                metadata_leverage,
                "Instrument metadata",
                "Explicit leverage supplied by instrument data.",
            )

        value = calculate_leverage(
            instrument
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Notional / market value",
            (
                "Approximate gross economic exposure "
                "relative to recorded market value."
            ),
        )

    # ----------------------------------------------------------
    # Currency exposure
    # ----------------------------------------------------------

    if metric == "currency_exposure":

        if market_value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        exposure_currency = (
            instrument.base_currency
            or instrument.currency
        )

        return calculated_result(
            instrument,
            metric,
            requirement,
            float(
                market_value
            ),
            "Position exposure",
            (
                f"Approximate exposure denominated in "
                f"{exposure_currency}."
            ),
        )

    # ----------------------------------------------------------
    # Carry
    # ----------------------------------------------------------

    if metric == "carry":

        value = safe_float(
            get_metadata_value(
                instrument,
                "carry",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Carry/rate-differential data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Instrument metadata",
            "Carry supplied by market/macro data layer.",
        )

    # ----------------------------------------------------------
    # Basis risk
    # ----------------------------------------------------------

    if metric == "basis_risk":

        value = safe_float(
            get_metadata_value(
                instrument,
                "basis",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Spot and derivative reference data required.",
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Spot-derivative basis",
            "Basis supplied by market-data layer.",
        )

    # ----------------------------------------------------------
    # Commodity exposure
    # ----------------------------------------------------------

    if metric == "commodity_price_risk":

        notional = calculate_notional_exposure(
            instrument
        )

        if notional is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            notional,
            "Notional commodity exposure",
            "Quantity × price × multiplier.",
        )

    # ----------------------------------------------------------
    # Real-estate exposure
    # ----------------------------------------------------------

    if metric == "real_estate_exposure":

        if market_value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            float(
                market_value
            ),
            "Position exposure",
            "Recorded real-estate/REIT market value.",
        )

    # ----------------------------------------------------------
    # Inflation exposure
    # ----------------------------------------------------------

    if metric == "inflation_risk":

        value = safe_float(
            get_metadata_value(
                instrument,
                "inflation_beta",
            )
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                (
                    "Inflation sensitivity requires historical "
                    "inflation/factor data or supplied exposure."
                ),
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Inflation-factor exposure",
            "Supplied inflation beta/exposure.",
        )

    # ----------------------------------------------------------
    # Tracking error
    # ----------------------------------------------------------

    if metric == "tracking_error":

        if (
            returns is None
            or benchmark_symbol is None
        ):

            return unavailable_result(
                instrument,
                metric,
                requirement,
                "Fund and benchmark histories required.",
            )

        benchmark_prices = get_price_series(
            benchmark_symbol,
            price_history,
        )

        benchmark_returns = price_to_returns(
            benchmark_prices
        )

        if benchmark_returns is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        aligned = pd.concat(
            [
                returns.rename(
                    "fund"
                ),
                benchmark_returns.rename(
                    "benchmark"
                ),
            ],
            axis=1,
        ).dropna()

        if len(aligned) < 2:

            return unavailable_result(
                instrument,
                metric,
                requirement,
            )

        active_return = (
            aligned[
                "fund"
            ]
            - aligned[
                "benchmark"
            ]
        )

        tracking_error = (
            active_return.std(
                ddof=1
            )
            * math.sqrt(
                TRADING_DAYS
            )
        )

        return calculated_result(
            instrument,
            metric,
            requirement,
            tracking_error,
            "Historical active-return volatility",
            f"Tracking error versus {benchmark_symbol}.",
        )

    # ----------------------------------------------------------
    # Metadata-supported qualitative/advanced metrics
    # ----------------------------------------------------------

    metadata_metric_map = {

        "factor_exposure":
            "factor_exposure",

        "liquidity_risk":
            "liquidity_risk",

        "concentration_risk":
            "concentration_risk",

        "counterparty_risk":
            "counterparty_risk",

        "underlying_concentration":
            "underlying_concentration",

    }

    if metric in metadata_metric_map:

        metadata_key = (
            metadata_metric_map[
                metric
            ]
        )

        value = get_metadata_value(
            instrument,
            metadata_key,
        )

        if value is None:

            return unavailable_result(
                instrument,
                metric,
                requirement,
                (
                    "Additional portfolio, market or "
                    "instrument data required."
                ),
            )

        return calculated_result(
            instrument,
            metric,
            requirement,
            value,
            "Instrument metadata",
            "Metric supplied by upstream analytics/data layer.",
        )

    # ----------------------------------------------------------
    # Unknown / future metric
    # ----------------------------------------------------------

    return unavailable_result(
        instrument,
        metric,
        requirement,
        (
            "Metric recognized by routing architecture "
            "but calculator is not implemented yet."
        ),
    )


# ==============================================================
# INSTRUMENT RISK ENGINE
# ==============================================================

def calculate_instrument_risk(
    instrument: Instrument,
    portfolio_value: Optional[float] = None,
    price_history: Optional[pd.DataFrame] = None,
    benchmark_symbol: Optional[str] = None,
    valuation_date: Optional[pd.Timestamp] = None,
) -> List[UnifiedRiskResult]:

    requirements = get_risk_requirements(
        instrument.asset_class
    )

    results = []

    for (
        metric,
        requirement,
    ) in requirements.items():

        result = calculate_metric(
            instrument=instrument,
            metric=metric,
            requirement=requirement,
            portfolio_value=portfolio_value,
            price_history=price_history,
            benchmark_symbol=benchmark_symbol,
            valuation_date=valuation_date,
        )

        results.append(
            result
        )

    return results


# ==============================================================
# PORTFOLIO ENGINE
# ==============================================================

def calculate_portfolio_value(
    instruments: Iterable[Instrument],
) -> float:

    total = 0.0

    for instrument in instruments:

        value = (
            instrument
            .calculate_market_value()
        )

        if (
            value is not None
            and finite_number(
                value
            )
        ):

            total += float(
                value
            )

    return total


def calculate_asset_class_exposure(
    instruments: Iterable[Instrument],
) -> pd.DataFrame:

    rows = []

    for instrument in instruments:

        market_value = (
            instrument
            .calculate_market_value()
        )

        if market_value is None:

            continue

        rows.append(
            {
                "asset_class":
                    instrument.asset_class.value,

                "market_value":
                    float(
                        market_value
                    ),
            }
        )

    if not rows:

        return pd.DataFrame(
            columns=[
                "asset_class",
                "market_value",
                "weight",
            ]
        )

    exposure = (
        pd.DataFrame(
            rows
        )
        .groupby(
            "asset_class",
            as_index=False,
        )[
            "market_value"
        ]
        .sum()
    )

    total = exposure[
        "market_value"
    ].sum()

    if abs(
        total
    ) > EPSILON:

        exposure[
            "weight"
        ] = (
            exposure[
                "market_value"
            ]
            / total
        )

    else:

        exposure[
            "weight"
        ] = np.nan

    return exposure.sort_values(
        "market_value",
        ascending=False,
    ).reset_index(
        drop=True
    )


# ==============================================================
# EXISTING VITTANTRA VaR INTEGRATION
# ==============================================================

def try_existing_portfolio_var(
    instruments: List[Instrument],
    price_history: Optional[pd.DataFrame],
) -> Tuple[
    Optional[Any],
    str,
]:

    if not EXISTING_VAR_ENGINE_AVAILABLE:

        return (
            None,
            "Existing var_engine.py unavailable.",
        )

    if price_history is None:

        return (
            None,
            "No price history supplied.",
        )

    # ----------------------------------------------------------
    # Build holdings in the exact format required by var_engine.py
    #
    # Required columns:
    #   ticker
    #   market_value
    # ----------------------------------------------------------

    holding_rows = []

    for instrument in instruments:

        symbol = instrument.symbol

        if symbol not in price_history.columns:

            continue

        market_value = (
            instrument
            .calculate_market_value()
        )

        if (
            market_value is None
            or not finite_number(
                market_value
            )
        ):

            continue

        holding_rows.append(
            {
                "ticker": symbol,
                "market_value": float(
                    market_value
                ),
            }
        )

    if not holding_rows:

        return (
            None,
            (
                "No holdings matched columns "
                "in supplied price history."
            ),
        )

    holdings = pd.DataFrame(
        holding_rows,
        columns=[
            "ticker",
            "market_value",
        ],
    )

    # ----------------------------------------------------------
    # Convert Day 60 wide price matrix to the long format
    # required by var_engine.py:
    #
    #   date | ticker | close_price
    # ----------------------------------------------------------

    prices = price_history.copy()

    if not isinstance(
        prices.index,
        pd.DatetimeIndex,
    ):

        try:

            prices.index = pd.to_datetime(
                prices.index
            )

        except Exception as exc:

            return (
                None,
                (
                    "Could not convert price-history "
                    f"index to dates: {exc}"
                ),
            )

    prices.index.name = "date"

    long_price_history = (
        prices
        .reset_index()
        .melt(
            id_vars="date",
            var_name="ticker",
            value_name="close_price",
        )
    )

    long_price_history[
        "close_price"
    ] = pd.to_numeric(
        long_price_history[
            "close_price"
        ],
        errors="coerce",
    )

    long_price_history = (
        long_price_history
        .dropna(
            subset=[
                "date",
                "ticker",
                "close_price",
            ]
        )
        .sort_values(
            [
                "ticker",
                "date",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    valid_tickers = set(
        holdings[
            "ticker"
        ]
        .astype(str)
    )

    long_price_history = (
        long_price_history[
            long_price_history[
                "ticker"
            ]
            .astype(str)
            .isin(
                valid_tickers
            )
        ]
        .copy()
    )

    if long_price_history.empty:

        return (
            None,
            (
                "No usable price observations remained "
                "after matching portfolio holdings."
            ),
        )

    # ----------------------------------------------------------
    # Call the existing Vittantra VaR engine.
    # It returns: (summary_dataframe, losses_series).
    # ----------------------------------------------------------

    try:

        var_summary, losses = calculate_historical_var(
            holdings=holdings,
            price_history=long_price_history,
            confidence_levels=(
                0.95,
                0.99,
            ),
        )

        result = {
            "summary": var_summary.to_dict(
                orient="records"
            ),
            "loss_observations": int(
                len(losses)
            ),
        }

        return (
            result,
            (
                "Calculated using existing "
                "var_engine.calculate_historical_var()."
            ),
        )

    except Exception as exc:

        return (
            None,
            (
                "Existing VaR engine could not calculate "
                f"with supplied data: {exc}"
            ),
        )


# ==============================================================
# COVERAGE REPORT
# ==============================================================

def build_risk_coverage(
    results_df: pd.DataFrame,
) -> pd.DataFrame:

    if results_df.empty:

        return pd.DataFrame()

    coverage = (
        results_df
        .groupby(
            [
                "asset_class",
                "requirement",
            ],
            dropna=False,
        )
        .agg(
            total_metrics=(
                "metric",
                "count",
            ),
            calculated_metrics=(
                "status",
                lambda x: int(
                    (
                        x
                        == "Calculated"
                    ).sum()
                ),
            ),
        )
        .reset_index()
    )

    coverage[
        "unavailable_metrics"
    ] = (
        coverage[
            "total_metrics"
        ]
        - coverage[
            "calculated_metrics"
        ]
    )

    coverage[
        "coverage_rate"
    ] = (
        coverage[
            "calculated_metrics"
        ]
        / coverage[
            "total_metrics"
        ]
    )

    return coverage


# ==============================================================
# MISSING DATA REPORT
# ==============================================================

def build_missing_data_report(
    results_df: pd.DataFrame,
) -> pd.DataFrame:

    if results_df.empty:

        return pd.DataFrame()

    missing = results_df[
        results_df[
            "status"
        ]
        == "Unavailable"
    ].copy()

    if missing.empty:

        return pd.DataFrame(
            columns=[
                "instrument_id",
                "symbol",
                "asset_class",
                "metric",
                "requirement",
                "reason",
            ]
        )

    return (
        missing[
            [
                "instrument_id",
                "symbol",
                "asset_class",
                "metric",
                "requirement",
                "reason",
            ]
        ]
        .sort_values(
            [
                "asset_class",
                "symbol",
                "metric",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ==============================================================
# PORTFOLIO SUMMARY
# ==============================================================

def build_portfolio_summary(
    instruments: List[Instrument],
    results_df: pd.DataFrame,
    asset_exposure: pd.DataFrame,
    portfolio_var_result: Optional[Any],
    portfolio_var_message: str,
) -> pd.DataFrame:

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    total_metrics = len(
        results_df
    )

    calculated_metrics = int(
        (
            results_df[
                "status"
            ]
            == "Calculated"
        ).sum()
    )

    unavailable_metrics = (
        total_metrics
        - calculated_metrics
    )

    required = results_df[
        results_df[
            "requirement"
        ]
        == MetricStatus.REQUIRED.value
    ]

    required_total = len(
        required
    )

    required_calculated = int(
        (
            required[
                "status"
            ]
            == "Calculated"
        ).sum()
    )

    largest_asset_class = None

    largest_asset_class_weight = np.nan

    if not asset_exposure.empty:

        largest_row = (
            asset_exposure
            .sort_values(
                "weight",
                ascending=False,
            )
            .iloc[
                0
            ]
        )

        largest_asset_class = (
            largest_row[
                "asset_class"
            ]
        )

        largest_asset_class_weight = (
            largest_row[
                "weight"
            ]
        )

    summary = [
        {
            "metric":
                "portfolio_value",

            "value":
                portfolio_value,

            "status":
                "Calculated",
        },
        {
            "metric":
                "instrument_count",

            "value":
                len(
                    instruments
                ),

            "status":
                "Calculated",
        },
        {
            "metric":
                "asset_class_count",

            "value":
                len(
                    asset_exposure
                ),

            "status":
                "Calculated",
        },
        {
            "metric":
                "total_routed_metrics",

            "value":
                total_metrics,

            "status":
                "Calculated",
        },
        {
            "metric":
                "calculated_metrics",

            "value":
                calculated_metrics,

            "status":
                "Calculated",
        },
        {
            "metric":
                "unavailable_metrics",

            "value":
                unavailable_metrics,

            "status":
                "Calculated",
        },
        {
            "metric":
                "overall_metric_coverage",

            "value":
                (
                    calculated_metrics
                    / total_metrics
                    if total_metrics
                    else np.nan
                ),

            "status":
                "Calculated",
        },
        {
            "metric":
                "required_metric_coverage",

            "value":
                (
                    required_calculated
                    / required_total
                    if required_total
                    else np.nan
                ),

            "status":
                "Calculated",
        },
        {
            "metric":
                "largest_asset_class",

            "value":
                largest_asset_class,

            "status":
                (
                    "Calculated"
                    if largest_asset_class
                    is not None
                    else "Unavailable"
                ),
        },
        {
            "metric":
                "largest_asset_class_weight",

            "value":
                largest_asset_class_weight,

            "status":
                (
                    "Calculated"
                    if finite_number(
                        largest_asset_class_weight
                    )
                    else "Unavailable"
                ),
        },
        {
            "metric":
                "existing_var_engine_available",

            "value":
                EXISTING_VAR_ENGINE_AVAILABLE,

            "status":
                "Calculated",
        },
        {
            "metric":
                "existing_portfolio_var_result",

            "value":
                (
                    str(
                        portfolio_var_result
                    )
                    if portfolio_var_result
                    is not None
                    else np.nan
                ),

            "status":
                (
                    "Calculated"
                    if portfolio_var_result
                    is not None
                    else "Unavailable"
                ),
        },
        {
            "metric":
                "existing_portfolio_var_message",

            "value":
                portfolio_var_message,

            "status":
                "Diagnostic",
        },
    ]

    return pd.DataFrame(
        summary
    )


# ==============================================================
# SAMPLE DATA ENRICHMENT
# ==============================================================

def enrich_sample_instruments(
    instruments: List[Instrument],
) -> List[Instrument]:

    """
    Adds illustrative model inputs only where needed to test
    calculation plumbing.

    These are NOT live market observations. Since Day 75, the option
    underlying price, risk-free rate and BBB credit spread come from
    live data (vittantra_data_hub.py) when it is available.
    """

    from vittantra_live_inputs import load_live_macro, load_live_prices

    live_prices = load_live_prices()
    live_macro = load_live_macro()
    underlying_price = float(
        live_prices.get("AAPL", {}).get("price", 205.0)
    )
    risk_free_rate = live_macro.get("DGS3MO", 4.0) / 100
    credit_spread_bps = live_macro.get("BAMLC0A4CBBB", 1.65) * 100

    for instrument in instruments:

        if instrument.metadata is None:

            instrument.metadata = {}

        if (
            instrument.asset_class
            == AssetClass.OPTION
        ):

            instrument.metadata.update(
                {
                    "underlying_price":
                        underlying_price,

                    "implied_volatility":
                        0.28,

                    "risk_free_rate":
                        risk_free_rate,
                }
            )

        if (
            instrument.asset_class
            == AssetClass.FIXED_INCOME
        ):

            instrument.metadata.update(
                {
                    "credit_spread_bps":
                        credit_spread_bps,
                }
            )

        if (
            instrument.asset_class
            == AssetClass.FX
        ):

            instrument.metadata.update(
                {
                    "carry":
                        0.01,
                }
            )

        if (
            instrument.asset_class
            == AssetClass.FUTURE
        ):

            instrument.metadata.update(
                {
                    "basis":
                        0.002,
                }
            )

    return instruments


# ==============================================================
# SYNTHETIC VALIDATION PRICE HISTORY
# ==============================================================

def build_validation_price_history(
    instruments: List[Instrument],
    observations: int = 320,
    seed: int = 60,
) -> pd.DataFrame:

    """
    Deterministic synthetic history used ONLY to validate the
    Day 60 calculation pipeline.

    It is not investment evidence and is not live market data.
    """

    rng = np.random.default_rng(
        seed
    )

    dates = pd.bdate_range(
        end=pd.Timestamp.today().normalize(),
        periods=observations,
    )

    data = {}

    benchmark_returns = rng.normal(
        loc=0.00025,
        scale=0.009,
        size=observations,
    )

    benchmark_prices = (
        100.0
        * np.exp(
            np.cumsum(
                benchmark_returns
            )
        )
    )

    data[
        "VITTANTRA_BENCHMARK"
    ] = benchmark_prices

    asset_volatility = {

        AssetClass.EQUITY:
            0.012,

        AssetClass.ETF_FUND:
            0.010,

        AssetClass.FIXED_INCOME:
            0.004,

        AssetClass.OPTION:
            0.025,

        AssetClass.FUTURE:
            0.013,

        AssetClass.FX:
            0.006,

        AssetClass.COMMODITY:
            0.011,

        AssetClass.CASH:
            0.0002,

        AssetClass.CRYPTO:
            0.030,

        AssetClass.REAL_ESTATE:
            0.012,

        AssetClass.OTHER:
            0.010,
    }

    for instrument in instruments:

        sigma = (
            asset_volatility.get(
                instrument.asset_class,
                0.01,
            )
        )

        idiosyncratic = rng.normal(
            loc=0.0,
            scale=sigma,
            size=observations,
        )

        if (
            instrument.asset_class
            in {
                AssetClass.EQUITY,
                AssetClass.ETF_FUND,
                AssetClass.REAL_ESTATE,
            }
        ):

            simulated_returns = (
                0.55
                * benchmark_returns
                + 0.75
                * idiosyncratic
            )

        else:

            simulated_returns = (
                0.20
                * benchmark_returns
                + idiosyncratic
            )

        start_price = safe_float(
            instrument.price
        )

        if (
            start_price is None
            or start_price <= 0
        ):

            start_price = 100.0

        prices = (
            start_price
            * np.exp(
                np.cumsum(
                    simulated_returns
                )
            )
        )

        data[
            instrument.symbol
        ] = prices

    return pd.DataFrame(
        data,
        index=dates,
    )


# ==============================================================
# VALIDATION SUITE
# ==============================================================

def validate_day60(
    instruments: List[Instrument],
    results_df: pd.DataFrame,
    portfolio_summary: pd.DataFrame,
    asset_exposure: pd.DataFrame,
) -> pd.DataFrame:

    checks = []

    # ----------------------------------------------------------
    # 1. All instruments produced risk results
    # ----------------------------------------------------------

    result_instruments = set(
        results_df[
            "instrument_id"
        ]
    )

    expected_instruments = {
        instrument.instrument_id
        for instrument
        in instruments
    }

    passed = (
        result_instruments
        == expected_instruments
    )

    checks.append(
        {
            "test":
                "Every instrument produced routed risk results",

            "passed":
                passed,

            "details":
                (
                    f"{len(result_instruments)} "
                    f"of {len(expected_instruments)} instruments"
                ),
        }
    )

    # ----------------------------------------------------------
    # 2. Market values calculate
    # ----------------------------------------------------------

    market_values = results_df[
        results_df[
            "metric"
        ]
        == "market_value"
    ]

    passed = (
        not market_values.empty
        and (
            market_values[
                "status"
            ]
            == "Calculated"
        ).all()
    )

    checks.append(
        {
            "test":
                "Market value calculation works",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{int((market_values['status'] == 'Calculated').sum())} "
                    f"of {len(market_values)} calculated"
                ),
        }
    )

    # ----------------------------------------------------------
    # 3. Historical volatility works
    # ----------------------------------------------------------

    volatility_rows = results_df[
        results_df[
            "metric"
        ]
        == "volatility"
    ]

    passed = (
        not volatility_rows.empty
        and (
            volatility_rows[
                "status"
            ]
            == "Calculated"
        ).any()
    )

    checks.append(
        {
            "test":
                "Historical volatility engine works",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{int((volatility_rows['status'] == 'Calculated').sum())} "
                    "volatility metrics calculated"
                ),
        }
    )

    # ----------------------------------------------------------
    # 4. VaR works
    # ----------------------------------------------------------

    var_rows = results_df[
        results_df[
            "metric"
        ]
        == "var"
    ]

    passed = (
        not var_rows.empty
        and (
            var_rows[
                "status"
            ]
            == "Calculated"
        ).any()
    )

    checks.append(
        {
            "test":
                "Historical VaR calculation works",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{int((var_rows['status'] == 'Calculated').sum())} "
                    "VaR metrics calculated"
                ),
        }
    )

    # ----------------------------------------------------------
    # 5. Bond analytics work
    # ----------------------------------------------------------

    bond_rows = results_df[
        (
            results_df[
                "asset_class"
            ]
            == AssetClass.FIXED_INCOME.value
        )
        & (
            results_df[
                "metric"
            ].isin(
                [
                    "duration",
                    "modified_duration",
                    "convexity",
                    "dv01",
                ]
            )
        )
    ]

    passed = (
        len(
            bond_rows
        )
        >= 4
        and (
            bond_rows[
                "status"
            ]
            == "Calculated"
        ).all()
    )

    checks.append(
        {
            "test":
                "Fixed-income analytics work",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{int((bond_rows['status'] == 'Calculated').sum())} "
                    f"of {len(bond_rows)} bond metrics calculated"
                ),
        }
    )

    # ----------------------------------------------------------
    # 6. Option Greeks work
    # ----------------------------------------------------------

    greek_rows = results_df[
        (
            results_df[
                "asset_class"
            ]
            == AssetClass.OPTION.value
        )
        & (
            results_df[
                "metric"
            ].isin(
                [
                    "delta",
                    "gamma",
                    "vega",
                    "theta",
                    "rho",
                ]
            )
        )
    ]

    passed = (
        len(
            greek_rows
        )
        >= 5
        and (
            greek_rows[
                "status"
            ]
            == "Calculated"
        ).all()
    )

    checks.append(
        {
            "test":
                "Option Greeks framework works",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{int((greek_rows['status'] == 'Calculated').sum())} "
                    f"of {len(greek_rows)} Greeks calculated"
                ),
        }
    )

    # ----------------------------------------------------------
    # 7. Asset exposure sums to 100%
    # ----------------------------------------------------------

    weight_sum = (
        asset_exposure[
            "weight"
        ].sum()
        if not asset_exposure.empty
        else np.nan
    )

    passed = (
        finite_number(
            weight_sum
        )
        and abs(
            float(
                weight_sum
            )
            - 1.0
        )
        < 1e-8
    )

    checks.append(
        {
            "test":
                "Asset-class exposure sums to 100%",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"weight sum = {weight_sum:.8f}"
                    if finite_number(
                        weight_sum
                    )
                    else "weight unavailable"
                ),
        }
    )

    # ----------------------------------------------------------
    # 8. Missing data explicitly flagged
    # ----------------------------------------------------------

    unavailable = results_df[
        results_df[
            "status"
        ]
        == "Unavailable"
    ]

    passed = (
        not unavailable.empty
        and unavailable[
            "reason"
        ].notna().all()
    )

    checks.append(
        {
            "test":
                "Unavailable metrics are explicitly explained",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{len(unavailable)} unavailable metrics "
                    "carry explicit reasons"
                ),
        }
    )

    # ----------------------------------------------------------
    # 9. Portfolio summary produced
    # ----------------------------------------------------------

    passed = (
        not portfolio_summary.empty
        and "portfolio_value"
        in set(
            portfolio_summary[
                "metric"
            ]
        )
    )

    checks.append(
        {
            "test":
                "Portfolio risk summary produced",

            "passed":
                bool(
                    passed
                ),

            "details":
                (
                    f"{len(portfolio_summary)} "
                    "portfolio summary metrics"
                ),
        }
    )

    # ----------------------------------------------------------
    # 10. Existing VaR integration detected
    # ----------------------------------------------------------

    checks.append(
        {
            "test":
                "Existing Vittantra VaR engine detected",

            "passed":
                bool(
                    EXISTING_VAR_ENGINE_AVAILABLE
                ),

            "details":
                (
                    "var_engine.calculate_historical_var available"
                    if EXISTING_VAR_ENGINE_AVAILABLE
                    else "existing VaR engine unavailable"
                ),
        }
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
# DISPLAY
# ==============================================================

def print_section(
    title: str,
) -> None:

    print()

    print(
        "=" * 80
    )

    print(
        title
    )

    print(
        "=" * 80
    )


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:

    print_section(
        "VITTANTRA — DAY 60"
    )

    print(
        "Unified Multi-Asset Risk Engine"
    )

    print()
    print(
        "Day 60 connects Day 59 asset-aware routing "
        "to actual risk calculations."
    )

    print()
    print(
        "Important:"
    )

    print(
        "The validation price history generated by this script "
        "is synthetic and deterministic."
    )

    print(
        "It tests calculation plumbing only. "
        "It is NOT market evidence or investment research."
    )

    # ----------------------------------------------------------
    # Build Day 59 sample instruments
    # ----------------------------------------------------------

    instruments = (
        build_sample_instruments()
    )

    instruments = (
        enrich_sample_instruments(
            instruments
        )
    )

    # ----------------------------------------------------------
    # Portfolio value
    # ----------------------------------------------------------

    portfolio_value = (
        calculate_portfolio_value(
            instruments
        )
    )

    print_section(
        "PORTFOLIO FOUNDATION"
    )

    print(
        f"Instruments: {len(instruments)}"
    )

    print(
        f"Illustrative portfolio value: "
        f"${portfolio_value:,.2f}"
    )

    print(
        f"Existing Vittantra VaR engine available: "
        f"{EXISTING_VAR_ENGINE_AVAILABLE}"
    )

    # ----------------------------------------------------------
    # Synthetic validation data
    # ----------------------------------------------------------

    price_history = load_price_history(

        [instrument.symbol for instrument in instruments]

    )

    data_mode = "LIVE" if price_history is not None else "SAMPLE"


    if price_history is None:

        price_history = (

            build_validation_price_history(

                instruments=instruments,

                observations=320,

                seed=60,

            )

        )


    print(f"Data mode: {data_mode} "

          f"({'real market history' if data_mode == 'LIVE' else 'synthetic validation history'})")

    benchmark_symbol = (
        "VITTANTRA_BENCHMARK"
    )

    # Use a fixed historical valuation date for the sample
    # option/bond examples so their sample expiries remain valid.
    valuation_date = pd.Timestamp(
        "2026-10-02"
    )

    if data_mode == "LIVE":
        valuation_date = live_valuation_date() or valuation_date

    # ----------------------------------------------------------
    # Calculate instrument risk
    # ----------------------------------------------------------

    all_results: List[
        UnifiedRiskResult
    ] = []

    for instrument in instruments:

        instrument_results = (
            calculate_instrument_risk(
                instrument=instrument,
                portfolio_value=portfolio_value,
                price_history=price_history,
                benchmark_symbol=benchmark_symbol,
                valuation_date=valuation_date,
            )
        )

        all_results.extend(
            instrument_results
        )

    results_df = pd.DataFrame(
        [
            asdict(
                result
            )
            for result
            in all_results
        ]
    )

    # ----------------------------------------------------------
    # Asset-class aggregation
    # ----------------------------------------------------------

    asset_exposure = (
        calculate_asset_class_exposure(
            instruments
        )
    )

    # ----------------------------------------------------------
    # Existing portfolio VaR engine integration
    # ----------------------------------------------------------

    (
        portfolio_var_result,
        portfolio_var_message,
    ) = try_existing_portfolio_var(
        instruments=instruments,
        price_history=price_history,
    )

    # ----------------------------------------------------------
    # Portfolio summary
    # ----------------------------------------------------------

    portfolio_summary = (
        build_portfolio_summary(
            instruments=instruments,
            results_df=results_df,
            asset_exposure=asset_exposure,
            portfolio_var_result=portfolio_var_result,
            portfolio_var_message=portfolio_var_message,
        )
    )

    portfolio_summary = pd.concat(
        [
            portfolio_summary,
            pd.DataFrame(
                [
                    {
                        portfolio_summary.columns[0]: "data_mode",
                        portfolio_summary.columns[1]: data_mode,
                        portfolio_summary.columns[2]: "Diagnostic",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    # ----------------------------------------------------------
    # Coverage
    # ----------------------------------------------------------

    coverage = build_risk_coverage(
        results_df
    )

    # ----------------------------------------------------------
    # Missing-data report
    # ----------------------------------------------------------

    missing_data = (
        build_missing_data_report(
            results_df
        )
    )

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    validation = validate_day60(
        instruments=instruments,
        results_df=results_df,
        portfolio_summary=portfolio_summary,
        asset_exposure=asset_exposure,
    )

    # ----------------------------------------------------------
    # Save outputs
    # ----------------------------------------------------------

    results_df.to_csv(
        OUTPUT_INSTRUMENT_RISK,
        index=False,
    )

    portfolio_summary.to_csv(
        OUTPUT_PORTFOLIO_RISK,
        index=False,
    )

    asset_exposure.to_csv(
        OUTPUT_ASSET_CLASS,
        index=False,
    )

    coverage.to_csv(
        OUTPUT_RISK_COVERAGE,
        index=False,
    )

    missing_data.to_csv(
        OUTPUT_DATA_REQUIREMENTS,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )

    # ----------------------------------------------------------
    # Terminal summary
    # ----------------------------------------------------------

    print_section(
        "ASSET-CLASS EXPOSURE"
    )

    print(
        asset_exposure.to_string(
            index=False
        )
    )

    print_section(
        "RISK CALCULATION COVERAGE"
    )

    print(
        coverage.to_string(
            index=False
        )
    )

    calculated_count = int(
        (
            results_df[
                "status"
            ]
            == "Calculated"
        ).sum()
    )

    unavailable_count = int(
        (
            results_df[
                "status"
            ]
            == "Unavailable"
        ).sum()
    )

    print()
    print(
        f"Calculated risk metrics: "
        f"{calculated_count}"
    )

    print(
        f"Unavailable / insufficient-data metrics: "
        f"{unavailable_count}"
    )

    print_section(
        "EXISTING VITTANTRA VaR INTEGRATION"
    )

    print(
        portfolio_var_message
    )

    if portfolio_var_result is not None:

        print()
        print(
            portfolio_var_result
        )

    print_section(
        "DAY 60 VALIDATION"
    )

    print(
        validation[
            [
                "test",
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

    print_section(
        "DAY 60 OUTPUTS"
    )

    outputs = [
        OUTPUT_INSTRUMENT_RISK,
        OUTPUT_PORTFOLIO_RISK,
        OUTPUT_ASSET_CLASS,
        OUTPUT_RISK_COVERAGE,
        OUTPUT_DATA_REQUIREMENTS,
        OUTPUT_VALIDATION,
    ]

    for output in outputs:

        print(
            output
        )

    print_section(
        "DAY 60 COMPLETE"
    )

    print(
        "Unified multi-asset risk calculation layer completed."
    )

    print()
    print(
        "Vittantra can now:"
    )

    print(
        "• identify the asset class"
    )

    print(
        "• route each instrument to appropriate risk metrics"
    )

    print(
        "• calculate return-based risk when price history exists"
    )

    print(
        "• calculate fixed-income duration / DV01 / convexity"
    )

    print(
        "• calculate Black-Scholes option Greeks when inputs exist"
    )

    print(
        "• calculate multi-asset exposures"
    )

    print(
        "• aggregate portfolio asset-class exposure"
    )

    print(
        "• reuse the existing Vittantra historical VaR engine"
    )

    print(
        "• explicitly identify missing data instead of "
        "fabricating risk numbers"
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