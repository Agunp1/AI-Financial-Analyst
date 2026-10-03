# Vittantra

### Investment research you can trust — every number traced, every decision human

Vittantra is an investment research and portfolio intelligence platform for the
five desks of an investment firm, built in 90 days on **free public data**:

| Desk | What Vittantra does |
|---|---|
| **Investment analyst** | 201 instruments across equities, rates, credit, FX, commodities, digital assets, REITs (incl. hotels and motels) and alternatives; economic dashboard; macro factor attribution; a weekly World & Markets Brief |
| **Equity research** | SEC EDGAR point-in-time fundamentals (33-stock research universe and all US-listed companies); five-pillar ratings tested with information coefficients; DCF, residual income and DDM valuation; evidence-linked research notes |
| **Portfolio management** | Model portfolio from the ratings inside a tracking-error budget; Brinson and factor attribution; what-if scenarios with live risk |
| **Portfolio risk** | Historical VaR/ES with Kupiec and Christoffersen backtests; full-revaluation stress tests; Euler risk budgets; governance, remediation and dual-approval workflow |
| **Advisory** | Retail risk questionnaire and institutional IPS; capital market assumptions; suitability checks; Monte Carlo goal planning; client reports |

On top sit a **copilot** that answers only from Vittantra's own evidence, with
citations, and an **Academy** where you learn each role by doing its daily work,
mapped to CFA Level II.

```
Free data (SEC EDGAR · FRED · Yahoo Finance · official RSS)
   → Research & valuation → Portfolio construction → Risk & attribution
   → Governance & suitability → Approval workflow → HUMAN DECISION
                                          (automatic execution = 0, always)
```

## Trust by design

- **Sourced and labelled:** every dataset is free and named in the app.
- **Point in time:** backtests only see facts filed by that date; signal weights
  only use completed periods.
- **Evidence-linked:** research claims and copilot answers cite file, field and
  value; when the data does not cover a question, Vittantra says so.
- **Textbook methods:** formulas are pinned to textbook values in
  `test_finance_formulas.py`; every method, correction and simplification is in
  [`FINANCE_AUDIT.md`](FINANCE_AUDIT.md).
- **Governed:** suitability checks for advice, risk budgets for portfolios, and
  one automated test per non-negotiable rule (`test_governance_rules.py`).
