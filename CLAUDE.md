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

## Non-negotiable rules

- **No automatic execution.** Nothing may submit or execute trades; keep
  `automatic_execution_authorized_count = 0`. Recommendations go through the
  approval workflow to a human.
- **Remediation must never increase modeled risk.**
- **The AI layer must not invent data.** If Vittantra's outputs do not support
  an answer, say so.
- **No look-ahead bias** in research: point-in-time data, walk-forward splits.
- Present backtests as historical research results, never as promised returns.

## Finance framework

- Shared formulas live in `vittantra_pricing.py` (Black-Scholes, bond
  analytics) and `vittantra_risk_model.py` (Euler covariance risk
  contributions, delta-adjusted option exposure). Reuse them; don't
  re-implement.
- `test_finance_formulas.py` pins formulas to textbook values; keep it
  green. `FINANCE_AUDIT.md` lists methods, fixes and known simplifications —
  update it when a method changes.
- Sharpe/Sortino use excess returns over the point-in-time T-bill rate for
  long-only portfolios; costs apply to every dollar traded.

## Data

- Free sources only (Yahoo Finance via yfinance, FRED public CSV). The owner
  cannot pay for data; do not add paid providers.
- Data modes: LIVE when `day75_live_instrument_prices.csv` exists, SAMPLE
  otherwise or with `VITTANTRA_DATA_MODE=sample`. Without live data the
  Day 60 risk engine uses synthetic validation history; label it as such.
- Fundamentals come from SEC EDGAR companyfacts (needs `SEC_USER_AGENT` in
  `.env`; cached in `sec_cache/`, git-ignored). Use only facts filed on or
  before the as-of date.
- The cloud sandbox cannot reach Yahoo/FRED/SEC; test with the fake fetchers in
  `test_data_hub.py`. Live downloads run on the owner's machine.

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
