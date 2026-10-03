# Changelog

## 1.1 — Private markets desk (Day 91)
- Sixth Academy role: PE / VC analyst at a small fund — deal screening, term sheet and waterfall, quick LBO,
  mock interviews; six lessons (CFA L2 Alternative Investments) and a VC/LBO item set.
- `private_markets.py`: VC method, priced rounds, cap table, exit waterfall, unit economics, fund power law, LBO.
- Private-bank visual theme across the app.

## 1.0 — Vittantra release (Day 90)

**Desks**
- Equity research: SEC point-in-time fundamentals (33 stocks + all US-listed), five-pillar ratings on the
  IC-weighted composite, DCF / residual income / DDM valuation with reverse DCF, evidence-linked notes.
- Investment analyst: 201-instrument multi-asset universe, economic dashboard, macro factor attribution,
  World & Markets Brief with free headlines and calendar.
- Portfolio management: Grinold–Kahn alpha, shrinkage covariance, tracking-error-budgeted optimizer,
  Brinson–Fachler and factor attribution, what-if scenarios.
- Portfolio risk: VaR/ES backtests, full-revaluation stress, Euler risk budgets, governance, remediation,
  dual-approval workflow.
- Advisory: questionnaire and IPS, capital market assumptions, suitability engine, Monte Carlo goals,
  client reports.

**Platform**
- Evidence-grounded copilot (optional free local LLM with a number-grounding check).
- Academy: Work Desk for five roles, 35 lessons, CFA Level II item sets, case studies, work record.
- One-command pipeline, free deployment guide, Home page with guided tour, consistent design.
- 250+ automated tests, including one per non-negotiable rule.

**Fixes during the final phase**
- Macro drivers: rate-beta check in the wrong units; date alignment hardened.
- Day 77: free daily prices, FRED regime data and SEC facts fetched when no local database exists.

## 0.x — Days 1–77
See the build history in `README.md`.
