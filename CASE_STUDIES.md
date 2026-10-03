# Vittantra case studies

*Generated from Vittantra's committed outputs by `case_studies.py` — every number below comes from a data file and updates with each refresh. Backtests are historical research results, not promises; sample clients are fictional.*

## 1. Equity research — is Walmart priced for perfection?

**Situation.** Walmart (WMT) trades at $104.29 and carries a multi-factor rating of
**Overweight**.

**Task.** Decide whether the price is supported by fundamentals, using a DCF that is transparent about its
assumptions.

**Analysis.** A three-stage FCFF DCF (WACC 9.4%, terminal growth 3.0%) gives
**$27.66** per share (-73% vs price). The reverse DCF is more telling: the price
implies **28.7%** growth a year for five years, against **6.2%**
recent revenue growth. Terminal value is 56% of the DCF, so the WACC × growth
sensitivity table matters more than the point estimate.

**Decision.** A strong rating and a demanding valuation are not a contradiction: momentum and quality can
persist while expectations are high. The note flags valuation as the key risk and names the evidence that
would change the view (growth below the implied rate).

**What I learned.** Lead with what the market already expects (reverse DCF), not with a precise target
price. *(Source: day78_valuation.csv, day77_current_ratings.csv.)*

## 2. Quant research — when combining signals makes things worse

**Situation.** Vittantra rates stocks on five pillars. The obvious design averages them equally.

**Task.** Test, point in time, whether each pillar predicts the next 20-day return.

**Analysis.** Information coefficients over 39 rebalance dates: best pillar
**fundamental** (IC 0.118, t 2.5); worst
**economic** (IC -0.120, t -1.9). The equal-weight composite scored IC
**-0.023** — the negative pillars cancelled the good ones. Weighting pillars by their past ICs
(only completed periods, no look-ahead) gave IC **0.068** and a top-quintile Sharpe ratio of
**1.35** vs 0.16 for
equal weights.

**Decision.** Ratings now use the IC-weighted composite; the equal-weight score is shown for comparison.

**What I learned.** "More factors" is not automatically better; a combination must beat its best single
input out of sample, and results are historical research, not promises. *(Source: day77_ic_summary.csv,
day77_backtest_summary.csv.)*

## 3. Portfolio management — from ratings to a portfolio that respects a risk budget

**Situation.** Ratings are not a portfolio. A PM needs position sizes that express the views without taking
unintended risk.

**Task.** Build a long-only model portfolio against an equal-weight benchmark with a 4% tracking-error budget.

**Analysis.** Scores became expected alpha with Grinold–Kahn (IC × volatility × score); risk came from a
Ledoit–Wolf shrinkage covariance; the optimizer respected position, sector, beta and risk-contribution limits.
Result: **23 holdings**, expected active return **+4.9%**,
tracking error **4.0%**, information ratio **1.22**, beta
1.10. One instructive output: **MCD** is held at
3.4% with a middling score of 40 — the optimizer uses it to keep beta
and tracking error inside their limits.

**Result (backtest).** Brinson attribution of the research portfolio from 2023-07-27 to 2026-08-07:
active return +50.5% = allocation +24.0%, selection
+17.0%, interaction +15.9%, costs -6.4%.

**Decision.** The proposal goes to the approval workflow; nothing executes automatically.

**What I learned.** Always ask *why* the optimizer holds each name, and check whether returns came from the
skill you claim (selection) or from sector bets (allocation). *(Source: day79_*, day80_*.)*

## 4. Portfolio risk — a leveraged position that blows through its budget

**Situation.** The monitored multi-asset portfolio shows status **CRITICAL**.

**Task.** Find what drives the risk and propose a fix that never increases modeled risk.

**Analysis.** Euler risk contributions (each position's share of portfolio volatility from the covariance
matrix) and delta-adjusted option exposure showed the maximum risk-budget utilization at
**700%** — a small premium can control a large notional.
Remediation targets bring the highest utilization to
**100%**, cutting total modeled portfolio risk by
59%.

**Decision.** Workflow status **AWAITING_DUAL_APPROVAL**, with
2 risk-reduction tickets and automatic execution
0.

**What I learned.** Measure option risk by delta-adjusted exposure, not premium; risk shares do not scale
linearly, so cut and recompute. *(Source: day67_*, day69_*, day70_*.)*

## 5. Advisory — matching a portfolio to a person (fictional sample client)

**Situation.** Sample client C — recent retiree drawing income: goal "Retirement income", 25-year horizon.

**Task.** Recommend a suitable allocation and say honestly how likely the goal is.

**Analysis.** The questionnaire scored willingness 2/5 and capacity 4/5;
the profile is the lower — **Moderately conservative**. The recommended mix has expected return
**7.4%** and volatility **7.5%**; a 1-in-20 bad year is about
−5%. Suitability checks: 6 of 6 passed → **SUITABLE**.
Monte Carlo (10,000 paths, today's money): **98%** chance of success; median
646,144, poor case 185,300.

**Decision.** A written proposal with the reasoning, the risks and the assumptions, awaiting client and
advisor approval.

**What I learned.** Suitability is documented reasoning (CFA Standard III(C)), and probabilities communicate
uncertainty better than one projected number. *(Source: day82_*, day83_*, day84_*.)*
