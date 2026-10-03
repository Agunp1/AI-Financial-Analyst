"""
Day 76d — Vittantra Macro Drivers

What moved each asset class, and why — the daily/weekly/monthly macro
read-across professionals keep in their heads, made explicit.

Factors (daily, from free data)
-------------------------------
Equity market          S&P 500 ETF return (SPY)
Interest rates         change in the 10-year Treasury yield (percentage points)
Inflation expectations change in 10-year breakeven inflation (percentage points)
Credit spreads         change in the US high-yield spread (percentage points)
US dollar              US Dollar Index return
Oil                    WTI crude futures return

Method
------
For every instrument, regress daily returns on the factor moves over the
last year (multiple OLS with t-statistics):

    R_t = α + Σ_k β_k · ΔF_k,t + ε_t

A rate beta of −17 means the instrument tends to lose ~17% when the 10-year
yield rises 1 percentage point — for a long Treasury fund that is its
duration. Attribution over a window splits the move into Σ β_k × (factor
move over the window) plus an unexplained part (stock-specific news,
factors not modelled).

Inputs: day76c_price_history.csv and day76c_fred_daily_history.csv written
by multi_asset_universe.py.

Usage:  python macro_drivers.py
Research only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ml_factor_attribution import calculate_ols


BASE_DIR = Path(__file__).resolve().parent
PRICE_HISTORY = BASE_DIR / "day76c_price_history.csv"
FRED_HISTORY = BASE_DIR / "day76c_fred_daily_history.csv"
UNIVERSE = BASE_DIR / "day76c_asset_universe.csv"

ESTIMATION_DAYS = 252
WINDOWS = {"1 week": 5, "1 month": 21, "3 months": 63}

FACTORS = {
    "equity_market": ("Equity market", "SPY", "return"),
    "interest_rates": ("Interest rates (10Y yield, pp)", "DGS10", "change"),
    "inflation_expectations": ("Inflation expectations (10Y breakeven, pp)", "T10YIE", "change"),
    "credit_spreads": ("Credit spreads (high yield, pp)", "BAMLH0A0HYM2", "change"),
    "us_dollar": ("US dollar", "DX-Y.NYB", "return"),
    "oil": ("Oil", "CL=F", "return"),
}
# An instrument is not regressed on itself.
SELF_FACTOR = {"SPY": "equity_market", "DX-Y.NYB": "us_dollar", "CL=F": "oil"}

REPRESENTATIVES = [
    ("Equity", "SPY"), ("Equity", "EFA"), ("Equity", "EEM"),
    ("Fixed Income", "TLT"), ("Fixed Income", "IEF"), ("Fixed Income", "TIP"),
    ("Fixed Income", "LQD"), ("Fixed Income", "HYG"),
    ("FX", "EURUSD=X"), ("FX", "USDJPY=X"),
    ("Commodity", "GC=F"), ("Commodity", "CL=F"), ("Commodity", "HG=F"), ("Commodity", "DBC"),
    ("Digital Asset", "BTC-USD"), ("Digital Asset", "ETH-USD"),
    ("Real Estate", "VNQ"), ("Real Estate", "HST"), ("Real Estate", "WH"), ("Real Estate", "BXP"),
    ("Real Estate", "PLD"), ("Real Estate", "EQIX"), ("Real Estate", "BXMT"),
    ("Alternative", "BX"), ("Alternative", "BIZD"), ("Alternative", "DBMF"),
]

OUTPUT_BETAS = "day76d_macro_betas.csv"
OUTPUT_ATTRIBUTION = "day76d_macro_attribution.csv"
OUTPUT_FACTOR_MOVES = "day76d_factor_moves.csv"
OUTPUT_NARRATIVE = "day76d_macro_narrative.csv"
OUTPUT_VALIDATION = "day76d_validation_summary.csv"


# ==============================================================
# DATA
# ==============================================================

def build_daily_frame(prices: pd.DataFrame, fred: pd.DataFrame):
    """Aligned business-day returns (instruments) and factor moves."""
    calendar = pd.DatetimeIndex(fred.dropna(how="all").index)
    if prices.empty or calendar.empty:
        return pd.DataFrame(), pd.DataFrame()
    prices = prices.copy()
    prices.index = pd.DatetimeIndex(prices.index)
    # Crypto trades at weekends: carry the latest price onto business days,
    # so weekend moves are included in Monday's return.
    aligned = prices.reindex(prices.index.union(calendar)).ffill(limit=4).reindex(calendar)
    returns = aligned.pct_change(fill_method=None)
    factors = pd.DataFrame(index=calendar)
    for key, (_, source, kind) in FACTORS.items():
        if kind == "change" and source in fred.columns:
            factors[key] = fred[source].reindex(calendar).ffill(limit=3).diff()
        elif kind == "return" and source in aligned.columns:
            factors[key] = returns[source]
    return returns.iloc[1:], factors.iloc[1:]


# ==============================================================
# REGRESSION AND ATTRIBUTION
# ==============================================================

def macro_betas(y: pd.Series, factors: pd.DataFrame, exclude: Optional[str] = None) -> Optional[dict]:
    usable = [c for c in factors.columns if c != exclude and factors[c].notna().sum() > 60]
    data = pd.concat([y.rename("y"), factors[usable]], axis=1).dropna().tail(ESTIMATION_DAYS)
    if len(data) < 60 or not usable:
        return None
    result = calculate_ols(data["y"], data[usable])
    out = {"observations": result["observations"], "alpha_daily": result["intercept"],
           "r_squared": result["r_squared"]}
    for factor in usable:
        out[f"beta_{factor}"] = result[factor]
        out[f"t_{factor}"] = result[f"{factor}_t_statistic"]
        # Standardized beta: effect of a typical (1 s.d.) daily factor move
        out[f"std_beta_{factor}"] = result[factor] * data[factor].std(ddof=1)
    return out


def attribution(y: pd.Series, factors: pd.DataFrame, betas: dict, days: int) -> dict:
    recent = pd.concat([y.rename("y"), factors], axis=1).dropna(subset=["y"]).tail(days)
    out = {"actual": float(recent["y"].sum())}
    explained = 0.0
    for factor in FACTORS:
        beta = betas.get(f"beta_{factor}")
        if beta is None or factor not in recent.columns:
            continue
        contribution = float(beta * recent[factor].fillna(0).sum())
        out[f"contribution_{factor}"] = contribution
        explained += contribution
    out["alpha"] = float(betas["alpha_daily"] * len(recent))
    out["unexplained"] = out["actual"] - explained - out["alpha"]
    return out


def narrative(name: str, row: dict, r_squared: float, window: str) -> str:
    parts = sorted(((k.replace("contribution_", ""), v) for k, v in row.items() if k.startswith("contribution_")),
                   key=lambda kv: abs(kv[1]), reverse=True)
    top = ", ".join(f"{FACTORS[k][0].split(' (')[0].lower()} {v:+.1%}" for k, v in parts[:3] if abs(v) >= 0.001)
    return (f"{name} {row['actual']:+.1%} over {window}: {top or 'no large macro effect'}; "
            f"unexplained {row['unexplained'] + row['alpha']:+.1%} (macro factors explain "
            f"{r_squared:.0%} of daily moves).")


# ==============================================================
# VALIDATION
# ==============================================================

def validate(betas: pd.DataFrame, factor_moves: pd.DataFrame, n_instruments: int) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add("Factors available", factor_moves["factor"].nunique() >= 5,
        f"{factor_moves['factor'].nunique()} of {len(FACTORS)} factors")
    add("Instruments modelled", len(betas) >= 0.8 * n_instruments, f"{len(betas)} of {n_instruments}")
    if "TLT" in betas.index and "beta_interest_rates" in betas.columns:
        rate_beta = betas.loc["TLT", "beta_interest_rates"]
        add("Long Treasuries: rate beta ≈ −duration (−12 to −22)", -22 <= rate_beta <= -12,
            f"TLT rate beta {rate_beta:.1f} per +1pp")
    if "HYG" in betas.index and "beta_credit_spreads" in betas.columns:
        add("High-yield bonds fall when spreads widen", betas.loc["HYG", "beta_credit_spreads"] < 0,
            f"HYG credit beta {betas.loc['HYG', 'beta_credit_spreads']:.2f}")
    if "GC=F" in betas.index and "beta_us_dollar" in betas.columns:
        add("Gold tends to move against the dollar", betas.loc["GC=F", "beta_us_dollar"] < 0,
            f"gold dollar beta {betas.loc['GC=F', 'beta_us_dollar']:.2f}")
    r2 = betas["r_squared"].dropna()
    add("R² between 0 and 1", r2.between(0, 1).all() if len(r2) else False,
        f"median R² {r2.median():.2f}" if len(r2) else "none")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_macro_drivers(prices: Optional[pd.DataFrame] = None, fred: Optional[pd.DataFrame] = None,
                      universe: Optional[pd.DataFrame] = None, out_dir: Path = BASE_DIR, verbose: bool = True):
    if prices is None:
        if not PRICE_HISTORY.exists() or not FRED_HISTORY.exists():
            raise SystemExit("Run `python multi_asset_universe.py` first (it saves the price and FRED history).")
        prices = pd.read_csv(PRICE_HISTORY, index_col=0, parse_dates=True)
        fred = pd.read_csv(FRED_HISTORY, index_col=0, parse_dates=True)
    universe = universe if universe is not None else pd.read_csv(UNIVERSE)
    info = universe.set_index("symbol")
    returns, factors = build_daily_frame(prices, fred)

    beta_rows, attribution_rows = [], []
    for symbol in returns.columns:
        betas = macro_betas(returns[symbol], factors, exclude=SELF_FACTOR.get(symbol))
        if betas is None:
            continue
        meta = info.loc[symbol] if symbol in info.index else {}
        beta_rows.append({"symbol": symbol, "name": meta.get("name", symbol),
                          "asset_class": meta.get("asset_class"), "sub_class": meta.get("sub_class"), **betas})
        for window, days in WINDOWS.items():
            attribution_rows.append({"symbol": symbol, "window": window,
                                     **attribution(returns[symbol], factors, betas, days)})
    betas = pd.DataFrame(beta_rows).set_index("symbol")
    attributions = pd.DataFrame(attribution_rows)

    moves = []
    for window, days in WINDOWS.items():
        recent = factors.tail(days)
        for key in factors.columns:
            label, _, kind = FACTORS[key]
            value = recent[key].sum()
            moves.append({"factor": key, "label": label, "window": window, "move": value,
                          "unit": "percentage points" if kind == "change" else "return"})
    factor_moves = pd.DataFrame(moves)

    stories = []
    for asset_class, symbol in REPRESENTATIVES:
        if symbol not in betas.index:
            continue
        row = attributions[(attributions["symbol"] == symbol) & (attributions["window"] == "1 month")]
        if row.empty:
            continue
        stories.append({"asset_class": asset_class, "symbol": symbol,
                        "story": narrative(betas.loc[symbol, "name"], row.iloc[0].to_dict(),
                                           betas.loc[symbol, "r_squared"], "1 month")})
    stories = pd.DataFrame(stories)
    validation = validate(betas, factor_moves, returns.shape[1])

    out_dir = Path(out_dir)
    betas.to_csv(out_dir / OUTPUT_BETAS)
    attributions.to_csv(out_dir / OUTPUT_ATTRIBUTION, index=False)
    factor_moves.to_csv(out_dir / OUTPUT_FACTOR_MOVES, index=False)
    stories.to_csv(out_dir / OUTPUT_NARRATIVE, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(factor_moves, stories, validation)
    return betas, attributions, factor_moves, stories, validation


def print_report(factor_moves, stories, validation) -> None:
    line = "=" * 92
    pd.set_option("display.width", 200)
    print(line)
    print("VITTANTRA — DAY 76d MACRO DRIVERS")
    print(line)
    print("Factor moves")
    print(factor_moves.pivot(index="label", columns="window", values="move").round(4).to_string())
    print("\nWhat moved each asset class (last month)")
    for row in stories.itertuples():
        print(f"- [{row.asset_class}] {row.story}")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 76d macro drivers complete.")
    print(line)


if __name__ == "__main__":
    run_macro_drivers()
