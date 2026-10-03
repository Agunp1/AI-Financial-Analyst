# Vittantra Roadmap — Days 75–90

**Vision:** an AI investment platform you can trust. It researches assets
across fundamental, technical, quantitative, economic and risk factors,
checks every recommendation against risk limits, explains it with evidence,
logs it, and leaves the final decision to a human.

```
                         VITTANTRA
   ┌──────────────┬───────────────┬───────────────┬──────────────────┐
   │ 1. RESEARCH  │ 2. PORTFOLIO  │ 3. PORTFOLIO  │ 4. ADVISORY      │
   │   (Analyst)  │     RISK      │  MANAGEMENT   │ Retail + Instit. │
   └──────┬───────┴───────┬───────┴───────┬───────┴────────┬─────────┘
          └───────────────┴───────┬───────┴────────────────┘
              Shared core: Data · Governance · Approval · AI Copilot
                                  ↓
                           HUMAN DECISION
```

Constraint: **free data sources only.**

| Day | Desk | Build | Status |
|-----|------|-------|--------|
| 75 | Core | Free live data hub, one-command pipeline, data freshness in the app | ✅ Done |
| 76 | Research | Fundamental engine (SEC EDGAR, free): valuation, growth, profitability, balance sheet | ✅ Done |
| 76b | Research | Fundamentals for all US-listed stocks (~6,000, SEC frames) | ✅ Built — run `python us_fundamental_engine.py` |
| 76c | Markets | Multi-asset universe: rates, credit, FX, commodities, digital assets, REITs, alternatives | ✅ Done (9/9 on real data) |
| Academy | Learning | Work Desk (5 roles, live tasks, grading), 25 lessons, role handbook, career levels, work record — then one new task/lesson with every feature | ✅ v1 built |
| 76d | Markets | Macro drivers, economic dashboard, commercial real estate (hotels, motels, office, …), CFA Level II item sets | ✅ Done (7/7 on real data) |
| 77 | Research | Multi-factor rating: fundamental + technical + quant + economic + risk, backtested; rated on the IC-weighted composite | ✅ Done (6/6 on real data) |
| 78 | Research | Valuation engine (DCF, residual income, DDM, reverse DCF, sensitivity) and evidence-linked research notes | ✅ Built |
| 78b | Markets | World & Markets Brief: free news headlines (central banks, regulators, markets), economic calendar, headlines linked to data, morning routine | ✅ Built |
| 79 | Portfolio Mgmt | Research-driven portfolio construction within the risk budget | ✅ Built |
| 80 | Portfolio Mgmt | Performance attribution (Brinson–Fachler, pillar factors) | ✅ Built |
| 81 | Risk | What-if scenario tool with live risk recalculation | ✅ Built |
| 82 | Advisory | Client profiles: retail risk questionnaire, institutional IPS/mandate | ✅ Built |
| 83 | Advisory | Suitability and mandate-compliance engine | ✅ Built |
| 84 | Advisory | Goals-based planning (Monte Carlo) and client reports | ✅ Built |
| 85 | Core | Copilot across all desks, evidence-grounded (free; optional local LLM) | ✅ Built |
| 86 | Core | Tests for every rule: suitability, risk limits, no auto-execution, no made-up answers | ✅ Built |
| 87 | Core | Deploy online (free tier) | ✅ Guide ready (`DEPLOY.md`) |
| 87b | Core | **Professional polish:** one design system (colours, typography, icons), landing page with the Vittantra story, guided demo mode, consistent tables/charts, mobile-friendly layout, no debug output | ✅ Done |
| 88 | Career | Case studies, one per desk | ✅ Done (`CASE_STUDIES.md`) |
| 89 | Career | Interview scripts and Emergent Ventures application draft | ✅ Drafts ready |
| 90 | Release | Vittantra v1.0 | ✅ Released |
| 91 | Private markets | VC / PE analyst desk for a small fund: deal screening, term sheets, waterfall, LBO, fund math, mock interviews | ✅ Built |
