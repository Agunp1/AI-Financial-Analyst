"""
Day 88 — Case Studies (one per desk), generated from Vittantra's own outputs

Each case study follows the format interviewers expect — situation, task,
analysis, decision, result, what I learned — and every number is read from
the committed CSV files, so the case studies update with each data refresh
and never contain invented figures. A section whose data is missing is
skipped and listed at the end.

Output: CASE_STUDIES.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "CASE_STUDIES.md"


def _csv(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    if not path.exists():
        raise FileNotFoundError(name)
    return pd.read_csv(path)


def case_equity_research() -> str:
    v = _csv("day78_valuation.csv").dropna(subset=["implied_growth", "dcf_initial_growth"])
    r = v.loc[(v["implied_growth"] - v["dcf_initial_growth"]).idxmax()]
    ratings = _csv("day77_current_ratings.csv").set_index("ticker")
    rating = ratings.at[r["ticker"], "rating"] if r["ticker"] in ratings.index else "n/a"
    return f"""## 1. Equity research — is {r['name']} priced for perfection?

**Situation.** {r['name']} ({r['ticker']}) trades at ${r['price']:,.2f} and carries a multi-factor rating of
**{rating}**.

**Task.** Decide whether the price is supported by fundamentals, using a DCF that is transparent about its
assumptions.

**Analysis.** A three-stage FCFF DCF (WACC {r['wacc']:.1%}, terminal growth {r['terminal_growth']:.1%}) gives
**${r['dcf_value']:,.2f}** per share ({r['upside']:+.0%} vs price). The reverse DCF is more telling: the price
implies **{r['implied_growth']:.1%}** growth a year for five years, against **{r['dcf_initial_growth']:.1%}**
recent revenue growth. Terminal value is {r['dcf_terminal_share']:.0%} of the DCF, so the WACC × growth
sensitivity table matters more than the point estimate.

**Decision.** A strong rating and a demanding valuation are not a contradiction: momentum and quality can
persist while expectations are high. The note flags valuation as the key risk and names the evidence that
would change the view (growth below the implied rate).

**What I learned.** Lead with what the market already expects (reverse DCF), not with a precise target
price. *(Source: day78_valuation.csv, day77_current_ratings.csv.)*
"""


def case_signal_research() -> str:
    ic = _csv("day77_ic_summary.csv").set_index("signal")
    bt = _csv("day77_backtest_summary.csv")
    top = bt[(bt["portfolio"] == "top quintile long")].set_index("signal")
    eq, icw = ic.loc["composite"], ic.loc["composite_ic_weighted"]
    best = ic.drop(index=["composite", "composite_ic_weighted"]).dropna(subset=["mean_ic"]).sort_values(
        "mean_ic", ascending=False)
    worst = best.iloc[-1]
    return f"""## 2. Quant research — when combining signals makes things worse

**Situation.** Vittantra rates stocks on five pillars. The obvious design averages them equally.

**Task.** Test, point in time, whether each pillar predicts the next 20-day return.

**Analysis.** Information coefficients over {int(eq['dates'])} rebalance dates: best pillar
**{best.index[0]}** (IC {best.iloc[0]['mean_ic']:.3f}, t {best.iloc[0]['ic_t_stat']:.1f}); worst
**{worst.name}** (IC {worst['mean_ic']:.3f}, t {worst['ic_t_stat']:.1f}). The equal-weight composite scored IC
**{eq['mean_ic']:.3f}** — the negative pillars cancelled the good ones. Weighting pillars by their past ICs
(only completed periods, no look-ahead) gave IC **{icw['mean_ic']:.3f}** and a top-quintile Sharpe ratio of
**{top.at['composite_ic_weighted', 'sharpe_ratio']:.2f}** vs {top.at['composite', 'sharpe_ratio']:.2f} for
equal weights.

**Decision.** Ratings now use the IC-weighted composite; the equal-weight score is shown for comparison.

**What I learned.** "More factors" is not automatically better; a combination must beat its best single
input out of sample, and results are historical research, not promises. *(Source: day77_ic_summary.csv,
day77_backtest_summary.csv.)*
"""


def case_portfolio_management() -> str:
    s = _csv("day79_portfolio_summary.csv").iloc[0]
    p = _csv("day79_model_portfolio.csv")
    a = _csv("day80_attribution_summary.csv").iloc[0]
    held = p[p["weight"] > 0]
    sizeable = held[held["weight"] >= 0.03]
    surprise = (sizeable if len(sizeable) else held).sort_values("score").iloc[0]
    return f"""## 3. Portfolio management — from ratings to a portfolio that respects a risk budget

**Situation.** Ratings are not a portfolio. A PM needs position sizes that express the views without taking
unintended risk.

**Task.** Build a long-only model portfolio against an equal-weight benchmark with a 4% tracking-error budget.

