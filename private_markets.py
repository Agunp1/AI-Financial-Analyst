"""
Day 91 — Private Markets Desk (venture capital and private equity)

The toolkit an analyst at a small VC / PE firm uses every week, plus a deal
simulator for practice. Deals are fictional; public comparables come from
Vittantra's real SEC data.

Venture capital
    VC method          post-money = exit value × retention / target multiple
    Round mechanics    pre/post-money, price per share, option-pool shuffle
    Cap table          ownership after each round (dilution)
    Exit waterfall     1x non-participating (or participating) preferences
    Unit economics     LTV, CAC payback, LTV/CAC, burn multiple, Rule of 40
    Fund math          power-law portfolio simulation: TVPI, fund returners

Private equity
    LBO                entry/exit multiples, leverage, debt paydown from FCF
    Returns            MOIC, IRR, value-creation bridge
                       (EBITDA growth, multiple change, deleveraging)

The small-fund setting (SMALL_FUND) is an illustrative early-stage fund, not
any real firm. Outputs: day91_public_comps.csv, day91_sample_deals.csv,
day91_validation_summary.csv.
"""

from __future__ import annotations

import math
import random
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

# An illustrative small early-stage fund (fictional)
SMALL_FUND = {
    "name": "your fund (illustrative)",
    "fund_size": 30_000_000,
    "team": "2 partners, 1 principal, 1 analyst (you)",
    "stage": "Seed to Series A",
    "check_range": (250_000, 1_000_000),
    "initial_check": 600_000,
    "target_deals": 25,
    "reserve_ratio": 0.40,          # share of the fund kept for follow-on rounds
    "entry_ownership": 0.08,
    "management_fee": 0.02,
    "carry": 0.20,
    "target_net_multiple": 3.0,
}

# Illustrative venture outcome distribution (multiple of capital invested in a deal)
POWER_LAW = [(0.0, 0.50), (1.0, 0.20), (3.0, 0.15), (10.0, 0.10), (30.0, 0.04), (100.0, 0.01)]


# ==============================================================
# VENTURE CAPITAL
# ==============================================================

def vc_method(exit_value: float, target_multiple: float, investment: float, retention: float = 1.0) -> Dict[str, float]:
    """VC method: value today = exit value × retention ÷ target multiple; ownership = investment ÷ post."""
    post = exit_value * retention / target_multiple
    return {"post_money": post, "pre_money": post - investment, "ownership_needed": investment / post,
            "ownership_at_exit": investment / post * retention}


def required_exit(post_money: float, target_multiple: float, retention: float = 1.0) -> float:
    """Exit value needed to earn the target multiple at this post-money (VC method in reverse)."""
    return post_money * target_multiple / retention


def target_multiple_from_irr(irr: float, years: float) -> float:
    return (1 + irr) ** years


def priced_round(pre_money: float, investment: float, shares_pre: float, pool_top_up: float = 0.0) -> Dict[str, float]:
    """
    Priced equity round. `pool_top_up` is new option-pool shares as a share of
    the POST-money fully diluted count, created before the round (the
    "option-pool shuffle": the pool dilutes existing holders, not the investor).
    """
    post = pre_money + investment
    investor_pct = investment / post
    # Post-money count N: investor_pct × N new shares, pool_top_up × N pool shares, shares_pre existing
    total = shares_pre / (1 - investor_pct - pool_top_up)
    new_shares = investor_pct * total
    pool_shares = pool_top_up * total
    price = investment / new_shares
    return {"price_per_share": price, "new_shares": new_shares, "pool_shares": pool_shares,
            "post_shares": total, "investor_ownership": investor_pct,
            "effective_pre_money": price * shares_pre}


def cap_table(founder_shares: float, rounds: List[dict]) -> pd.DataFrame:
    """Ownership after each round. rounds: [{name, pre_money, investment, pool_top_up}]."""
    holders = {"Founders": founder_shares}
    rows = [{"after": "Founding", **{k: 1.0 for k in holders}}]
    for r in rounds:
        shares_pre = sum(holders.values())
        result = priced_round(r["pre_money"], r["investment"], shares_pre, r.get("pool_top_up", 0.0))
        holders["Option pool"] = holders.get("Option pool", 0.0) + result["pool_shares"]
        holders[r["name"]] = result["new_shares"]
        total = sum(holders.values())
        rows.append({"after": r["name"], **{k: v / total for k, v in holders.items()},
                     "price_per_share": result["price_per_share"], "post_money": r["pre_money"] + r["investment"]})
    return pd.DataFrame(rows).fillna(0.0)


