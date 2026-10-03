"""
Vittantra covariance risk model (Euler risk contributions).

Replaces fixed asset-class "risk multipliers" with the standard
portfolio-risk framework used by institutional risk systems:

    x      dollar economic exposure per position (signed)
             - stocks, ETFs, bonds, FX, commodities, crypto: market value
             - futures: contract notional
             - options: delta-adjusted underlying exposure
                        Δ × underlying price × quantity × multiplier
    Σ      annualized covariance matrix of daily returns
    σp     portfolio volatility = sqrt(xᵀ Σ x)
    RCi    Euler risk contribution = xi (Σx)i / σp,  Σ RCi = σp
    share  RCi / σp (sums to 1; negative for positions that hedge)

Price history is real market data in LIVE mode, otherwise the Day 60
synthetic validation history (clearly labelled).
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from vittantra_live_inputs import data_mode_label, load_price_history, valuation_date
from vittantra_pricing import black_scholes_delta


TRADING_DAYS = 252
EPSILON = 1e-12


def load_risk_history(instruments) -> Tuple[pd.DataFrame, str]:
    """Daily prices per symbol: real in LIVE mode, synthetic otherwise."""
    symbols = [instrument.symbol for instrument in instruments]
    history = load_price_history(symbols)
    if history is not None:
        return history, "LIVE market history"
    from unified_risk_engine import build_validation_price_history

    return (
        build_validation_price_history(instruments=instruments, observations=320, seed=60),
        "SAMPLE synthetic validation history",
    )


def option_delta(instrument) -> Optional[float]:
    metadata = instrument.metadata or {}
    needed = [metadata.get("underlying_price"), metadata.get("implied_volatility"),
              metadata.get("risk_free_rate"), instrument.strike, instrument.expiration_date]
    if any(value is None for value in needed):
        return None
    years = (pd.Timestamp(instrument.expiration_date) - valuation_date()).days / 365.0
    return black_scholes_delta(
        float(metadata["underlying_price"]), float(instrument.strike), years,
        float(metadata["risk_free_rate"]), float(metadata["implied_volatility"]),
        instrument.option_type or "call",
    )


def economic_exposure(
    instrument,
    market_value: float,
    quantity: Optional[float] = None,
) -> Tuple[float, str]:
    """Signed dollar exposure that drives market risk, and how it was measured."""
    if instrument is not None and instrument.asset_class.value == "Option":
        delta = option_delta(instrument)
        if delta is not None:
            underlying = float(instrument.metadata["underlying_price"])
            multiplier = instrument.contract_multiplier or 1.0
            units = instrument.quantity if quantity is None else quantity
            return delta * underlying * units * multiplier, f"delta-adjusted (delta={delta:.2f})"
    return float(market_value), "market value / notional"


def risk_driver_symbol(instrument) -> str:
    """Options move with their underlying; everything else with itself."""
    if instrument.asset_class.value == "Option" and instrument.underlying:
        return instrument.underlying
    return instrument.symbol


def annualized_covariance(history: pd.DataFrame, symbols: Iterable[str]) -> pd.DataFrame:
    returns = history[list(symbols)].pct_change().dropna()
    return returns.cov() * TRADING_DAYS


def euler_risk_contributions(
    exposures: pd.Series,
    covariance: pd.DataFrame,
) -> Tuple[pd.Series, float]:
    """
    Returns (risk share per position, portfolio volatility in dollars).
    Shares sum to 1 when portfolio volatility is positive.
    """
    x = exposures.astype(float).to_numpy()
    sigma = covariance.to_numpy()
    variance = float(x @ sigma @ x)
    if variance <= EPSILON:
        return pd.Series(0.0, index=exposures.index), 0.0
    portfolio_vol = math.sqrt(variance)
    marginal = sigma @ x / portfolio_vol
    contributions = x * marginal
    return pd.Series(contributions / portfolio_vol, index=exposures.index), portfolio_vol


def portfolio_risk_shares(
    exposures_by_symbol: Dict[str, float],
    instruments,
    history: Optional[pd.DataFrame] = None,
) -> Tuple[pd.Series, float, str]:
    """
    Euler risk share for each symbol in exposures_by_symbol.

    exposures_by_symbol: {portfolio symbol: signed dollar exposure}
    """
    by_symbol = {instrument.symbol: instrument for instrument in instruments}
    source = "provided history"
    if history is None:
        history, source = load_risk_history(instruments)
    symbols = list(exposures_by_symbol)
    drivers = [risk_driver_symbol(by_symbol[s]) if s in by_symbol else s for s in symbols]
    covariance = annualized_covariance(history, list(dict.fromkeys(drivers)))
    covariance = covariance.loc[drivers, drivers]
    covariance.index = covariance.columns = symbols
    shares, portfolio_vol = euler_risk_contributions(
        pd.Series(exposures_by_symbol, dtype=float), covariance,
    )
    return shares, portfolio_vol, source


def load_enriched_instruments():
    from multi_asset_risk import build_sample_instruments
    from unified_risk_engine import enrich_sample_instruments

    return enrich_sample_instruments(build_sample_instruments())


def risk_model_label(source: str) -> str:
    return f"Euler covariance risk contribution ({source}; data mode {data_mode_label()})"


def constant_correlation_shrinkage(returns: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Ledoit–Wolf (2004) "Honey, I shrunk the sample covariance matrix":
    shrink the sample covariance S toward a constant-correlation target F
    (every pair has the average sample correlation), Σ = δF + (1 − δ)S, with
    the optimal intensity δ estimated from the data. Unlike shrinkage toward a
    scaled identity, it keeps the typical correlation between assets, so the
    risk of diversified portfolios is not understated.

    returns: T × N array of period returns (no missing values).
    Returns (covariance per period, shrinkage intensity δ).
    """
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    x = x - x.mean(axis=0)
    sample = x.T @ x / t
    var = np.diag(sample)
    sd = np.sqrt(var)
    corr = sample / np.outer(sd, sd)
    rbar = (corr.sum() - n) / (n * (n - 1))
    prior = rbar * np.outer(sd, sd)
    np.fill_diagonal(prior, var)
    y = x ** 2
    phi_mat = y.T @ y / t - sample ** 2
    phi = phi_mat.sum()
    theta = (x ** 3).T @ x / t - var[:, None] * sample
    np.fill_diagonal(theta, 0.0)
    rho = np.trace(phi_mat) + rbar * (np.outer(1 / sd, sd) * theta).sum()
    gamma = np.linalg.norm(sample - prior, "fro") ** 2
    delta = 0.0 if gamma <= 0 else max(0.0, min(1.0, (phi - rho) / gamma / t))
    return delta * prior + (1 - delta) * sample, delta
