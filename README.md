# Vittantra — Investment Intelligence System

### A 90-day build: from Python fundamentals to a governed, explainable investment-research and risk platform

Vittantra (which began as *AI Financial Analyst*) is an end-to-end investment
research and portfolio-intelligence system built in Python, SQL and Streamlit.
It connects market and economic data, machine-learning research, portfolio
construction, multi-asset risk, risk budgeting, governance, remediation and an
approval workflow — and puts an AI analyst and research copilot on top so that
quantitative output can be read and questioned in plain language.

The guiding design principle is **human control**: the system detects,
explains and recommends, but it never trades on its own.

```
Market & Economic Data
        ↓
Research & Machine Learning        Days 1–58
        ↓
Portfolio Construction
        ↓
Multi-Asset Risk Engine            Days 35–62
        ↓
Rebalancing & Exposure Control     Days 63–65
        ↓
Risk Budgeting & Monitoring        Days 66–67
        ↓
Governance → Remediation           Days 68–69
        ↓
Approval Workflow                  Day 70
        ↓
Vittantra App · AI Analyst · Research Copilot    Days 71–74
        ↓
HUMAN DECISION        (automatic execution authorized = 0)
```

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run vittantra_app.py     # launch the Vittantra Command Center
python -m unittest discover -p "test_*.py"   # run the test suite
```

The app reads the `dayNN_*.csv` outputs committed in the repository, so it runs
without re-generating the research pipeline. Local SQLite databases
(`hedge_fund.db`, `paper_trading.db`, `vittantra_market.db`) are intentionally
not committed.

### Live market data (free)

```bash
python run_vittantra.py            # download free market data, then run Days 59–73
python run_vittantra.py --loop 15  # keep everything updated every 15 minutes
python run_vittantra.py --sample   # original illustrative sample data
```

`vittantra_data_hub.py` collects prices for stocks, ETFs, futures, FX and crypto
from Yahoo Finance and Treasury yields, credit spreads, VIX and economic series
from FRED, with no paid subscription or API key needed. The bond and option in
the risk portfolio are priced with models from live inputs (Treasury yield +
BBB spread, Black-Scholes). Every number carries an as-of date and a
FRESH / STALE / MISSING status. If a download fails, Vittantra keeps using the
last good data. Free prices may be delayed by about 15 minutes.

---

## The Vittantra application

`vittantra_app.py` brings the whole system into one Streamlit interface:

| Page | What it shows |
|------|---------------|
| **Markets** | All asset classes: yield curve, credit spreads, FX carry, commodities, digital assets, REITs, alternatives, equity indices |
| **Research** | Fundamental scores for the 33-stock universe: value, growth, quality, financial health; company detail |
| **Command Center** | Portfolio status, instrument count, approval queue, immediate priorities, maximum risk-budget utilization, workflow state |
| **Portfolio** | Risk-budget rankings, asset-class risk allocation, modeled risk contribution, Top-1 / Top-3 risk share, effective risk positions, automated observations |
| **Risk Intelligence** | Instrument- and asset-class-level risk monitoring and alerts |
| **Governance** | Governance status, actions and reasons per instrument |
| **Remediation** | Modeled risk-reduction actions and priorities |
| **AI Analyst** | Executive brief, risk drivers, priority queue and human-attention items |
| **System** | Data sources and system state |

**Portfolio snapshot from the committed outputs: LIVE market data as of
2 October 2026.** The positions are the illustrative Day 59 example portfolio,
valued at real prices with real price history. Run `python run_vittantra.py`
to refresh.

| Metric | Value |
|--------|------:|
| Portfolio status | CRITICAL |
| Instruments | 10 (8 within budget, 2 critical) |
| Maximum risk-budget utilization | 700.0% (AAPL call, deep in the money, delta ≈ 1.0) |
| Next highest | 583.3% (ES future) |
| Single-name concentration | AAPL stock + AAPL call ≈ 42% of portfolio risk before rebalancing |
| Portfolio value / 1-day 95% VaR | $626,307 / $9,341 (99% VaR $15,864) |
| Estimated post-remediation max utilization | 100% |
| Workflow | AWAITING DUAL APPROVAL |
| Automatic execution authorized | **0** |

---

## Project phases

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

## Finance framework

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

## Tech stack

- **Python:** pandas, NumPy, SciPy, scikit-learn
- **Application:** Streamlit, Plotly, Matplotlib
- **Data:** SQLite, SQL window functions and CTEs, yfinance, economic data APIs
- **Engineering:** unittest, Git/GitHub, modular pipeline with validation outputs
- **Finance:** portfolio optimization, CAPM, VaR/ES and VaR backtesting, stress
  and macro-scenario testing, factor attribution, risk budgeting, governance

## Design principles

1. **No look-ahead bias** — point-in-time data and walk-forward validation.
2. **Challenge every result** — robustness and attribution before conclusions.
3. **Risk before return** — every signal passes risk checks before it becomes an order.
4. **Governed, not automated** — recommendations become tickets that require human approval.
5. **Explainable** — every governance action carries a reason; the AI layer cites evidence.

## Project status

Days 1–76 complete. Next: continue extending the AI layer and the end-to-end
research-to-decision workflow through Day 90.

## Disclaimer

This repository is an educational research project. All backtests and model
results are historical and simulated, depend on modeling assumptions, and do
not predict future performance. Nothing here constitutes investment advice.
