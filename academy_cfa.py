"""
Vittantra Academy — CFA Level II style item sets from live data.

Each generator builds a short case (vignette) from Vittantra's real outputs
followed by multiple-choice questions with three options, the format used
in Level II item sets, and a worked explanation for every answer. Numbers
come from Vittantra data; where a case needs an input free data cannot
provide (e.g. a property's NOI), it is stated as an illustrative assumption.

This is practice for applying the curriculum, not a replacement for the
official CFA Institute curriculum and question bank (topics change yearly).
"""

from __future__ import annotations

import ast
import math
import random
from datetime import date
from typing import Callable, Dict, List, Optional

import pandas as pd

import academy_live as live
from academy_live import MissingData, _csv, money, pct


CFA_TOPICS = [
    "Quantitative Methods", "Economics", "Financial Statement Analysis", "Corporate Issuers",
    "Equity Valuation", "Fixed Income", "Derivatives", "Alternative Investments",
    "Portfolio Management", "Ethical and Professional Standards",
]

# Level II topic area for each Academy lesson.
LESSON_CFA_TOPIC = {
    "IA1": "Quantitative Methods", "IA2": "Quantitative Methods", "IA3": "Fixed Income",
    "IA4": "Fixed Income", "IA5": "Economics", "IA6": "Economics",
    "ER1": "Financial Statement Analysis", "ER2": "Equity Valuation", "ER3": "Financial Statement Analysis",
    "ER4": "Financial Statement Analysis", "ER5": "Quantitative Methods",
    "ER6": "Equity Valuation", "ER7": "Ethical and Professional Standards",
    "RA1": "Portfolio Management", "RA2": "Portfolio Management", "RA3": "Fixed Income",
    "RA4": "Derivatives", "RA5": "Portfolio Management",
    "PM1": "Portfolio Management", "PM2": "Portfolio Management", "PM3": "Portfolio Management",
    "PM4": "Quantitative Methods", "PM5": "Portfolio Management", "PM6": "Portfolio Management",
    "PM7": "Portfolio Management", "PM8": "Portfolio Management", "RA6": "Portfolio Management",
    "AD1": "Ethical and Professional Standards", "AD2": "Portfolio Management",
    "AD3": "Quantitative Methods", "AD4": "Portfolio Management", "AD5": "Ethical and Professional Standards",
}


def _question(text: str, correct: str, wrong: List[str], explanation: str, rng: random.Random) -> dict:
    """Three options: the answer plus the first two distinct distractors (pass spares in `wrong`)."""
    distinct = []
    for option in wrong:
        if option != correct and option not in distinct:
            distinct.append(option)
    options = [correct] + distinct[:2]
    rng.shuffle(options)
    return {"question": text, "options": options, "answer": options.index(correct), "explanation": explanation}


def _rng(name: str, day: Optional[date] = None) -> random.Random:
    day = day or date.today()
    return random.Random(day.toordinal() * 7 + sum(map(ord, name)))


# ==============================================================
# ITEM SETS
# ==============================================================

