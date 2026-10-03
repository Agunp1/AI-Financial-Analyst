"""
Day 80 — Performance Attribution

Why did the research portfolio beat (or lag) its benchmark? Two standard
answers, both on the Day 77 point-in-time backtest (top-quintile portfolio
of the IC-weighted score vs the equal-weighted research universe, rebalanced
every 20 trading days):

1. Brinson–Fachler sector attribution (per period, sector s)
       Allocation   (w_p,s − w_b,s) × (R_b,s − R_b)      sector bets
       Selection     w_b,s × (R_p,s − R_b,s)             stock picking
       Interaction  (w_p,s − w_b,s) × (R_p,s − R_b,s)
   Allocation + selection + interaction = R_p − R_b in every period.
   Periods are linked with Carino's logarithmic smoothing so the effects add
   up to the compounded active return; trading costs are a separate line.

2. Factor (pillar) attribution, risk-model style
       Each period: cross-sectional OLS of returns on the five standardized
       pillar scores gives a factor return f_k; the portfolio's active
       exposure x_k = Σ (w_p − w_b) z_k; contribution = x_k × f_k.
       The rest is stock-specific (residual) return.

Outputs: day80_brinson_by_period.csv, day80_brinson_by_sector.csv,
         day80_factor_attribution.csv, day80_attribution_summary.csv,
         day80_validation_summary.csv

Historical research results, not a promise of future returns.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

HISTORY = "day77_score_history.csv"
SIGNAL = "composite_ic_weighted"
PILLARS = ["fundamental", "technical", "quant", "economic", "risk"]
QUINTILE = 0.20
COST_PER_DOLLAR = 0.0010

OUTPUT_BY_PERIOD = "day80_brinson_by_period.csv"
OUTPUT_BY_SECTOR = "day80_brinson_by_sector.csv"
OUTPUT_FACTORS = "day80_factor_attribution.csv"
OUTPUT_SUMMARY = "day80_attribution_summary.csv"
OUTPUT_VALIDATION = "day80_validation_summary.csv"


# ==============================================================
# BRINSON–FACHLER
# ==============================================================

def brinson_fachler(wp: pd.Series, wb: pd.Series, returns: pd.Series, sectors: pd.Series) -> pd.DataFrame:
    """Single-period sector attribution; weights and returns indexed by ticker."""
    names = wb.index
    wp = wp.reindex(names).fillna(0.0)
    r, sec = returns.reindex(names), sectors.reindex(names)
    rb_total = float((wb * r).sum())
    rows = []
    for sector in sorted(sec.unique()):
        m = sec == sector
        wbs, wps = float(wb[m].sum()), float(wp[m].sum())
        rbs = float((wb[m] * r[m]).sum() / wbs) if wbs > 0 else 0.0
        rps = float((wp[m] * r[m]).sum() / wps) if wps > 0 else rbs   # no holdings: no selection effect
        rows.append({"sector": sector, "portfolio_weight": wps, "benchmark_weight": wbs,
                     "portfolio_return": rps if wps > 0 else np.nan, "benchmark_return": rbs,
                     "allocation": (wps - wbs) * (rbs - rb_total),
                     "selection": wbs * (rps - rbs),
                     "interaction": (wps - wbs) * (rps - rbs)})
    return pd.DataFrame(rows)


def carino_factors(rp: pd.Series, rb: pd.Series) -> pd.Series:
    """Per-period scaling k_t / K so arithmetic effects sum to the compounded active return."""
    def k(a, b):
        return (math.log1p(a) - math.log1p(b)) / (a - b) if abs(a - b) > 1e-12 else 1 / (1 + a)

    total_p, total_b = float(np.prod(1 + rp) - 1), float(np.prod(1 + rb) - 1)
    big_k = k(total_p, total_b)
    return pd.Series([k(a, b) / big_k for a, b in zip(rp, rb)], index=rp.index)


# ==============================================================
# FACTOR ATTRIBUTION
# ==============================================================

def factor_returns(scores: pd.DataFrame, returns: pd.Series) -> Optional[pd.Series]:
    """Cross-sectional OLS of returns on standardized pillar scores (with intercept)."""
    usable = [p for p in PILLARS if scores[p].notna().sum() >= 0.8 * len(scores)]
    data = pd.concat([scores[usable], returns.rename("r")], axis=1).dropna()
    if len(data) < len(usable) + 5 or not usable:
        return None
    z = (data[usable] - data[usable].mean()) / data[usable].std(ddof=0)
    x = np.column_stack([np.ones(len(z)), z.to_numpy()])
    coef, *_ = np.linalg.lstsq(x, data["r"].to_numpy(), rcond=None)
    return pd.Series(coef[1:], index=usable)


def standardized(scores: pd.DataFrame, columns) -> pd.DataFrame:
    return (scores[columns] - scores[columns].mean()) / scores[columns].std(ddof=0)


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_attribution(history: Optional[pd.DataFrame] = None, sectors: Optional[Dict[str, str]] = None,
                    base: Path = BASE_DIR, out_dir: Optional[Path] = None, verbose: bool = True):
    out_dir = Path(out_dir or base)
    if history is None:
        if not (base / HISTORY).exists():
            raise SystemExit("Run `python multi_factor_rating.py` first (Day 77 score history).")
        history = pd.read_csv(base / HISTORY, parse_dates=["date"])
    if sectors is None:
        import fundamental_engine as fe
        sectors = {t: info["sector"] for t, info in fe.load_universe().items()}
    history = history.dropna(subset=["forward_return_20d", SIGNAL]).copy()
    history["sector"] = history["ticker"].map(sectors).fillna("Other")

    period_rows, sector_rows, factor_rows = [], [], []
    previous = pd.Series(dtype=float)
    for date, g in history.groupby("date"):
        g = g.set_index("ticker")
        if len(g) < 10:
            continue
        n = max(1, int(round(len(g) * QUINTILE)))
        top = g.sort_values(SIGNAL, ascending=False).head(n).index
        wp = pd.Series(1.0 / n, index=top)
        wb = pd.Series(1.0 / len(g), index=g.index)
        r = g["forward_return_20d"].astype(float)
        bf = brinson_fachler(wp, wb, r, g["sector"])
        rp, rb = float((wp * r.reindex(top)).sum()), float((wb * r).sum())
        traded = float(wp.reindex(wp.index.union(previous.index)).fillna(0)
                       .sub(previous.reindex(wp.index.union(previous.index)).fillna(0)).abs().sum())
        cost = traded * COST_PER_DOLLAR
        previous = wp
        period_rows.append({"date": date, "portfolio_return": rp - cost, "gross_portfolio_return": rp,
                            "benchmark_return": rb, "allocation": bf["allocation"].sum(),
                            "selection": bf["selection"].sum(), "interaction": bf["interaction"].sum(),
                            "costs": -cost})
        sector_rows.append(bf.assign(date=date))

        f = factor_returns(g[PILLARS].astype(float), r)
        if f is not None:
            z = standardized(g[PILLARS].astype(float), list(f.index)).fillna(0.0)
            active = wp.reindex(g.index).fillna(0.0) - wb
            exposure = z.mul(active, axis=0).sum()
            contribution = exposure * f
            factor_rows.append({"date": date, **{f"exposure_{k}": exposure[k] for k in f.index},
                                **{f"factor_return_{k}": f[k] for k in f.index},
                                **{f"contribution_{k}": contribution[k] for k in f.index},
                                "specific": (rp - rb) - contribution.sum(), "active_return": rp - rb})

    periods = pd.DataFrame(period_rows)
    scale = carino_factors(periods["portfolio_return"], periods["benchmark_return"])
    effects = ["allocation", "selection", "interaction", "costs"]
    linked = {e: float((periods[e] * scale).sum()) for e in effects}
    by_sector = pd.concat(sector_rows, ignore_index=True)
    period_scale = dict(zip(periods["date"], scale))
    by_sector["scale"] = by_sector["date"].map(period_scale)
    sector_table = (by_sector.assign(**{e: by_sector[e] * by_sector["scale"]
                                        for e in ("allocation", "selection", "interaction")})
                    .groupby("sector")[["allocation", "selection", "interaction"]].sum()
                    .assign(total=lambda d: d.sum(axis=1))
                    .join(by_sector.groupby("sector")[["portfolio_weight", "benchmark_weight"]].mean()
                          .rename(columns=lambda c: f"average_{c}"))
                    .sort_values("total", ascending=False).reset_index())
    factors = pd.DataFrame(factor_rows)
    factor_totals = factors.filter(like="contribution_").sum() if len(factors) else pd.Series(dtype=float)

    total_p = float(np.prod(1 + periods["portfolio_return"]) - 1)
    total_b = float(np.prod(1 + periods["benchmark_return"]) - 1)
    years = len(periods) / 12.6
    summary = {
        "periods": len(periods), "start": str(periods["date"].min().date()), "end": str(periods["date"].max().date()),
        "portfolio_cumulative": total_p, "benchmark_cumulative": total_b, "active_cumulative": total_p - total_b,
        "portfolio_annualized": (1 + total_p) ** (1 / years) - 1, "benchmark_annualized": (1 + total_b) ** (1 / years) - 1,
        **{f"{e}_linked": v for e, v in linked.items()},
        "best_sector": sector_table.iloc[0]["sector"], "worst_sector": sector_table.iloc[-1]["sector"],
        **{f"factor_{k.replace('contribution_', '')}_sum": float(v) for k, v in factor_totals.items()},
        "specific_sum": float(factors["specific"].sum()) if len(factors) else None,
    }
    validation = validate_attribution(periods, linked, summary, factors)

    periods.to_csv(out_dir / OUTPUT_BY_PERIOD, index=False)
    sector_table.to_csv(out_dir / OUTPUT_BY_SECTOR, index=False)
    factors.to_csv(out_dir / OUTPUT_FACTORS, index=False)
    pd.DataFrame([summary]).to_csv(out_dir / OUTPUT_SUMMARY, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(summary, sector_table, factor_totals, validation)
    return periods, sector_table, factors, summary, validation


def validate_attribution(periods, linked, summary, factors) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    gap = (periods[["allocation", "selection", "interaction"]].sum(axis=1)
           - (periods["gross_portfolio_return"] - periods["benchmark_return"])).abs().max()
    add("Effects add up to active return every period", gap < 1e-10, f"max gap {gap:.1e}")
    linked_total = sum(linked.values())
    add("Linked effects equal compounded active return", abs(linked_total - summary["active_cumulative"]) < 1e-8,
        f"{linked_total:+.4%} vs {summary['active_cumulative']:+.4%}")
    if len(factors):
        f_gap = (factors.filter(like="contribution_").sum(axis=1) + factors["specific"]
                 - factors["active_return"]).abs().max()
        add("Factor contributions + specific = active return", f_gap < 1e-10, f"max gap {f_gap:.1e}")
    add("Enough periods", summary["periods"] >= 20, f"{summary['periods']} periods")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def print_report(summary, sector_table, factor_totals, validation) -> None:
    line = "=" * 92
    print(line)
    print("VITTANTRA — DAY 80 PERFORMANCE ATTRIBUTION (Day 77 research portfolio vs equal-weight universe)")
    print(line)
    print(f"{summary['start']} → {summary['end']} ({summary['periods']} periods): portfolio "
          f"{summary['portfolio_cumulative']:+.1%}, benchmark {summary['benchmark_cumulative']:+.1%}, active "
          f"{summary['active_cumulative']:+.1%}")
    print(f"Allocation {summary['allocation_linked']:+.2%} | selection {summary['selection_linked']:+.2%} | "
          f"interaction {summary['interaction_linked']:+.2%} | costs {summary['costs_linked']:+.2%}")
    print("\nBy sector (linked)")
    print(sector_table.to_string(index=False, float_format=lambda x: f"{x:+.2%}"))
    if len(factor_totals):
        print("\nBy pillar (sum of period contributions)")
        print(factor_totals.rename(lambda k: k.replace("contribution_", "")).to_string(float_format=lambda x: f"{x:+.2%}"))
        print(f"specific (stock-specific)  {summary['specific_sum']:+.2%}")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 80 attribution complete. Historical research results, not a promise of future returns.")
    print(line)


if __name__ == "__main__":
    run_attribution()