def waterfall(exit_value: float, preferred: List[dict], common_shares: float) -> pd.DataFrame:
    """
    Exit proceeds by class. preferred: [{name, invested, shares, multiple (1.0), participating (False)}],
    paid in order of seniority given (most senior first). Non-participating holders take the greater of
    their preference or converting to common; the choice is solved by iteration.
    """
    convert = {p["name"]: False for p in preferred}
    for _ in range(len(preferred) + 2):
        remaining = exit_value
        payout = {}
        for p in preferred:
            if p.get("participating") or not convert[p["name"]]:
                pref = min(remaining, p["invested"] * p.get("multiple", 1.0))
                payout[p["name"]] = pref
                remaining -= pref
        sharers = common_shares + sum(p["shares"] for p in preferred
                                      if convert[p["name"]] or p.get("participating"))
        per_share = remaining / sharers if sharers else 0.0
        for p in preferred:
            if convert[p["name"]] or p.get("participating"):
                payout[p["name"]] = payout.get(p["name"], 0.0) + p["shares"] * per_share
        common = common_shares * per_share
        changed = False
        for p in preferred:
            if p.get("participating"):
                continue
            as_common = p["shares"] * (exit_value / (common_shares + sum(q["shares"] for q in preferred)))
            should = as_common > p["invested"] * p.get("multiple", 1.0)
            if should != convert[p["name"]]:
                convert[p["name"]], changed = should, True
        if not changed:
            break
    rows = [{"class": p["name"], "proceeds": payout[p["name"]], "converted": convert[p["name"]],
             "multiple_on_invested": payout[p["name"]] / p["invested"]} for p in preferred]
    rows.append({"class": "Common (founders, employees)", "proceeds": common, "converted": None,
                 "multiple_on_invested": None})
    return pd.DataFrame(rows)


def unit_economics(arpu_month: float, gross_margin: float, monthly_churn: float, cac: float,
                   net_new_arr: Optional[float] = None, net_burn: Optional[float] = None) -> Dict[str, float]:
    ltv = arpu_month * gross_margin / monthly_churn if monthly_churn > 0 else float("inf")
    out = {"ltv": ltv, "ltv_to_cac": ltv / cac if cac else float("inf"),
           "cac_payback_months": cac / (arpu_month * gross_margin) if arpu_month * gross_margin else float("inf"),
           "customer_lifetime_months": 1 / monthly_churn if monthly_churn else float("inf")}
    if net_new_arr and net_burn is not None:
        out["burn_multiple"] = net_burn / net_new_arr
    return out


def rule_of_40(growth: float, profit_margin: float) -> float:
    return growth + profit_margin


def simulate_fund(fund_size: float = SMALL_FUND["fund_size"], n_deals: int = SMALL_FUND["target_deals"],
                  outcomes=POWER_LAW, fee_drag: float = 0.20, sims: int = 20_000, seed: int = 7) -> Dict[str, object]:
    """Power-law portfolio: gross multiple = mean of deal outcomes on invested capital; net after fees/carry."""
    rng = np.random.default_rng(seed)
    multiples, probs = np.array([m for m, _ in outcomes]), np.array([p for _, p in outcomes])
    draws = rng.choice(multiples, size=(sims, n_deals), p=probs / probs.sum())
    invested = fund_size * (1 - fee_drag)                       # fees and expenses over the fund's life
    gross = draws.mean(axis=1) * invested
    profit = np.maximum(gross - fund_size, 0)
    net_tvpi = (gross - SMALL_FUND["carry"] * profit) / fund_size
    top_share = draws.max(axis=1) / np.maximum(draws.sum(axis=1), 1e-9)
    return {"net_tvpi": net_tvpi, "median_net_tvpi": float(np.median(net_tvpi)),
            "p_lose_money": float((net_tvpi < 1).mean()), "p_3x": float((net_tvpi >= 3).mean()),
            "median_top_deal_share": float(np.median(top_share)),
            "fund_returner_exit": fund_size / SMALL_FUND["entry_ownership"] / 0.6}   # ~40% dilution to exit