def item_fixed_income(day=None) -> dict:
    rng = _rng("fi", day)
    d = live._risk_metric("CORP_BOND", "modified_duration")
    c = live._risk_metric("CORP_BOND", "convexity")
    mac = live._risk_metric("CORP_BOND", "duration")
    dv01 = live._risk_metric("CORP_BOND", "dv01")
    curve = _csv("day76c_yield_curve.csv", "multi_asset_universe.py").set_index("maturity")
    slope = curve["slope_2s10s_bp"].iloc[0]
    dy = 0.01
    correct = -d * dy + 0.5 * c * dy ** 2
    vignette = (f"Maya Patel, a fixed-income analyst, reviews a BBB corporate bond held in a client portfolio. "
                f"Vittantra reports a Macaulay duration of {mac:.2f}, modified duration of {d:.2f}, convexity of "
                f"{c:.1f} and a DV01 of ${dv01:.2f} for the position. The 10-year Treasury yields "
                f"{curve.loc['10Y', 'yield_pct']:.2f}% and the 2s10s spread is {slope:.0f} bp.")
    questions = [
        _question("Using duration and convexity, the estimated percentage price change for a 100 bp parallel "
                  "increase in yield is closest to:",
                  f"{correct:.2%}", [f"{-d * dy:.2%}", f"{-mac * dy:.2%}"],
                  f"ΔP/P ≈ −D_mod·Δy + ½·C·Δy² = −{d:.2f}×0.01 + ½×{c:.1f}×0.01² = {correct:.2%}. Ignoring convexity "
                  "gives −D_mod·Δy; using Macaulay instead of modified duration overstates the loss.", rng),
        _question(f"The DV01 of ${dv01:.2f} means that for a 1 bp increase in yield the position's value:",
                  f"falls by about ${dv01:.2f}", [f"rises by about ${dv01:.2f}", f"falls by about ${dv01 * 100:.2f}"],
                  "DV01 = market value × modified duration × 0.0001: the money loss for a one basis-point rise.", rng),
        _question(f"A 2s10s spread of {slope:.0f} bp most likely indicates that the yield curve is:",
                  "upward sloping" if slope > 0 else "inverted",
                  ["inverted" if slope > 0 else "upward sloping", "flat by construction"],
                  "2s10s = 10-year yield − 2-year yield; a positive value means longer maturities yield more.", rng),
    ]
    return {"topic": "Fixed Income", "title": "Duration, convexity and the curve", "vignette": vignette,
            "questions": questions}


def item_derivatives(day=None) -> dict:
    from vittantra_pricing import black_scholes_price

    rng = _rng("deriv", day)
    prices = _csv("day75_live_instrument_prices.csv", "vittantra_data_hub.py").set_index("symbol")
    spot = float(prices.loc["AAPL", "price"])
    strike = round(spot / 5) * 5
    rate, vol, years = 0.04, 0.28, 0.5
    call = black_scholes_price(spot, strike, years, rate, vol, "call")
    put = call - spot + strike * math.exp(-rate * years)
    vignette = (f"Jon Reyes, a derivatives analyst, prices six-month European options on Apple. Apple trades at "
                f"${spot:.2f} (Vittantra live price). An at-the-money strike of ${strike:.0f} is used, the "
                f"continuously compounded risk-free rate is {rate:.0%}, and implied volatility is {vol:.0%} "
                f"(assumptions for the case). The Black-Scholes call value is ${call:.2f}.")
    questions = [
        _question("Using put-call parity, the value of the European put with the same strike and expiry is closest to:",
                  f"${put:.2f}", [f"${call + spot - strike:.2f}", f"${call - spot + strike:.2f}"],
                  f"P = C − S + K·e^(−rT) = {call:.2f} − {spot:.2f} + {strike:.0f}×e^(−0.04×0.5) = {put:.2f}. "
                  "Forgetting to discount the strike gives the third option.", rng),
        _question("If implied volatility rises and everything else is unchanged, the call value will most likely:",
                  "increase", ["decrease", "stay unchanged"],
                  "Vega is positive for both calls and puts: more uncertainty raises the value of optionality.", rng),
        _question("An at-the-money call's delta is closest to:",
                  "about 0.5 to 0.6", ["about 0.0", "exactly 1.0"],
                  "N(d1) for an at-the-money option is slightly above 0.5 because of the drift term (r + σ²/2).", rng),
    ]
    return {"topic": "Derivatives", "title": "Option valuation and parity", "vignette": vignette,
            "questions": questions}


