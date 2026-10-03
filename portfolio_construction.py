"""
Day 79 — Research-Driven Portfolio Construction (within a risk budget)

Turns the Day 77 ratings into a model equity portfolio the way an
institutional PM does: expected alpha from the signal, a risk model, and an
optimizer that respects an explicit risk budget and position limits.

1. Alpha (Grinold–Kahn "alpha = IC × volatility × score")
       z_i      = standardized IC-weighted score (cross-section)
       α_i,20d  = IC × σ_i,20d × z_i          IC = realized mean IC of the score
       α_i,year = α_i,20d × 12.6
   With no positive IC there is no alpha and the optimizer just controls risk.

2. Risk model
       Ledoit–Wolf shrinkage of the one-year daily covariance toward a
       constant-correlation target, annualized: more stable than the sample
       covariance while keeping the average correlation between stocks.

3. Optimizer (SLSQP)
       maximize   αᵀw − λ/2 · (w − b)ᵀ Σ (w − b)
       subject to Σw = 1, 0 ≤ w ≤ 8%, |sector active weight| ≤ 10%,
                  tracking error ≤ 4% (the active-risk budget),
                  each holding ≤ 15% of portfolio risk (Euler),
                  beta to the benchmark between 0.9 and 1.1
   Benchmark b = equal-weighted research universe (as in the Day 77 backtest).

The proposal is written with status PENDING_HUMAN_APPROVAL: it must pass the
approval workflow; automatic_execution_authorized_count stays 0.

Outputs: day79_model_portfolio.csv, day79_portfolio_summary.csv,
         day79_sector_weights.csv, day79_validation_summary.csv
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from vittantra_risk_model import constant_correlation_shrinkage, euler_risk_contributions


BASE_DIR = Path(__file__).resolve().parent

RATINGS = "day77_current_ratings.csv"
IC_SUMMARY = "day77_ic_summary.csv"
VALUATION = "day78_valuation.csv"

OUTPUT_PORTFOLIO = "day79_model_portfolio.csv"
OUTPUT_SUMMARY = "day79_portfolio_summary.csv"
OUTPUT_SECTORS = "day79_sector_weights.csv"
OUTPUT_VALIDATION = "day79_validation_summary.csv"

POLICY = {
    "max_weight": 0.08,
    "max_sector_active": 0.10,
    "tracking_error_budget": 0.04,
    "max_risk_share": 0.15,
    "max_beta_gap": 0.10,            # beta to the benchmark within 0.9–1.1
    "risk_aversion": 10.0,
    "cost_per_dollar_traded": 0.0010,
    "estimation_days": 252,
    "periods_per_year_20d": 12.6,
    "min_weight_reported": 0.0005,
}


# ==============================================================
# INPUTS
# ==============================================================

def shrunk_covariance(returns: pd.DataFrame, periods_per_year: float) -> pd.DataFrame:
    """Ledoit–Wolf constant-correlation shrinkage covariance, annualized."""
    clean = returns.dropna(axis=1, thresh=int(0.8 * len(returns))).fillna(0.0)
    cov, delta = constant_correlation_shrinkage(clean.to_numpy())
    out = pd.DataFrame(cov * periods_per_year, index=clean.columns, columns=clean.columns)
    out.attrs["shrinkage"] = delta
    return out


def periods_per_year(index: pd.DatetimeIndex) -> float:
    spacing = pd.Series(index).diff().dt.days.median()
    return 252.0 if spacing is None or spacing <= 1.5 else 365.25 / spacing


def grinold_alpha(score: pd.Series, volatility: pd.Series, ic: float) -> pd.Series:
    """Annualized alpha = IC × σ_20d × z × 12.6 (zero when IC ≤ 0)."""
    if ic is None or not np.isfinite(ic) or ic <= 0:
        return pd.Series(0.0, index=score.index)
    z = (score - score.mean()) / score.std(ddof=0)
    sigma_20d = volatility / math.sqrt(POLICY["periods_per_year_20d"])
    return ic * sigma_20d * z * POLICY["periods_per_year_20d"]


# ==============================================================
# OPTIMIZER
# ==============================================================

def optimize(alpha: pd.Series, cov: pd.DataFrame, benchmark: pd.Series, sectors: pd.Series,
             policy: Optional[dict] = None) -> pd.Series:
    p = {**POLICY, **(policy or {})}
    names = list(alpha.index)
    a, b, S = alpha.to_numpy(), benchmark.reindex(names).to_numpy(), cov.loc[names, names].to_numpy()
    n = len(names)

    def objective(w):
        active = w - b
        return -(a @ w) + p["risk_aversion"] / 2 * active @ S @ active

    def gradient(w):
        return -a + p["risk_aversion"] * S @ (w - b)

    def tracking_error(w):
        active = w - b
        return math.sqrt(max(active @ S @ active, 0.0))

    def max_risk_share_gap(w):
        variance = w @ S @ w
        shares = w * (S @ w) / variance if variance > 0 else np.zeros(n)
        return p["max_risk_share"] - shares   # each ≥ 0

    bench_var = b @ S @ b
    beta_row = S @ b / bench_var                                   # beta(w) = wᵀΣb / bᵀΣb
    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)},
                   {"type": "ineq", "fun": lambda w: p["max_beta_gap"] - (beta_row @ w - 1.0), "jac": lambda w: -beta_row},
                   {"type": "ineq", "fun": lambda w: p["max_beta_gap"] + (beta_row @ w - 1.0), "jac": lambda w: beta_row},
                   {"type": "ineq", "fun": lambda w: p["tracking_error_budget"] - tracking_error(w)},
                   {"type": "ineq", "fun": max_risk_share_gap}]
    for sector in sorted(sectors.unique()):
        mask = (sectors.reindex(names) == sector).to_numpy().astype(float)
        constraints.append({"type": "ineq", "fun": lambda w, m=mask: p["max_sector_active"] - (m @ (w - b))})
        constraints.append({"type": "ineq", "fun": lambda w, m=mask: p["max_sector_active"] + (m @ (w - b))})
    start = np.clip(b, 0, p["max_weight"])
    start = start / start.sum()
    result = minimize(objective, start, jac=gradient, method="SLSQP", bounds=[(0.0, p["max_weight"])] * n,
                      constraints=constraints, options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(result.x, 0.0, None)
    w[w < p["min_weight_reported"]] = 0.0
    return pd.Series(w / w.sum(), index=names)


# ==============================================================
# ORCHESTRATION
# ==============================================================

def build_portfolio(ratings: pd.DataFrame, prices: pd.DataFrame, ic: Optional[float],
                    valuation: Optional[pd.DataFrame] = None, previous: Optional[pd.Series] = None,
                    policy: Optional[dict] = None) -> Dict[str, object]:
    p = {**POLICY, **(policy or {})}
    ratings = ratings.dropna(subset=["composite_ic_weighted"]).copy()
    prices = prices[[t for t in ratings.index if t in prices.columns]].sort_index()
    returns = prices.pct_change(fill_method=None).iloc[1:]
    ppy = periods_per_year(returns.index)
    window = int(p["estimation_days"] * ppy / 252) if ppy < 252 else p["estimation_days"]
    window = max(window, min(len(returns), 36))
    cov = shrunk_covariance(returns.tail(window), ppy)
    names = [t for t in ratings.index if t in cov.index]
    ratings, cov = ratings.loc[names], cov.loc[names, names]
    vol = pd.Series(np.sqrt(np.diag(cov)), index=names)
    alpha = grinold_alpha(ratings["composite_ic_weighted"].astype(float), vol, ic)
    benchmark = pd.Series(1.0 / len(names), index=names)
    weights = optimize(alpha, cov, benchmark, ratings["sector"], p)

    shares, port_vol = euler_risk_contributions(weights, cov)
    active = weights - benchmark
    te = math.sqrt(max(float(active @ cov @ active), 0.0))
    bench_vol = math.sqrt(float(benchmark @ cov @ benchmark))
    beta = float(weights @ cov @ benchmark) / bench_vol ** 2
    expected_alpha = float(alpha @ weights - alpha @ benchmark)
    prior = previous.reindex(names).fillna(0.0) if previous is not None else benchmark
    traded = float((weights - prior).abs().sum())

    table = pd.DataFrame({
        "ticker": names, "name": ratings["name"], "sector": ratings["sector"], "rating": ratings["rating"],
        "score": ratings["composite_ic_weighted"], "alpha": alpha, "volatility": vol,
        "weight": weights, "benchmark_weight": benchmark, "active_weight": active, "risk_share": shares,
    })
    if valuation is not None and len(valuation):
        v = valuation.set_index("ticker")
        table["valuation_signal"] = table["ticker"].map(v.get("valuation_signal", pd.Series(dtype=object)))
        table["upside"] = table["ticker"].map(v.get("upside", pd.Series(dtype=float)))
    table = table.sort_values("weight", ascending=False).reset_index(drop=True)

    sectors = (table.groupby("sector")[["weight", "benchmark_weight", "risk_share"]].sum()
               .assign(active_weight=lambda d: d["weight"] - d["benchmark_weight"]).reset_index()
               .sort_values("weight", ascending=False))
    summary = {
        "holdings": int((weights > 0).sum()), "universe": len(names),
        "expected_active_return": expected_alpha, "tracking_error": te,
        "information_ratio": expected_alpha / te if te > 0 else 0.0,
        "portfolio_volatility": port_vol, "benchmark_volatility": bench_vol, "beta_to_benchmark": beta,
        "active_share": 0.5 * float(active.abs().sum()), "largest_weight": float(weights.max()),
        "largest_risk_share": float(shares.max()), "turnover_traded": traded,
        "estimated_cost": traded * p["cost_per_dollar_traded"], "signal_ic": ic,
        "periods_per_year": ppy, "estimation_observations": int(min(window, len(returns))),
        "covariance_shrinkage": cov.attrs.get("shrinkage"),
        "tracking_error_budget": p["tracking_error_budget"],
        "approval_status": "PENDING_HUMAN_APPROVAL", "automatic_execution_authorized_count": 0,
    }
    return {"portfolio": table, "sectors": sectors, "summary": summary, "covariance": cov}


def validate_portfolio(result: Dict[str, object], policy: Optional[dict] = None) -> pd.DataFrame:
    p = {**POLICY, **(policy or {})}
    t, s, sectors = result["portfolio"], result["summary"], result["sectors"]
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add("Fully invested, long only", abs(t["weight"].sum() - 1) < 1e-6 and (t["weight"] >= 0).all(),
        f"sum {t['weight'].sum():.4f}")
    add("Position limit", t["weight"].max() <= p["max_weight"] + 1e-4, f"largest {t['weight'].max():.1%}")
    add("Sector active-weight limit", sectors["active_weight"].abs().max() <= p["max_sector_active"] + 1e-4,
        f"largest {sectors['active_weight'].abs().max():.1%}")
    add("Tracking error within the risk budget", s["tracking_error"] <= p["tracking_error_budget"] + 1e-4,
        f"{s['tracking_error']:.2%} vs budget {p['tracking_error_budget']:.0%}")
    add("No holding above the risk-share cap", s["largest_risk_share"] <= p["max_risk_share"] + 1e-3,
        f"largest {s['largest_risk_share']:.1%}")
    add("Beta to benchmark within 0.9–1.1", abs(s["beta_to_benchmark"] - 1) <= p["max_beta_gap"] + 1e-3,
        f"beta {s['beta_to_benchmark']:.2f}")
    minimum = min(15, s["universe"] // 2)
    add(f"Diversified (at least {minimum} holdings)", s["holdings"] >= minimum, f"{s['holdings']} holdings")
    add("Human approval required; no automatic execution",
        s["approval_status"] == "PENDING_HUMAN_APPROVAL" and s["automatic_execution_authorized_count"] == 0,
        "status PENDING_HUMAN_APPROVAL")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def run_portfolio(base: Path = BASE_DIR, out_dir: Optional[Path] = None, prices: Optional[pd.DataFrame] = None,
                  verbose: bool = True):
    out_dir = Path(out_dir or base)
    if not (base / RATINGS).exists():
        raise SystemExit("Run `python multi_factor_rating.py` first.")
    ratings = pd.read_csv(base / RATINGS).set_index("ticker")
    ic_table = pd.read_csv(base / IC_SUMMARY).set_index("signal") if (base / IC_SUMMARY).exists() else None
    ic = float(ic_table.at["composite_ic_weighted", "mean_ic"]) if ic_table is not None else None
    valuation = pd.read_csv(base / VALUATION) if (base / VALUATION).exists() else None
    previous = None
    if (out_dir / OUTPUT_PORTFOLIO).exists():
        previous = pd.read_csv(out_dir / OUTPUT_PORTFOLIO).set_index("ticker")["weight"]
    if prices is None:
        import multi_factor_rating as mfr
        prices, source = mfr.load_prices()
    else:
        source = "supplied"
    result = build_portfolio(ratings, prices, ic, valuation, previous)
    result["summary"]["price_source"] = source
    result["summary"]["as_of"] = str(pd.Timestamp(prices.index.max()).date())
    validation = validate_portfolio(result)

    result["portfolio"].to_csv(out_dir / OUTPUT_PORTFOLIO, index=False)
    result["sectors"].to_csv(out_dir / OUTPUT_SECTORS, index=False)
    pd.DataFrame([result["summary"]]).to_csv(out_dir / OUTPUT_SUMMARY, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(result, validation)
    return result, validation


def print_report(result, validation) -> None:
    line = "=" * 92
    s = result["summary"]
    print(line)
    print("VITTANTRA — DAY 79 RESEARCH-DRIVEN MODEL PORTFOLIO")
    print(line)
    print(f"Prices: {s.get('price_source')} ({s['estimation_observations']} observations); signal IC {s['signal_ic']}")
    view = result["portfolio"][result["portfolio"]["weight"] > 0][
        ["ticker", "sector", "rating", "score", "alpha", "weight", "active_weight", "risk_share"]]
    print(view.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\nExpected active return {s['expected_active_return']:+.2%} a year | tracking error "
          f"{s['tracking_error']:.2%} (budget {s['tracking_error_budget']:.0%}) | IR {s['information_ratio']:.2f}")
    print(f"Volatility {s['portfolio_volatility']:.1%} vs benchmark {s['benchmark_volatility']:.1%} | beta "
          f"{s['beta_to_benchmark']:.2f} | active share {s['active_share']:.0%} | turnover {s['turnover_traded']:.0%}"
          f" (cost {s['estimated_cost']:.2%})")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 79 portfolio construction complete. Proposal awaits human approval; nothing is executed.")
    print(line)


if __name__ == "__main__":
    run_portfolio()