def irr(cashflows: List[float]) -> float:
    """IRR by bisection on annual cash flows (first is negative)."""
    def npv(r):
        return sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
    low, high = -0.99, 10.0
    if npv(low) * npv(high) > 0:
        return float("nan")
    for _ in range(200):
        mid = (low + high) / 2
        if npv(low) * npv(mid) <= 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


# ==============================================================
# PRIVATE EQUITY — LBO
# ==============================================================

def lbo(entry_ebitda: float, entry_multiple: float, debt_multiple: float, interest_rate: float,
        ebitda_growth: float, years: int, exit_multiple: float, fcf_conversion: float = 0.5,
        tax_rate: float = 0.25, fees: float = 0.02) -> Dict[str, object]:
    """
    Simple LBO: free cash flow (after interest and tax) repays debt each year.
        FCF_t = (EBITDA_t × conversion − interest_t) × (1 − tax on the interest-adjusted part)
    Simplified: unlevered cash = EBITDA × conversion; levered FCF = unlevered − interest × (1 − tax).
    """
    entry_ev = entry_ebitda * entry_multiple
    debt = entry_ebitda * debt_multiple
    equity = entry_ev * (1 + fees) - debt
    rows, ebitda = [], entry_ebitda
    for t in range(1, years + 1):
        ebitda *= 1 + ebitda_growth
        interest = debt * interest_rate
        fcf = ebitda * fcf_conversion - interest * (1 - tax_rate)
        paydown = min(max(fcf, 0.0), debt)
        debt -= paydown
        rows.append({"year": t, "ebitda": ebitda, "interest": interest, "fcf": fcf, "debt_paydown": paydown,
                     "debt_end": debt})
    exit_ev = ebitda * exit_multiple
    exit_equity = exit_ev - debt
    moic = exit_equity / equity
    bridge = {"ebitda_growth": (ebitda - entry_ebitda) * entry_multiple,
              "multiple_change": (exit_multiple - entry_multiple) * ebitda,
              "debt_paydown": entry_ebitda * debt_multiple - debt,
              "fees": -entry_ev * fees}
    return {"schedule": pd.DataFrame(rows), "entry_ev": entry_ev, "entry_equity": equity, "entry_debt":
            entry_ebitda * debt_multiple, "exit_ev": exit_ev, "exit_equity": exit_equity, "moic": moic,
            "irr": moic ** (1 / years) - 1, "bridge": bridge}


# ==============================================================
# PUBLIC COMPARABLES (real Vittantra data)
# ==============================================================

def public_comps(base: Path = BASE_DIR) -> pd.DataFrame:
    """Median EV/revenue and EV/EBITDA by sector from Vittantra's SEC fundamentals (non-financials)."""
    frames = [base / "day76_us_fundamental_metrics.csv", base / "day76_fundamental_metrics.csv"]
    path = next((f for f in frames if f.exists()), None)
    if path is None:
        raise FileNotFoundError("Run `python fundamental_engine.py` for public comparables.")
    m = pd.read_csv(path)
    m = m[(m["sector"] != "Financials") & (m["enterprise_value"] > 0)]
    m = m.assign(ev_revenue=m["enterprise_value"] / m["revenue_ttm"], ev_ebitda=m["enterprise_value"] / m["ebitda_ttm"])
    m = m[(m["ev_revenue"] > 0) & (m["ev_revenue"] < 100)]
    out = m.groupby("sector").agg(companies=("ticker", "count"), median_ev_revenue=("ev_revenue", "median"),
                                  median_ev_ebitda=("ev_ebitda", lambda s: s[(s > 0) & (s < 150)].median()),
                                  median_revenue_growth=("revenue_growth", "median")).reset_index()
    out["source"] = path.name
    return out.sort_values("median_ev_revenue", ascending=False)


# ==============================================================
# DEAL SIMULATOR (fictional startups)
# ==============================================================