def item_portfolio_risk(day=None) -> dict:
    from var_validation import kupiec_pof_test

    rng = _rng("pmrisk", day)
    v = live._var_summary()
    row95 = next(r for r in v["rows"] if r["Confidence"] == "95%")
    breaches = 20
    kupiec = kupiec_pof_test(breaches, 250, 0.95)
    vignette = (f"The risk team reports a one-day 95% historical VaR of {money(row95['Historical VaR ($)'])} and an "
                f"Expected Shortfall of {money(row95['Expected Shortfall ($)'])} for a {money(v['value'])} portfolio. "
                f"In a backtest over 250 days, the portfolio's losses exceeded VaR on {breaches} days.")
    questions = [
        _question("Which statement about the VaR figure is most accurate?",
                  "On about 5% of days, losses are expected to exceed the VaR amount",
                  ["The maximum possible one-day loss is the VaR amount",
                   "Losses will exceed VaR on 95% of days"],
                  "VaR is a loss threshold at a confidence level, not a maximum loss. ES describes the average beyond it.",
                  rng),
        _question("Using the Kupiec proportion-of-failures test at the 5% level, the analyst should:",
                  "reject the model" if kupiec["Reject at 5%"] else "not reject the model",
                  ["not reject the model" if kupiec["Reject at 5%"] else "reject the model",
                   "conclude nothing without the Christoffersen test"],
                  f"Expected breaches = 12.5. LR = {kupiec['Kupiec LR Statistic']:.2f}, p = {kupiec['P-Value']:.3f}; "
                  f"{'p < 0.05 → reject' if kupiec['Reject at 5%'] else 'p ≥ 0.05 → do not reject'}.", rng),
        _question("Compared with VaR at the same confidence level, Expected Shortfall is:",
                  "greater than or equal to VaR", ["always smaller than VaR", "identical to VaR"],
                  "ES averages the losses beyond VaR, so it cannot be smaller than VaR.", rng),
    ]
    return {"topic": "Portfolio Management", "title": "Measuring and backtesting market risk",
            "vignette": vignette, "questions": questions}


def item_economics_fx(day=None) -> dict:
    rng = _rng("fx", day)
    carry = _csv("day76c_fx_carry.csv", "multi_asset_universe.py").set_index("pair")
    assets = _csv("day76c_asset_analytics.csv", "multi_asset_universe.py").set_index("symbol")
    spot = float(assets.loc["USDJPY=X", "price"])
    r_usd = float(carry.loc["USD/JPY", "base_rate_pct"]) / 100
    r_jpy = float(carry.loc["USD/JPY", "quote_rate_pct"]) / 100
    forward = spot * (1 + r_jpy) / (1 + r_usd)
    vignette = (f"An economist examines USD/JPY (yen per dollar), quoted at {spot:.2f}. One-year interest rates are "
                f"{r_usd:.2%} in the US and {r_jpy:.2%} in Japan (OECD 3-month rates via Vittantra, used as "
                "one-year rates for the case).")
    questions = [
        _question("Using covered interest rate parity, the one-year forward USD/JPY rate is closest to:",
                  f"{forward:.2f}", [f"{spot * (1 + r_usd) / (1 + r_jpy):.2f}", f"{spot:.2f}"],
                  f"F = S × (1 + i_JPY)/(1 + i_USD) = {spot:.2f} × {1 + r_jpy:.4f}/{1 + r_usd:.4f} = {forward:.2f}. "
                  "The price currency's rate goes in the numerator.", rng),
        _question("Relative to the spot rate, the US dollar trades in the forward market at a:",
                  "forward discount" if forward < spot else "forward premium",
                  ["forward premium" if forward < spot else "forward discount", "neither premium nor discount"],
                  "The higher-yielding currency trades at a forward discount, offsetting its interest advantage.", rng),
        _question("A carry trader borrows yen and invests in dollars for one year. If the spot rate is unchanged, the "
                  "return is approximately:",
                  f"{r_usd - r_jpy:.2%}", [f"{r_jpy - r_usd:.2%}", "0%"],
                  "With no currency move, the carry trade earns the interest differential i_USD − i_JPY.", rng),
    ]
    return {"topic": "Economics", "title": "Currency exchange rates and parity", "vignette": vignette,
            "questions": questions}