- **Never trades:** proposals wait for human approval.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run vittantra_app.py      # opens the Home page with a guided tour
python -m unittest discover -p "test_*.py"
```

The app runs on the committed `dayNN_*.csv` outputs. To refresh with live free
data (add `SEC_USER_AGENT=Your Name your@email.com` and, optionally, a free
`FRED_API_KEY` to `.env`):

```bash
python run_vittantra.py               # data → research → portfolio → advisory → risk chain
python run_vittantra.py --us-market   # also score all US-listed companies (15–30 min)
python run_vittantra.py --loop 15     # repeat every 15 minutes
```

Deploy online for free: [`DEPLOY.md`](DEPLOY.md).

## Documentation

| File | Contents |
|---|---|
| [`FINANCE_AUDIT.md`](FINANCE_AUDIT.md) | Every method, what was corrected, known simplifications |
| [`CASE_STUDIES.md`](CASE_STUDIES.md) | One case per desk, generated from current data |
| [`CAREER_KIT.md`](CAREER_KIT.md) | Pitch, talking points and interview answers |
| [`ROADMAP.md`](ROADMAP.md) | Days 75–90 plan and status |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |
| [`CLAUDE.md`](CLAUDE.md) | Module map and project rules |

---

## Build history — 90 days

### Phase 1 — Python for financial analytics (Days 1–7)
Returns, cumulative returns, volatility, Sharpe ratio, drawdowns, CAPM beta and
alpha, Monte Carlo simulation, VaR/CVaR and a first portfolio dashboard.

### Phase 2 — Portfolio & quantitative analytics (Days 8–15)
Hedge-fund database, trading-strategy analysis, portfolio optimization,
out-of-sample and rolling backtests, stress testing, risk attribution and risk
parity.

### Phase 3 — SQL & data engineering (Days 16–30)
SQLite financial database (`hedge_fund.db`), SQL window functions and CTEs for
returns, portfolio analytics, trade transactions and backtesting; rebalancing;
economic-data integration, release calendar, economic pipeline
(`economic_pipeline.py`), regime analysis and point-in-time backtesting to avoid
look-ahead bias (`economic_analytics.py`).

### Phase 4 — Vittantra dashboard & paper trading (Days 31–35)
Streamlit dashboard (`app.py`), paper-trading architecture
(`paper_orders.py`, `paper_order_form.py`, `paper_dashboard.py`) backed by
`paper_trading.db` (accounts, positions, trades, equity snapshots). Every order
passes pre-trade risk limits — maximum order value, maximum position weight,
maximum order weight and minimum cash reserve:

```
Signal → Risk Check → Order Decision
```

### Phase 5 — Risk engine & VaR validation (Days 35–44)
| Module | Purpose |
|--------|---------|
| `risk_engine.py` | Pre-trade risk limits |
| `risk_dashboard.py` | Integrated risk monitoring |
| `stress_engine.py` | Portfolio stress testing |
| `var_engine.py` | Historical VaR and Expected Shortfall |
| `var_backtesting.py` | VaR exception backtesting |
| `var_validation.py` | Kupiec POF, Christoffersen independence and conditional-coverage tests |

All covered by unit tests (`test_*.py`).

### Phase 6 — Machine-learning research (Days 46–54)
A research pipeline rather than a single model: baseline (`ml_baseline.py`),
feature engineering, target/horizon research, model comparison, walk-forward
validation, robustness and cross-security analysis, then an expanded universe
(`market_universe_ingestion.py`, `ml_expanded_universe.py`).

- Universe: **33 equities across sectors**
- Out-of-sample Random Forest pooled balanced accuracy: **52.4%**
- Random Forest above 50% balanced accuracy on **21 of 33** securities
- Benchmarked against a majority-class rule (47.4% mean) and a 20-day momentum
  rule (48.1% mean)

A modest edge, treated as a research finding, not proof of alpha.

### Phase 7 — Cross-sectional ranking, portfolios & attribution (Days 55–58)
| Day | Module | Result |
|-----|--------|--------|
| 55 | `ml_cross_sectional_ranking.py` | Up-probabilities → universe ranks, percentiles, sector ranks, score buckets |
| 56 | `ml_portfolio_backtest.py` | Quintile and long/short portfolios with transaction costs and turnover |
| 57 | `ml_portfolio_robustness.py` | Bootstrap, basket-size, cost, subperiod, sector-neutral and monotonicity tests |
| 58 | `ml_factor_attribution.py` | Factor regression to separate model information from factor exposure |

**Long/short research backtest (39 periods, Jul 2023 – Aug 2026, 10 bps per
dollar traded):**

| Strategy | Ann. return | Ann. vol | Sharpe | Sortino | Max drawdown |
|----------|-----------:|---------:|-------:|--------:|-------------:|
| Long/Short (50% long / 50% short) | 9.3% | 6.8% | 1.35 | 2.63 | −4.5% |
| Top quintile long | 24.9% | 14.4% | 1.31 | 2.51 | −8.5% |
| Equal-weight universe | 17.2% | 9.7% | 1.23 | 2.20 | −5.9% |

Sharpe and Sortino for long-only portfolios use returns in excess of the
point-in-time 3-month T-bill yield (FRED DGS3MO; 4.6% average over the
period). Long/short returns are self-financing excess returns.

- Robustness: **5 of 6 checks passed**: positive across basket sizes, in both
  sample halves, sector-neutral, with the bootstrap 95% CI above zero, and still
  positive at 50 bps costs (6.9% a year, break-even about 70 bps). The failed
  check: score buckets are not perfectly monotonic.
- Factor attribution: annualized alpha ≈ 2.4%, but **not statistically
  significant** (t = 0.40, p = 0.70) with 10 factors and 39 observations. The
  only significant exposure is value (t = 2.56). The result is a promising lead,
  not proven alpha.

### Phase 8 — Multi-asset risk architecture (Days 59–62)
| Day | Module | Purpose |
|-----|--------|---------|
| 59 | `multi_asset_risk.py` | Asset-class schema, risk-metric catalog and routing across equities, ETFs, futures, options, FX, crypto, bonds, commodities, REITs and cash |
| 60 | `unified_risk_engine.py` | Volatility, VaR/CVaR, drawdown, beta, bond duration/convexity/DV01, option Greeks, leverage |
| 61 | `cross_asset_stress.py` | Cross-asset stress scenarios; bonds and options fully revalued (shocked yield, Black-Scholes) |
| 62 | `macro_scenario_engine.py` | Macro inputs translated into asset-class and instrument shocks by regime |

### Phase 9 — Rebalancing, exposure control & risk budgeting (Days 63–67)
| Day | Module | Purpose |
|-----|--------|---------|
| 63 | `portfolio_rebalancing_engine.py` | Target-driven rebalance orders with before/after risk |
| 64 | `exposure_risk_engine.py` | Capital vs notional exposure (futures), delta-adjusted option exposure, Euler covariance risk contributions |
| 65 | `exposure_aware_rebalancer.py` | Rebalance orders within capital, gross and risk-contribution limits |
| 66 | `portfolio_risk_budgeting.py` | Risk budgets, utilization, excess and breaches |
| 67 | `portfolio_risk_monitor.py` | Consolidated portfolio risk dashboard and alerts |

### Phase 10 — Governance, remediation & approval (Days 68–70)
```
Risk detected → Governance evaluates → Remediation proposed
             → Decision ticket → Approval workflow → Human decision
