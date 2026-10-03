# CLAUDE.md — Vittantra

Vittantra is a 90-day investment-research and portfolio-intelligence project
(formerly "AI Financial Analyst"). The owner is learning Python/SQL/ML on top of
a finance background; explanations should be step by step and beginner-friendly,
with exact commands for Windows PowerShell + VS Code when the owner must run
something locally.

## Architecture

```
Data → ML research → Portfolio construction → Multi-asset risk → Rebalancing
→ Risk budgeting → Monitoring → Governance → Remediation → Approval workflow
→ Vittantra app / AI Analyst / Research Copilot → Human decision
```

Each day's module reads earlier days' CSV outputs and writes `dayNN_*.csv`
outputs plus a `dayNN_validation_summary.csv`. Key chain:

| Day | Module | Main output |
|-----|--------|-------------|
| 66 | `portfolio_risk_budgeting.py` | `day66_*` risk budgets |
| 67 | `portfolio_risk_monitor.py` | `day67_portfolio_risk_dashboard.csv` |
| 68 | `portfolio_risk_governance.py` | `day68_*governance*` |
| 69 | `portfolio_risk_remediation.py` | `day69_*remediation*` |
| 70 | `portfolio_approval_workflow.py` | `day70_*` tickets, queue, audit log |
| 71–72 | `vittantra_app.py` | Streamlit app (7 pages) |
| 73 | `vittantra_ai_analyst.py` | Analyst brief from Days 67–70 |
| 74 | `vittantra_research_copilot.py` | NL Q&A over Vittantra data |
| 75 | `vittantra_data_hub.py`, `vittantra_live_inputs.py`, `run_vittantra.py` | Free live data → risk chain; one-command pipeline |
| 76 | `fundamental_engine.py`, `vittantra_research_page.py` | SEC EDGAR point-in-time fundamentals and scores |
| 76b | `us_fundamental_engine.py` | All US-listed stocks via SEC frames; sector-relative scores |
| 76c | `multi_asset_universe.py`, `vittantra_markets_page.py` | Rates, credit, FX, commodities, crypto, REITs, alternatives |
| 76d | `macro_drivers.py` | Macro factor betas and attribution per asset class; economic dashboard; CRE by property type |
| 77 | `multi_factor_rating.py` | Five-pillar rating, IC tests; ratings use the IC-weighted composite, point in time |
| 78 | `valuation_engine.py`, `research_report.py` | DCF (FCFF), residual income, DDM, reverse DCF; evidence-linked research notes |
| 78b | `world_brief.py` | Free RSS headlines tagged by theme, FOMC/FRED release calendar, data moves linked to headlines |
| 79 | `portfolio_construction.py` | Grinold–Kahn alpha, shrinkage covariance, optimizer within a 4% tracking-error budget; proposal pending human approval |
| 80 | `performance_attribution.py` | Brinson–Fachler (Carino-linked) and pillar-factor attribution of the Day 77 backtest |
| 81 | `whatif_engine.py`, `vittantra_pm_page.py` | What-if weights and macro scenarios with live risk (vol, VaR/ES, beta, Euler shares) |
| Academy | `academy_content.py`, `academy_live.py`, `academy_desk.py`, `vittantra_academy_page.py` | Learn-by-doing desk for 5 roles; progress in `academy_progress.json` |

## Non-negotiable rules

- **No automatic execution.** Nothing may submit or execute trades; keep
  `automatic_execution_authorized_count = 0`. Recommendations go through the
  approval workflow to a human.
- **Remediation must never increase modeled risk.**
- **The AI layer must not invent data.** If Vittantra's outputs do not support
  an answer, say so. Research notes cite source file, field and value for
  every claim.
- **No look-ahead bias** in research: point-in-time data, walk-forward splits.
- Present backtests as historical research results, never as promised returns.

## Finance framework

- Shared formulas live in `vittantra_pricing.py` (Black-Scholes, bond
  analytics, CAPM/WACC/DCF/residual income/DDM) and `vittantra_risk_model.py` (Euler covariance risk
  contributions, delta-adjusted option exposure, Ledoit–Wolf
  constant-correlation shrinkage). Reuse them; don't
  re-implement.
- `test_finance_formulas.py` pins formulas to textbook values; keep it
  green. `FINANCE_AUDIT.md` lists methods, fixes and known simplifications —
  update it when a method changes.
- Sharpe/Sortino use excess returns over the point-in-time T-bill rate for
  long-only portfolios; costs apply to every dollar traded.

## Data

- Free sources only (Yahoo Finance via yfinance, FRED public CSV, public RSS
  feeds; the FRED release calendar uses the free `FRED_API_KEY`). The owner
  cannot pay for data; do not add paid providers.
- Data modes: LIVE when `day75_live_instrument_prices.csv` exists, SAMPLE
  otherwise or with `VITTANTRA_DATA_MODE=sample`. Without live data the
  Day 60 risk engine uses synthetic validation history; label it as such.
- Fundamentals come from SEC EDGAR companyfacts (needs `SEC_USER_AGENT` in
  `.env`; cached in `sec_cache/`, git-ignored). Use only facts filed on or
  before the as-of date.
- The cloud sandbox cannot reach Yahoo/FRED/SEC; test with the fake fetchers in
  `test_data_hub.py`. Live downloads run on the owner's machine.

## Academy

- The owner wants to learn by doing the job, not from a book: tasks first,
  lessons on demand. Keep adding desk tasks and lessons as features are built
  (one lesson per new feature).
- Live examples must use Vittantra data and raise `MissingData` rather than
  invent numbers; reference answers are labelled as one reasonable view.
- CFA Level II: tag new lessons in `academy_cfa.LESSON_CFA_TOPIC` and add item
  sets for new features; the owner studies Level II through the desk work.
- `academy_progress.json` is the owner's work record (committed so their work
  can be reviewed).

## Presentation

- The finished Vittantra must look impressive and professional (owner's goal):
  consistent design, clear navigation, no raw/debug output in the UI, labelled
  sources and assumptions. A dedicated polish phase is on the roadmap.

## Conventions

- New work continues the `dayNN_` numbering; every module ends with a
  validation step and prints a completion line.
- Python 3.11+; dependencies in `requirements.txt`.
- `*.db` files are local only (git-ignored); the committed CSVs let the app run.

## Commands

```bash
pip install -r requirements.txt
python -m unittest discover -p "test_*.py"
streamlit run vittantra_app.py
python run_vittantra.py              # refresh data + run Days 59-73
python run_vittantra.py --sample     # original sample data
python vittantra_ai_analyst.py
python vittantra_research_copilot.py
```