def item_equity(day=None) -> dict:
    rng = _rng("equity", day)
    m = _csv("day76_fundamental_metrics.csv", "fundamental_engine.py").set_index("ticker")
    m = m.dropna(subset=["market_cap", "total_debt", "cash", "operating_income_ttm", "net_income_ttm",
                         "revenue_ttm", "equity", "equity_to_assets"])
    m = m[(m["equity"] > 0) & (m["sector"] != "Financials")]
    ticker = rng.choice(sorted(m.index))
    r = m.loc[ticker]
    ev = r["market_cap"] + r["total_debt"] - r["cash"]
    assets = r["equity"] / r["equity_to_assets"]
    margin, turnover, leverage = r["net_income_ttm"] / r["revenue_ttm"], r["revenue_ttm"] / assets, assets / r["equity"]
    roe = margin * turnover * leverage
    vignette = (f"An equity analyst reviews {r['name']} ({ticker}) using Vittantra's SEC data: market cap "
                f"{money(r['market_cap'])}, total debt {money(r['total_debt'])}, cash {money(r['cash'])}, TTM revenue "
                f"{money(r['revenue_ttm'])}, operating income (EBIT) {money(r['operating_income_ttm'])}, net income "
                f"{money(r['net_income_ttm'])}, total assets {money(assets)} and equity {money(r['equity'])}.")
    questions = [
        _question("The company's EV/EBIT multiple is closest to:",
                  f"{ev / r['operating_income_ttm']:.1f}x",
                  [f"{r['market_cap'] / r['operating_income_ttm']:.1f}x",
                   f"{(r['market_cap'] + r['total_debt']) / r['operating_income_ttm']:.1f}x"],
                  f"EV = market cap + debt − cash = {money(ev)}; EV/EBIT = {ev / r['operating_income_ttm']:.1f}x. "
                  "Using market cap alone ignores debt holders; forgetting cash overstates EV.", rng),
        _question("Using a three-part DuPont decomposition, return on equity is closest to:",
                  f"{roe:.1%}", [f"{margin * turnover:.1%}", f"{margin * leverage:.1%}"],
                  f"ROE = net margin {margin:.1%} × asset turnover {turnover:.2f} × leverage {leverage:.2f} = {roe:.1%}. "
                  "Margin × turnover alone is ROA.", rng),
        _question("Ranking stocks by earnings yield (E/P) rather than P/E is preferred mainly because it:",
                  "handles negative earnings in a meaningful order",
                  ["always produces higher values", "removes the effect of leverage"],
                  "P/E becomes meaningless with losses; E/P keeps a monotonic ranking.", rng),
    ]
    return {"topic": "Equity Valuation", "title": f"Valuation and DuPont: {ticker}", "vignette": vignette,
            "questions": questions}


def item_quant(day=None) -> dict:
    rng = _rng("quant", day)
    s = _csv("day58_factor_regression_summary.csv", "ml_factor_attribution.py").set_index("metric")["value"]
    n = int(float(s["observations"]))
    k = sum(1 for idx in s.index if str(idx).startswith("beta_"))
    r2 = float(s["r_squared"])
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    t = float(s["alpha_t_statistic"])
    vignette = (f"A quantitative analyst regresses a strategy's period returns on {k} factor returns using {n} "
                f"observations (Vittantra Day 58). The intercept (alpha) has a t-statistic of {t:.2f}, and the "
                f"regression R² is {r2:.2f}.")
    questions = [
        _question("At the 5% significance level (two-tailed critical value ≈ 2.0), the analyst should conclude "
                  "that alpha is:",
                  "not statistically different from zero" if abs(t) < 2 else "statistically different from zero",
                  ["statistically different from zero" if abs(t) < 2 else "not statistically different from zero",
                   "significant because it is positive"],
                  f"|t| = {abs(t):.2f} {'<' if abs(t) < 2 else '>'} 2.0.", rng),
        _question("The adjusted R² is closest to:",
                  f"{adj:.2f}", [f"{r2:.2f}", f"{1 - (1 - r2) * n / (n - k):.2f}"],
                  f"Adjusted R² = 1 − (1 − R²)(n − 1)/(n − k − 1) = 1 − (1 − {r2:.2f})×{n - 1}/{n - k - 1} = {adj:.2f}.",
                  rng),
        _question("A large gap between R² and adjusted R² most likely indicates:",
                  "too many independent variables relative to observations",
                  ["heteroskedasticity in the residuals", "perfect multicollinearity"],
                  "Adjusted R² penalizes adding regressors; with few observations, extra factors inflate R².", rng),
    ]
    return {"topic": "Quantitative Methods", "title": "Multiple regression and significance", "vignette": vignette,
            "questions": questions}