**Analysis.** Scores became expected alpha with Grinold–Kahn (IC × volatility × score); risk came from a
Ledoit–Wolf shrinkage covariance; the optimizer respected position, sector, beta and risk-contribution limits.
Result: **{int(s['holdings'])} holdings**, expected active return **{s['expected_active_return']:+.1%}**,
tracking error **{s['tracking_error']:.1%}**, information ratio **{s['information_ratio']:.2f}**, beta
{s['beta_to_benchmark']:.2f}. One instructive output: **{surprise['ticker']}** is held at
{surprise['weight']:.1%} with a middling score of {surprise['score']:.0f} — the optimizer uses it to keep beta
and tracking error inside their limits.

**Result (backtest).** Brinson attribution of the research portfolio from {a['start']} to {a['end']}:
active return {a['active_cumulative']:+.1%} = allocation {a['allocation_linked']:+.1%}, selection
{a['selection_linked']:+.1%}, interaction {a['interaction_linked']:+.1%}, costs {a['costs_linked']:+.1%}.

**Decision.** The proposal goes to the approval workflow; nothing executes automatically.

**What I learned.** Always ask *why* the optimizer holds each name, and check whether returns came from the
skill you claim (selection) or from sector bets (allocation). *(Source: day79_*, day80_*.)*
"""


def case_risk() -> str:
    r = _csv("day67_portfolio_risk_dashboard.csv").iloc[0]
    m = _csv("day69_portfolio_remediation_summary.csv").iloc[0]
    approval = _csv("day70_portfolio_approval_summary.csv").iloc[0]
    return f"""## 4. Portfolio risk — a leveraged position that blows through its budget

**Situation.** The monitored multi-asset portfolio shows status **{r['portfolio_status']}**.

**Task.** Find what drives the risk and propose a fix that never increases modeled risk.

**Analysis.** Euler risk contributions (each position's share of portfolio volatility from the covariance
matrix) and delta-adjusted option exposure showed the maximum risk-budget utilization at
**{m['maximum_current_risk_budget_utilization']:.0%}** — a small premium can control a large notional.
Remediation targets bring the highest utilization to
**{m['maximum_estimated_post_remediation_utilization']:.0%}**, cutting total modeled portfolio risk by
{m['portfolio_modeled_risk_reduction_fraction']:.0%}.

**Decision.** Workflow status **{approval['portfolio_workflow_status']}**, with
{int(approval['risk_reduction_ticket_count'])} risk-reduction tickets and automatic execution
{int(approval['automatic_execution_authorized_count'])}.

**What I learned.** Measure option risk by delta-adjusted exposure, not premium; risk shares do not scale
linearly, so cut and recompute. *(Source: day67_*, day69_*, day70_*.)*
"""


def case_advisory() -> str:
    p = _csv("day82_client_profiles.csv")
    g = _csv("day84_goal_summary.csv").set_index("client_id")
    rules = _csv("day83_suitability_results.csv")
    r = p[p["type"] == "retail"].sort_values("willingness").iloc[0]
    goal = g.loc[r["client_id"]]
    checks = rules[rules["client_id"] == r["client_id"]]
    return f"""## 5. Advisory — matching a portfolio to a person (fictional sample client)

**Situation.** {r['name']}: goal "{r['goal']}", {int(r['horizon_years'])}-year horizon.

**Task.** Recommend a suitable allocation and say honestly how likely the goal is.

**Analysis.** The questionnaire scored willingness {r['willingness']:.0f}/5 and capacity {r['capacity']:.0f}/5;
the profile is the lower — **{r['profile_name']}**. The recommended mix has expected return
**{r['expected_return']:.1%}** and volatility **{r['volatility']:.1%}**; a 1-in-20 bad year is about
−{r['bad_year_loss']:.0%}. Suitability checks: {int(checks['passed'].sum())} of {len(checks)} passed → **{r['suitability']}**.
Monte Carlo (10,000 paths, today's money): **{goal['probability']:.0%}** chance of success; median
{goal['median_real']:,.0f}, poor case {goal['p10_real']:,.0f}.

**Decision.** A written proposal with the reasoning, the risks and the assumptions, awaiting client and
advisor approval.

**What I learned.** Suitability is documented reasoning (CFA Standard III(C)), and probabilities communicate
uncertainty better than one projected number. *(Source: day82_*, day83_*, day84_*.)*
"""


CASES: List[Callable[[], str]] = [case_equity_research, case_signal_research, case_portfolio_management,
                                  case_risk, case_advisory]


def build_case_studies() -> str:
    parts, missing = [], []
    for case in CASES:
        try:
            parts.append(case())
        except (FileNotFoundError, KeyError, IndexError, ValueError) as error:
            missing.append(f"{case.__name__.replace('case_', '').replace('_', ' ')} ({error})")
    header = ("# Vittantra case studies\n\n*Generated from Vittantra's committed outputs by `case_studies.py` — "
              "every number below comes from a data file and updates with each refresh. Backtests are historical "
              "research results, not promises; sample clients are fictional.*\n")
    text = header + "\n" + "\n".join(parts)
    if missing:
        text += "\n---\nNot generated (data missing): " + "; ".join(missing) + "\n"
    return text


if __name__ == "__main__":
    text = build_case_studies()
    OUTPUT.write_text(text, encoding="utf-8")
    print(text[:1500])
    print(f"\nWrote {OUTPUT.name}. Day 88 case studies complete.")
