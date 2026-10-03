"""
Day 78 — Valuation Engine (intrinsic value, CFA Level II equity framework)

Three models, all built from the Day 76 point-in-time SEC fundamentals:

1. FCFF discounted cash flow (non-financial companies)
       FCFF_0 = CFO + interest × (1 − t) − capex
       Three stages: recent revenue growth for 5 years, a linear fade to the
       terminal rate over the next 5, then a Gordon terminal value; all
       discounted at the WACC.
       Equity = enterprise value − debt + cash.

2. Residual income (all companies; the standard model for banks)
       V_0 = B_0 + Σ (ROE_t − r_e) × B_{t−1} / (1 + r_e)^t
       ROE fades from today's level to the cost of equity over ten years
       (competition erodes excess returns), clean-surplus book growth.

3. Dividend discount (dividend payers)
       D_0 = dividends paid ÷ shares; growth starts at the sustainable rate
       b × ROE and fades to the terminal rate; discounted at the cost of equity.

The fair value is the primary model for the business type (banks and
insurers: residual income; dividend-paying utilities and REITs: dividend
discount; other companies: DCF). The other models are cross-checks.

Discount rates:
    r_e  = r_f + β_adj × ERP          (CAPM, Blume-adjusted beta)
    r_d  = r_f + credit spread of the synthetic rating implied by interest
           coverage (ICE BofA spreads by rating from FRED)
    WACC = E/V × r_e + D/V × r_d × (1 − t)

r_f is the 10-year Treasury yield (Day 76c). Every assumption is written to
day78_valuation_assumptions.csv, and a reverse DCF reports the growth rate the
current price implies.

Outputs
-------
day78_valuation.csv               one row per stock: models, fair value, upside
day78_dcf_sensitivity.csv         DCF value per share across WACC × terminal growth
day78_valuation_assumptions.csv   every assumption and its source
day78_validation_summary.csv

Intrinsic values are model estimates under stated assumptions, not price
targets. No trades are submitted or executed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from vittantra_pricing import (  # noqa: I001
    blume_adjusted_beta,
    capm_cost_of_equity,
    fading_growth_path,
    residual_income_value,
    sustainable_growth,
    two_stage_value,
    wacc,
)


BASE_DIR = Path(__file__).resolve().parent

METRICS_FILE = "day76_fundamental_metrics.csv"
RATINGS_FILE = "day77_current_ratings.csv"
CURVE_FILE = "day76c_yield_curve.csv"
CREDIT_FILE = "day76c_credit_spreads.csv"

OUTPUT_VALUATION = "day78_valuation.csv"
OUTPUT_SENSITIVITY = "day78_dcf_sensitivity.csv"
OUTPUT_ASSUMPTIONS = "day78_valuation_assumptions.csv"
OUTPUT_VALIDATION = "day78_validation_summary.csv"

ASSUMPTIONS = {
    "equity_risk_premium": 0.045,    # close to recent implied US equity premium estimates; review yearly
    "tax_rate": 0.21,                # US federal statutory rate
    "high_growth_years": 5,          # stage 1: recent growth continues
    "fade_years": 5,                 # stage 2: growth fades linearly to the terminal rate
    "ri_fade_years": 10,             # years for ROE to fade to the cost of equity
    "max_initial_growth": 0.20,
    "max_cyclical_growth": 0.05,     # energy/materials: recent growth mostly reflects commodity prices
    "min_initial_growth": -0.05,
    "max_terminal_growth": 0.03,     # long-run nominal growth cap (≤ r_f as well)
    "default_retention": 0.5,        # used only when dividends are not reported
    "default_risk_free": 0.0425,     # used only when the yield curve file is missing
    "fair_value_band": 0.15,         # ±15% = "fairly valued"
}

# Interest coverage → synthetic rating (large non-financial firms; Damodaran-style)
COVERAGE_RATINGS = [(8.5, "AAA"), (6.5, "AA"), (4.25, "A"), (3.0, "BBB"), (2.0, "BB"),
                    (1.25, "B"), (-np.inf, "CCC & below")]
DEFAULT_SPREADS_BP = {"AAA": 50, "AA": 65, "A": 85, "BBB": 120, "BB": 220, "B": 350, "CCC & below": 900}

FINANCIALS = "Financials"
REAL_ESTATE = "Real Estate"
CYCLICAL_SECTORS = {"Energy", "Materials"}


# ==============================================================
# MARKET INPUTS
# ==============================================================

def market_inputs(base: Path = BASE_DIR) -> Dict[str, object]:
    """Risk-free rate (10Y Treasury) and credit spreads by rating, with sources."""
    out = {"risk_free": ASSUMPTIONS["default_risk_free"], "risk_free_source": "assumption (no yield curve file)",
           "spreads_bp": dict(DEFAULT_SPREADS_BP), "spread_source": "assumption (no credit spread file)"}
    curve_path, credit_path = base / CURVE_FILE, base / CREDIT_FILE
    if curve_path.exists():
        curve = pd.read_csv(curve_path)
        ten = curve[curve["maturity"] == "10Y"]
        if len(ten) and pd.notna(ten["yield_pct"].iloc[0]):
            out["risk_free"] = float(ten["yield_pct"].iloc[0]) / 100
            out["risk_free_source"] = f"10Y Treasury (FRED DGS10) on {ten['date'].iloc[0]}"
    if credit_path.exists():
        credit = pd.read_csv(credit_path).set_index("segment")["spread_bp"]
        found = {r: float(credit[r]) for r in DEFAULT_SPREADS_BP if r in credit.index and pd.notna(credit[r])}
        if found:
            out["spreads_bp"].update(found)
            out["spread_source"] = "ICE BofA option-adjusted spreads by rating (FRED)"
    return out


def synthetic_rating(interest_coverage) -> Optional[str]:
    if interest_coverage is None or pd.isna(interest_coverage):
        return None
    return next(rating for floor, rating in COVERAGE_RATINGS if interest_coverage >= floor)


def _num(row, key) -> Optional[float]:
    value = row.get(key)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(value) else value


# ==============================================================
# MODELS
# ==============================================================

def three_stage_path(initial_growth: float, terminal_growth: float) -> list:
    """Stage 1: initial growth for 5 years; stage 2: linear fade to terminal over 5 years."""
    a = ASSUMPTIONS
    fade = fading_growth_path(initial_growth, terminal_growth, a["fade_years"] + 1)[1:]
    return [initial_growth] * a["high_growth_years"] + fade


def primary_model(sector: Optional[str], has_dividends: bool) -> list:
    """Model preference by business type (CFA: match the model to the company)."""
    if sector == FINANCIALS:
        return ["ri_value", "ddm_value"]            # debt is raw material; book value is meaningful
    if sector in ("Utilities", REAL_ESTATE) and has_dividends:
        return ["ddm_value", "dcf_value", "ri_value"]   # regulated / high-payout, stable dividends
    return ["dcf_value", "ri_value", "ddm_value"]

def dcf_per_share(fcff0: float, initial_growth: float, terminal_growth: float, discount: float,
                  debt: float, cash: float, shares: float) -> Optional[dict]:
    if discount <= terminal_growth + 0.01:
        return None
    result = two_stage_value(fcff0, discount, three_stage_path(initial_growth, terminal_growth),
                             terminal_growth)
    equity = result["value"] - debt + cash
    if equity <= 0:
        return None
    return {**result, "equity_value": equity, "per_share": equity / shares}


def implied_growth(price: float, fcff0: float, terminal_growth: float, discount: float,
                   debt: float, cash: float, shares: float) -> Optional[float]:
    """Reverse DCF: initial growth (fading to terminal) at which DCF value = price (bisection)."""
    def gap(g):
        value = dcf_per_share(fcff0, g, terminal_growth, discount, debt, cash, shares)
        equity_floor = -debt + cash  # value with no operations
        per_share = value["per_share"] if value else min(equity_floor / shares, 0.0)
        return per_share - price

    low, high = -0.5, 1.5
    if gap(low) > 0 or gap(high) < 0:
        return None
    for _ in range(80):
        mid = (low + high) / 2
        if gap(mid) > 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def value_company(row: dict, beta_raw: Optional[float], market: dict) -> Dict[str, object]:
    a = ASSUMPTIONS
    rf = market["risk_free"]
    terminal = min(a["max_terminal_growth"], rf)
    price, shares = _num(row, "price"), _num(row, "shares_outstanding")
    out: Dict[str, object] = {"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"),
                              "price": price, "notes": []}
    notes = out["notes"]
    if not price or not shares:
        notes.append("price or shares missing: not valued")
        return out

    beta_known = beta_raw is not None and np.isfinite(beta_raw)
    beta = blume_adjusted_beta(beta_raw) if beta_known else 1.0
    if not beta_known:
        notes.append("beta unavailable: market beta 1.0 assumed")
    cost_of_equity = capm_cost_of_equity(rf, beta, a["equity_risk_premium"])
    out.update({"beta_raw": beta_raw if beta_known else None, "beta_adjusted": beta,
                "risk_free": rf, "cost_of_equity": cost_of_equity, "terminal_growth": terminal})

    market_cap = price * shares
    debt = _num(row, "total_debt") or 0.0
    cash = _num(row, "cash") or 0.0
    coverage = _num(row, "interest_coverage")
    rating = synthetic_rating(coverage)
    if rating is None:
        rating = "BBB"
        notes.append("interest coverage unavailable: BBB credit spread assumed")
    cost_of_debt = rf + market["spreads_bp"][rating] / 10_000
    discount = wacc(market_cap, debt, cost_of_equity, cost_of_debt, a["tax_rate"])
    out.update({"synthetic_rating": rating, "cost_of_debt": cost_of_debt, "wacc": discount,
                "debt_weight": debt / (market_cap + debt)})

    revenue_growth = _num(row, "revenue_growth")
    initial = float(np.clip(revenue_growth, a["min_initial_growth"], a["max_initial_growth"])) \
        if revenue_growth is not None else terminal
    if row.get("sector") in CYCLICAL_SECTORS and initial > a["max_cyclical_growth"]:
        initial = a["max_cyclical_growth"]
        notes.append("cyclical sector: growth capped at 5%, because recent growth mostly reflects commodity "
                     "prices (professionals value cyclicals on mid-cycle earnings)")
    roe = _num(row, "roe")
    net_income = _num(row, "net_income_ttm")
    dividends = _num(row, "dividends_ttm")
    if dividends is not None and net_income and net_income > 0:
        retention = float(np.clip(1 - dividends / net_income, 0.0, 1.0))
        out["retention_source"] = "1 − dividends / net income"
    else:
        retention = a["default_retention"]
        out["retention_source"] = "assumption"
    out["retention"] = retention
    sector = row.get("sector")

    # 1. FCFF DCF (not meaningful for banks and insurers)
    if sector == FINANCIALS:
        notes.append("financial company: DCF not used (debt is operating, not financing); residual income preferred")
    else:
        cfo, capex, interest = (_num(row, k) for k in ("operating_cash_flow_ttm", "capex_ttm", "interest_expense_ttm"))
        if cfo is not None and capex is not None:
            fcff0 = cfo + (interest or 0.0) * (1 - a["tax_rate"]) - capex
            out["fcff_source"] = "CFO + interest × (1 − t) − capex"
        else:
            fcff0 = _num(row, "free_cash_flow_ttm")
            out["fcff_source"] = "free cash flow (CFO − capex); interest add-back unavailable"
        out["fcff_ttm"] = fcff0
        if fcff0 is None or fcff0 <= 0:
            notes.append("free cash flow not positive: DCF not meaningful")
        else:
            dcf = dcf_per_share(fcff0, initial, terminal, discount, debt, cash, shares)
            if dcf:
                out.update({"dcf_value": dcf["per_share"], "dcf_terminal_share": dcf["terminal_share"],
                            "dcf_initial_growth": initial})
                out["implied_growth"] = implied_growth(price, fcff0, terminal, discount, debt, cash, shares)
            else:
                notes.append("DCF equity value not positive")
        if sector == REAL_ESTATE:
            notes.append("REIT: professionals value REITs on FFO/AFFO; DCF on free cash flow is an approximation")

    # 2. Residual income
    book = _num(row, "equity")
    if book and book > 0 and roe is not None:
        roe0 = float(np.clip(roe, -0.2, 0.5))
        path = fading_growth_path(roe0, cost_of_equity, a["ri_fade_years"])
        ri = residual_income_value(book, path, cost_of_equity, retention)
        if ri["value"] > 0:
            out["ri_value"] = ri["value"] / shares
            out["book_value_per_share"] = book / shares
    else:
        notes.append("book equity or ROE unavailable: residual income not used")

    # 3. Dividend discount
    if dividends and dividends > 0 and roe is not None:
        d0 = dividends / shares
        g0 = float(np.clip(sustainable_growth(roe, retention), 0.0, 0.10))
        if cost_of_equity > terminal + 0.01:
            ddm = two_stage_value(d0, cost_of_equity, three_stage_path(g0, terminal), terminal)
            out.update({"ddm_value": ddm["value"], "dividend_per_share": d0, "ddm_initial_growth": g0})

    models = {k: out.get(k) for k in ("dcf_value", "ri_value", "ddm_value") if out.get(k) is not None}
    if models:
        preference = primary_model(sector, bool(dividends and dividends > 0))
        primary = next(k for k in preference + list(models) if k in models)
        fair = float(models[primary])
        upside = fair / price - 1
        band = a["fair_value_band"]
        out.update({
            "primary_model": primary.replace("_value", "").upper(),
            "models_used": ", ".join(k.replace("_value", "").upper() for k in models),
            "fair_value": fair, "upside": upside,
            "cross_check_median": float(np.median(list(models.values()))),
            "model_dispersion": (max(models.values()) - min(models.values())) / fair if len(models) > 1 else 0.0,
            "valuation_signal": ("Undervalued" if upside > band else "Overvalued" if upside < -band
                                 else "Fairly valued"),
        })
        if primary == "dcf_value" and "ri_value" in models and models["ri_value"] < 0.5 * fair:
            notes.append("residual income well below DCF: RI assumes returns above the cost of equity fade within "
                         "10 years, so it is conservative for high-ROE or buyback-heavy companies")
    return out


def dcf_sensitivity(row: dict, valuation: dict) -> pd.DataFrame:
    """DCF value per share for WACC ±1pp and terminal growth ±0.5pp."""
    if valuation.get("dcf_value") is None:
        return pd.DataFrame()
    rows = []
    shares, debt, cash = _num(row, "shares_outstanding"), _num(row, "total_debt") or 0.0, _num(row, "cash") or 0.0
    for dw in (-0.01, 0.0, 0.01):
        for dg in (-0.005, 0.0, 0.005):
            value = dcf_per_share(valuation["fcff_ttm"], valuation["dcf_initial_growth"],
                                  valuation["terminal_growth"] + dg, valuation["wacc"] + dw,
                                  debt, cash, shares)
            rows.append({"ticker": row["ticker"], "wacc": valuation["wacc"] + dw,
                         "terminal_growth": valuation["terminal_growth"] + dg,
                         "value_per_share": value["per_share"] if value else np.nan})
    return pd.DataFrame(rows)


# ==============================================================
# VALIDATION AND ORCHESTRATION
# ==============================================================

def validate_day78(valuation: pd.DataFrame, metrics: pd.DataFrame, market: dict) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    valued = valuation["fair_value"].notna() if "fair_value" in valuation else pd.Series(False, index=valuation.index)
    add("Stocks with at least one model", valued.mean() >= 0.8, f"{int(valued.sum())} of {len(valuation)}")
    values = valuation.reindex(columns=["dcf_value", "ri_value", "ddm_value", "fair_value"]).apply(
        pd.to_numeric, errors="coerce").stack().dropna().astype(float)
    add("Model values positive and finite", bool(len(values)) and bool(np.isfinite(values).all() and (values > 0).all()),
        f"{len(values)} model values")
    w = valuation["wacc"].dropna() if "wacc" in valuation else pd.Series(dtype=float)
    add("WACC within 4%–15%", len(w) > 0 and w.between(0.04, 0.15).all(),
        f"range {w.min():.1%} – {w.max():.1%}" if len(w) else "none")
    ts = valuation["dcf_terminal_share"].dropna() if "dcf_terminal_share" in valuation else pd.Series(dtype=float)
    add("Terminal value share of DCF plausible (median 40%–90%)", len(ts) == 0 or 0.4 <= ts.median() <= 0.9,
        f"median {ts.median():.0%}" if len(ts) else "no DCFs")
    add("Terminal growth ≤ risk-free rate", (valuation["terminal_growth"].dropna() <= market["risk_free"] + 1e-12).all(),
        f"g ≤ {market['risk_free']:.2%}")
    reverse_ok = True
    for row in valuation.dropna(subset=["implied_growth"]).itertuples() if "implied_growth" in valuation else []:
        m = metrics.loc[row.ticker].to_dict()
        check = dcf_per_share(row.fcff_ttm, row.implied_growth, row.terminal_growth, row.wacc,
                              _num(m, "total_debt") or 0.0, _num(m, "cash") or 0.0, _num(m, "shares_outstanding"))
        reverse_ok &= check is not None and abs(check["per_share"] / row.price - 1) < 0.01
    add("Reverse DCF reproduces the market price", reverse_ok, "value at implied growth = price (±1%)")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def run_valuation(base: Path = BASE_DIR, out_dir: Optional[Path] = None, verbose: bool = True):
    out_dir = Path(out_dir or base)
    metrics_path = base / METRICS_FILE
    if not metrics_path.exists():
        raise SystemExit("Run `python fundamental_engine.py` first (Day 76 fundamentals).")
    metrics = pd.read_csv(metrics_path)
    metrics = metrics[metrics["ticker"].notna()].drop_duplicates("ticker").set_index("ticker", drop=False)
    betas = {}
    ratings_path = base / RATINGS_FILE
    if ratings_path.exists():
        ratings = pd.read_csv(ratings_path)
        if "beta" in ratings:
            betas = dict(zip(ratings["ticker"], pd.to_numeric(ratings["beta"], errors="coerce")))
    market = market_inputs(base)

    rows, grids = [], []
    for ticker, row in metrics.iterrows():
        record = row.to_dict()
        result = value_company(record, betas.get(ticker), market)
        grids.append(dcf_sensitivity(record, result))
        result["notes"] = " | ".join(result["notes"])
        rows.append(result)
    valuation = pd.DataFrame(rows)
    sensitivity = pd.concat([g for g in grids if len(g)], ignore_index=True) if any(len(g) for g in grids) \
        else pd.DataFrame(columns=["ticker", "wacc", "terminal_growth", "value_per_share"])
    valuation["as_of"] = metrics["as_of"].iloc[0] if "as_of" in metrics else None

    assumptions = pd.DataFrame(
        [{"assumption": k, "value": v, "source": "Vittantra policy assumption"} for k, v in ASSUMPTIONS.items()]
        + [{"assumption": "risk_free_rate", "value": market["risk_free"], "source": market["risk_free_source"]}]
        + [{"assumption": f"credit_spread_{r}", "value": s / 10_000, "source": market["spread_source"]}
           for r, s in market["spreads_bp"].items()])
    validation = validate_day78(valuation, metrics, market)

    valuation.to_csv(out_dir / OUTPUT_VALUATION, index=False)
    sensitivity.to_csv(out_dir / OUTPUT_SENSITIVITY, index=False)
    assumptions.to_csv(out_dir / OUTPUT_ASSUMPTIONS, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(valuation, market, validation)
    return valuation, sensitivity, assumptions, validation


def print_report(valuation, market, validation) -> None:
    line = "=" * 100
    pd.set_option("display.width", 220)
    print(line)
    print("VITTANTRA — DAY 78 VALUATION ENGINE (DCF · residual income · dividend discount)")
    print(line)
    print(f"Risk-free: {market['risk_free']:.2%} ({market['risk_free_source']}); "
          f"ERP {ASSUMPTIONS['equity_risk_premium']:.1%}; spreads: {market['spread_source']}")
    columns = ["ticker", "price", "dcf_value", "ri_value", "ddm_value", "primary_model", "fair_value", "upside",
               "dcf_initial_growth", "implied_growth", "wacc", "valuation_signal"]
    view = valuation.reindex(columns=columns).sort_values("upside", ascending=False)
    print(view.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 78 valuation complete. Intrinsic values are model estimates, not price targets.")
    print(line)


if __name__ == "__main__":
    run_valuation()