def item_real_estate(day=None) -> dict:
    rng = _rng("re", day)
    curve = _csv("day76c_yield_curve.csv", "multi_asset_universe.py").set_index("maturity")
    assets = _csv("day76c_asset_analytics.csv", "multi_asset_universe.py").set_index("symbol")
    ten = float(curve.loc["10Y", "yield_pct"]) / 100
    premium, noi = 0.035, 12_000_000
    cap = ten + premium
    value = noi / cap
    value_up = noi / (cap + 0.005)
    hotel_12m = assets["return_12m"].get("HST")
    vignette = (f"A real estate analyst values a select-service hotel with net operating income (NOI) of "
                f"{money(noi)} (illustrative). Hotel cap rates are assumed to equal the 10-year Treasury yield "
                f"({ten:.2%}, live) plus a {premium:.1%} risk premium. Host Hotels' 12-month return was "
                f"{pct(hotel_12m)} (Vittantra).")
    questions = [
        _question("Using direct capitalization, the hotel's value is closest to:",
                  money(value), [money(noi / ten), money(noi * cap * 100)],
                  f"Value = NOI / cap rate = {money(noi)} / {cap:.2%} = {money(value)}. Using the Treasury yield "
                  "alone ignores the property risk premium.", rng),
        _question("If Treasury yields rise 50 bp and the premium is unchanged, the hotel's value changes by about:",
                  f"{value_up / value - 1:.1%}", [f"{-0.005:.1%}", f"{value / value_up - 1:+.1%}"],
                  f"New value = NOI/({cap:.2%} + 0.50%) → change = {value_up / value - 1:.1%}. Property values are "
                  "very sensitive to cap rates.", rng),
        _question("Compared with a net-lease property, hotel NOI is typically:",
                  "more volatile, because room rates reset daily and operating costs are high",
                  ["less volatile, because hotels sign long leases", "unaffected by the economic cycle"],
                  "Hotels have very short 'leases' (nightly) and high operating leverage, so NOI swings with "
                  "travel demand.", rng),
    ]
    return {"topic": "Alternative Investments", "title": "Commercial real estate: hotels and cap rates",
            "vignette": vignette, "questions": questions}


