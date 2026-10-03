"""
Days 82–84 — Advisory Engine (retail and institutional)

Day 82  Client profiles and strategic allocation
        Retail: a risk questionnaire scores willingness (loss reaction,
        experience) and capacity (horizon, liquidity needs, income) to take
        risk; the profile is the LOWER of the two (CFA practice: when they
        conflict, capacity limits willingness, and the gap is discussed).
        Institutional: an investment policy statement (IPS) with return
        objective, risk limits and constraints.
        Capital market assumptions (building blocks from live yields):
            cash = 3M T-bill; Treasuries = 7Y yield; TIPS = real + breakeven;
            IG credit = 10Y + spread − expected loss; HY = 5Y + spread −
            default loss; equities = 10Y + equity risk premium; REITs =
            10Y + 3%; gold = breakeven inflation.
        Correlations from one year of daily ETF history (shrinkage
        covariance); volatility = 50% past year + 50% long-run level.
        One optimized allocation per risk profile (max expected return at a
        target volatility, within asset-class limits).

Day 83  Suitability and mandate-compliance engine
        Every recommendation is checked against the client: volatility,
        a 1-in-20 bad year vs loss tolerance, equity vs horizon,
        concentration, complex products, liquidity, IPS ranges and
        exclusions, and the required return. Each rule cites its basis
        (CFA Standard III(C) Suitability; the IPS). Result: SUITABLE,
        REVIEW REQUIRED or NOT SUITABLE. Nothing is executed.

Day 84  Goals-based planning (Monte Carlo) and client reports
        10,000 lognormal annual-return paths with inflation-adjusted
        contributions or withdrawals; probability of reaching the goal (or of
        not running out), wealth percentiles, and the saving needed for an
        80% chance. A plain-language report for each client.

Outputs: day82_capital_market_assumptions.csv, day82_client_profiles.csv,
         day82_model_allocations.csv, day83_suitability_results.csv,
         day84_goal_projections.csv, day84_goal_summary.csv,
         day84_client_reports.csv, day84_validation_summary.csv

Projections are estimates under stated assumptions, not guarantees.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from vittantra_risk_model import constant_correlation_shrinkage


BASE_DIR = Path(__file__).resolve().parent
CLIENTS_FILE = BASE_DIR / "advisory_clients.json"

OUT = {
    "cma": "day82_capital_market_assumptions.csv", "profiles": "day82_client_profiles.csv",
    "allocations": "day82_model_allocations.csv", "suitability": "day83_suitability_results.csv",
    "projections": "day84_goal_projections.csv", "goals": "day84_goal_summary.csv",
    "reports": "day84_client_reports.csv", "validation": "day84_validation_summary.csv",
}

# sleeve → (ticker, group, complexity)
SLEEVES = {
    "US equity": ("SPY", "Equity", "simple"),
    "International developed equity": ("EFA", "Equity", "simple"),
    "Emerging-market equity": ("EEM", "Equity", "simple"),
    "US Treasuries": ("IEF", "Fixed income", "simple"),
    "Inflation-linked Treasuries": ("TIP", "Fixed income", "simple"),
    "Investment-grade credit": ("LQD", "Fixed income", "simple"),
    "High-yield credit": ("HYG", "Fixed income", "complex"),
    "US REITs": ("VNQ", "Alternatives", "simple"),
    "Gold": ("GLD", "Alternatives", "simple"),
    "Cash (T-bills)": ("BIL", "Cash", "simple"),
}

PROFILES = {
    1: {"name": "Conservative", "target_vol": 0.05, "max_equity": 0.30, "min_cash": 0.10},
    2: {"name": "Moderately conservative", "target_vol": 0.075, "max_equity": 0.45, "min_cash": 0.05},
    3: {"name": "Moderate", "target_vol": 0.10, "max_equity": 0.65, "min_cash": 0.03},
    4: {"name": "Growth", "target_vol": 0.13, "max_equity": 0.85, "min_cash": 0.02},
    5: {"name": "Aggressive", "target_vol": 0.16, "max_equity": 1.00, "min_cash": 0.00},
}
MAX_SLEEVE = 0.60
MAX_ALTERNATIVES = 0.15
MAX_HIGH_YIELD = 0.15
# Policy ranges (upper limits) per sleeve, as an IPS would set them; they stop the
# optimizer piling into whichever sleeve has the highest estimated return.
SLEEVE_MAX = {"US equity": 0.60, "International developed equity": 0.30, "Emerging-market equity": 0.15,
              "US Treasuries": 0.60, "Inflation-linked Treasuries": 0.25, "Investment-grade credit": 0.30,
              "High-yield credit": 0.15, "US REITs": 0.10, "Gold": 0.10, "Cash (T-bills)": 0.60}
# Long-run annual volatility anchors (approximate long-history levels). Strategic assumptions
# blend these 50/50 with the past year, so one unusual year does not drive the allocation.
LONG_RUN_VOL = {"US equity": 0.16, "International developed equity": 0.17, "Emerging-market equity": 0.22,
                "US Treasuries": 0.06, "Inflation-linked Treasuries": 0.06, "Investment-grade credit": 0.07,
                "High-yield credit": 0.09, "US REITs": 0.20, "Gold": 0.16, "Cash (T-bills)": 0.005}
VOL_BLEND = 0.5

ASSUMPTIONS = {
    "equity_risk_premium": 0.045, "international_premium": 0.005, "emerging_premium": 0.015,
    "reit_premium": 0.03, "ig_expected_loss": 0.002, "hy_default_rate": 0.035, "hy_loss_given_default": 0.60,
    "default_inflation": 0.025, "simulations": 10_000, "success_target": 0.80, "seed": 7,
}

LOSS_TOLERANCE = {"Would sell everything": 0.10, "Worried, would probably hold": 0.20, "Would buy more": 0.30}
LOSS_SCORE = {"Would sell everything": 1, "Worried, would probably hold": 3, "Would buy more": 5}
EXPERIENCE_SCORE = {"None": 1, "Some": 3, "Extensive": 5}
INCOME_SCORE = {"Unstable": 1, "Stable": 4, "Pension covers essentials": 4, "Very secure": 5}


# ==============================================================
# DAY 82 — CAPITAL MARKET ASSUMPTIONS AND ALLOCATIONS
# ==============================================================

def capital_market_assumptions(base: Path = BASE_DIR) -> pd.DataFrame:
    curve = pd.read_csv(base / "day76c_yield_curve.csv")
    credit = pd.read_csv(base / "day76c_credit_spreads.csv").set_index("segment")["spread_bp"] / 10_000
    y = curve.set_index("maturity")["yield_pct"] / 100
    first = curve.iloc[0]
    breakeven = (float(first["breakeven_10y_pct"]) / 100 if pd.notna(first.get("breakeven_10y_pct"))
                 else ASSUMPTIONS["default_inflation"])
    real10 = float(first["real_yield_10y_pct"]) / 100 if pd.notna(first.get("real_yield_10y_pct")) else y["10Y"] - breakeven
    a = ASSUMPTIONS
    equity = y["10Y"] + a["equity_risk_premium"]
    rows = {
        "US equity": (equity, "10Y yield + equity risk premium"),
        "International developed equity": (equity + a["international_premium"], "US equity + 0.5% (lower valuations)"),
        "Emerging-market equity": (equity + a["emerging_premium"], "US equity + 1.5% (higher risk premium)"),
        "US Treasuries": (y.get("7Y", y["10Y"]), "7-year Treasury yield (fund duration ≈ 7)"),
        "Inflation-linked Treasuries": (real10 + breakeven, "10Y real yield + breakeven inflation"),
        "Investment-grade credit": (y["10Y"] + credit.get("US investment grade", 0.009) - a["ig_expected_loss"],
                                    "10Y yield + IG spread − 0.2% expected loss"),
        "High-yield credit": (y.get("5Y", y["10Y"]) + credit.get("US high yield", 0.035)
                              - a["hy_default_rate"] * a["hy_loss_given_default"],
                              "5Y yield + HY spread − default rate 3.5% × loss 60%"),
        "US REITs": (y["10Y"] + a["reit_premium"], "10Y yield + 3% real-estate premium"),
        "Gold": (breakeven, "keeps pace with expected inflation (no income)"),
        "Cash (T-bills)": (y["3M"], "3-month T-bill yield"),
    }
    cma = pd.DataFrame([{"sleeve": k, "ticker": SLEEVES[k][0], "group": SLEEVES[k][1], "expected_return": v[0],
                         "method": v[1]} for k, v in rows.items()])
    cma.attrs["inflation"] = breakeven
    return cma


def sleeve_covariance(base: Path = BASE_DIR) -> pd.DataFrame:
    prices = pd.read_csv(base / "day76c_price_history.csv", index_col=0, parse_dates=True)
    tickers = [SLEEVES[s][0] for s in SLEEVES]
    returns = prices[[t for t in tickers if t in prices]].pct_change(fill_method=None).iloc[1:].dropna(how="all")
    returns = returns.fillna(0.0).tail(252)
    cov, _ = constant_correlation_shrinkage(returns.to_numpy())
    names = [s for s in SLEEVES if SLEEVES[s][0] in returns.columns]
    cov = cov * 252
    sample_vol = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sample_vol, sample_vol)
    vol = np.array([VOL_BLEND * LONG_RUN_VOL[n] + (1 - VOL_BLEND) * v for n, v in zip(names, sample_vol)])
    out = pd.DataFrame(corr * np.outer(vol, vol), index=names, columns=names)
    out.attrs["sample_vol"] = dict(zip(names, sample_vol))
    return out


def optimize_allocation(mu: pd.Series, cov: pd.DataFrame, target_vol: float, max_equity: float, min_cash: float,
                        excluded: Optional[List[str]] = None, min_fixed_income: float = 0.0,
                        max_alternatives: float = MAX_ALTERNATIVES) -> pd.Series:
    """Maximize expected return subject to volatility ≤ target and asset-class limits."""
    names = [s for s in cov.index if s not in (excluded or [])]
    m, S = mu.reindex(names).to_numpy(), cov.loc[names, names].to_numpy()
    group = np.array([SLEEVES[s][1] for s in names])
    eq, fi, alt = (group == "Equity").astype(float), (group == "Fixed income").astype(float), \
        (group == "Alternatives").astype(float)
    cash = np.array([s == "Cash (T-bills)" for s in names], dtype=float)
    hy = np.array([s == "High-yield credit" for s in names], dtype=float)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1},
            {"type": "ineq", "fun": lambda w: target_vol ** 2 - w @ S @ w},
            {"type": "ineq", "fun": lambda w: max_equity - eq @ w},
            {"type": "ineq", "fun": lambda w: cash @ w - min_cash},
            {"type": "ineq", "fun": lambda w: fi @ w + cash @ w - min_fixed_income},
            {"type": "ineq", "fun": lambda w: max_alternatives - alt @ w},
            {"type": "ineq", "fun": lambda w: MAX_HIGH_YIELD - hy @ w}]
    start = np.full(len(names), 1 / len(names))
    result = minimize(lambda w: -(m @ w), start, jac=lambda w: -m, method="SLSQP",
                      bounds=[(0, min(MAX_SLEEVE, SLEEVE_MAX.get(n, MAX_SLEEVE))) for n in names], constraints=cons,
                      options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(result.x, 0, None)
    w[w < 0.005] = 0
    return pd.Series(w / w.sum(), index=names).reindex(cov.index).fillna(0.0)


def portfolio_stats(w: pd.Series, mu: pd.Series, cov: pd.DataFrame) -> Dict[str, float]:
    w = w.reindex(cov.index).fillna(0.0)
    vol = math.sqrt(float(w @ cov @ w))
    expected = float(w @ mu.reindex(cov.index))
    group = pd.Series({s: SLEEVES[s][1] for s in cov.index})
    return {"expected_return": expected, "volatility": vol, "bad_year_loss": max(0.0, 1.645 * vol - expected),
            "equity_share": float(w[group == "Equity"].sum()), "cash_share": float(w.get("Cash (T-bills)", 0.0)),
            "fixed_income_share": float(w[group == "Fixed income"].sum()),
            "alternatives_share": float(w[group == "Alternatives"].sum())}


def retail_profile(client: dict) -> dict:
    """Willingness and capacity scores (1–5); the profile is the lower of the two."""
    willingness = round((LOSS_SCORE[client["loss_reaction"]] * 2 + EXPERIENCE_SCORE[client["experience"]]) / 3)
    horizon = client["horizon_years"]
    horizon_score = 1 if horizon < 3 else 2 if horizon < 7 else 3 if horizon < 12 else 4 if horizon < 20 else 5
    income = INCOME_SCORE.get(client.get("income_stability"), 3)
    withdrawal_rate = client.get("annual_withdrawal", 0) / max(client["wealth"], 1)
    liquidity = 1 if withdrawal_rate > 0.08 else 3 if withdrawal_rate > 0.04 else 5
    capacity = round((horizon_score * 2 + income + liquidity) / 4)
    profile = int(max(1, min(5, min(willingness, capacity))))
    note = ("Willingness and capacity agree." if willingness == capacity else
            f"Willingness {willingness} vs capacity {capacity}: the lower sets the profile; discuss the gap with the client.")
    return {"willingness": willingness, "capacity": capacity, "profile": profile, "profile_note": note,
            "loss_tolerance": LOSS_TOLERANCE[client["loss_reaction"]]}


def institutional_profile(client: dict, inflation: float) -> dict:
    ips = client["ips"]
    required = ips.get("required_return",
                       ips.get("spending_rate", 0) + inflation + ips.get("cost_rate", 0))
    profile = max(k for k, p in PROFILES.items() if p["target_vol"] <= ips["max_volatility"] + 1e-9)
    return {"willingness": None, "capacity": None, "profile": profile, "required_return": required,
            "loss_tolerance": ips["max_bad_year_loss"],
            "profile_note": f"Set by the IPS: volatility at most {ips['max_volatility']:.0%}; required return "
                            f"{required:.2%} (spending/liabilities + inflation + costs)."}


def recommend(client: dict, profile: dict, mu: pd.Series, cov: pd.DataFrame) -> pd.Series:
    p = PROFILES[profile["profile"]]
    if client["type"] == "institutional":
        ips = client["ips"]
        return optimize_allocation(mu, cov, min(p["target_vol"], ips["max_volatility"]), p["max_equity"],
                                   max(p["min_cash"], ips.get("liquidity_need_12m", 0) / client["wealth"]),
                                   ips.get("excluded_sleeves"), ips.get("min_fixed_income", 0.0),
                                   ips.get("max_alternatives", MAX_ALTERNATIVES))
    liquidity = client.get("liquidity_need_12m", 0) / max(client["wealth"], 1)
    max_equity = min(p["max_equity"], 0.20 if client["horizon_years"] < 3 else 1.0)
    # Suitability by design: complex holdings only for experienced investors
    excluded = [s for s in SLEEVES if SLEEVES[s][2] == "complex"] if client.get("experience") != "Extensive" else []
    return optimize_allocation(mu, cov, p["target_vol"], max_equity, max(p["min_cash"], min(liquidity, 0.5)),
                               excluded)


# ==============================================================
# DAY 83 — SUITABILITY
# ==============================================================

def suitability(client: dict, profile: dict, weights: pd.Series, mu: pd.Series, cov: pd.DataFrame) -> pd.DataFrame:
    stats = portfolio_stats(weights, mu, cov)
    p = PROFILES[profile["profile"]]
    rules = []

    def rule(name, passed, severity, detail, basis="CFA Standard III(C) Suitability"):
        rules.append({"client_id": client["client_id"], "rule": name, "passed": bool(passed),
                      "severity": "ok" if passed else severity, "detail": detail, "basis": basis})

    max_vol = client["ips"]["max_volatility"] if client["type"] == "institutional" else p["target_vol"]
    rule("Volatility within the risk profile", stats["volatility"] <= max_vol * 1.05 + 1e-9, "block",
         f"{stats['volatility']:.1%} vs limit {max_vol:.1%}")
    rule("A 1-in-20 bad year within loss tolerance", stats["bad_year_loss"] <= profile["loss_tolerance"] + 1e-9,
         "block", f"possible loss {stats['bad_year_loss']:.0%} vs tolerance {profile['loss_tolerance']:.0%}")
    horizon_cap = 0.20 if client["horizon_years"] < 3 else 1.0
    rule("Equity share suits the horizon and profile",
         stats["equity_share"] <= min(p["max_equity"], horizon_cap) + 1e-6, "review",
         f"equity {stats['equity_share']:.0%} vs cap {min(p['max_equity'], horizon_cap):.0%} "
         f"({client['horizon_years']}-year horizon)")
    rule("No single sleeve above 60%", weights.max() <= MAX_SLEEVE + 1e-6, "review",
         f"largest {weights.idxmax()} {weights.max():.0%}")
    complex_weight = sum(w for s, w in weights.items() if w > 0 and (s not in SLEEVES or SLEEVES[s][2] == "complex"))
    experienced = client["type"] == "institutional" or client.get("experience") == "Extensive"
    rule("Complex or speculative holdings only for experienced investors",
         complex_weight <= (MAX_HIGH_YIELD if experienced else 0.05) + 1e-6, "review",
         f"complex holdings {complex_weight:.0%}; experience {client.get('experience', 'institutional')}")
    need = (client["ips"].get("liquidity_need_12m", 0) if client["type"] == "institutional"
            else client.get("liquidity_need_12m", 0)) / client["wealth"]
    rule("Cash covers the next 12 months' needs", stats["cash_share"] + 1e-6 >= min(need, 0.5), "review",
         f"cash {stats['cash_share']:.1%} vs need {need:.1%}")
    if client["type"] == "institutional":
        ips = client["ips"]
        held_excluded = [s for s in ips.get("excluded_sleeves", []) if weights.get(s, 0) > 0]
        rule("IPS exclusions respected", not held_excluded, "block",
             "none held" if not held_excluded else ", ".join(held_excluded), "Investment policy statement")
        rule("IPS minimum fixed income", stats["fixed_income_share"] + stats["cash_share"]
             >= ips.get("min_fixed_income", 0) - 1e-6, "block",
             f"{stats['fixed_income_share'] + stats['cash_share']:.0%} vs minimum {ips.get('min_fixed_income', 0):.0%}",
             "Investment policy statement")
        rule("IPS maximum alternatives", stats["alternatives_share"] <= ips.get("max_alternatives", 1) + 1e-6,
             "block", f"{stats['alternatives_share']:.0%} vs maximum {ips.get('max_alternatives', 1):.0%}",
             "Investment policy statement")
        required = profile["required_return"]
        rule("Expected return meets the return objective", stats["expected_return"] >= required - 1e-9, "review",
             f"expected {stats['expected_return']:.2%} vs required {required:.2%}"
             + ("" if stats["expected_return"] >= required else ": discuss lowering spending or accepting more risk"),
             "Investment policy statement")
    return pd.DataFrame(rules)


def suitability_verdict(results: pd.DataFrame) -> str:
    if (results["severity"] == "block").any():
        return "NOT SUITABLE"
    if (results["severity"] == "review").any():
        return "REVIEW REQUIRED"
    return "SUITABLE"


# ==============================================================
# DAY 84 — MONTE CARLO GOALS
# ==============================================================

def simulate_wealth(wealth: float, contribution: float, withdrawal: float, years: int, mu: float, sigma: float,
                    inflation: float, paths: int = 10_000, seed: int = 7) -> np.ndarray:
    """Real (today's money) wealth paths, shape (paths, years + 1); flows grow with inflation."""
    rng = np.random.default_rng(seed)
    s2 = math.log(1 + sigma ** 2 / (1 + mu) ** 2)            # lognormal matching mean and variance
    m = math.log(1 + mu) - s2 / 2
    growth = np.exp(m + math.sqrt(s2) * rng.standard_normal((paths, years)))
    nominal = np.empty((paths, years + 1))
    nominal[:, 0] = wealth
    for t in range(years):
        flow = (contribution - withdrawal) * (1 + inflation) ** (t + 1)
        nominal[:, t + 1] = np.maximum(nominal[:, t] * growth[:, t] + flow, 0.0)
    deflator = (1 + inflation) ** np.arange(years + 1)
    return nominal / deflator


def goal_probability(paths: np.ndarray, target_real: float, withdrawal: float) -> float:
    if target_real > 0:
        return float((paths[:, -1] >= target_real).mean())
    if withdrawal > 0:
        return float((paths[:, 1:] > 0).all(axis=1).mean())        # never runs out
    return float((paths[:, -1] >= paths[:, 0]).mean())


def required_contribution(client: dict, mu: float, sigma: float, inflation: float, target: float = 0.80) -> Optional[float]:
    if client.get("goal_target_real", 0) <= 0:
        return None

    def prob(c):
        paths = simulate_wealth(client["wealth"], c, client.get("annual_withdrawal", 0), client["horizon_years"],
                                mu, sigma, inflation, 4000, ASSUMPTIONS["seed"])
        return goal_probability(paths, client["goal_target_real"], 0)

    low, high = 0.0, max(client["goal_target_real"] / max(client["horizon_years"], 1), 1.0)
    if prob(high) < target:
        return None
    for _ in range(40):
        mid = (low + high) / 2
        low, high = (mid, high) if prob(mid) < target else (low, mid)
    return high


# ==============================================================
# REPORTS AND ORCHESTRATION
# ==============================================================

def client_report(client: dict, profile: dict, weights: pd.Series, stats: dict, results: pd.DataFrame,
                  goal: dict, cma: pd.DataFrame) -> str:
    verdict = suitability_verdict(results)
    lines = [f"# Investment proposal — {client['name']}", "",
             f"*Goal: {client['goal']} · Horizon: {client['horizon_years']} years · Profile: "
             f"**{PROFILES[profile['profile']]['name']}** · Suitability: **{verdict}***", "",
             "## Your risk profile", profile["profile_note"]]
    if client["type"] == "retail":
        lines.append(f"Willingness to take risk {profile['willingness']}/5, capacity {profile['capacity']}/5. "
                     f"You told us a loss of about {profile['loss_tolerance']:.0%} in a bad year is your limit.")
    lines += ["", "## Recommended mix", "| Holding | Weight | Example fund |", "|---|---:|---|"]
    lines += [f"| {s} | {w:.0%} | {SLEEVES[s][0]} |" for s, w in weights.sort_values(ascending=False).items() if w > 0]
    lines += ["", f"Expected return about **{stats['expected_return']:.1%} a year** (before inflation of about "
                  f"{cma.attrs.get('inflation', ASSUMPTIONS['default_inflation']):.1%}), with typical swings (volatility) of "
                  f"{stats['volatility']:.0%}. In a bad year (about 1 in 20) the portfolio could fall about "
                  f"**{stats['bad_year_loss']:.0%}**.", "", "## Your goal"]
    if goal["target_real"] > 0:
        lines.append(f"Chance of reaching {goal['target_real']:,.0f} (today's money) in {client['horizon_years']} years: "
                     f"**{goal['probability']:.0%}**. Median outcome {goal['median_real']:,.0f}; poor case (10th "
                     f"percentile) {goal['p10_real']:,.0f}.")
        if goal.get("required_contribution") is not None:
            lines.append(f"Saving about **{goal['required_contribution']:,.0f} a year** would raise the chance to 80%.")
    elif goal["withdrawal"] > 0:
        lines.append(f"Chance the money lasts {client['horizon_years']} years while withdrawing "
                     f"{goal['withdrawal']:,.0f} a year (rising with inflation): **{goal['probability']:.0%}**.")
    lines += ["", "## Suitability checks"] + [f"- {'✅' if r.passed else '⚠️'} {r.rule}: {r.detail} *({r.basis})*"
                                              for r in results.itertuples()]
    lines += ["", "## Important", "- Projections use assumptions (below) and 10,000 simulated market paths. They are "
              "estimates, not guarantees; real returns can be worse.",
              "- Expected returns are built from today's yields and spreads plus stated premiums; they change with "
              "markets.", "- This is a proposal for discussion. Any change requires your approval; nothing is "
              "executed automatically."]
    return "\n".join(lines)


def load_clients(path: Path = CLIENTS_FILE) -> List[dict]:
    return json.loads(Path(path).read_text())["clients"]


def run_advisory(base: Path = BASE_DIR, out_dir: Optional[Path] = None, clients: Optional[List[dict]] = None,
                 verbose: bool = True):
    out_dir = Path(out_dir or base)
    clients = clients if clients is not None else load_clients()
    cma = capital_market_assumptions(base)
    inflation = cma.attrs["inflation"]
    cov = sleeve_covariance(base)
    mu = cma.set_index("sleeve")["expected_return"]
    cma["volatility"] = cma["sleeve"].map(pd.Series(np.sqrt(np.diag(cov)), index=cov.index))
    cma["volatility_past_year"] = cma["sleeve"].map(cov.attrs.get("sample_vol", {}))
    cma["volatility_long_run"] = cma["sleeve"].map(LONG_RUN_VOL)

    allocations = []
    for level, p in PROFILES.items():
        w = optimize_allocation(mu, cov, p["target_vol"], p["max_equity"], p["min_cash"])
        allocations.append({"profile": level, "profile_name": p["name"], **w.to_dict(),
                            **portfolio_stats(w, mu, cov)})
    allocations = pd.DataFrame(allocations)

    profile_rows, rule_rows, proj_rows, goal_rows, reports = [], [], [], [], []
    for client in clients:
        profile = (retail_profile(client) if client["type"] == "retail"
                   else institutional_profile(client, inflation))
        weights = recommend(client, profile, mu, cov)
        stats = portfolio_stats(weights, mu, cov)
        results = suitability(client, profile, weights, mu, cov)
        paths = simulate_wealth(client["wealth"], client.get("annual_contribution", 0),
                                client.get("annual_withdrawal", 0), client["horizon_years"],
                                stats["expected_return"], stats["volatility"], inflation,
                                ASSUMPTIONS["simulations"], ASSUMPTIONS["seed"])
        target = client.get("goal_target_real", 0)
        goal = {"client_id": client["client_id"], "target_real": target,
                "withdrawal": client.get("annual_withdrawal", 0),
                "probability": goal_probability(paths, target, client.get("annual_withdrawal", 0)),
                "median_real": float(np.median(paths[:, -1])), "p10_real": float(np.percentile(paths[:, -1], 10)),
                "p90_real": float(np.percentile(paths[:, -1], 90)),
                "required_contribution": required_contribution(client, stats["expected_return"], stats["volatility"],
                                                               inflation)}
        for year in range(client["horizon_years"] + 1):
            column = paths[:, year]
            proj_rows.append({"client_id": client["client_id"], "year": year,
                              "p10": np.percentile(column, 10), "p50": np.percentile(column, 50),
                              "p90": np.percentile(column, 90)})
        verdict = suitability_verdict(results)
        profile_rows.append({"client_id": client["client_id"], "name": client["name"], "type": client["type"],
                             "goal": client["goal"], "horizon_years": client["horizon_years"],
                             "wealth": client["wealth"], **{k: v for k, v in profile.items()},
                             "profile_name": PROFILES[profile["profile"]]["name"], **stats,
                             **{f"w_{s}": w for s, w in weights.items()}, "suitability": verdict,
                             "approval_status": "PENDING_CLIENT_AND_ADVISOR_APPROVAL",
                             "automatic_execution_authorized_count": 0})
        rule_rows.append(results)
        goal_rows.append(goal)
        reports.append({"client_id": client["client_id"],
                        "report": client_report(client, profile, weights, stats, results, goal, cma)})

    profiles = pd.DataFrame(profile_rows)
    suit = pd.concat(rule_rows, ignore_index=True)
    projections, goals, report_table = pd.DataFrame(proj_rows), pd.DataFrame(goal_rows), pd.DataFrame(reports)
    validation = validate_advisory(cma, allocations, profiles, suit, goals)
    for key, frame in (("cma", cma), ("profiles", profiles), ("allocations", allocations), ("suitability", suit),
                       ("projections", projections), ("goals", goals), ("reports", report_table),
                       ("validation", validation)):
        frame.to_csv(out_dir / OUT[key], index=False)
    if verbose:
        print_report(cma, allocations, profiles, goals, validation)
    return {"cma": cma, "allocations": allocations, "profiles": profiles, "suitability": suit,
            "projections": projections, "goals": goals, "reports": report_table, "validation": validation}


def validate_advisory(cma, allocations, profiles, suit, goals) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add("Capital market assumptions for every sleeve", cma["expected_return"].notna().all() and len(cma) == len(SLEEVES),
        f"{len(cma)} sleeves")
    add("Model allocations fully invested", np.allclose(allocations[list(SLEEVES)].sum(axis=1), 1.0),
        "weights sum to 100%")
    add("Risk rises with the profile", allocations["volatility"].is_monotonic_increasing,
        " → ".join(f"{v:.1%}" for v in allocations["volatility"]))
    add("Allocations within target volatility", (allocations["volatility"] <= allocations["profile"].map(
        {k: p["target_vol"] for k, p in PROFILES.items()}) + 1e-4).all(), "all profiles")
    add("Every recommendation suitability-checked", set(suit["client_id"]) == set(profiles["client_id"]),
        f"{len(suit)} rule checks for {len(profiles)} clients")
    add("Probabilities between 0 and 1", goals["probability"].between(0, 1).all(), "all clients")
    add("No automatic execution", (profiles["automatic_execution_authorized_count"] == 0).all(),
        "proposals await client and advisor approval")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def print_report(cma, allocations, profiles, goals, validation) -> None:
    line = "=" * 92
    print(line)
    print("VITTANTRA — DAYS 82–84 ADVISORY (profiles · suitability · goals)")
    print(line)
    print(cma[["sleeve", "expected_return", "volatility", "method"]].to_string(
        index=False, float_format=lambda x: f"{x:.2%}"))
    print("\nModel allocations by risk profile")
    view = allocations[["profile_name", *SLEEVES, "expected_return", "volatility"]].set_index("profile_name").T
    print((view * 100).round(1).to_string())
    print("\nClients")
    print(profiles[["client_id", "profile_name", "expected_return", "volatility", "bad_year_loss", "suitability"]]
          .merge(goals[["client_id", "probability"]], on="client_id")
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDays 82–84 advisory complete. Projections are estimates, not guarantees; nothing is executed.")
    print(line)


if __name__ == "__main__":
    run_advisory()
