"""
Vittantra Academy — Work Desk.

Real tasks for each role, generated from Vittantra's live data, with
automatic grading where there is an objective answer and a reference
answer plus checklist where judgment is involved. Progress, XP and a work
record are saved locally in academy_progress.json.

Pure functions (no Streamlit) so the logic is testable.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from academy_live import MissingData, _csv, money, pct


BASE_DIR = Path(__file__).resolve().parent
PROGRESS_FILE = BASE_DIR / "academy_progress.json"

LEVELS = [(0, "Junior"), (300, "Analyst"), (1000, "Senior"), (2500, "Lead")]

RISK_CAP = 0.35            # single-position risk-share limit (Day 65 policy)
TURNOVER_CAP = 0.35        # one-way turnover limit (Day 65 policy)

# Long-run assumptions for the advisor desk (stated assumptions, not forecasts).
SLEEVE_RETURN = {"Stocks": 0.06, "Bonds": 0.04, "Cash": 0.03, "Alternatives": 0.05}
SLEEVE_CORR = {
    ("Stocks", "Bonds"): 0.0, ("Stocks", "Cash"): 0.0, ("Stocks", "Alternatives"): 0.6,
    ("Bonds", "Cash"): 0.0, ("Bonds", "Alternatives"): 0.2, ("Cash", "Alternatives"): 0.0,
}


def _rng(role: str, day: Optional[date] = None) -> random.Random:
    day = day or date.today()
    return random.Random(day.toordinal() * 31 + sum(map(ord, role)))


# ==============================================================
# PROGRESS / CAREER
# ==============================================================

def load_progress(path: Optional[Path] = None) -> dict:
    try:
        return json.loads(Path(path or PROGRESS_FILE).read_text())
    except Exception:
        return {"xp": {}, "records": [], "lessons_read": []}


def save_progress(progress: dict, path: Optional[Path] = None) -> None:
    Path(path or PROGRESS_FILE).write_text(json.dumps(progress, indent=2, default=str))


def record_task(progress: dict, role: str, task: str, score: float, answer: dict, review: str) -> dict:
    xp = int(round(score))
    progress.setdefault("xp", {})[role] = progress.get("xp", {}).get(role, 0) + xp
    progress.setdefault("records", []).append({
        "time": datetime.now().isoformat(timespec="minutes"), "role": role, "task": task,
        "score": round(score, 1), "xp": xp, "answer": answer, "review": review,
    })
    return progress


def level_for(xp: int) -> tuple:
    """(level name, next level name or None, XP needed for next level)."""
    current, nxt = LEVELS[0][1], None
    needed = None
    for threshold, name in LEVELS:
        if xp >= threshold:
            current = name
        elif nxt is None:
            nxt, needed = name, threshold - xp
    return current, nxt, needed


def work_record_markdown(progress: dict) -> str:
    lines = ["# Vittantra Work Record", ""]
    for role, xp in progress.get("xp", {}).items():
        lines.append(f"- **{role.replace('_', ' ').title()}**: {xp} XP — {level_for(xp)[0]}")
    lines.append("")
    for r in progress.get("records", []):
        lines += [f"## {r['time']} — {r['task']} ({r['role'].replace('_', ' ')})",
                  f"Score: {r['score']}", "", "**My work:**"]
        lines += [f"- {k}: {v}" for k, v in r["answer"].items()]
        lines += ["", "**Review:**", r["review"], ""]
    return "\n".join(lines)


# ==============================================================
# INVESTMENT ANALYST — morning brief
# ==============================================================

def morning_brief_task() -> dict:
    a = _csv("day76c_asset_analytics.csv", "multi_asset_universe.py")
    market = a[a["source"] == "Yahoo Finance"].dropna(subset=["return_1d"])
    movers = market.reindex(market["return_1d"].abs().sort_values(ascending=False).index).head(6)
    curve = _csv("day76c_yield_curve.csv", "multi_asset_universe.py")
    credit = _csv("day76c_credit_spreads.csv", "multi_asset_universe.py").set_index("segment")
    by = curve.set_index("maturity")
    snapshot = ["| Instrument | Class | 1 day | 1 month |", "|---|---|---:|---:|"]
    snapshot += [f"| {r.name} | {r.asset_class} | {pct(r.return_1d, 2)} | {pct(r.return_1m)} |"
                 for r in movers.itertuples()]
    snapshot.append(f"\n10Y Treasury **{by.loc['10Y', 'yield_pct']:.2f}%** "
                    f"({by.loc['10Y', 'change_1m_bp']:+.0f} bp in 1 month); 2s10s "
                    f"**{curve['slope_2s10s_bp'].iloc[0]:.0f} bp**; high-yield spread "
                    f"**{credit.loc['US high yield', 'spread_bp']:.0f} bp** "
                    f"({credit.loc['US high yield', 'change_1y_bp']:+.0f} bp in 1 year).")
    top = movers.iloc[0]
    reference = (f"- **{top['name']} moved {pct(top['return_1d'], 2)}** — the largest move today "
                 f"({top['asset_class']}).\n"
                 f"- Rates: 10Y at {by.loc['10Y', 'yield_pct']:.2f}% "
                 f"({by.loc['10Y', 'change_1m_bp']:+.0f} bp over the month); curve "
                 f"{'inverted' if curve['slope_3m10y_bp'].iloc[0] < 0 else 'upward-sloping'}.\n"
                 f"- Credit: high-yield spreads {credit.loc['US high yield', 'spread_bp']:.0f} bp, "
                 f"{credit.loc['US high yield', 'percentile_in_history']:.0f}th percentile of recent history.\n"
                 "- Watch: whether today's biggest mover is news-driven or part of a trend (check 1-month move).")
    news = BASE_DIR / "day78b_brief.csv"
    if news.exists():
        brief = pd.read_csv(news)
        brief = brief[brief["headline_count"] > 0].head(3)
        if len(brief):
            snapshot.append("\n**Headlines this week by theme** (possible drivers — check before you cite them)")
            snapshot += [f"- *{r.theme}* — {r.data_move}. {str(r.top_headlines).split(' || ')[0]}"
                         for r in brief.itertuples()]
    calendar_path = BASE_DIR / "day78b_calendar.csv"
    if calendar_path.exists():
        calendar = pd.read_csv(calendar_path).head(3)
        if len(calendar):
            snapshot.append("\n**Coming up:** " + "; ".join(f"{r.date} {r.event}" for r in calendar.itertuples()))
            reference = reference.replace("- Watch: ", f"- Watch: {calendar.iloc[0]['event']} on "
                                          f"{calendar.iloc[0]['date']}; and ")
    return {"context": "\n".join(snapshot), "reference": reference, "lessons": ["IA1", "IA3", "IA4", "IA6"]}


# ==============================================================
# EQUITY RESEARCHER — tear sheet
# ==============================================================

PILLARS = {"value_score": "Valuation", "growth_score": "Growth",
           "quality_score": "Quality", "financial_health_score": "Financial health"}
BANDS = ["Weak", "Average", "Strong"]


def score_band(score: float) -> str:
    return BANDS[0] if score < 33.3 else BANDS[1] if score < 66.7 else BANDS[2]


def tear_sheet_task(day: Optional[date] = None, ticker: Optional[str] = None) -> dict:
    scores = _csv("day76_fundamental_scores.csv", "fundamental_engine.py").set_index("ticker")
    metrics = _csv("day76_fundamental_metrics.csv", "fundamental_engine.py").set_index("ticker")
    scores = scores.dropna(subset=["fundamental_score"])
    ticker = ticker or _rng("equity_researcher", day).choice(sorted(scores.index))
    m, s = metrics.loc[ticker], scores.loc[ticker]

    def num(key, fmt):
        value = m.get(key)
        return "n/a" if value is None or value != value else fmt.format(value)

    context = (f"**{ticker} — {m['name']}** ({m['sector']}), market cap {money(m['market_cap'])}\n\n"
               f"| Metric | Value |\n|---|---:|\n"
               f"| P/E | {num('pe_ratio', '{:.1f}x')} |\n| Earnings yield | {pct(m['earnings_yield'])} |\n"
               f"| FCF yield | {pct(m['fcf_yield'])} |\n| Revenue growth (TTM) | {pct(m['revenue_growth'])} |\n"
               f"| EPS growth (TTM) | {pct(m['eps_growth'])} |\n| ROE | {pct(m['roe'])} |\n"
               f"| Operating margin | {pct(m['operating_margin'])} |\n| Debt / equity | {num('debt_to_equity', '{:.2f}')} |\n"
               f"| Interest coverage | {num('interest_coverage', '{:.1f}x')} |\n\n"
               "Rate each pillar **relative to the other 32 research-universe companies**.")
    answer_key = {label: score_band(s[col]) for col, label in PILLARS.items() if s[col] == s[col]}
    best = max(answer_key, key=lambda k: s[[c for c, l in PILLARS.items() if l == k][0]])
    worst = min(answer_key, key=lambda k: s[[c for c, l in PILLARS.items() if l == k][0]])
    reference = (f"Vittantra's percentile scores: " +
                 ", ".join(f"{label} {s[col]:.0f}" for col, label in PILLARS.items() if s[col] == s[col]) +
                 f"; overall **{s['fundamental_score']:.0f}/100** (rank {int(s['fundamental_rank'])}).\n\n"
                 f"Strongest pillar: **{best}**; weakest: **{worst}**. A good note leads with the strongest "
                 f"evidence and names the weakest pillar as the key risk.")
    return {"ticker": ticker, "context": context, "answer_key": answer_key, "reference": reference,
            "lessons": ["ER2", "ER3", "ER4"]}


def grade_tear_sheet(answer_key: Dict[str, str], ratings: Dict[str, str]) -> tuple:
    correct = sum(ratings.get(k) == v for k, v in answer_key.items())
    near = sum(abs(BANDS.index(ratings[k]) - BANDS.index(v)) == 1
               for k, v in answer_key.items() if k in ratings and ratings[k] != v)
    score = 100 * (correct + 0.5 * near) / max(len(answer_key), 1)
    feedback = [f"- {k}: you said **{ratings.get(k, '—')}**, data says **{v}**"
                + (" ✅" if ratings.get(k) == v else "") for k, v in answer_key.items()]
    return score, "\n".join(feedback)


def valuation_call_task(day: Optional[date] = None, ticker: Optional[str] = None) -> dict:
    """Equity researcher: estimate a DCF value from the inputs, then make the call."""
    v = _csv("day78_valuation.csv", "valuation_engine.py").dropna(subset=["dcf_value", "fcff_ttm", "wacc"])
    if v.empty:
        raise MissingData("No DCF valuations yet. Run `python valuation_engine.py`.")
    v = v.set_index("ticker")
    ticker = ticker or _rng("valuation_call", day).choice(sorted(v.index))
    r = v.loc[ticker]
    metrics = _csv("day76_fundamental_metrics.csv", "fundamental_engine.py").set_index("ticker").loc[ticker]
    debt, cash = float(metrics.get("total_debt") or 0), float(metrics.get("cash") or 0)
    debt, cash = (0.0 if debt != debt else debt), (0.0 if cash != cash else cash)
    context = (f"**{ticker} — {r['name']}**, price **${r['price']:,.2f}**\n\n"
               f"| Input | Value |\n|---|---:|\n| Free cash flow to the firm (TTM) | {money(r['fcff_ttm'])} |\n"
               f"| Growth years 1–5, then fading to terminal by year 10 | {pct(r['dcf_initial_growth'])} |\n"
               f"| Terminal growth | {pct(r['terminal_growth'])} |\n| WACC | {pct(r['wacc'])} |\n"
               f"| Debt | {money(debt)} |\n| Cash | {money(cash)} |\n"
               f"| Shares | {float(metrics['shares_outstanding']) / 1e9:,.2f}bn |\n\n"
               "Estimate the value per share (a spreadsheet or the single-stage shortcut is fine), then make your "
               "call versus the price.")
    signal = r["valuation_signal"]
    reference = (f"Vittantra's three-stage DCF: **${r['dcf_value']:,.2f}** per share ({r['upside']:+.0%} vs price) → "
                 f"**{signal}** (±15% band). Terminal value is {pct(r['dcf_terminal_share'], 0)} of the total.\n\n"
                 f"Reverse DCF: the price implies {pct(r.get('implied_growth'))} growth for five years. "
                 "A strong note argues whether that growth is achievable — that is the real debate, not the "
                 "decimal places. One reasonable view; your own forecast may differ.")
    return {"ticker": ticker, "context": context, "model_value": float(r["dcf_value"]), "signal": signal,
            "price": float(r["price"]), "reference": reference, "lessons": ["ER6", "ER7"]}


def grade_valuation_call(task: dict, estimate: float, call: str) -> tuple:
    """Half the marks for the estimate (within 10% full, within 25% half), half for the call."""
    error = abs(estimate / task["model_value"] - 1) if estimate and task["model_value"] else 1.0
    estimate_score = 50 if error <= 0.10 else 25 if error <= 0.25 else 0
    call_score = 50 if call == task["signal"] else 0
    feedback = (f"- Your value ${estimate:,.2f} vs model ${task['model_value']:,.2f} ({error:.0%} apart)"
                + (" ✅" if estimate_score == 50 else "") +
                f"\n- Your call **{call}**, model says **{task['signal']}**" + (" ✅" if call_score else ""))
    return estimate_score + call_score, feedback


# ==============================================================
# PORTFOLIO / RISK ANALYST — daily risk check, stress question
# ==============================================================

def risk_check_task() -> dict:
    b = _csv("day66_instrument_risk_budgets.csv", "run_vittantra.py")
    table = b[["symbol", "asset_class", "target_risk_weight", "instrument_risk_budget"]].copy()
    context = ["| Position | Asset class | Risk share | Risk budget |", "|---|---|---:|---:|"]
    context += [f"| {r.symbol} | {r.asset_class} | {pct(r.target_risk_weight)} | {pct(r.instrument_risk_budget)} |"
                for r in table.itertuples()]
    breaches = sorted(b.loc[b["risk_budget_status"] == "BREACH", "symbol"])
    detail = b[b["symbol"].isin(breaches)].sort_values("risk_budget_utilization", ascending=False)
    reference = "\n".join(
        f"- **{r.symbol}**: risk share {pct(r.target_risk_weight)} vs budget {pct(r.instrument_risk_budget)} "
        f"→ utilization **{pct(r.risk_budget_utilization, 0)}**" for r in detail.itertuples())
    reference += ("\n\nEscalate to the PM with the numbers, the cause (concentration / delta exposure) and a "
                  "proposed reduction — execution needs human approval.")
    return {"context": "\n".join(context), "symbols": sorted(b["symbol"]), "answer": breaches,
            "reference": reference, "lessons": ["RA5", "RA4"]}


def grade_set(answer: List[str], picked: List[str]) -> tuple:
    answer, picked = set(answer), set(picked)
    hits, false_alarms, missed = answer & picked, picked - answer, answer - picked
    score = 100 * len(hits) / max(len(answer | picked), 1)
    lines = [f"- Correctly flagged: {', '.join(sorted(hits)) or 'none'}",
             f"- Missed breaches: {', '.join(sorted(missed)) or 'none'}",
             f"- False alarms: {', '.join(sorted(false_alarms)) or 'none'}"]
    return score, "\n".join(lines)


def stress_task() -> dict:
    r = _csv("day61_scenario_ranking.csv", "run_vittantra.py")
    r = r.sort_values("loss_amount", ascending=False)
    worst = r.iloc[0]
    options = r["scenario"].tolist()
    reference = (f"Worst scenario: **{worst['scenario']}** — loss {money(worst['loss_amount'])} "
                 f"({pct(worst['portfolio_return'])}). Largest single contributor: **{worst['largest_loss_symbol']}**. "
                 "Next step in real life: show the PM how much hedging or reducing that position would save.")
    return {"scenarios": options, "symbols": sorted(_csv("day61_instrument_stress_results.csv",
                                                         "run_vittantra.py")["symbol"].unique()),
            "answer": (worst["scenario"], worst["largest_loss_symbol"]), "reference": reference,
            "lessons": ["RA3"]}


# ==============================================================
# PORTFOLIO MANAGER — interactive rebalance
# ==============================================================

def rebalance_inputs() -> dict:
    e = _csv("day64_instrument_exposures.csv", "run_vittantra.py")
    return {
        "exposures": dict(zip(e["symbol"], e["signed_notional_exposure"])),
        "capital": dict(zip(e["symbol"], e["capital_exposure"])),
        "risk_share": dict(zip(e["symbol"], e["risk_weight"])),
    }


def evaluate_rebalance(inputs: dict, cuts: Dict[str, float]) -> dict:
    """Apply % cuts, recompute Euler risk shares and turnover; check the limits."""
    from vittantra_risk_model import load_enriched_instruments, load_risk_history, portfolio_risk_shares

    instruments = load_enriched_instruments()
    history, _ = load_risk_history(instruments)
    new_exposure = {s: x * (1 - cuts.get(s, 0.0)) for s, x in inputs["exposures"].items()}
    shares, _, _ = portfolio_risk_shares(new_exposure, instruments, history=history)
    total_capital = sum(abs(v) for v in inputs["capital"].values())
    traded = sum(abs(inputs["capital"][s]) * cuts.get(s, 0.0) for s in inputs["capital"])
    turnover = traded / total_capital if total_capital else 0.0
    max_symbol = shares.idxmax()
    within_cap = shares.max() <= RISK_CAP + 1e-9
    within_turnover = turnover <= TURNOVER_CAP + 1e-9
    score = 50 * within_cap + 30 * within_turnover + 20 * (1 - min(turnover / TURNOVER_CAP, 1)) * within_cap
    return {"shares": shares, "turnover": turnover, "max_symbol": max_symbol, "max_share": float(shares.max()),
            "within_cap": within_cap, "within_turnover": within_turnover, "score": score}


# ==============================================================
# ADVISOR — client meeting
# ==============================================================

CLIENT_TEMPLATES = [
    {"name": "Priya", "age": 29, "goal": "Buy a home", "horizon": 4, "savings": 40_000, "target": 80_000,
     "annual_saving": 8_000, "income": "Stable salary", "reaction": "Worried, would probably hold"},
    {"name": "Robert", "age": 63, "goal": "Retirement income", "horizon": 2, "savings": 900_000, "target": 950_000,
     "annual_saving": 20_000, "income": "Retiring soon", "reaction": "Would sell everything"},
    {"name": "Aisha", "age": 35, "goal": "Retirement", "horizon": 25, "savings": 60_000, "target": 1_200_000,
     "annual_saving": 15_000, "income": "Stable salary", "reaction": "Would buy more"},
    {"name": "Daniel", "age": 45, "goal": "Children's university", "horizon": 10, "savings": 70_000,
     "target": 250_000, "annual_saving": 10_000, "income": "Variable (self-employed)",
     "reaction": "Worried, would probably hold"},
]
TOLERANCE_LOSS_LIMIT = {"Would sell everything": 0.10, "Worried, would probably hold": 0.20, "Would buy more": 0.30}


def client_task(day: Optional[date] = None) -> dict:
    client = dict(_rng("advisor", day).choice(CLIENT_TEMPLATES))
    return {"client": client, "lessons": ["AD1", "AD2", "AD3", "AD4"]}


def sleeve_volatility() -> Dict[str, float]:
    s = _csv("day76c_asset_class_summary.csv", "multi_asset_universe.py").set_index(["asset_class", "sub_class"])
    def get(key, default):
        try:
            return float(s.loc[key, "median_volatility"])
        except KeyError:
            return default
    return {"Stocks": get(("Equity", "US broad"), 0.16), "Bonds": get(("Fixed Income", "Aggregate ETF"), 0.06),
            "Cash": 0.005,                     # T-bills: near-zero price volatility
            "Alternatives": get(("Real Estate", "REIT ETF"), 0.18)}


def evaluate_allocation(client: dict, weights: Dict[str, float], vols: Dict[str, float]) -> dict:
    total = sum(weights.values())
    w = {k: v / total for k, v in weights.items()} if total else weights
    variance = 0.0
    names = list(w)
    for i in names:
        for j in names:
            rho = 1.0 if i == j else SLEEVE_CORR.get((i, j), SLEEVE_CORR.get((j, i), 0.0))
            variance += w[i] * w[j] * rho * vols[i] * vols[j]
    vol = math.sqrt(variance)
    expected = sum(w[k] * SLEEVE_RETURN[k] for k in w)
    bad_year = max(0.0, 1.645 * vol - expected)         # ~1-in-20 bad year (normal approximation)
    n = client["horizon"]
    projected = client["savings"] * (1 + expected) ** n + client["annual_saving"] * (((1 + expected) ** n - 1) / expected)
    checks = []
    equity_cap = 0.30 if n <= 3 else 0.60 if n <= 7 else 0.90
    checks.append(("Stock share fits the time horizon", w["Stocks"] <= equity_cap + 1e-9,
                   f"stocks {pct(w['Stocks'], 0)} vs max {pct(equity_cap, 0)} for a {n}-year horizon"))
    limit = TOLERANCE_LOSS_LIMIT[client["reaction"]]
    checks.append(("Bad-year loss within risk tolerance", bad_year <= limit + 1e-9,
                   f"1-in-20 bad year ≈ {pct(bad_year)} ({money(bad_year * client['savings'])}) vs limit {pct(limit, 0)}"))
    reserve = 0.10 if client["income"].startswith(("Variable", "Retiring")) else 0.05
    checks.append(("Liquidity reserve held in cash", w["Cash"] >= reserve - 1e-9,
                   f"cash {pct(w['Cash'], 0)} vs at least {pct(reserve, 0)}"))
    checks.append(("Plan reaches the goal (on stated assumptions)", projected >= client["target"],
                   f"projected {money(projected)} vs goal {money(client['target'])}"))
    score = 100 * sum(ok for _, ok, _ in checks) / len(checks)
    return {"weights": w, "volatility": vol, "expected_return": expected, "bad_year_loss": bad_year,
            "projected": projected, "checks": checks, "score": score}


def reference_allocation(client: dict, vols: Dict[str, float]) -> dict:
    """Highest-stock allocation (5% steps) that passes the suitability checks."""
    reserve = 0.10 if client["income"].startswith(("Variable", "Retiring")) else 0.05
    best = None
    for stocks in [x / 20 for x in range(0, 19)]:
        for alts in (0.0, 0.05, 0.10):
            bonds = 1 - stocks - alts - reserve
            if bonds < 0:
                continue
            weights = {"Stocks": stocks, "Bonds": bonds, "Cash": reserve, "Alternatives": alts}
            result = evaluate_allocation(client, weights, vols)
            suitable = all(ok for name, ok, _ in result["checks"] if not name.startswith("Plan"))
            if suitable and (best is None or result["expected_return"] > best["expected_return"]):
                best = result
    return best


# ==============================================================
# PRIVATE MARKETS ANALYST (small VC / PE fund) — fictional deals
# ==============================================================

def deal_screen_task(day: Optional[date] = None) -> dict:
    import private_markets as pm
    deals = pm.generate_deals(day)
    screens = [pm.screen_deal(d) for d in deals]
    return {"deals": deals, "screens": screens, "lessons": ["PV1", "PV2"]}


def grade_deal_screen(task: dict, decisions: Dict[str, str]) -> tuple:
    lines, correct = [], 0
    for deal, screen in zip(task["deals"], task["screens"]):
        mine = decisions.get(deal["company"])
        ok = mine == screen["decision"]
        correct += ok
        failed = [f"{name} ({detail})" for name, passed, detail in screen["checks"] if not passed]
        lines.append(f"- **{deal['company']}**: you said **{mine}**, rubric says **{screen['decision']}**"
                     + (" ✅" if ok else "") + (f" — weak points: {'; '.join(failed)}" if failed else " — clean on every check"))
    return 100 * correct / len(task["deals"]), "\n".join(lines)


def term_sheet_task(day: Optional[date] = None) -> dict:
    import private_markets as pm
    deals = pm.generate_deals(day)
    d = next((x for x in deals if x["stage"] == "Seed"), deals[0])
    post = d["pre_money_ask"] + d["raise"]
    return {"deal": d, "post_money": post, "ownership": d["raise"] / post,
            "required_exit": pm.required_exit(post, 20, 0.6), "lessons": ["PV3", "PV4", "PV5"]}


def grade_term_sheet(task: dict, post: float, ownership_pct: float, exit_value: float) -> tuple:
    def close(a, b, tol=0.05):
        return b and abs(a / b - 1) <= tol
    parts = [("Post-money", close(post, task["post_money"]), f"{task['post_money']:,.0f}"),
             ("Ownership", close(ownership_pct / 100, task["ownership"]), f"{task['ownership']:.1%}"),
             ("Required exit (20×, 60% retention)", close(exit_value, task["required_exit"], 0.10),
              f"{task['required_exit']:,.0f}")]
    score = 100 * sum(ok for _, ok, _ in parts) / len(parts)
    return score, "\n".join(f"- {'✅' if ok else '❌'} {name}: answer {value}" for name, ok, value in parts)


def lbo_task(day: Optional[date] = None) -> dict:
    import private_markets as pm
    rng = _rng("lbo", day)
    inputs = {"entry_ebitda": round(rng.uniform(5, 30)), "entry_multiple": round(rng.uniform(7, 11), 1),
              "debt_multiple": round(rng.uniform(3, 5.5), 1), "interest_rate": round(rng.uniform(0.07, 0.10), 3),
              "ebitda_growth": round(rng.uniform(0.02, 0.10), 3), "years": 5}
    inputs["exit_multiple"] = inputs["entry_multiple"]
    result = pm.lbo(inputs["entry_ebitda"] * 1e6, inputs["entry_multiple"], inputs["debt_multiple"],
                    inputs["interest_rate"], inputs["ebitda_growth"], inputs["years"], inputs["exit_multiple"])
    return {"inputs": inputs, "result": result, "lessons": ["PV6"]}


def grade_lbo(task: dict, moic: float, irr_pct: float) -> tuple:
    r = task["result"]
    ok_m = abs(moic - r["moic"]) <= 0.15 * r["moic"]
    ok_i = abs(irr_pct / 100 - r["irr"]) <= 0.03
    b = r["bridge"]
    feedback = (f"- {'✅' if ok_m else '❌'} MOIC: model {r['moic']:.2f}×\n- {'✅' if ok_i else '❌'} IRR: model "
                f"{r['irr']:.1%}\n- Value creation: EBITDA growth {money(b['ebitda_growth'])}, debt paydown "
                f"{money(b['debt_paydown'])}, multiple change {money(b['multiple_change'])}, fees {money(b['fees'])}")
    return 50 * ok_m + 50 * ok_i, feedback


# Interview bank for VC / PE analyst roles at a small fund: model answer points (one reasonable view)
INTERVIEW_BANK = [
    {"q": "Why venture capital, and why a small fund like ours?",
     "points": ["genuine curiosity about founders/startups", "specific sectors you follow", "small fund = breadth "
                "and responsibility early", "what you add: finance + analysis + your network"],
     "keywords": ["founder", "sector", "small", "responsib", "analy"]},
    {"q": "Pitch me a startup you would invest in.",
     "points": ["problem and who has it", "why now", "market size with a bottom-up estimate", "traction or proof",
                "team edge", "main risk and what would change your mind"],
     "keywords": ["problem", "market", "traction", "team", "risk", "why now"]},
    {"q": "How would you source deals for us?",
     "points": ["thesis-driven market maps", "founder and operator networks, communities", "university/accelerator "
                "pipelines", "warm intros from portfolio founders", "track it in a CRM and follow up"],
     "keywords": ["thesis", "network", "community", "portfolio", "crm"]},
    {"q": "Walk me through how you evaluate a seed-stage SaaS company.",
     "points": ["team", "market", "product/moat", "growth for the stage", "gross margin, churn, burn multiple",
                "valuation and round size vs milestones", "can it return the fund"],
     "keywords": ["team", "market", "growth", "churn", "burn", "valuation", "return the fund"]},
    {"q": "What is a burn multiple, and what LTV/CAC would you want?",
     "points": ["net burn ÷ net new ARR", "below ~1.5× strong, above ~2–3× weak", "LTV/CAC ≥ ~3", "payback "
                "< 12–18 months", "cohort data beats averages"],
     "keywords": ["net burn", "new arr", "ltv", "cac", "payback"]},
    {"q": "Explain pre-money, post-money and dilution with an example.",
     "points": ["post = pre + investment", "ownership = investment ÷ post", "option-pool shuffle lowers effective "
                "pre-money", "later rounds dilute everyone"],
     "keywords": ["post", "pre", "ownership", "option pool", "dilut"]},
    {"q": "What is a 1× non-participating liquidation preference?",
     "points": ["investor gets the greater of money back or converting", "matters in modest exits", "participating "
                "takes both", "affects founder and employee payouts"],
     "keywords": ["greater", "convert", "money back", "participating", "exit"]},
    {"q": "Why do VCs care so much about market size?",
     "points": ["power law: winners must be huge", "a deal must be able to return the fund", "exit value × "
                "ownership ≥ fund size", "small markets cap the outcome"],
     "keywords": ["power law", "return the fund", "ownership", "exit"]},
    {"q": "Walk me through a simple LBO.",
     "points": ["entry EV = EBITDA × multiple", "debt + equity", "project EBITDA and free cash flow", "repay debt",
                "exit EV − debt = equity", "MOIC and IRR; value creation bridge"],
     "keywords": ["ebitda", "multiple", "debt", "free cash flow", "moic", "irr"]},
    {"q": "Tell me about a deal you would pass on, and why.",
     "points": ["specific metric-based reason", "separate fixable from fatal issues", "what would make you look "
                "again", "pass kindly and quickly"],
     "keywords": ["churn", "growth", "valuation", "team", "again"]},
    {"q": "How would you help a portfolio company after we invest?",
     "points": ["hiring and customer intros", "fundraising prep and investor intros", "KPI dashboards and board "
                "prep", "be responsive, not intrusive"],
     "keywords": ["hiring", "customer", "fundrais", "kpi", "board"]},
    {"q": "What is TVPI vs DPI, and why do LPs care?",
     "points": ["TVPI = (distributions + NAV) ÷ paid-in", "DPI = distributions ÷ paid-in", "DPI is cash, TVPI "
                "includes marks", "J-curve early"],
     "keywords": ["tvpi", "dpi", "paid-in", "distribution", "nav"]},
]


def interview_question(day: Optional[date] = None, offset: int = 0) -> dict:
    rng = _rng("interview", day)
    order = list(range(len(INTERVIEW_BANK)))
    rng.shuffle(order)
    return INTERVIEW_BANK[order[offset % len(order)]]


def grade_interview(question: dict, answer: str) -> tuple:
    """Coach heuristic: share of key ideas mentioned (keyword match) — a prompt to reflect, not a verdict."""
    text = answer.lower()
    hits = [k for k in question["keywords"] if k in text]
    score = 100 * len(hits) / len(question["keywords"])
    missing = [k for k in question["keywords"] if k not in hits]
    feedback = (f"Covered: {', '.join(hits) or 'none of the key ideas yet'}."
                + (f" Consider adding: {', '.join(missing)}." if missing else " Strong coverage.")
                + " Length: " + ("good" if 60 <= len(answer.split()) <= 220 else "aim for 60–220 words (about 1–2 minutes spoken)") + ".")
    return score, feedback