def item_macro(day=None) -> dict:
    rng = _rng("macro", day)
    b = _csv("day76d_macro_betas.csv", "macro_drivers.py").set_index("symbol")
    tlt = float(b.loc["TLT", "beta_interest_rates"])   # decimal return per +1pp
    candidates = [s for s in ("EURUSD=X", "GC=F", "SPY") if s in b.index and "beta_us_dollar" in b.columns]
    dollar = {s: b.loc[s, "beta_us_dollar"] for s in candidates if pd.notna(b.loc[s, "beta_us_dollar"])}
    most = min(dollar, key=dollar.get) if dollar else "EURUSD=X"
    vignette = (f"A macro strategist estimates factor sensitivities from one year of daily data (Vittantra macro "
                f"drivers). The long-Treasury ETF's beta to the 10-year yield is {tlt:+.1%} per percentage point. "
                "Dollar betas: " + ", ".join(f"{s} {v:.2f}" for s, v in dollar.items()) + ".")
    questions = [
        _question("If the 10-year yield rises 0.50 percentage points, the expected move in the Treasury ETF is "
                  "closest to:",
                  f"{tlt * 0.5:.1%}", [f"{-tlt * 0.5:.1%}", "0.0%"],
                  f"Expected return ≈ β × Δy = {tlt:+.1%} × 0.5 = {tlt * 0.5:.1%}. The rate beta behaves like "
                  f"(negative) duration: an implied duration of about {-tlt * 100:.0f}.", rng),
        _question("Which instrument is most negatively exposed to a stronger US dollar?",
                  most, [s for s in dollar if s != most][:2] or ["SPY", "GC=F"],
                  "The most negative dollar beta falls the most when the dollar index rises.", rng),
        _question("A low R² in an asset's macro regression most likely means:",
                  "most of its moves come from factors not in the model or asset-specific news",
                  ["the betas must be zero", "the asset has no risk"],
                  "R² is the share of variance explained by the factors; the rest is idiosyncratic.", rng),
    ]
    return {"topic": "Economics", "title": "Macro factor sensitivities", "vignette": vignette,
            "questions": questions}


def item_equity_valuation(day=None) -> dict:
    rng = _rng("equity_valuation", day)
    v = _csv("day78_valuation.csv", "valuation_engine.py").dropna(
        subset=["dcf_value", "fcff_ttm", "wacc", "terminal_growth", "risk_free", "beta_adjusted"])
    if v.empty:
        raise MissingData("No DCF valuations yet.")
    r = v.set_index("ticker").loc[rng.choice(sorted(v["ticker"]))]
    erp = (r["cost_of_equity"] - r["risk_free"]) / r["beta_adjusted"]
    g, w, f = r["terminal_growth"], r["wacc"], r["fcff_ttm"]
    single = f * (1 + g) / (w - g)
    vignette = (f"An analyst values {r['name']} with Vittantra's inputs: trailing free cash flow to the firm "
                f"{money(f)}, WACC {w:.2%}, long-run growth {g:.2%}, 10-year Treasury yield {r['risk_free']:.2%}, "
                f"adjusted beta {r['beta_adjusted']:.2f} and an equity risk premium of {erp:.1%}.")
    questions = [
        _question("The cost of equity using CAPM is closest to:",
                  f"{r['cost_of_equity']:.2%}",
                  [f"{r['beta_adjusted'] * erp:.2%}", f"{r['risk_free'] + r['beta_adjusted'] * (erp - r['risk_free']):.2%}",
                   f"{w:.2%}", f"{r['risk_free'] * r['beta_adjusted']:.2%}"],
                  f"r_e = r_f + β × ERP = {r['risk_free']:.2%} + {r['beta_adjusted']:.2f} × {erp:.1%} = "
                  f"{r['cost_of_equity']:.2%}. Forgetting r_f gives β × ERP; subtracting r_f again treats the "
                  "premium as the market return; the WACC is the firm's rate, not the equity rate.", rng),
        _question("If FCFF grew at the long-run rate from today (single-stage model), firm value would be closest to:",
                  f"${single / 1e9:,.0f}B", [f"${f * (1 + g) / w / 1e9:,.0f}B", f"${f / (w + g) / 1e9:,.0f}B",
                                             f"${f / w / 1e9:,.0f}B"],
                  f"V = FCFF_0 × (1 + g) / (WACC − g) = {money(f)} × {1 + g:.4f} / ({w:.2%} − {g:.2%}) = "
                  f"${single / 1e9:,.0f}B. Growth is subtracted in the denominator; leaving it out treats the "
                  "cash flow as flat.", rng),
        _question("In a residual income model, if a company's ROE equals its cost of equity forever, its value is:",
                  "equal to its current book value",
                  ["zero", "equal to its dividends divided by the cost of equity"],
                  "Residual income = (ROE − r) × book = 0, so V_0 = B_0: the firm earns exactly what investors "
                  "require, so it is worth what has been invested.", rng),
        _question(f"A reverse DCF shows the price implies {r['implied_growth']:.1%} growth a year for five years. "
                  "An analyst forecasting lower growth would most likely conclude the stock is:",
                  "overvalued relative to the analyst's forecast",
                  ["undervalued relative to the analyst's forecast", "fairly valued, since price equals DCF value"],
                  "The price already assumes the implied growth; lower expected growth means a lower value than "
                  "the price.", rng) if pd.notna(r.get("implied_growth")) else
        _question("The terminal value in a DCF is most sensitive to:",
                  "the spread between WACC and long-run growth",
                  ["the first year's cash flow only", "the number of shares outstanding"],
                  "TV = CF(1+g)/(WACC − g): as WACC − g narrows, value rises sharply.", rng),
    ]
    return {"topic": "Equity Valuation", "title": f"Free cash flow and residual income: {r['name']}",
            "vignette": vignette, "questions": questions}


