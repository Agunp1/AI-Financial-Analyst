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
(`hedge_fund.db`, `paper_trading.db`) are intentionally not committed.

---

## The Vittantra application

`vittantra_app.py` brings the whole system into one Streamlit interface:

| Page | What it shows |
|------|---------------|
| **Command Center** | Portfolio status, instrument count, approval queue, immediate priorities, maximum risk-budget utilization, workflow state |
| **Portfolio** | Risk-budget rankings, asset-class risk allocation, modeled risk contribution, Top-1 / Top-3 risk share, effective risk positions, automated observations |
| **Risk Intelligence** | Instrument- and asset-class-level risk monitoring and alerts |
| **Governance** | Governance status, actions and reasons per instrument |
| **Remediation** | Modeled risk-reduction actions and priorities |
| **AI Analyst** | Executive brief, risk drivers, priority queue and human-attention items |
| **System** | Data sources and system state |

**Current portfolio snapshot (from the committed outputs):**

| Metric | Value |
|--------|------:|
| Portfolio status | CRITICAL |
| Instruments | 10 (8 normal, 2 critical) |
| Maximum risk-budget utilization | 880.9% (ES future) |
| Second-highest utilization | 194.8% (BTC) |
| Modeled risk reduction required | 54.4% |
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

All covered by unit tests (`test_*.py`, 44 tests).

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

**Long/short research backtest (39 periods, Jul 2023 – Aug 2026, net of modeled costs):**

| Strategy | Ann. return | Ann. vol | Sharpe | Max drawdown |
|----------|-----------:|---------:|-------:|-------------:|
| Long/Short | 10.3% | 6.8% | 1.47 | −4.4% |
| Top quintile long | 26.0% | 14.4% | 1.69 | −8.4% |
| Equal-weight universe | 17.2% | 9.6% | 1.70 | −5.9% |

- Robustness: **5 of 6 checks passed** — positive at 50 bps costs, across basket
  sizes, in both sample halves, sector-neutral, and bootstrap 95% CI above zero.
  The failed check: score buckets are not perfectly monotonic.
- Factor attribution: annualized alpha ≈ 3.3%, R² ≈ 0.29 — a large share of
  returns is not explained by the factors tested, but the sample is short.

### Phase 8 — Multi-asset risk architecture (Days 59–62)
| Day | Module | Purpose |
|-----|--------|---------|
| 59 | `multi_asset_risk.py` | Asset-class schema, risk-metric catalog and routing across equities, ETFs, futures, options, FX, crypto, bonds, commodities, REITs and cash |
| 60 | `unified_risk_engine.py` | Instrument- and portfolio-level risk with coverage and missing-data checks |
| 61 | `cross_asset_stress.py` | Cross-asset stress scenarios and scenario ranking |
| 62 | `macro_scenario_engine.py` | Macro inputs translated into asset-class and instrument shocks by regime |

### Phase 9 — Rebalancing, exposure control & risk budgeting (Days 63–67)
| Day | Module | Purpose |
|-----|--------|---------|
| 63 | `portfolio_rebalancing_engine.py` | Target-driven rebalance orders with before/after risk |
| 64 | `exposure_risk_engine.py` | Instrument and asset-class exposures, concentration checks |
| 65 | `exposure_aware_rebalancer.py` | Rebalance orders that respect exposure constraints |
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

Days 1–74 complete. Next: continue extending the AI layer and the end-to-end
research-to-decision workflow through Day 90.

## Disclaimer

This repository is an educational research project. All backtests and model
results are historical and simulated, depend on modeling assumptions, and do
not predict future performance. Nothing here constitutes investment advice.