```
| Day | Module | Purpose |
|-----|--------|---------|
| 68 | `portfolio_risk_governance.py` | Governance status, action and reason per instrument; flags review and blocks incremental risk |
| 69 | `portfolio_risk_remediation.py` | Modeled risk-reduction actions; validated so remediation never increases modeled risk |
| 70 | `portfolio_approval_workflow.py` | Decision tickets, risk/portfolio review, dual approval, priority queue and audit trail |

### Phase 11 — Application & AI layer (Days 71–74)
| Day | Module | Purpose |
|-----|--------|---------|
| 71 | `vittantra_app.py` | Vittantra Command Center (Streamlit) |
| 72 | `vittantra_app.py` | Portfolio intelligence: risk concentration, effective positions, governance overlays |
| 73 | `vittantra_ai_analyst.py` | Turns Days 67–70 outputs into an executive brief, risk drivers, priority queue and governance/remediation/approval interpretation |
| 74 | `vittantra_research_copilot.py` | Natural-language Q&A over Vittantra's own data: intent detection → evidence retrieval → evidence-backed answer |

The copilot answers questions such as *"Why is the portfolio critical?"*,
*"Which positions contribute the most risk?"* or *"What is the current approval
status?"* — and **says so when the data does not support an answer rather than
inventing one**.

---

### Phase 12 — Live data & one-command pipeline (Day 75)
| Module | Purpose |
|--------|---------|
| `vittantra_data_hub.py` | Free data collector (Yahoo Finance + FRED) → SQLite store, freshness checks, refresh audit log |
| `vittantra_live_inputs.py` | Feeds live prices, rates, spreads and real history into the Day 59–70 risk chain |
| `run_vittantra.py` | Runs data refresh → Days 59–70 → AI Analyst in order, on a schedule if wanted |

### Finance framework

Every core formula is checked against textbook references in
`test_finance_formulas.py`. [`FINANCE_AUDIT.md`](FINANCE_AUDIT.md) lists each
method, where it lives in the code, what was corrected and which
simplifications remain.

### Phase 13 — Research desk: fundamentals (Day 76)
| Module | Purpose |
|--------|---------|
| `fundamental_engine.py` | SEC EDGAR 10-K/10-Q data (free) → point-in-time valuation, growth, quality and financial-health metrics, percentile scores |
| `vittantra_research_page.py` | Research page in the app: ranked universe and company detail |

`us_fundamental_engine.py` applies the same engine to **every operating company
listed on NYSE, Nasdaq and NYSE American (about 6,000, including REITs)**, using
SEC XBRL frames (one request per line item and period for all companies),
SEC industry codes mapped to sectors, Yahoo prices, and sector-relative
percentile scores. SPACs and funds are excluded. Run
`python us_fundamental_engine.py` (15–30 minutes the first time).

Only filings published on or before the analysis date are used (no look-ahead),
restatements replace earlier values only once filed, and flow items use
trailing twelve months. Banks are scored without industrial ratios. Set
`SEC_USER_AGENT=Your Name your@email.com` in `.env` (SEC fair-access rule).

### Phase 14 — Every asset class (Day 76c)
`multi_asset_universe.py` covers **161 instruments across 7 asset classes** with
free data: the US Treasury curve (1M–30Y), TIPS real yields and breakeven
inflation, credit spreads AAA→CCC, bond ETFs, 24 FX pairs with carry from OECD
short rates, energy/metals/agricultural futures, major cryptocurrencies and
stablecoins, REIT ETFs, listed alternatives (private-equity managers, BDCs,
infrastructure, managed futures, volatility, farmland, timber) and equity index
ETFs. Each instrument gets returns, 12-1 momentum, volatility annualized on its
own trading calendar, drawdown, trend and beta to the S&P 500. The **Markets**
page shows it by asset class.

### Phase 14b — Macro drivers, economic releases and commercial real estate (Day 76d)
- **Economic dashboard:** inflation (CPI, core CPI, core PCE), jobs (unemployment,
  payrolls, claims), growth (GDP, industrial production), consumers, the Fed,
  housing, and CRE indicators (hotel room-price inflation, CRE loan delinquencies,
  commercial construction) from FRED.
- **Macro drivers (`macro_drivers.py`):** regresses every instrument's daily returns
  on six macro factors (equity market, 10Y yield, breakeven inflation, high-yield
  spreads, dollar, oil) and explains each asset class's recent move factor by
  factor. A long-Treasury fund's rate beta is checked against its duration.
- **Commercial real estate by property type:** hotels, motels/economy brands
  (Wyndham, Choice), office, industrial, retail, net lease, apartments, data
  centers and towers, healthcare, self-storage, CRE lenders and CMBS.

### Phase 15 — Multi-factor rating (Day 77)
`multi_factor_rating.py` combines five pillars — fundamental (point-in-time SEC
facts), technical (12-1 momentum, trend), quant (walk-forward ML), economic
(risk-on/risk-off beta tilt from credit spreads and the yield curve) and risk
(low volatility) — into Overweight / Neutral / Underweight research ratings.
It tests each pillar and the composites with the **information coefficient**
(rank correlation with the next 20-day return, with t-statistics) and with
cost-adjusted portfolios, and adds an IC-weighted composite that learns weights
only from outcomes already known. In the first test the ML pillar alone was
strongest (IC 0.099, t = 2.77); the equal-weight composite diluted it, which is
why the IC-weighted version exists. Ratings are on the Research page.

### Vittantra Academy — learn by doing
The **Academy** page turns Vittantra into a training desk for five roles:
investment analyst, equity researcher, portfolio/risk analyst, portfolio manager
and advisor.

- **Work Desk:** daily tasks built from live data (morning brief, company tear
  sheet, risk check and stress question, rebalance proposal checked live by the
  risk model, client meeting with suitability checks), graded automatically where
  there is an objective answer, with a senior-style reference answer.
- **Lessons on demand:** 25 lessons, each with concept, formulas, a live example
  from your own data, the code location, an exercise and interview questions.
- **Role handbook:** framework, daily/weekly/monthly duties, outputs, KPIs, career
  path and credentials for each role.
- **CFA Level II alongside the work:** every lesson is tagged with its Level II
  topic area, and each desk produces a daily Level II-style item set (case plus
  A/B/C questions with worked answers) from live data — fixed income, derivatives,
  portfolio risk, currency parity, equity valuation, regression, real estate and
  macro sensitivities — with accuracy tracked by topic.
- **Career and work record:** XP and levels (Junior → Analyst → Senior → Lead) per
  role, and a downloadable record of your work for interviews.


### Phase 16 — Valuation and research notes (Days 78–78b)
DCF (FCFF, three-stage), residual income and dividend discount models with a
reverse DCF and sensitivity table (`valuation_engine.py`); evidence-linked
research notes where every claim cites file, field and value
(`research_report.py`); a World & Markets Brief linking each week's data moves
to free news headlines and the economic calendar (`world_brief.py`).

### Phase 17 — Portfolio management (Days 79–81)
Grinold–Kahn alpha, Ledoit–Wolf shrinkage covariance and an optimizer inside a
4% tracking-error budget (`portfolio_construction.py`); Brinson–Fachler and
factor attribution (`performance_attribution.py`); a what-if tool with live
VaR, beta, risk shares and macro scenarios (`whatif_engine.py`).

### Phase 18 — Advisory (Days 82–84)
Risk questionnaire and IPS, building-block capital market assumptions, model
allocations, a suitability engine citing CFA Standard III(C), Monte Carlo goal
planning and client reports (`advisory_engine.py`).

### Phase 19 — Copilot, rule tests, deployment, polish (Days 85–87b)
An evidence-grounded copilot across all desks (`vittantra_copilot.py`), one
test per non-negotiable rule (`test_governance_rules.py`), free deployment
(`DEPLOY.md`) and a professional Home page and design pass.

### Phase 20 — Career and release (Days 88–90)
Data-generated case studies (`case_studies.py` → `CASE_STUDIES.md`), the career
kit (`CAREER_KIT.md`), an Emergent Ventures draft and Vittantra v1.0.

## Tech stack

Python 3.11 · pandas · NumPy · SciPy · scikit-learn · Streamlit · Plotly ·
SQLite · yfinance · requests · free data from SEC EDGAR, FRED, Yahoo Finance and
official RSS feeds.

## Design principles

1. **No look-ahead bias** — point-in-time data and walk-forward validation.
2. **Challenge every result** — test signals out of sample; a combination must beat its best input.
3. **Risk before return** — every proposal passes risk budgets and suitability checks.
4. **Governed, not automated** — recommendations become tickets that require human approval.
5. **Explainable** — every number cites its source; the AI layer never invents data.

## Project status

**Vittantra 1.0** — all 90 days complete. Next ideas: FFO-based REIT valuation,
consensus-free earnings forecasts, a larger universe for stronger signal tests,
and historical scenario replay.

## Disclaimer

Vittantra is a research and education project. Nothing in it is investment
advice. Backtests are historical research results, not promises of future
returns; sample clients are fictional. Market data from free sources may be
delayed or incomplete. No trades are submitted or executed.