def item_news_surprise(day=None) -> dict:
    rng = _rng("news_surprise", day)
    dash = _csv("day76c_economic_dashboard.csv", "multi_asset_universe.py").set_index("series_id")
    betas = _csv("day76d_macro_betas.csv", "macro_drivers.py").set_index("symbol")
    cpi, core = dash.loc["CPIAUCSL"], dash.loc["CPILFESL"]
    fed = dash.loc["FEDFUNDS"]
    tlt = float(betas.loc["TLT", "beta_interest_rates"])
    move = 0.15                                  # assumed yield reaction to the surprise, pp
    vignette = (f"Headline CPI inflation is {cpi['latest']:.1f}% year on year (previous {cpi['previous']:.1f}%), core "
                f"CPI {core['latest']:.1f}%, and the effective fed funds rate {fed['latest']:.2f}%. The next CPI "
                f"release comes in 0.3 percentage points above consensus and the 10-year yield rises {move * 100:.0f} bp "
                f"on the day. Vittantra estimates the long-Treasury ETF loses {-tlt:.1%} per +1pp of 10-year yield.")
    real = fed["latest"] - cpi["latest"]
    questions = [
        _question("The market reaction is driven mainly by:",
                  "the difference between actual and expected inflation",
                  ["the level of inflation alone", "the previous month's inflation"],
                  "Prices already reflect consensus; only the surprise is new information.", rng),
        _question("The expected one-day move in the long-Treasury ETF is closest to:",
                  f"{tlt * move:.1%}", [f"{-tlt * move:.1%}", f"{tlt * move * 10:.1%}", "0.0%"],
                  f"β × Δy = {tlt:+.1%} × {move:.2f} = {tlt * move:.1%}; rising yields mean falling bond prices.", rng),
        _question("Using headline CPI, the real policy rate (fed funds minus inflation) is closest to:",
                  f"{real:+.2f}%", [f"{fed['latest'] + cpi['latest']:+.2f}%", f"{-real:+.2f}%"],
                  f"{fed['latest']:.2f}% − {cpi['latest']:.2f}% = {real:+.2f}%. A positive real rate is restrictive; "
                  "a negative one is accommodative (a Taylor-rule style comparison).", rng),
    ]
    return {"topic": "Economics", "title": "Reading an inflation surprise", "vignette": vignette,
            "questions": questions}


