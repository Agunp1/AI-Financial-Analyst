"""
Vittantra pricing formulas, shared by the data hub, the stress engine and
the risk model so every module values instruments the same way.

All formulas are the standard textbook versions:

- Black-Scholes (1973) European option price and delta, no dividends.
- Fixed-coupon bond price from yield to maturity, with Macaulay duration,
  modified duration and convexity (discrete compounding).
- Equity valuation (Day 78): CAPM, Blume-adjusted beta, WACC, Gordon growth,
  two-stage DCF/DDM with fading growth, residual income (clean surplus).
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


# ==============================================================
# EQUITY VALUATION (CFA Level II equity)
# ==============================================================

def capm_cost_of_equity(risk_free: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: r_e = r_f + β × ERP."""
    return risk_free + beta * equity_risk_premium


def blume_adjusted_beta(raw_beta: float) -> float:
    """Blume adjustment toward 1: β_adj = 2/3 β_raw + 1/3 (betas mean-revert)."""
    return 2.0 / 3.0 * raw_beta + 1.0 / 3.0


def wacc(equity_value: float, debt_value: float, cost_of_equity: float,
         pretax_cost_of_debt: float, tax_rate: float) -> float:
    """WACC = E/V × r_e + D/V × r_d × (1 − t), market-value weights."""
    total = equity_value + debt_value
    return (equity_value / total * cost_of_equity
            + debt_value / total * pretax_cost_of_debt * (1 - tax_rate))


def gordon_growth_value(next_cash_flow: float, discount_rate: float, growth: float) -> float:
    """Constant-growth value: V_0 = CF_1 / (r − g); requires r > g."""
    if discount_rate <= growth:
        raise ValueError("discount rate must exceed the growth rate")
    return next_cash_flow / (discount_rate - growth)


def fading_growth_path(initial_growth: float, terminal_growth: float, years: int) -> list:
    """Growth that fades linearly from the initial rate to the terminal rate by the final year."""
    if years == 1:
        return [terminal_growth]
    return [initial_growth + (terminal_growth - initial_growth) * t / (years - 1) for t in range(years)]


def two_stage_value(current_cash_flow: float, discount_rate: float, growth_path: list,
                    terminal_growth: float) -> Dict[str, float]:
    """
    Present value of cash flows growing along `growth_path` (one rate per
    year) plus a Gordon terminal value at the end of the explicit period.

        CF_t = CF_{t-1} × (1 + g_t),  PV = Σ CF_t/(1+r)^t + TV_N/(1+r)^N,
        TV_N = CF_N × (1 + g_T) / (r − g_T)
    """
    cash_flow, pv_explicit = current_cash_flow, 0.0
    for t, g in enumerate(growth_path, start=1):
        cash_flow *= 1 + g
        pv_explicit += cash_flow / (1 + discount_rate) ** t
    n = len(growth_path)
    terminal = gordon_growth_value(cash_flow * (1 + terminal_growth), discount_rate, terminal_growth)
    pv_terminal = terminal / (1 + discount_rate) ** n
    return {"value": pv_explicit + pv_terminal, "pv_explicit": pv_explicit,
            "pv_terminal": pv_terminal, "terminal_share": pv_terminal / (pv_explicit + pv_terminal)}


def residual_income_value(book_value: float, roe_path: list, cost_of_equity: float,
                          retention: float, persistence: float = 0.0) -> Dict[str, float]:
    """
    Residual income model (clean surplus):

        RI_t = (ROE_t − r) × B_{t−1},   B_t = B_{t−1} × (1 + ROE_t × b)
        V_0  = B_0 + Σ RI_t/(1+r)^t + continuing value

    Continuing value after the last year: RI_{N+1} / (1 + r − ω) discounted
    from year N, where ω is the persistence factor (0 = RI ends after N).
    """
    book, pv_ri, ri = book_value, 0.0, 0.0
    for t, roe in enumerate(roe_path, start=1):
        ri = (roe - cost_of_equity) * book
        pv_ri += ri / (1 + cost_of_equity) ** t
        book *= 1 + roe * retention
    n = len(roe_path)
    continuing = ri * persistence / (1 + cost_of_equity - persistence) / (1 + cost_of_equity) ** n
    return {"value": book_value + pv_ri + continuing, "book_value": book_value,
            "pv_residual_income": pv_ri, "pv_continuing": continuing}


def sustainable_growth(roe: float, retention: float) -> float:
    """g = b × ROE (growth financed by retained earnings)."""
    return retention * roe
