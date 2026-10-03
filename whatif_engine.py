"""
Day 81 — What-If Scenario Engine (live risk recalculation)

Change holdings or apply a macro shock and see the risk change immediately.

Risk measures for a set of weights:
    volatility        √(wᵀΣw) with the Ledoit–Wolf constant-correlation covariance
    VaR / ES (99%)    parametric (normal) and historical over the same window, 1 day
    risk shares       Euler contributions w_i(Σw)_i / σ_p
    beta              to the S&P 500 (SPY)

Scenario P&L uses each holding's factor sensitivities, estimated by OLS on
the same return history (equity market, 10Y yield, breakeven inflation,
high-yield spread, US dollar, oil — the Day 76d factors):
    P&L_i = w_i × Σ_k β_i,k × shock_k
A linear factor model: large shocks ignore convexity (bonds, options) and
correlation changes in a crisis, so results are approximations.

Built-in scenarios are hypothetical, set roughly to the size of past moves.
A what-if is a proposal only: saving it creates a ticket with status
PENDING_HUMAN_APPROVAL. Nothing is executed.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ml_factor_attribution import calculate_ols
from vittantra_risk_model import constant_correlation_shrinkage, euler_risk_contributions


BASE_DIR = Path(__file__).resolve().parent
PROPOSALS = "day81_whatif_proposals.csv"
Z99 = 2.326347874
ES_FACTOR_99 = 2.665214220     # φ(z)/(1−α) for α = 99%

FACTORS = {
    "equity_market": ("S&P 500 return", "SPY", "return"),
    "interest_rates": ("10Y Treasury yield change (pp)", "DGS10", "change"),
    "inflation_expectations": ("10Y breakeven change (pp)", "T10YIE", "change"),
    "credit_spreads": ("High-yield spread change (pp)", "BAMLH0A0HYM2", "change"),
    "us_dollar": ("US dollar index return", "DX-Y.NYB", "return"),
    "oil": ("Crude oil return", "CL=F", "return"),
}

SCENARIOS = {
    "Equity sell-off": {"equity_market": -0.20, "credit_spreads": 1.5, "interest_rates": -0.5, "us_dollar": 0.03},
    "Rate shock (2022-like)": {"interest_rates": 2.4, "equity_market": -0.19, "credit_spreads": 1.6,
                               "us_dollar": 0.08, "inflation_expectations": 0.2},
    "Credit crisis (2008-like)": {"equity_market": -0.38, "credit_spreads": 6.0, "interest_rates": -1.8,
                                  "us_dollar": 0.06, "oil": -0.50},
    "Inflation surprise": {"interest_rates": 0.5, "inflation_expectations": 0.3, "equity_market": -0.05},
    "Oil spike": {"oil": 0.40, "inflation_expectations": 0.4, "equity_market": -0.08, "interest_rates": 0.3},
    "Soft-landing rally": {"equity_market": 0.10, "credit_spreads": -0.5, "interest_rates": -0.5},
}


# ==============================================================
# DATA
# ==============================================================

def load_prices(base: Path = BASE_DIR) -> pd.DataFrame:
    """Research-universe stocks (Day 77 prices) plus the multi-asset universe (Day 76c), aligned."""
    frames = []
    try:
        import multi_factor_rating as mfr
        stocks, _ = mfr.load_prices()
        frames.append(stocks)
    except Exception:
        pass
    path = base / "day76c_price_history.csv"
    if path.exists():
        frames.append(pd.read_csv(path, index_col=0, parse_dates=True))
    if not frames:
        return pd.DataFrame()
    return align_prices(frames)


def align_prices(frames) -> pd.DataFrame:
    """Put frames on the calendar of the coarsest one (so returns share one frequency)."""
    frames = [f.sort_index() for f in frames if len(f)]
    coarse = max(frames, key=lambda f: pd.Series(f.index).diff().dt.days.median())
    dates = coarse.index[coarse.index >= max(f.index.min() for f in frames)]
    out = []
    for f in frames:
        out.append(f.reindex(f.index.union(dates)).ffill(limit=10).reindex(dates))
    combined = pd.concat(out, axis=1)
    return combined.loc[:, ~combined.columns.duplicated()]


def load_fred(base: Path = BASE_DIR) -> pd.DataFrame:
    frames = []
    for name in ("day76c_fred_daily_history.csv", "day77_macro_history.csv"):
        path = base / name
        if path.exists():
            frames.append(pd.read_csv(path, index_col=0, parse_dates=True))
    if not frames:
        return pd.DataFrame()
    fred = pd.concat(frames, axis=1)
    fred = fred.loc[:, ~fred.columns.duplicated()].sort_index()
    return fred


def factor_moves(prices: pd.DataFrame, fred: pd.DataFrame) -> pd.DataFrame:
    """Factor moves on the price calendar: returns for prices, changes for FRED rates."""
    out = pd.DataFrame(index=prices.index)
    for key, (_, source, kind) in FACTORS.items():
        if kind == "return" and source in prices.columns:
            out[key] = prices[source].pct_change(fill_method=None)
        elif kind == "change" and source in fred.columns:
            series = fred[source].dropna()
            out[key] = series.reindex(series.index.union(prices.index)).ffill(limit=10).reindex(prices.index).diff()
    return out


# ==============================================================
# RISK
# ==============================================================

class RiskModel:
    """Covariance, factor betas and return history for every instrument with enough data."""

    def __init__(self, prices: pd.DataFrame, fred: Optional[pd.DataFrame] = None, window: int = 252):
        prices = prices.sort_index()
        spacing = pd.Series(prices.index).diff().dt.days.median()
        self.periods_per_year = 252.0 if spacing <= 1.5 else 365.25 / spacing
        self.horizon_days = 1.0 if spacing <= 1.5 else float(spacing) * 252 / 365.25
        returns = prices.pct_change(fill_method=None).iloc[1:]
        window = window if spacing <= 1.5 else max(36, int(window * self.periods_per_year / 252))
        returns = returns.tail(window)
        self.returns = returns.loc[:, returns.notna().mean() >= 0.8]
        clean = self.returns.fillna(0.0)
        cov, self.shrinkage = constant_correlation_shrinkage(clean.to_numpy())
        self.cov = pd.DataFrame(cov, index=clean.columns, columns=clean.columns)          # per period
        self.factors = factor_moves(prices, fred if fred is not None else pd.DataFrame()).reindex(self.returns.index)
        self.betas = self._betas()

    def _betas(self) -> pd.DataFrame:
        usable = [k for k in FACTORS if k in self.factors and self.factors[k].notna().mean() >= 0.8]
        rows = {}
        for symbol in self.returns.columns:
            own = [k for k in usable if FACTORS[k][1] != symbol]
            data = pd.concat([self.returns[symbol].rename("y"), self.factors[own]], axis=1).dropna()
            if len(data) < max(len(own) + 10, 30):
                continue
            result = calculate_ols(data["y"], data[own])
            rows[symbol] = {k: result[k] for k in own}
            rows[symbol]["r_squared"] = result["r_squared"]
            for k in usable:
                if FACTORS[k][1] == symbol:          # the factor itself: beta 1 to its own move
                    rows[symbol][k] = 1.0 if FACTORS[k][2] == "return" else 0.0
        return pd.DataFrame.from_dict(rows, orient="index")

    def available(self):
        return list(self.cov.index)


def portfolio_risk(model: RiskModel, weights: Dict[str, float], value: float = 1_000_000.0) -> Dict[str, object]:
    w = pd.Series(weights, dtype=float)
    w = w[w.abs() > 0]
    missing = [s for s in w.index if s not in model.cov.index]
    w = w.drop(missing)
    if w.empty:
        return {"missing": missing, "error": "no holdings with price history"}
    cov = model.cov.loc[w.index, w.index]
    shares, vol_period = euler_risk_contributions(w, cov)
    scale_day = 1 / math.sqrt(model.horizon_days)
    vol_day = vol_period * scale_day
    history = (model.returns[w.index].fillna(0.0) * w).sum(axis=1) * scale_day
    loss_q = -np.quantile(history, 0.01) if len(history) >= 50 else np.nan
    tail = history[history <= -loss_q] if np.isfinite(loss_q) else pd.Series(dtype=float)
    beta = np.nan
    if "SPY" in model.returns.columns:
        spy = model.returns["SPY"]
        beta = float(np.cov(history / scale_day, spy.fillna(0.0))[0, 1] / spy.var())
    return {
        "volatility_annual": vol_period * math.sqrt(model.periods_per_year),
        "var99_1d_parametric": Z99 * vol_day * value,
        "es99_1d_parametric": ES_FACTOR_99 * vol_day * value,
        "var99_1d_historical": loss_q * value if np.isfinite(loss_q) else np.nan,
        "es99_1d_historical": -tail.mean() * value if len(tail) else np.nan,
        "beta_spy": beta, "gross_exposure": float(w.abs().sum()), "net_exposure": float(w.sum()),
        "risk_shares": shares, "largest_risk_share": float(shares.max()), "missing": missing,
        "observations": len(history),
    }


def scenario_pnl(model: RiskModel, weights: Dict[str, float], shocks: Dict[str, float],
                 value: float = 1_000_000.0) -> pd.DataFrame:
    rows = []
    for symbol, weight in weights.items():
        if weight == 0:
            continue
        if symbol not in model.betas.index:
            rows.append({"symbol": symbol, "weight": weight, "scenario_return": np.nan, "pnl": np.nan,
                         "note": "no factor history"})
            continue
        b = model.betas.loc[symbol]
        ret = sum(float(b.get(k, 0.0) if pd.notna(b.get(k)) else 0.0) * s for k, s in shocks.items())
        rows.append({"symbol": symbol, "weight": weight, "scenario_return": ret, "pnl": weight * ret * value,
                     "note": f"R² {b['r_squared']:.2f}"})
    return pd.DataFrame(rows).sort_values("pnl", na_position="last").reset_index(drop=True)


def compare(model: RiskModel, before: Dict[str, float], after: Dict[str, float], shocks: Dict[str, float],
            value: float = 1_000_000.0) -> pd.DataFrame:
    rows = []
    for label, weights in (("Current", before), ("What-if", after)):
        risk = portfolio_risk(model, weights, value)
        pnl = scenario_pnl(model, weights, shocks, value)
        rows.append({"portfolio": label, "volatility_annual": risk.get("volatility_annual"),
                     "var99_1d_parametric": risk.get("var99_1d_parametric"),
                     "es99_1d_parametric": risk.get("es99_1d_parametric"),
                     "var99_1d_historical": risk.get("var99_1d_historical"),
                     "beta_spy": risk.get("beta_spy"), "largest_risk_share": risk.get("largest_risk_share"),
                     "scenario_pnl": pnl["pnl"].sum(min_count=1)})
    out = pd.DataFrame(rows).set_index("portfolio")
    out.loc["Change"] = out.loc["What-if"] - out.loc["Current"]
    return out


def save_proposal(weights: Dict[str, float], rationale: str, scenario: str, metrics: Dict[str, float],
                  path: Optional[Path] = None) -> pd.DataFrame:
    """Record a what-if as a ticket for the human approval workflow (never executed)."""
    path = Path(path or BASE_DIR / PROPOSALS)
    previous = pd.read_csv(path) if path.exists() else pd.DataFrame()
    ticket = {
        "proposal_id": f"WI-{len(previous) + 1:04d}",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "weights": "; ".join(f"{k} {v:.2%}" for k, v in weights.items() if v),
        "scenario": scenario, "rationale": rationale,
        **{k: v for k, v in metrics.items() if isinstance(v, (int, float))},
        "status": "PENDING_HUMAN_APPROVAL", "automatic_execution_authorized": 0,
    }
    table = pd.concat([previous, pd.DataFrame([ticket])], ignore_index=True)
    table.to_csv(path, index=False)
    return table


if __name__ == "__main__":
    prices = load_prices()
    model = RiskModel(prices, load_fred())
    portfolio = BASE_DIR / "day79_model_portfolio.csv"
    weights = (pd.read_csv(portfolio).set_index("ticker")["weight"].to_dict() if portfolio.exists()
               else {s: 1 / 5 for s in model.available()[:5]})
    print("=" * 92)
    print("VITTANTRA — DAY 81 WHAT-IF ENGINE")
    print("=" * 92)
    print(f"{len(model.available())} instruments; {len(model.returns)} observations "
          f"({model.periods_per_year:.0f} a year); shrinkage {model.shrinkage:.2f}")
    risk = portfolio_risk(model, weights)
    print(f"Model portfolio: volatility {risk['volatility_annual']:.1%}, 1-day 99% VaR ${risk['var99_1d_parametric']:,.0f}"
          f" per $1m, beta {risk['beta_spy']:.2f}")
    if model.betas.empty:
        print("  Scenario P&L needs at least 30 overlapping observations (daily prices); not enough history.")
    for name, shocks in SCENARIOS.items() if not model.betas.empty else []:
        pnl = scenario_pnl(model, weights, shocks)
        print(f"  {name:<26} {pnl['pnl'].sum(min_count=1):>12,.0f}  per $1m")
    hedged = {**weights, "TLT": 0.10}
    total = sum(hedged.values())
    hedged = {k: v / total for k, v in hedged.items()}
    print("\nAdding 10% long Treasuries (TLT), scaled to 100%:")
    print(compare(model, weights, hedged, SCENARIOS["Equity sell-off"]).round(4).to_string())
    print("\nDay 81 what-if engine complete. Scenario results are approximations; nothing is executed.")
    print("=" * 92)
