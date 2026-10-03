"""
VITTANTRA
Day 59 — Multi-Asset Risk Foundation

Purpose
-------
Create a unified, extensible multi-asset risk schema for Vittantra.

This module does NOT replace the existing:
    risk_engine.py
    stress_engine.py
    risk_dashboard.py

Instead, it creates the common instrument/risk language that those
systems can use later.

Supported asset families
------------------------
- Equity
- ETF / Fund
- Fixed Income / Bond
- Option
- Future
- FX
- Commodity
- Cash / Money Market
- Crypto
- Real Estate / REIT
- Other

Core principle
--------------
Different assets require different risk measures.

Vittantra should NEVER manufacture a metric that is not meaningful
or cannot be calculated from available data.

Unavailable metrics are explicitly marked as:
    N/A / insufficient data

Day 59 is architecture + validation.
It is NOT a live pricing or trading engine.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ==============================================================
# OUTPUT FILES
# ==============================================================

OUTPUT_ASSET_SCHEMA = Path("day59_asset_risk_schema.csv")
OUTPUT_RISK_CATALOG = Path("day59_risk_metric_catalog.csv")
OUTPUT_SAMPLE_INSTRUMENTS = Path("day59_sample_instruments.csv")
OUTPUT_ROUTING_MATRIX = Path("day59_risk_routing_matrix.csv")
OUTPUT_VALIDATION = Path("day59_validation_summary.csv")
OUTPUT_JSON = Path("day59_multi_asset_schema.json")


# ==============================================================
# CONSTANTS
# ==============================================================

NA_REASON = "N/A / insufficient data"


# ==============================================================
# ENUMS
# ==============================================================

class AssetClass(str, Enum):
    EQUITY = "Equity"
    ETF_FUND = "ETF/Fund"
    FIXED_INCOME = "Fixed Income"
    OPTION = "Option"
    FUTURE = "Future"
    FX = "FX"
    COMMODITY = "Commodity"
    CASH = "Cash/Money Market"
    CRYPTO = "Crypto"
    REAL_ESTATE = "Real Estate/REIT"
    OTHER = "Other"


class RiskCategory(str, Enum):
    MARKET = "Market Risk"
    VOLATILITY = "Volatility Risk"
    DRAWDOWN = "Drawdown Risk"
    FACTOR = "Factor Risk"
    CONCENTRATION = "Concentration Risk"
    LIQUIDITY = "Liquidity Risk"
    INTEREST_RATE = "Interest Rate Risk"
    CREDIT = "Credit Risk"
    CURVE = "Yield Curve Risk"
    SPREAD = "Spread Risk"
    OPTIONALITY = "Optionality Risk"
    LEVERAGE = "Leverage Risk"
    CURRENCY = "Currency Risk"
    COMMODITY = "Commodity Risk"
    COUNTERPARTY = "Counterparty Risk"
    INFLATION = "Inflation Risk"
    MODEL = "Model Risk"
    BASIS = "Basis Risk"
    TAIL = "Tail Risk"


class MetricStatus(str, Enum):
    REQUIRED = "Required"
    APPLICABLE = "Applicable"
    OPTIONAL = "Optional"
    NOT_APPLICABLE = "Not Applicable"


# ==============================================================
# DATA STRUCTURES
# ==============================================================

@dataclass
class Instrument:
    instrument_id: str
    symbol: str
    name: str
    asset_class: AssetClass

    currency: str = "USD"
    quantity: float = 0.0
    price: Optional[float] = None
    market_value: Optional[float] = None

    exchange: Optional[str] = None
    country: Optional[str] = None
    sector: Optional[str] = None

    issuer: Optional[str] = None

    maturity_date: Optional[str] = None
    coupon_rate: Optional[float] = None
    yield_to_maturity: Optional[float] = None
    credit_rating: Optional[str] = None

    underlying: Optional[str] = None
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration_date: Optional[str] = None
    contract_multiplier: Optional[float] = None

    base_currency: Optional[str] = None
    quote_currency: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_market_value(self) -> Optional[float]:
        if self.market_value is not None:
            return float(self.market_value)

        if self.price is None:
            return None

        multiplier = (
            self.contract_multiplier
            if self.contract_multiplier is not None
            else 1.0
        )

        return float(
            self.quantity
            * self.price
            * multiplier
        )


@dataclass
class RiskMetric:
    metric: str
    category: RiskCategory
    description: str
    unit: str
    requires_market_data: bool = True
    requires_instrument_data: bool = False


@dataclass
class RiskResult:
    instrument_id: str
    symbol: str
    asset_class: str
    metric: str
    category: str
    value: Any
    status: str
    reason: str


# ==============================================================
# MASTER RISK METRIC CATALOG
# ==============================================================

RISK_METRICS: Dict[str, RiskMetric] = {

    "market_value": RiskMetric(
        metric="market_value",
        category=RiskCategory.CONCENTRATION,
        description="Current economic value of the position.",
        unit="currency",
        requires_market_data=False,
        requires_instrument_data=True,
    ),

    "portfolio_weight": RiskMetric(
        metric="portfolio_weight",
        category=RiskCategory.CONCENTRATION,
        description="Position market value divided by total portfolio value.",
        unit="percent",
        requires_market_data=False,
        requires_instrument_data=True,
    ),

    "volatility": RiskMetric(
        metric="volatility",
        category=RiskCategory.VOLATILITY,
        description="Historical or model-implied variability of returns.",
        unit="percent",
    ),

    "beta": RiskMetric(
        metric="beta",
        category=RiskCategory.MARKET,
        description="Sensitivity to a selected market benchmark.",
        unit="beta",
    ),

    "var": RiskMetric(
        metric="var",
        category=RiskCategory.TAIL,
        description="Value at Risk at a specified confidence level.",
        unit="currency_or_percent",
    ),

    "cvar": RiskMetric(
        metric="cvar",
        category=RiskCategory.TAIL,
        description="Expected loss beyond the VaR threshold.",
        unit="currency_or_percent",
    ),

    "maximum_drawdown": RiskMetric(
        metric="maximum_drawdown",
        category=RiskCategory.DRAWDOWN,
        description="Largest peak-to-trough historical decline.",
        unit="percent",
    ),

    "correlation": RiskMetric(
        metric="correlation",
        category=RiskCategory.MARKET,
        description="Return relationship with another asset or benchmark.",
        unit="correlation",
    ),

    "factor_exposure": RiskMetric(
        metric="factor_exposure",
        category=RiskCategory.FACTOR,
        description="Exposure to systematic investment factors.",
        unit="exposure",
    ),

    "liquidity_risk": RiskMetric(
        metric="liquidity_risk",
        category=RiskCategory.LIQUIDITY,
        description="Risk associated with exiting or resizing a position.",
        unit="score_or_cost",
    ),

    "concentration_risk": RiskMetric(
        metric="concentration_risk",
        category=RiskCategory.CONCENTRATION,
        description="Exposure concentration by position, issuer, sector or asset class.",
        unit="percent_or_score",
        requires_market_data=False,
        requires_instrument_data=True,
    ),

    "duration": RiskMetric(
        metric="duration",
        category=RiskCategory.INTEREST_RATE,
        description="Approximate sensitivity of bond price to yield changes.",
        unit="years",
        requires_instrument_data=True,
    ),

    "modified_duration": RiskMetric(
        metric="modified_duration",
        category=RiskCategory.INTEREST_RATE,
        description="Percentage price sensitivity to a change in yield.",
        unit="years",
        requires_instrument_data=True,
    ),

    "convexity": RiskMetric(
        metric="convexity",
        category=RiskCategory.INTEREST_RATE,
        description="Curvature of the bond price-yield relationship.",
        unit="convexity",
        requires_instrument_data=True,
    ),

    "dv01": RiskMetric(
        metric="dv01",
        category=RiskCategory.INTEREST_RATE,
        description="Approximate currency value change for a 1 bp yield move.",
        unit="currency_per_bp",
        requires_instrument_data=True,
    ),

    "credit_spread": RiskMetric(
        metric="credit_spread",
        category=RiskCategory.SPREAD,
        description="Yield spread over a reference risk-free curve.",
        unit="basis_points",
        requires_instrument_data=True,
    ),

    "credit_risk": RiskMetric(
        metric="credit_risk",
        category=RiskCategory.CREDIT,
        description="Issuer default and credit deterioration exposure.",
        unit="score_or_spread",
        requires_instrument_data=True,
    ),

    "yield_curve_exposure": RiskMetric(
        metric="yield_curve_exposure",
        category=RiskCategory.CURVE,
        description="Sensitivity to changes in the shape of the yield curve.",
        unit="exposure",
        requires_instrument_data=True,
    ),

    "delta": RiskMetric(
        metric="delta",
        category=RiskCategory.OPTIONALITY,
        description="Option sensitivity to the underlying asset price.",
        unit="delta",
        requires_instrument_data=True,
    ),

    "gamma": RiskMetric(
        metric="gamma",
        category=RiskCategory.OPTIONALITY,
        description="Sensitivity of option delta to underlying price.",
        unit="gamma",
        requires_instrument_data=True,
    ),

    "vega": RiskMetric(
        metric="vega",
        category=RiskCategory.OPTIONALITY,
        description="Option sensitivity to implied volatility.",
        unit="currency_per_vol_point",
        requires_instrument_data=True,
    ),

    "theta": RiskMetric(
        metric="theta",
        category=RiskCategory.OPTIONALITY,
        description="Option sensitivity to passage of time.",
        unit="currency_per_day",
        requires_instrument_data=True,
    ),

    "rho": RiskMetric(
        metric="rho",
        category=RiskCategory.OPTIONALITY,
        description="Option sensitivity to interest rates.",
        unit="rho",
        requires_instrument_data=True,
    ),

    "implied_volatility": RiskMetric(
        metric="implied_volatility",
        category=RiskCategory.VOLATILITY,
        description="Market-implied volatility embedded in option prices.",
        unit="percent",
        requires_instrument_data=True,
    ),

    "leverage": RiskMetric(
        metric="leverage",
        category=RiskCategory.LEVERAGE,
        description="Economic exposure relative to capital committed.",
        unit="multiple",
        requires_instrument_data=True,
    ),

    "currency_exposure": RiskMetric(
        metric="currency_exposure",
        category=RiskCategory.CURRENCY,
        description="Sensitivity to changes in exchange rates.",
        unit="currency_or_percent",
        requires_instrument_data=True,
    ),

    "carry": RiskMetric(
        metric="carry",
        category=RiskCategory.CURRENCY,
        description="Expected carry associated with holding the exposure.",
        unit="percent",
        requires_instrument_data=True,
    ),

    "basis_risk": RiskMetric(
        metric="basis_risk",
        category=RiskCategory.BASIS,
        description="Risk that related spot and derivative prices diverge.",
        unit="spread_or_percent",
        requires_instrument_data=True,
    ),

    "commodity_price_risk": RiskMetric(
        metric="commodity_price_risk",
        category=RiskCategory.COMMODITY,
        description="Sensitivity to commodity price movements.",
        unit="exposure",
    ),

    "inflation_risk": RiskMetric(
        metric="inflation_risk",
        category=RiskCategory.INFLATION,
        description="Sensitivity of real purchasing power to inflation.",
        unit="exposure",
    ),

    "counterparty_risk": RiskMetric(
        metric="counterparty_risk",
        category=RiskCategory.COUNTERPARTY,
        description="Potential loss due to counterparty failure.",
        unit="exposure_or_score",
        requires_instrument_data=True,
    ),

    "tracking_error": RiskMetric(
        metric="tracking_error",
        category=RiskCategory.MARKET,
        description="Volatility of active returns versus benchmark.",
        unit="percent",
    ),

    "underlying_concentration": RiskMetric(
        metric="underlying_concentration",
        category=RiskCategory.CONCENTRATION,
        description="Concentration within a fund or pooled investment.",
        unit="percent",
        requires_instrument_data=True,
    ),

    "real_estate_exposure": RiskMetric(
        metric="real_estate_exposure",
        category=RiskCategory.MARKET,
        description="Sensitivity to property-market conditions.",
        unit="exposure",
    ),
}


# ==============================================================
# ASSET-SPECIFIC RISK ROUTING
# ==============================================================

ASSET_RISK_MAP: Dict[AssetClass, Dict[str, MetricStatus]] = {

    AssetClass.EQUITY: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "beta": MetricStatus.REQUIRED,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.REQUIRED,
        "maximum_drawdown": MetricStatus.REQUIRED,
        "correlation": MetricStatus.APPLICABLE,
        "factor_exposure": MetricStatus.APPLICABLE,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.ETF_FUND: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "beta": MetricStatus.APPLICABLE,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.REQUIRED,
        "maximum_drawdown": MetricStatus.REQUIRED,
        "tracking_error": MetricStatus.APPLICABLE,
        "factor_exposure": MetricStatus.APPLICABLE,
        "underlying_concentration": MetricStatus.APPLICABLE,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.FIXED_INCOME: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.APPLICABLE,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.APPLICABLE,
        "duration": MetricStatus.REQUIRED,
        "modified_duration": MetricStatus.REQUIRED,
        "convexity": MetricStatus.APPLICABLE,
        "dv01": MetricStatus.REQUIRED,
        "credit_spread": MetricStatus.APPLICABLE,
        "credit_risk": MetricStatus.REQUIRED,
        "yield_curve_exposure": MetricStatus.REQUIRED,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.OPTION: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.APPLICABLE,
        "var": MetricStatus.APPLICABLE,
        "delta": MetricStatus.REQUIRED,
        "gamma": MetricStatus.REQUIRED,
        "vega": MetricStatus.REQUIRED,
        "theta": MetricStatus.REQUIRED,
        "rho": MetricStatus.APPLICABLE,
        "implied_volatility": MetricStatus.REQUIRED,
        "leverage": MetricStatus.REQUIRED,
        "liquidity_risk": MetricStatus.REQUIRED,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.FUTURE: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.APPLICABLE,
        "leverage": MetricStatus.REQUIRED,
        "basis_risk": MetricStatus.REQUIRED,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "commodity_price_risk": MetricStatus.APPLICABLE,
        "currency_exposure": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.FX: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.APPLICABLE,
        "currency_exposure": MetricStatus.REQUIRED,
        "carry": MetricStatus.APPLICABLE,
        "correlation": MetricStatus.APPLICABLE,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.COMMODITY: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.APPLICABLE,
        "maximum_drawdown": MetricStatus.APPLICABLE,
        "commodity_price_risk": MetricStatus.REQUIRED,
        "correlation": MetricStatus.APPLICABLE,
        "inflation_risk": MetricStatus.APPLICABLE,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.CASH: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "currency_exposure": MetricStatus.APPLICABLE,
        "inflation_risk": MetricStatus.REQUIRED,
        "counterparty_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.APPLICABLE,
    },

    AssetClass.CRYPTO: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.REQUIRED,
        "var": MetricStatus.REQUIRED,
        "cvar": MetricStatus.REQUIRED,
        "maximum_drawdown": MetricStatus.REQUIRED,
        "correlation": MetricStatus.APPLICABLE,
        "liquidity_risk": MetricStatus.REQUIRED,
        "counterparty_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.REAL_ESTATE: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.OPTIONAL,
        "var": MetricStatus.OPTIONAL,
        "real_estate_exposure": MetricStatus.REQUIRED,
        "interest_rate_risk": MetricStatus.OPTIONAL,
        "liquidity_risk": MetricStatus.REQUIRED,
        "inflation_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },

    AssetClass.OTHER: {
        "market_value": MetricStatus.REQUIRED,
        "portfolio_weight": MetricStatus.REQUIRED,
        "volatility": MetricStatus.OPTIONAL,
        "var": MetricStatus.OPTIONAL,
        "liquidity_risk": MetricStatus.APPLICABLE,
        "concentration_risk": MetricStatus.REQUIRED,
    },
}


# ==============================================================
# FIX EXTENSIBLE METRICS
# ==============================================================

# Add an explicit generic interest-rate metric used by real estate.
RISK_METRICS["interest_rate_risk"] = RiskMetric(
    metric="interest_rate_risk",
    category=RiskCategory.INTEREST_RATE,
    description="General sensitivity to changes in interest rates.",
    unit="exposure",
)


# ==============================================================
# ASSET CLASSIFICATION
# ==============================================================

ASSET_CLASS_ALIASES = {

    "stock": AssetClass.EQUITY,
    "stocks": AssetClass.EQUITY,
    "equity": AssetClass.EQUITY,
    "equities": AssetClass.EQUITY,

    "etf": AssetClass.ETF_FUND,
    "fund": AssetClass.ETF_FUND,
    "mutual fund": AssetClass.ETF_FUND,

    "bond": AssetClass.FIXED_INCOME,
    "fixed income": AssetClass.FIXED_INCOME,
    "treasury": AssetClass.FIXED_INCOME,
    "corporate bond": AssetClass.FIXED_INCOME,

    "option": AssetClass.OPTION,
    "options": AssetClass.OPTION,

    "future": AssetClass.FUTURE,
    "futures": AssetClass.FUTURE,

    "fx": AssetClass.FX,
    "forex": AssetClass.FX,
    "currency": AssetClass.FX,

    "commodity": AssetClass.COMMODITY,
    "commodities": AssetClass.COMMODITY,

    "cash": AssetClass.CASH,
    "money market": AssetClass.CASH,

    "crypto": AssetClass.CRYPTO,
    "cryptocurrency": AssetClass.CRYPTO,

    "reit": AssetClass.REAL_ESTATE,
    "real estate": AssetClass.REAL_ESTATE,
}


def classify_asset(asset_type: str) -> AssetClass:

    normalized = (
        str(asset_type)
        .strip()
        .lower()
    )

    return ASSET_CLASS_ALIASES.get(
        normalized,
        AssetClass.OTHER,
    )


# ==============================================================
# ROUTING ENGINE
# ==============================================================

def get_risk_requirements(
    asset_class: AssetClass,
) -> Dict[str, MetricStatus]:

    return ASSET_RISK_MAP.get(
        asset_class,
        ASSET_RISK_MAP[
            AssetClass.OTHER
        ],
    )


def get_applicable_metrics(
    asset_class: AssetClass,
) -> List[str]:

    requirements = get_risk_requirements(
        asset_class
    )

    return [
        metric
        for metric, status
        in requirements.items()
        if status
        != MetricStatus.NOT_APPLICABLE
    ]


def route_instrument(
    instrument: Instrument,
) -> pd.DataFrame:

    requirements = get_risk_requirements(
        instrument.asset_class
    )

    rows = []

    for metric_name, status in requirements.items():

        metric_definition = RISK_METRICS.get(
            metric_name
        )

        if metric_definition is None:
            category = "Unclassified"
            description = (
                "Metric registered in routing map "
                "but not metric catalog."
            )
            unit = "unknown"

        else:
            category = metric_definition.category.value
            description = metric_definition.description
            unit = metric_definition.unit

        rows.append(
            {
                "instrument_id": instrument.instrument_id,
                "symbol": instrument.symbol,
                "asset_class": instrument.asset_class.value,
                "metric": metric_name,
                "status": status.value,
                "category": category,
                "unit": unit,
                "description": description,
            }
        )

    return pd.DataFrame(
        rows
    )


# ==============================================================
# BASIC POSITION-LEVEL CALCULATIONS
# ==============================================================

def calculate_basic_risk_results(
    instrument: Instrument,
    portfolio_value: Optional[float] = None,
) -> List[RiskResult]:

    results = []

    market_value = instrument.calculate_market_value()

    if market_value is None:

        results.append(
            RiskResult(
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol,
                asset_class=instrument.asset_class.value,
                metric="market_value",
                category=RiskCategory.CONCENTRATION.value,
                value=np.nan,
                status="Unavailable",
                reason=NA_REASON,
            )
        )

    else:

        results.append(
            RiskResult(
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol,
                asset_class=instrument.asset_class.value,
                metric="market_value",
                category=RiskCategory.CONCENTRATION.value,
                value=market_value,
                status="Calculated",
                reason="Quantity × price × contract multiplier.",
            )
        )

    if (
        market_value is not None
        and portfolio_value is not None
        and portfolio_value > 0
    ):

        portfolio_weight = (
            market_value
            / portfolio_value
        )

        results.append(
            RiskResult(
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol,
                asset_class=instrument.asset_class.value,
                metric="portfolio_weight",
                category=RiskCategory.CONCENTRATION.value,
                value=portfolio_weight,
                status="Calculated",
                reason="Position market value / portfolio market value.",
            )
        )

    else:

        results.append(
            RiskResult(
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol,
                asset_class=instrument.asset_class.value,
                metric="portfolio_weight",
                category=RiskCategory.CONCENTRATION.value,
                value=np.nan,
                status="Unavailable",
                reason=NA_REASON,
            )
        )

    return results


# ==============================================================
# SAMPLE MULTI-ASSET PORTFOLIO
# ==============================================================

def build_sample_instruments() -> List[Instrument]:

    return [

        Instrument(
            instrument_id="EQ_AAPL",
            symbol="AAPL",
            name="Apple Equity Example",
            asset_class=AssetClass.EQUITY,
            quantity=100,
            price=200.0,
            sector="Technology",
            country="US",
        ),

        Instrument(
            instrument_id="ETF_SPY",
            symbol="SPY",
            name="Broad Equity ETF Example",
            asset_class=AssetClass.ETF_FUND,
            quantity=50,
            price=550.0,
            country="US",
        ),

        Instrument(
            instrument_id="BOND_CORP_01",
            symbol="CORP_BOND",
            name="Corporate Bond Example",
            asset_class=AssetClass.FIXED_INCOME,
            quantity=100,
            price=98.50,
            issuer="Example Corporation",
            maturity_date="2031-06-15",
            coupon_rate=0.045,
            yield_to_maturity=0.052,
            credit_rating="BBB",
        ),

        Instrument(
            instrument_id="OPT_AAPL_CALL",
            symbol="AAPL_CALL",
            name="Apple Call Option Example",
            asset_class=AssetClass.OPTION,
            quantity=5,
            price=8.50,
            underlying="AAPL",
            option_type="Call",
            strike=210.0,
            expiration_date="2027-01-15",
            contract_multiplier=100,
        ),

        Instrument(
            instrument_id="FUT_ES",
            symbol="ES",
            name="Equity Index Future Example",
            asset_class=AssetClass.FUTURE,
            quantity=1,
            price=6000.0,
            contract_multiplier=50,
        ),

        Instrument(
            instrument_id="FX_EURUSD",
            symbol="EURUSD",
            name="EUR/USD FX Example",
            asset_class=AssetClass.FX,
            quantity=10000,
            price=1.10,
            base_currency="EUR",
            quote_currency="USD",
        ),

        Instrument(
            instrument_id="CMD_GOLD",
            symbol="GOLD",
            name="Gold Exposure Example",
            asset_class=AssetClass.COMMODITY,
            quantity=10,
            price=2600.0,
        ),

        Instrument(
            instrument_id="CASH_USD",
            symbol="USD",
            name="US Dollar Cash",
            asset_class=AssetClass.CASH,
            quantity=10000,
            price=1.0,
            currency="USD",
        ),

        Instrument(
            instrument_id="CRYPTO_BTC",
            symbol="BTC",
            name="Bitcoin Example",
            asset_class=AssetClass.CRYPTO,
            quantity=0.25,
            price=100000.0,
        ),

        Instrument(
            instrument_id="REIT_SAMPLE",
            symbol="REIT",
            name="Real Estate / REIT Example",
            asset_class=AssetClass.REAL_ESTATE,
            quantity=100,
            price=100.0,
        ),
    ]


# ==============================================================
# TABLE BUILDERS
# ==============================================================

def build_asset_schema() -> pd.DataFrame:

    rows = []

    for asset_class in AssetClass:

        requirements = get_risk_requirements(
            asset_class
        )

        required = [
            metric
            for metric, status
            in requirements.items()
            if status == MetricStatus.REQUIRED
        ]

        applicable = [
            metric
            for metric, status
            in requirements.items()
            if status == MetricStatus.APPLICABLE
        ]

        optional = [
            metric
            for metric, status
            in requirements.items()
            if status == MetricStatus.OPTIONAL
        ]

        rows.append(
            {
                "asset_class": asset_class.value,
                "required_metrics": ", ".join(required),
                "applicable_metrics": ", ".join(applicable),
                "optional_metrics": ", ".join(optional),
                "metric_count": len(requirements),
            }
        )

    return pd.DataFrame(
        rows
    )


def build_metric_catalog() -> pd.DataFrame:

    rows = []

    for metric_name, metric in RISK_METRICS.items():

        rows.append(
            {
                "metric": metric_name,
                "category": metric.category.value,
                "description": metric.description,
                "unit": metric.unit,
                "requires_market_data": metric.requires_market_data,
                "requires_instrument_data": metric.requires_instrument_data,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            [
                "category",
                "metric",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def build_sample_instrument_table(
    instruments: List[Instrument],
) -> pd.DataFrame:

    rows = []

    for instrument in instruments:

        market_value = (
            instrument.calculate_market_value()
        )

        rows.append(
            {
                "instrument_id": instrument.instrument_id,
                "symbol": instrument.symbol,
                "name": instrument.name,
                "asset_class": instrument.asset_class.value,
                "currency": instrument.currency,
                "quantity": instrument.quantity,
                "price": instrument.price,
                "market_value": market_value,
                "sector": instrument.sector,
                "issuer": instrument.issuer,
                "maturity_date": instrument.maturity_date,
                "credit_rating": instrument.credit_rating,
                "underlying": instrument.underlying,
                "option_type": instrument.option_type,
                "base_currency": instrument.base_currency,
                "quote_currency": instrument.quote_currency,
            }
        )

    return pd.DataFrame(
        rows
    )


def build_routing_matrix() -> pd.DataFrame:

    rows = []

    all_metrics = sorted(
        RISK_METRICS.keys()
    )

    for asset_class in AssetClass:

        requirements = get_risk_requirements(
            asset_class
        )

        row = {
            "asset_class": asset_class.value
        }

        for metric in all_metrics:

            status = requirements.get(
                metric,
                MetricStatus.NOT_APPLICABLE,
            )

            row[metric] = status.value

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


# ==============================================================
# VALIDATION
# ==============================================================

def validate_architecture(
    instruments: List[Instrument],
) -> pd.DataFrame:

    checks = []

    # ----------------------------------------------------------
    # Check 1
    # Every asset class has a routing map.
    # ----------------------------------------------------------

    all_classes_routed = all(
        asset_class in ASSET_RISK_MAP
        for asset_class in AssetClass
    )

    checks.append(
        {
            "test": "Every asset class has risk routing",
            "passed": all_classes_routed,
            "details": (
                f"{len(ASSET_RISK_MAP)} routing definitions"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 2
    # Every routed metric exists in catalog.
    # ----------------------------------------------------------

    missing_metrics = []

    for asset_class, requirements in ASSET_RISK_MAP.items():

        for metric in requirements:

            if metric not in RISK_METRICS:

                missing_metrics.append(
                    f"{asset_class.value}:{metric}"
                )

    checks.append(
        {
            "test": "Every routed metric exists in catalog",
            "passed": len(missing_metrics) == 0,
            "details": (
                "None"
                if not missing_metrics
                else ", ".join(missing_metrics)
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 3
    # Sample instruments span major asset families.
    # ----------------------------------------------------------

    sample_classes = {
        instrument.asset_class
        for instrument in instruments
    }

    major_classes = {
        AssetClass.EQUITY,
        AssetClass.ETF_FUND,
        AssetClass.FIXED_INCOME,
        AssetClass.OPTION,
        AssetClass.FUTURE,
        AssetClass.FX,
        AssetClass.COMMODITY,
        AssetClass.CASH,
        AssetClass.CRYPTO,
        AssetClass.REAL_ESTATE,
    }

    major_coverage = (
        major_classes
        .issubset(
            sample_classes
        )
    )

    checks.append(
        {
            "test": "Sample portfolio spans major asset families",
            "passed": major_coverage,
            "details": (
                f"{len(sample_classes)} asset classes represented"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 4
    # Basic market values calculate.
    # ----------------------------------------------------------

    values = [
        instrument.calculate_market_value()
        for instrument in instruments
    ]

    valid_market_values = all(
        value is not None
        and np.isfinite(value)
        for value in values
    )

    checks.append(
        {
            "test": "Sample market values calculate",
            "passed": valid_market_values,
            "details": (
                f"{sum(v is not None for v in values)} "
                f"of {len(values)} calculated"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 5
    # Bond risk routes correctly.
    # ----------------------------------------------------------

    bond_requirements = get_risk_requirements(
        AssetClass.FIXED_INCOME
    )

    bond_metrics_ok = all(
        metric in bond_requirements
        for metric in [
            "duration",
            "modified_duration",
            "dv01",
            "credit_risk",
            "yield_curve_exposure",
        ]
    )

    checks.append(
        {
            "test": "Fixed income routes to rate and credit risk",
            "passed": bond_metrics_ok,
            "details": (
                "duration, modified duration, DV01, "
                "credit and curve exposure"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 6
    # Option Greeks route correctly.
    # ----------------------------------------------------------

    option_requirements = get_risk_requirements(
        AssetClass.OPTION
    )

    option_metrics_ok = all(
        metric in option_requirements
        for metric in [
            "delta",
            "gamma",
            "vega",
            "theta",
            "implied_volatility",
        ]
    )

    checks.append(
        {
            "test": "Options route to Greeks",
            "passed": option_metrics_ok,
            "details": (
                "delta, gamma, vega, theta and implied volatility"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 7
    # FX routes correctly.
    # ----------------------------------------------------------

    fx_requirements = get_risk_requirements(
        AssetClass.FX
    )

    fx_metrics_ok = all(
        metric in fx_requirements
        for metric in [
            "currency_exposure",
            "volatility",
            "var",
        ]
    )

    checks.append(
        {
            "test": "FX routes to currency risk",
            "passed": fx_metrics_ok,
            "details": (
                "currency exposure, volatility and VaR"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 8
    # Cash does not incorrectly require equity beta.
    # ----------------------------------------------------------

    cash_requirements = get_risk_requirements(
        AssetClass.CASH
    )

    cash_no_beta = (
        "beta"
        not in cash_requirements
    )

    checks.append(
        {
            "test": "Cash does not require equity beta",
            "passed": cash_no_beta,
            "details": (
                "Asset-specific risk logic preserved"
            ),
        }
    )

    # ----------------------------------------------------------
    # Check 9
    # Every instrument can route.
    # ----------------------------------------------------------

    routing_success = True

    for instrument in instruments:

        routed = route_instrument(
            instrument
        )

        if routed.empty:
            routing_success = False
            break

    checks.append(
        {
            "test": "Every sample instrument routes successfully",
            "passed": routing_success,
            "details": (
                f"{len(instruments)} instruments tested"
            ),
        }
    )

    validation = pd.DataFrame(
        checks
    )

    validation[
        "passed_tests"
    ] = validation[
        "passed"
    ].sum()

    validation[
        "total_tests"
    ] = len(
        validation
    )

    validation[
        "pass_rate"
    ] = (
        validation[
            "passed_tests"
        ]
        / validation[
            "total_tests"
        ]
    )

    return validation


# ==============================================================
# JSON EXPORT
# ==============================================================

def export_json_schema(
    instruments: List[Instrument],
) -> None:

    payload = {

        "project": "Vittantra",

        "module": (
            "Day 59 — Multi-Asset Risk Foundation"
        ),

        "asset_classes": [
            asset_class.value
            for asset_class in AssetClass
        ],

        "risk_metrics": {
            metric_name: {
                "category": metric.category.value,
                "description": metric.description,
                "unit": metric.unit,
                "requires_market_data": metric.requires_market_data,
                "requires_instrument_data": metric.requires_instrument_data,
            }
            for metric_name, metric
            in RISK_METRICS.items()
        },

        "risk_routing": {
            asset_class.value: {
                metric: status.value
                for metric, status
                in requirements.items()
            }
            for asset_class, requirements
            in ASSET_RISK_MAP.items()
        },

        "sample_instruments": [
            {
                **asdict(instrument),
                "asset_class": instrument.asset_class.value,
            }
            for instrument in instruments
        ],
    }

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
            default=str,
        )


# ==============================================================
# DISPLAY HELPERS
# ==============================================================

def print_section(
    title: str,
) -> None:

    print()
    print(
        "=" * 78
    )
    print(
        title
    )
    print(
        "=" * 78
    )


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:

    print_section(
        "VITTANTRA — DAY 59"
    )

    print(
        "Multi-Asset Risk Foundation"
    )

    print()
    print(
        "Building a common instrument and risk-routing "
        "architecture for Vittantra."
    )

    # ----------------------------------------------------------
    # Build sample multi-asset universe
    # ----------------------------------------------------------

    instruments = build_sample_instruments()

    print_section(
        "SUPPORTED ASSET CLASSES"
    )

    for asset_class in AssetClass:

        requirements = get_risk_requirements(
            asset_class
        )

        print(
            f"{asset_class.value:<22} "
            f"{len(requirements):>2} routed risk metrics"
        )

    # ----------------------------------------------------------
    # Asset schema
    # ----------------------------------------------------------

    asset_schema = build_asset_schema()

    # ----------------------------------------------------------
    # Metric catalog
    # ----------------------------------------------------------

    metric_catalog = build_metric_catalog()

    # ----------------------------------------------------------
    # Sample instruments
    # ----------------------------------------------------------

    sample_table = (
        build_sample_instrument_table(
            instruments
        )
    )

    total_portfolio_value = (
        sample_table[
            "market_value"
        ]
        .dropna()
        .sum()
    )

    print_section(
        "SAMPLE MULTI-ASSET PORTFOLIO"
    )

    print(
        sample_table[
            [
                "symbol",
                "asset_class",
                "market_value",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        f"Illustrative portfolio value: "
        f"${total_portfolio_value:,.2f}"
    )

    # ----------------------------------------------------------
    # Basic risk calculations
    # ----------------------------------------------------------

    basic_results = []

    for instrument in instruments:

        instrument_results = (
            calculate_basic_risk_results(
                instrument=instrument,
                portfolio_value=total_portfolio_value,
            )
        )

        basic_results.extend(
            instrument_results
        )

    basic_results_df = pd.DataFrame(
        [
            asdict(result)
            for result
            in basic_results
        ]
    )

    # ----------------------------------------------------------
    # Routing matrix
    # ----------------------------------------------------------

    routing_matrix = (
        build_routing_matrix()
    )

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------

    validation = validate_architecture(
        instruments
    )

    print_section(
        "ARCHITECTURE VALIDATION"
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

    pass_rate = (
        passed_tests
        / total_tests
        if total_tests
        else np.nan
    )

    print()
    print(
        f"Passed: {passed_tests}/{total_tests}"
    )

    print(
        f"Pass rate: {pass_rate:.2%}"
    )

    # ----------------------------------------------------------
    # Save outputs
    # ----------------------------------------------------------

    asset_schema.to_csv(
        OUTPUT_ASSET_SCHEMA,
        index=False,
    )

    metric_catalog.to_csv(
        OUTPUT_RISK_CATALOG,
        index=False,
    )

    sample_table.to_csv(
        OUTPUT_SAMPLE_INSTRUMENTS,
        index=False,
    )

    routing_matrix.to_csv(
        OUTPUT_ROUTING_MATRIX,
        index=False,
    )

    validation.to_csv(
        OUTPUT_VALIDATION,
        index=False,
    )

    export_json_schema(
        instruments
    )

    print_section(
        "DAY 59 OUTPUTS"
    )

    outputs = [
        OUTPUT_ASSET_SCHEMA,
        OUTPUT_RISK_CATALOG,
        OUTPUT_SAMPLE_INSTRUMENTS,
        OUTPUT_ROUTING_MATRIX,
        OUTPUT_VALIDATION,
        OUTPUT_JSON,
    ]

    for output in outputs:

        print(
            output
        )

    print_section(
        "DAY 59 COMPLETE"
    )

    print(
        "Multi-asset risk foundation built successfully."
    )

    print()
    print(
        "Vittantra now has an asset-aware risk-routing layer."
    )

    print(
        "It knows that different instruments require different "
        "risk models instead of forcing equity metrics onto "
        "every asset."
    )

    print()
    print(
        "This architecture does NOT yet calculate every live "
        "risk metric."
    )

    print(
        "Those calculations will be connected to market and "
        "instrument data in the unified risk engine."
    )

    print()
    print(
        "Next architecture layer:"
    )

    print(
        "Asset data -> Risk routing -> Unified calculations -> "
        "Portfolio aggregation -> Stress scenarios -> "
        "Rebalancing -> Dashboard"
    )


if __name__ == "__main__":
    main()