def item_active_management(day=None) -> dict:
    rng = _rng("active_management", day)
    s = _csv("day79_portfolio_summary.csv", "portfolio_construction.py").iloc[0]
    p = _csv("day79_model_portfolio.csv", "portfolio_construction.py")
    a = _csv("day80_attribution_summary.csv", "performance_attribution.py").iloc[0]
    r = p[p["weight"] > 0].set_index("ticker").loc[rng.choice(sorted(p[p["weight"] > 0]["ticker"]))]
    ic, te, ir = float(s["signal_ic"]), float(s["tracking_error"]), float(s["information_ratio"])
    breadth = 33 * 12.6
    vignette = (f"A PM's model portfolio has a signal IC of {ic:.3f}, tracking error {te:.1%} and expected active "
                f"return {s['expected_active_return']:.1%}. {r['name']} has annual volatility {r['volatility']:.0%} "
                f"and an IC-weighted score of {r['score']:.0f}. Over {a['start']} to {a['end']} the backtested "
                f"portfolio's active return of {a['active_cumulative']:.1%} split into allocation "
                f"{a['allocation_linked']:.1%}, selection {a['selection_linked']:.1%}, interaction "
                f"{a['interaction_linked']:.1%} and costs {a['costs_linked']:.1%}.")
    questions = [
        _question("The ex-ante information ratio is closest to:", f"{ir:.2f}",
                  [f"{s['expected_active_return'] / s['portfolio_volatility']:.2f}", f"{ic * breadth ** 0.5:.2f}",
                   f"{te / s['expected_active_return']:.2f}"],
                  f"IR = expected active return / tracking error = {s['expected_active_return']:.2%} / {te:.2%} = "
                  f"{ir:.2f}. Dividing by total volatility gives a Sharpe-like ratio, not the IR.", rng),
        _question("By the fundamental law of active management, with 33 stocks rebalanced 12.6 times a year the "
                  "maximum IR is closest to:", f"{ic * breadth ** 0.5:.2f}", [f"{ic * 33 ** 0.5:.2f}", f"{ic * breadth:.1f}"],
                  f"IR ≈ IC × √breadth = {ic:.3f} × √{breadth:.0f} = {ic * breadth ** 0.5:.2f} (an upper bound; the "
                  "transfer coefficient is below 1 when constraints bind).", rng),
        _question("In the attribution, the selection effect measures:",
                  "the return from choosing better stocks within each sector",
                  ["the return from overweighting sectors that beat the benchmark",
                   "the return lost to trading costs"],
                  "Selection = benchmark sector weight × (portfolio sector return − benchmark sector return).", rng),
    ]
    return {"topic": "Portfolio Management", "title": "Active management: IR, breadth and attribution",
            "vignette": vignette, "questions": questions}


ITEM_SETS: Dict[str, Callable] = {
    "fixed_income": item_fixed_income, "derivatives": item_derivatives,
    "portfolio_risk": item_portfolio_risk, "economics_fx": item_economics_fx,
    "equity": item_equity, "quant": item_quant, "real_estate": item_real_estate, "macro": item_macro,
    "equity_valuation": item_equity_valuation, "news_surprise": item_news_surprise,
    "active_management": item_active_management,
}

DESK_ITEM_SETS = {
    "investment_analyst": ["news_surprise", "macro", "economics_fx"],
    "equity_researcher": ["equity_valuation", "equity", "quant"],
    "portfolio_analyst": ["portfolio_risk", "fixed_income"],
    "portfolio_manager": ["active_management", "quant", "derivatives"],
    "advisor": ["real_estate", "portfolio_risk"],
}


def todays_item_set(role: str, day: Optional[date] = None) -> Optional[dict]:
    """One item set for the desk, rotating daily; skips sets whose data is missing."""
    keys = DESK_ITEM_SETS[role]
    start = (day or date.today()).toordinal() % len(keys)
    for key in keys[start:] + keys[:start]:
        try:
            return {"key": key, **ITEM_SETS[key](day)}
        except (MissingData, KeyError, ValueError, IndexError, StopIteration):
            continue
    return None


def grade(item: dict, choices: List[Optional[int]]) -> tuple:
    correct = sum(c == q["answer"] for c, q in zip(choices, item["questions"]))
    return 100 * correct / len(item["questions"]), correct


def record_cfa(progress: dict, topic: str, correct: int, total: int) -> dict:
    stats = progress.setdefault("cfa", {}).setdefault(topic, {"answered": 0, "correct": 0})
    stats["answered"] += total
    stats["correct"] += correct
    return progress
