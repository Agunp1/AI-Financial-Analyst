"""
Vittantra pricing formulas, shared by the data hub, the stress engine and
the risk model so every module values instruments the same way.

All formulas are the standard textbook versions:

- Black-Scholes (1973) European option price and delta, no dividends.
- Fixed-coupon bond price from yield to maturity, with Macaulay duration,
  modified duration and convexity (discrete compounding).
"""

from __future__ import annotations

import math
from typing import Dict


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1_d2(spot, strike, years, rate, vol):
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * math.sqrt(years))
    return d1, d1 - vol * math.sqrt(years)


def black_scholes_price(spot, strike, years, rate, vol, option_type="call") -> float:
    """
    C = S·N(d1) − K·e^(−rT)·N(d2)
    P = K·e^(−rT)·N(−d2) − S·N(−d1)
    At or after expiry (or zero volatility) the option is worth its
    intrinsic value.
    """
    is_call = str(option_type).strip().lower() in {"call", "c"}
    if years <= 0 or vol <= 0:
        return max(spot - strike, 0.0) if is_call else max(strike - spot, 0.0)
    d1, d2 = _d1_d2(spot, strike, years, rate, vol)
    discount = math.exp(-rate * years)
    if is_call:
        return spot * normal_cdf(d1) - strike * discount * normal_cdf(d2)
    return strike * discount * normal_cdf(-d2) - spot * normal_cdf(-d1)


def black_scholes_delta(spot, strike, years, rate, vol, option_type="call") -> float:
    """Call delta = N(d1); put delta = N(d1) − 1."""
    is_call = str(option_type).strip().lower() in {"call", "c"}
    if years <= 0 or vol <= 0:
        in_the_money = spot > strike if is_call else spot < strike
        return (1.0 if is_call else -1.0) if in_the_money else 0.0
    d1, _ = _d1_d2(spot, strike, years, rate, vol)
    return normal_cdf(d1) if is_call else normal_cdf(d1) - 1.0


def bond_price(coupon_rate, yield_rate, years, frequency=2, face=100.0) -> float:
    """P = Σ C/(1+y/f)^k + F/(1+y/f)^n, per 100 face."""
    return bond_analytics(coupon_rate, yield_rate, years, frequency, face)["price"]


def bond_analytics(coupon_rate, yield_rate, years, frequency=2, face=100.0) -> Dict[str, float]:
    """
    Price, Macaulay duration, modified duration and convexity (in years²)
    for a fixed-coupon bond. Cash flows are placed on a regular schedule
    ending at maturity (the first-period stub is approximated).
    """
    periods = max(int(round(years * frequency)), 1)
    coupon = face * coupon_rate / frequency
    per_period_yield = yield_rate / frequency
    price = macaulay = convexity = 0.0
    for k in range(1, periods + 1):
        cash_flow = coupon + (face if k == periods else 0.0)
        discount = (1 + per_period_yield) ** k
        pv = cash_flow / discount
        price += pv
        macaulay += (k / frequency) * pv
        convexity += cash_flow * k * (k + 1) / (1 + per_period_yield) ** (k + 2)
    macaulay /= price
    return {
        "price": price,
        "macaulay_duration": macaulay,
        "modified_duration": macaulay / (1 + per_period_yield),
        "convexity": convexity / (price * frequency * frequency),
    }
