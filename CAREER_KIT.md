# Vittantra career kit — Day 89

How to talk about Vittantra in interviews, networking and applications.
Practise these out loud; replace anything that does not sound like you.

---

## 1. The pitch

**30 seconds**

> I built Vittantra, an investment research and portfolio platform that runs
> on free public data — SEC filings, FRED and market prices. It rates US
> stocks on five factors and tests which ones actually predict returns, values
> them with DCF and residual-income models, turns the ratings into a
> risk-budgeted portfolio, and checks advice for suitability. Every number is
> traceable to its source and nothing trades without human approval. I used it
> to learn the analyst, PM, risk and advisory roles by doing them, alongside
> CFA Level II.

**2 minutes** — add one story from `CASE_STUDIES.md`. The best one is
**"when combining signals makes things worse"**: the equal-weight composite had
a negative IC, so I switched to weighting pillars by their past predictive
power, using only completed periods to avoid look-ahead bias.

## 2. Be precise about how it was built

Interviewers respect honesty and will probe. A good formulation:

> I designed the project, chose the methods, made the decisions and checked
> every result; I used an AI coding assistant (Claude Code) as a pair
> programmer to write much of the code. My learning was in the finance — why
> each method is the standard, where it breaks, and how to test it.

Then prove it: explain any formula below without notes. Never claim a live
track record, real clients or real money — the results are **backtests and
fictional sample clients**.

## 3. Desk-by-desk talking points

| Desk | What you did | Method you must be able to explain |
|---|---|---|
| Investment analyst | Multi-asset monitor, economic dashboard, macro drivers, world brief | Rate beta ≈ −duration; OLS factor attribution; FX carry and covered interest parity |
| Equity research | SEC point-in-time fundamentals, five-pillar rating, valuation, evidence-linked notes | TTM = FY + YTD − prior YTD; IC and t-stat; FCFF DCF, WACC, residual income, reverse DCF |
| Portfolio management | Model portfolio within a 4% tracking-error budget; attribution | Grinold–Kahn alpha; shrinkage covariance; Brinson–Fachler; fundamental law (IR ≈ IC√breadth) |
| Portfolio risk | VaR/ES with backtests, stress tests, risk budgets, remediation | Euler risk contributions; Kupiec and Christoffersen tests; delta-adjusted option exposure |
| Advisory | Risk questionnaire, IPS, capital market assumptions, suitability, Monte Carlo | Willingness vs capacity; building-block expected returns; lognormal simulation; Standard III(C) |

## 4. Questions you will be asked (with honest answers)

**"How do you know your signals work?"**
Point-in-time information coefficients across rebalance dates, with t-stats.
The fundamental and ML pillars had t-stats above 2; the low-volatility pillar
was negative in this period. It's a short sample of 33 stocks over about
3 years, so I treat the results as evidence, not proof.

**"What is the biggest weakness of your DCF?"**
The terminal value is 55–75% of the value, and it is driven by WACC minus
growth. That's why I show a sensitivity table and lead with the reverse DCF.
Growth starts from trailing revenue rather than forecasts, and cash flows
aren't normalized for cyclicals (energy and materials are capped instead).

**"Why did your optimizer hold a stock with a mediocre score?"**
To meet the beta and tracking-error limits. A low-beta name lowers portfolio
risk, so an optimizer's output has to be questioned before it is accepted.

**"How do you avoid look-ahead bias?"**
Fundamentals are used only if filed by the analysis date. Signal weights use
only ICs whose 20-day windows have closed. The ML ranking uses walk-forward
training with a purge.

**"What would you do with better data?"**
FFO for REITs, consensus estimates for valuation, implied volatility for
options, licensed bond prices, and a larger universe to make the IC tests
statistically stronger. See `FINANCE_AUDIT.md`, *Known simplifications*.

**"Is this investment advice?"**
No. It's a research and education platform: recommendations go through an
approval workflow to a human, and automatic execution is always zero.

## 5. Show, don't tell

- Open the deployed app (see `DEPLOY.md`) and run the **guided tour** on the
  Home page in 5 minutes.
- Bring two printed pages: one research note (Research → Valuation & reports →
  download) and one client proposal (Advisory → Clients → download).
- Mention the **252+ automated tests**, including one test per non-negotiable
  rule (`test_governance_rules.py`).