SECTORS = {
    "B2B SaaS": ("Information Technology", 0.78), "AI infrastructure": ("Information Technology", 0.65),
    "Fintech": ("Financials", 0.60), "Health-tech": ("Health Care", 0.62), "Climate tech": ("Industrials", 0.45),
    "Consumer subscription": ("Consumer Discretionary", 0.55), "Logistics software": ("Industrials", 0.70),
}
SYLLABLES = ["nova", "lume", "terra", "fin", "kai", "ora", "vex", "pulse", "grid", "mint", "sol", "arc", "loop", "quil"]
BENCHMARKS = {   # rough, commonly cited early-stage bars (vary by market and year)
    "Seed": {"min_arr": 0.1e6, "min_growth": 2.0, "max_burn_multiple": 3.0, "min_gm": 0.50, "max_churn": 0.04,
             "max_arr_multiple": 60},
    "Series A": {"min_arr": 1.0e6, "min_growth": 2.0, "max_burn_multiple": 2.0, "min_gm": 0.60, "max_churn": 0.025,
                 "max_arr_multiple": 35},
}


def _name(rng: random.Random) -> str:
    return (rng.choice(SYLLABLES) + rng.choice(SYLLABLES)).capitalize()


def generate_deals(day: Optional[date] = None, n: int = 5) -> List[dict]:
    """Today's inbound deals (fictional, reproducible per day)."""
    rng = random.Random((day or date.today()).toordinal() * 13 + 91)
    deals, used = [], set()
    for _ in range(n):
        name = _name(rng)
        while name in used:
            name = _name(rng)
        used.add(name)
        sector = rng.choice(list(SECTORS))
        stage = rng.choice(["Seed", "Seed", "Series A"])
        arr = rng.uniform(0.05, 0.8) * 1e6 if stage == "Seed" else rng.uniform(0.6, 4.0) * 1e6
        growth = min(6.0, max(1.05, rng.lognormvariate(math.log(1.8), 0.4)))   # ARR multiple year over year
        gm = min(0.92, max(0.25, rng.gauss(SECTORS[sector][1], 0.10)))
        churn = max(0.005, rng.gauss(0.032, 0.015))
        net_new_arr = arr - arr / growth
        burn = net_new_arr * rng.uniform(0.8, 5.0)
        raise_amount = (rng.uniform(1.5, 4.0) if stage == "Seed" else rng.uniform(6, 15)) * 1e6
        pre_money = arr * rng.uniform(15, 70) if stage == "Series A" else max(arr * rng.uniform(20, 90), 4e6)
        cash = rng.uniform(0.3, 2.5) * 1e6
        deals.append({
            "company": name, "sector": sector, "public_sector": SECTORS[sector][0], "stage": stage,
            "arr": arr, "arr_growth_multiple": growth, "gross_margin": gm, "monthly_churn": churn,
            "annual_net_burn": burn, "net_new_arr": net_new_arr, "cash": cash,
            "runway_months": cash / (burn / 12), "raise": raise_amount, "pre_money_ask": pre_money,
            "repeat_founder": rng.random() < 0.3, "domain_expert": rng.random() < 0.5,
            "customer_concentration": rng.choice(["low", "low", "medium", "high"]),
        })
    return deals


def screen_deal(deal: dict) -> Dict[str, object]:
    """Rubric a small early-stage fund might use for 'take the first meeting?' (one reasonable view)."""
    b = BENCHMARKS[deal["stage"]]
    burn_multiple = deal["annual_net_burn"] / deal["net_new_arr"] if deal["net_new_arr"] > 0 else float("inf")
    arr_multiple = deal["pre_money_ask"] / deal["arr"]
    checks = [
        ("Traction for the stage", deal["arr"] >= b["min_arr"], f"ARR ${deal['arr'] / 1e6:.2f}m vs ${b['min_arr'] / 1e6:.1f}m+"),
        ("Growth", deal["arr_growth_multiple"] >= b["min_growth"], f"{deal['arr_growth_multiple']:.1f}× year over year"),
        ("Capital efficiency (burn multiple)", burn_multiple <= b["max_burn_multiple"], f"{burn_multiple:.1f}× (net burn ÷ net new ARR)"),
        ("Gross margin", deal["gross_margin"] >= b["min_gm"], f"{deal['gross_margin']:.0%}"),
        ("Retention", deal["monthly_churn"] <= b["max_churn"], f"{deal['monthly_churn']:.1%} monthly churn"),
        ("Valuation discipline", arr_multiple <= b["max_arr_multiple"], f"ask {arr_multiple:.0f}× ARR"),
        ("Team", deal["repeat_founder"] or deal["domain_expert"],
         "repeat founder" if deal["repeat_founder"] else "domain expert" if deal["domain_expert"] else "no edge shown"),
        ("Customer concentration", deal["customer_concentration"] != "high", deal["customer_concentration"]),
    ]
    passed = sum(ok for _, ok, _ in checks)
    red_flags = [name for name, ok, _ in checks if not ok and name in ("Capital efficiency (burn multiple)", "Retention",
                                                                       "Customer concentration")]
    gates = {"Traction for the stage", "Growth", "Retention"}       # must-pass for a first meeting
    gates_ok = all(ok for name, ok, _ in checks if name in gates)
    decision = "Take meeting" if gates_ok and passed >= 6 and len(red_flags) <= 1 else "Pass"
    if deal["runway_months"] < 6:
        red_flags.append("Runway under 6 months")
    return {"decision": decision, "score": passed, "checks": checks, "red_flags": red_flags, "gates_ok": gates_ok,
            "burn_multiple": burn_multiple, "arr_multiple": arr_multiple}


