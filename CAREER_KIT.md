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
| PE / VC (small fund) | Deal screening, term sheets, exit waterfall, LBO, fund math (Academy → Private Equity / VC desk) | Burn multiple; VC method; pre/post-money and option-pool shuffle; 1× non-participating preference; power law and "return the fund"; MOIC/IRR |

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

## 5. For your VC / PE analyst role

Practise daily on Academy → **Private Equity / Venture Capital Analyst**:
screen the five fictional deals (Monday deal flow), check a term sheet, run a
quick LBO, then answer one **mock interview** question out loud. The question
bank covers "why VC", "pitch me a startup", sourcing, unit economics,
dilution, liquidation preferences, the power law, LBOs and TVPI/DPI. Answer in
your own words about your own firm's strategy — the desk uses a generic small
fund, not your employer's real process.

You already work at a small VC firm, so use the desk as rehearsal for real
work: practise the screening rubric before partner meetings, rebuild a term
sheet or waterfall by hand for a deal you actually see, and keep confidential
deal information out of Vittantra (it stays on fictional cases and public data).

## 6. Show, don't tell

- Open the live app at <https://vittantra.streamlit.app> and run the **guided tour** on the
  Home page in 5 minutes.
- Bring two printed pages: one research note (Research → Valuation & reports →
  download) and one client proposal (Advisory → Clients → download).
- Mention the **300+ automated tests**, including one test per non-negotiable
  rule (`test_governance_rules.py`).

## 7. Resume and LinkedIn

**Resume — Projects section** (pick 3–4 bullets for a one-page resume; for
VC/PE roles lead with valuation and the PE/VC desk)

**Vittantra — Investment Research & Portfolio Intelligence Platform** ·
vittantra.streamlit.app · github.com/Agunp1/AI-Financial-Analyst

- Designed and launched a multi-desk investment platform (equity research,
  portfolio management, risk, advisory, PE/VC) on free public data (SEC EDGAR,
  FRED, Yahoo Finance), refreshed automatically during the day.
- Built point-in-time fundamentals for 4,000+ US-listed companies and a
  five-factor stock rating weighted by information-coefficient (IC) tests,
  free of look-ahead bias.
- Implemented FCFF DCF, residual income, DDM and reverse DCF valuation with
  evidence-linked research notes for any US company on demand.
- Built portfolio construction (Grinold–Kahn alpha, shrinkage covariance, 4%
  tracking-error budget) and Brinson–Fachler performance attribution.
- Built a multi-asset risk engine (200+ instruments): VaR/ES with backtests,
  macro stress tests, Euler risk budgets and a dual-approval remediation
  workflow with zero automatic execution.
- Built an advisory module (risk questionnaire, IPS, CFA Standard III(C)
  suitability, Monte Carlo goal planning) and a learn-by-doing Academy for
  6 finance roles, used to study for CFA Level II.
- 300+ automated tests including one per governance rule; Python, pandas,
  Streamlit, GitHub Actions; AI coding assistant used as pair programmer.

**LinkedIn**

- Featured: the live app link, titled "Vittantra — investment research & risk
  platform (live)", with a Home page screenshot.
- Projects: the first three resume bullets.
- Launch post (edit into your own voice):

> Over the past 90 days I built **Vittantra**, an investment research and
> portfolio platform that runs entirely on free public data.
>
> It rates US stocks on five factors and tests which ones actually predict
> returns, values companies with DCF and residual-income models, builds a
> risk-budgeted portfolio, stress-tests it across asset classes, and checks
> every piece of advice for suitability. Nothing trades without human approval.
>
> What I learned: combining signals can make things worse. My equal-weight
> score had a *negative* information coefficient, so I switched to weighting
> each factor by its past predictive power, using only data available at the
> time.
>
> I designed it and checked every result, and used an AI coding assistant to
> write much of the code. I've also used it to practise the analyst, PM, risk
> and advisory roles alongside CFA Level II.
>
> Try it: vittantra.streamlit.app (research and education only, not
> investment advice)

**Before sharing**

- Never post screenshots of Streamlit Secrets, token pages or `.env`.
- Keep employer deals and internal process out of posts and the app.
- Describe what it does; keep "inspired by platforms such as Aladdin" for
  conversation rather than writing.
- Clear any pending remediation so the Command Center shows NORMAL, and open
  the app a minute before a demo (free apps sleep; first load ~30 seconds).