# ==============================================================
# VALIDATION
# ==============================================================

def validate() -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    v = vc_method(200e6, 20, 2e6, retention=0.7)
    add("VC method textbook", abs(v["post_money"] - 7e6) < 1 and abs(v["pre_money"] - 5e6) < 1,
        "exit $200m × 70% retention ÷ 20× = $7m post; $5m pre")
    r = priced_round(8e6, 2e6, 1e6, pool_top_up=0.10)
    add("Option-pool shuffle lowers effective pre-money", r["effective_pre_money"] < 8e6 and
        abs(r["investor_ownership"] - 0.2) < 1e-12, f"effective pre ${r['effective_pre_money'] / 1e6:.1f}m")
    w = waterfall(10e6, [{"name": "Series A", "invested": 8e6, "shares": 2e6}], 8e6)
    add("1x non-participating takes preference in a low exit", abs(w.iloc[0]["proceeds"] - 8e6) < 1, "A gets $8m of $10m")
    w = waterfall(100e6, [{"name": "Series A", "invested": 8e6, "shares": 2e6}], 8e6)
    add("…and converts in a high exit", bool(w.iloc[0]["converted"]) and abs(w.iloc[0]["proceeds"] - 20e6) < 1, "A gets 20%")
    deal = lbo(10, 10, 5, 0.08, 0.05, 5, 10)
    add("LBO equity grows with EBITDA and paydown", deal["moic"] > 1 and deal["schedule"]["debt_end"].iloc[-1] < 50,
        f"MOIC {deal['moic']:.2f}×, IRR {deal['irr']:.1%}")
    add("IRR solver", abs(irr([-100, 0, 0, 0, 0, 200]) - (2 ** 0.2 - 1)) < 1e-6, "2× in 5 years = 14.9%")
    f = simulate_fund(sims=5000)
    add("Power law: top deal dominates", f["median_top_deal_share"] > 0.3, f"median top-deal share {f['median_top_deal_share']:.0%}")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


if __name__ == "__main__":
    line = "=" * 92
    print(line)
    print("VITTANTRA — DAY 91 PRIVATE MARKETS DESK (VC and PE)")
    print(line)
    try:
        comps = public_comps()
        comps.to_csv(BASE_DIR / "day91_public_comps.csv", index=False)
        print("Public comparables (median multiples, Vittantra SEC data)")
        print(comps.round(2).to_string(index=False))
    except FileNotFoundError as error:
        print(error)
    deals = generate_deals()
    table = pd.DataFrame([{**d, **{k: v for k, v in screen_deal(d).items() if k in ("decision", "score")}} for d in deals])
    table.to_csv(BASE_DIR / "day91_sample_deals.csv", index=False)
    print("\nToday's inbound deals (fictional)")
    print(table[["company", "sector", "stage", "arr", "arr_growth_multiple", "pre_money_ask", "decision"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    f = simulate_fund()
    print(f"\nSmall fund ${SMALL_FUND['fund_size'] / 1e6:.0f}m, {SMALL_FUND['target_deals']} deals: median net TVPI "
          f"{f['median_net_tvpi']:.2f}×, P(lose money) {f['p_lose_money']:.0%}, P(≥3×) {f['p_3x']:.0%}; a fund "
          f"returner needs an exit near ${f['fund_returner_exit'] / 1e6:,.0f}m")
    validation = validate()
    validation.to_csv(BASE_DIR / "day91_validation_summary.csv", index=False)
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 91 private markets desk complete. Deals are fictional practice cases.")
    print(line)
