"""
Vittantra Guide: how to use every page, step-by-step playbooks, asset-class
primers with live Vittantra numbers, and a glossary.

Content is plain data so it can be tested; live numbers come only from saved
Vittantra outputs and are omitted (with a note) when the file is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
ANALYTICS = "day76c_asset_analytics.csv"
IC_SUMMARY = "day77_ic_summary.csv"
MACRO_BETAS = "day76d_macro_betas.csv"

# ==============================================================
# 1. EVERY PAGE: what it is for and how to use it
# ==============================================================

PAGE_HELP: Dict[str, dict] = {
    "Home": {
        "what": "The front door: what Vittantra is, today's highlights from the data, and a 5-minute tour.",
        "steps": ["Read the stat strip for the size of the data and its date.",
                  "Click Open on a desk card to jump to that desk.",
                  "Follow the guided tour at the bottom, one Go button at a time."],
        "tip": "New here? Open the Guide page next; it explains every page and walks you through each job.",
    },
    "Guide": {
        "what": "This page: how to navigate, how to do each job step by step, and what every asset class is.",
        "steps": ["Start with 'Find your way' to learn the sidebar.",
                  "Pick a playbook (research a stock, manage the portfolio...) and press Go at each step.",
                  "Open an asset class to learn what drives it, with live numbers from Vittantra.",
                  "Search the glossary for any term you meet in the app."],
        "tip": "Every page also has a 'How to use this page' box at the top.",
    },
    "Command Center": {
        "what": "One-screen status of the model portfolio's risk: alerts, the risk → remediation chain and the "
                "decision workflow.",
        "steps": ["Read the status badges first (portfolio state and workflow state).",
                  "Scan Portfolio Alerts: each alert names the instrument, the limit and how far it is breached.",
                  "Follow Risk → Remediation to see what fix is proposed and whether it lowers risk.",
                  "When a fix is ready, the owner reviews the proposed sizes, ticks both reviewer boxes, writes a "
                  "comment and approves; the risk chain then re-runs with the new sizes."],
        "tip": "Red means a limit is breached now; amber means close to a limit. Nothing here trades by itself.",
    },
    "Research": {
        "what": "Equity research: SEC fundamentals, five-pillar ratings, valuation and evidence-linked notes — "
                "for the 33-stock research universe and any US-listed company.",
        "steps": ["View 'Research universe' for the 33 stocks, or 'All US-listed stocks' to screen 4,000+ "
                  "companies by sector, size and name.",
                  "Open 'Multi-factor ratings' to see each stock's five pillar scores and which pillars have "
                  "actually predicted returns (IC).",
                  "Open 'Valuation & reports': type any ticker (e.g. TSLA) for an on-demand note, or pick one of "
                  "the 33 for the full report.",
                  "Read the note's Evidence list: every claim shows the file, field and value it came from."],
        "tip": "Start with the reverse DCF: 'growth priced in' tells you what the market already expects.",
    },
    "Markets": {
        "what": "Every asset class in one place, the economy, and the World Brief (headlines linked to data moves).",
        "steps": ["Open World Brief each morning: what moved, why (headlines), and the event calendar.",
                  "Overview compares all asset classes on return, volatility and drawdown.",
                  "Macro & Economy shows the dashboard of growth, inflation, jobs and rates, and how each asset "
                  "class reacts to them (macro betas).",
                  "Use the asset-class tabs (Rates & Credit, FX, Commodities, Digital Assets, Real Estate, "
                  "Alternatives, Equity Indices) to go deeper."],
        "tip": "Headlines explain; data confirms. Check that a story actually shows up in prices before acting.",
    },
    "Portfolio Manager": {
        "what": "Turns the ratings into a model portfolio within a tracking-error budget, explains past returns "
                "(attribution) and tests changes (what-if).",
        "steps": ["Model portfolio: read the summary (expected active return, tracking error, information ratio) "
                  "and the holdings vs benchmark.",
                  "Attribution: see whether past returns came from allocation, selection or factor bets.",
                  "What-if: change weights or pick a macro scenario and compare risk before and after.",
                  "If the change is sound, write a rationale and send it to the approval queue (owner only)."],
        "tip": "A proposal is never executed: it waits as PENDING HUMAN APPROVAL.",
    },
    "Advisory": {
        "what": "Client advice: risk questionnaire / IPS, capital market assumptions, model allocations, "
                "suitability checks and Monte Carlo goal plans.",
        "steps": ["Clients: review each (fictional) client's profile, allocation and suitability result.",
                  "New client questionnaire: answer the questions to get a risk profile and recommended mix.",
                  "Model allocations: compare the five model portfolios and their expected return and risk.",
                  "Goal planner: see the probability of reaching a goal and the extra saving needed."],
        "tip": "Risk profile = the lower of willingness and capacity. Every recommendation must pass suitability.",
    },
    "Copilot": {
        "what": "Ask questions in plain English; answers come only from Vittantra's data, with citations.",
        "steps": ["Type a question, e.g. 'Why is XOM rated Overweight?' or 'What is the portfolio's biggest risk?'.",
                  "Read the cited evidence under the answer.",
                  "If the data does not cover the question, the copilot says so instead of guessing."],
        "tip": "It refuses trade requests by design: decisions go through the approval workflow.",
    },
    "Risk Intelligence": {
        "what": "Portfolio risk in depth: VaR and expected shortfall, stress tests, VaR backtests and risk by "
                "asset class.",
        "steps": ["Read VaR (a bad day, 1 in 20 or 1 in 100) and expected shortfall (the average of those bad days).",
                  "Check the VaR backtest: Kupiec and Christoffersen tests show whether the model's breaches are "
                  "too many or clustered.",
                  "Review stress tests: what historical-style shocks would do to the portfolio.",
                  "See which instruments and asset classes contribute most to risk."],
        "tip": "A model that never breaches VaR is as suspicious as one that breaches too often.",
    },
    "Portfolio": {
        "what": "Risk budgets: how much of the portfolio's risk each position uses compared with its budget.",
        "steps": ["Start with the Portfolio Snapshot.",
                  "Read the Risk-Budget Utilization Ranking: above 100% means a budget is exceeded.",
                  "Check Asset-Class Risk Allocation and Risk Contribution Concentration.",
                  "Risk-Budget Excess lists what needs fixing; the Governance overlay shows the rule involved."],
        "tip": "Risk contributions (Euler) add up to total portfolio risk, so they show who really drives it.",
    },
    "Governance": {
        "what": "The rules: which limits apply, which are breached, and the approval workflow for any change.",
        "steps": ["Read each governance check and its status.",
                  "Open the Governance Workflow to see tickets, their approvers and the audit log.",
                  "Changes need dual approval; automatic execution must always be 0."],
        "tip": "Governance is what makes the numbers usable in a real firm: who decided what, and why.",
    },
    "Remediation": {
        "what": "Proposed fixes for risk breaches, checked so that a fix never increases modeled risk.",
        "steps": ["Read the Remediation Summary: which positions change and by how much.",
                  "Compare risk before and after: remediation must lower or keep risk.",
                  "Check the Control Boundary: what the system may and may not do on its own."],
        "tip": "A fix that reduces one breach but raises total risk is rejected.",
    },
    "AI Analyst": {
        "what": "A written brief of the portfolio's risk state, generated from the risk, governance and "
                "remediation outputs.",
        "steps": ["Read the brief top to bottom: status, main risks, proposed actions, approvals needed.",
                  "Use it as the starting point for a risk meeting, then check the numbers on the risk pages."],
        "tip": "Like the copilot, it only states what the data supports.",
    },
    "Academy": {
        "what": "Learn by doing: daily desk tasks on live data for six roles, lessons on demand, CFA Level II "
                "item sets, case studies and your work record.",
        "steps": ["Sign in (sidebar) so your work is saved.",
                  "Work Desk: pick a role and do today's task; you get a score and a senior's reference answer.",
                  "Stuck? Open 'Learn what you need for this task' for the lesson.",
                  "CFA Level II: answer an item set built from today's data.",
                  "My Work Record: everything you have done, for interview preparation."],
        "tip": "Private Equity / VC desk: deal flow, term sheets, LBOs and mock interviews.",
    },
    "System": {
        "what": "Behind the scenes: data sources, freshness, the pipeline and the architecture.",
        "steps": ["Check Market Data for the as-of date and data mode (LIVE or SAMPLE).",
                  "Read the Architecture to see how data flows from sources to decisions."],
        "tip": "Data refreshes every weekday evening automatically.",
    },
}

# ==============================================================
# 2. FIND YOUR WAY
# ==============================================================

NAVIGATION = [
    ("Sidebar (left)", "Every page is listed there. Click a name to open it. On a phone, tap the » arrow at the "
                       "top left to show the sidebar."),
    ("Sign in", "At the bottom of the sidebar: 'Sign in / create account'. Signed in, your Academy work is saved. "
                "Visitors can still see everything."),
    ("Tabs", "Most pages have tabs across the top (e.g. Markets → World Brief, Overview...). Click a tab to switch."),
    ("Tables", "Click a column name to sort. Hover over a table to search it or make it full screen."),
    ("Charts", "Hover for exact values; drag to zoom; double-click to reset."),
    ("How to use this page", "Every page starts with this box. Open it whenever you are unsure."),
    ("Data date", "The sidebar shows whether data is LIVE and its date. It refreshes every weekday evening."),
]

# ==============================================================
# 3. PLAYBOOKS: do the job step by step
# ==============================================================

PLAYBOOKS: List[dict] = [
    {"title": "Research a stock", "role": "Equity research",
     "goal": "Form a view on one company, with evidence for every point.",
     "steps": [("Research", "Open Research & Valuation → 'Valuation & reports' and type the ticker."),
               ("Research", "Read 'Growth priced in' (reverse DCF): is it above or below recent growth?"),
               ("Research", "Compare intrinsic value with the price, and check the DCF sensitivity table."),
               ("Research", "Read the bull and bear cases; open 'All US-listed stocks' to compare with sector peers."),
               ("Markets", "Check the macro: Markets → Macro & Economy (rates and growth drive valuations)."),
               ("Copilot", "Ask the copilot follow-up questions; it cites its evidence.")]},
    {"title": "Start the day like an analyst", "role": "Investment analyst",
     "goal": "Know what moved, why, and what is coming up.",
     "steps": [("Markets", "Open Markets → World Brief: biggest moves, linked headlines, and the event calendar."),
               ("Markets", "Open Overview: which asset classes are up or down over 1 month and 12 months."),
               ("Markets", "Open Macro & Economy: inflation, jobs, growth, the yield curve."),
               ("Academy", "Academy → Work Desk → Investment Analyst: write today's market note.")]},
    {"title": "Manage the model portfolio", "role": "Portfolio management",
     "goal": "Understand the portfolio, explain its performance and propose changes safely.",
     "steps": [("Portfolio Manager", "Model portfolio tab: holdings, active weights, tracking error and IR."),
               ("Portfolio Manager", "Attribution tab: did returns come from sector allocation or stock selection?"),
               ("Risk Intelligence", "Check VaR, stress tests and what drives risk."),
               ("Portfolio", "Risk Budgets: any position using more than its budget?"),
               ("Portfolio Manager", "What-if tab: test a change or a macro scenario; compare before and after."),
               ("Governance", "Send the proposal for approval and follow it in the Governance Workflow.")]},
    {"title": "Fix a risk breach", "role": "Portfolio risk",
     "goal": "Find a breach, propose a fix that lowers risk, and get it approved.",
     "steps": [("Command Center", "Read the alerts: which limit is breached and by how much."),
               ("Portfolio", "Risk Budgets: confirm the position's risk contribution vs its budget."),
               ("Remediation", "Review the proposed fix; check that total risk falls."),
               ("Governance", "Check the ticket, approvers and audit log; nothing executes automatically."),
               ("AI Analyst", "Read the brief for the risk meeting.")]},
    {"title": "Advise a client", "role": "Advisory",
     "goal": "Recommend a suitable allocation and show the client their goal odds.",
     "steps": [("Advisory", "New client questionnaire: answer for the (fictional) client."),
               ("Advisory", "Read the risk profile: the lower of willingness and capacity."),
               ("Advisory", "Check suitability: every rule must pass before advice is given."),
               ("Advisory", "Goal planner: probability of success and the extra saving needed."),
               ("Advisory", "Clients tab: download the client report.")]},
    {"title": "Screen a startup deal", "role": "PE / VC analyst",
     "goal": "Decide whether a fictional startup deserves a partner meeting, and price the round.",
     "steps": [("Academy", "Academy → Work Desk → Private Equity / VC → Deal flow: screen the deals."),
               ("Academy", "Term sheet tab: work out pre/post-money, dilution and the option-pool shuffle."),
               ("Academy", "LBO tab: estimate MOIC and IRR for a buyout."),
               ("Academy", "Mock interview tab: answer one question out loud, then compare.")]},
]

# ==============================================================
# 4. ASSET CLASSES
# ==============================================================

ASSET_CLASSES: List[dict] = [
    {"name": "Equities (stocks)", "key": "Equity", "markets_tab": "Equity Indices",
     "what": "Ownership shares in companies. You earn dividends plus the change in the share price.",
     "why": "The main long-run growth asset: equity owners get what is left after everyone else is paid, so "
            "they bear the most risk and expect the highest return.",
     "drivers": ["Earnings growth", "Interest rates (higher rates lower the value of future profits)",
                 "Risk appetite and valuations (P/E)", "The economic cycle"],
     "risks": ["Large drawdowns in recessions (30–50% has happened)", "Single-company risk",
               "Paying too much: high valuations lower future returns"],
     "metrics": ["P/E and earnings yield", "Free-cash-flow yield", "ROE and margins", "Revenue and EPS growth",
                 "Beta (market sensitivity)"],
     "how_pros": "Top-down (economy → sectors) and bottom-up (company fundamentals and valuation: DCF, multiples). "
                 "Portfolios are built against a benchmark with a tracking-error budget.",
     "in_vittantra": "Research & Valuation (SEC fundamentals, ratings, DCF), Portfolio Manager, Markets → Equity "
                     "Indices.",
     "lessons": ["ER1", "ER2", "ER6", "PM7"]},
    {"name": "Government bonds and rates", "key": "Fixed Income", "markets_tab": "Rates & Credit",
     "what": "Loans to governments (e.g. US Treasuries). You receive fixed coupons and your money back at maturity.",
     "why": "Income, capital preservation, and usually a hedge when stocks fall in a recession.",
     "drivers": ["Interest rates: when yields rise, bond prices fall", "Inflation expectations",
                 "Central bank policy (the Fed)", "Flight to safety in crises"],
     "risks": ["Duration risk: a 20-year bond can lose about 17% if yields rise 1 percentage point",
               "Inflation eating fixed coupons", "Stocks and bonds can fall together when inflation is the shock "
                                                 "(as in 2022)"],
     "metrics": ["Yield to maturity", "Duration (price sensitivity to rates)", "Convexity",
                 "Yield curve shape (2s10s)", "Real yield (inflation-adjusted)"],
     "how_pros": "Position along the curve (short vs long maturities), manage duration against a benchmark, "
                 "and watch the curve: an inverted curve has often come before recessions.",
     "in_vittantra": "Markets → Rates & Credit (yield curve, Treasury ETFs), Macro & Economy (rate betas).",
     "lessons": ["IA3"]},
    {"name": "Corporate credit", "key": "Fixed Income", "markets_tab": "Rates & Credit",
     "what": "Bonds issued by companies: investment grade (safer) and high yield (riskier, higher coupons).",
     "why": "Extra yield over government bonds (the credit spread) in exchange for default risk.",
     "drivers": ["Credit spreads (widen in stress, tighten in good times)", "Default rates", "Government yields",
                 "Company leverage and interest coverage"],
     "risks": ["Defaults and downgrades", "Spreads widening sharply in recessions",
               "Liquidity: hard to sell in a crisis"],
     "metrics": ["Option-adjusted spread (OAS)", "Credit rating", "Interest coverage", "Net debt / EBITDA"],
     "how_pros": "Compare spread with expected default losses; credit is often an early warning for equities.",
     "in_vittantra": "Markets → Rates & Credit (spreads by rating), Valuation (synthetic rating → cost of debt).",
     "lessons": ["IA4"]},
    {"name": "Currencies (FX)", "key": "FX", "markets_tab": "FX",
     "what": "The price of one currency in another (e.g. EUR/USD). The world's most traded market.",
     "why": "Hedging foreign investments, carry (earning a higher interest rate), and macro views.",
     "drivers": ["Interest-rate differences between countries", "Growth and trade balances",
                 "Risk appetite (the dollar often rises in crises)", "Central bank policy"],
     "risks": ["Sudden reversals of carry trades", "Political and policy shocks",
               "Emerging-market currency crises"],
     "metrics": ["Spot rate", "Interest-rate differential (carry)", "Covered interest parity (forward points)",
                 "Dollar index (DXY)"],
     "how_pros": "Combine carry, value and momentum; always ask whether foreign returns are hedged.",
     "in_vittantra": "Markets → FX (G10, crosses, emerging markets, dollar index).",
     "lessons": ["IA5"]},
    {"name": "Commodities", "key": "Commodity", "markets_tab": "Commodities",
     "what": "Raw materials: energy (oil, gas), precious metals (gold), industrial metals (copper), agriculture.",
     "why": "Inflation protection and diversification; gold is a classic crisis hedge.",
     "drivers": ["Supply and demand (OPEC, weather, mining)", "Global growth (copper, oil)",
                 "The US dollar (commodities are priced in dollars)", "Real interest rates (for gold)"],
     "risks": ["Very high volatility", "Roll costs in futures-based funds",
               "Supply shocks and geopolitics"],
     "metrics": ["Spot vs futures (contango / backwardation)", "Inventories", "Real yields (gold)",
                 "Volatility"],
     "how_pros": "Use commodities tactically or as inflation hedges; mind how the fund holds them (futures).",
     "in_vittantra": "Markets → Commodities.",
     "lessons": []},
    {"name": "Digital assets (crypto)", "key": "Digital Asset", "markets_tab": "Digital Assets",
     "what": "Cryptocurrencies such as Bitcoin and Ether, stablecoins, and crypto ETFs.",
     "why": "A speculative, high-risk asset; some investors hold a small amount as a diversifier.",
     "drivers": ["Risk appetite and liquidity", "Regulation", "Adoption and flows (e.g. ETFs)",
                 "Supply rules (e.g. Bitcoin halving)"],
     "risks": ["Extreme volatility and 50–80% drawdowns", "Regulatory and custody risk",
               "Fraud and exchange failures"],
     "metrics": ["Volatility", "Drawdown", "Correlation with stocks", "On-chain activity"],
     "how_pros": "Size positions small, by risk rather than by dollars, and treat the asset as speculative.",
     "in_vittantra": "Markets → Digital Assets.",
     "lessons": []},
    {"name": "Real estate (including hotels and motels)", "key": "Real Estate", "markets_tab": "Real Estate",
     "what": "Property: offices, apartments, warehouses, retail, data centers, hotels and motels — owned directly "
             "or through listed REITs.",
     "why": "Income (rents), some inflation protection, and diversification.",
     "drivers": ["Interest rates and cap rates", "Occupancy and rent growth", "The economy",
                 "For hotels: travel demand, RevPAR (revenue per available room)"],
     "risks": ["Rising rates lower property values", "Sector shifts (e.g. offices after remote work)",
               "Leverage; hotels are especially cyclical"],
     "metrics": ["Cap rate (net operating income / value)", "FFO / AFFO (REIT earnings)", "Occupancy",
                 "RevPAR and ADR for hotels", "Loan-to-value"],
     "how_pros": "Value REITs on FFO, not P/E; compare cap rates with bond yields; look at each property type.",
     "in_vittantra": "Markets → Real Estate (REITs by property type, hotels and lodging, motels and economy).",
     "lessons": []},
    {"name": "Alternatives (private equity, VC, private credit, hedge strategies)", "key": "Alternative",
     "markets_tab": "Alternatives",
     "what": "Investments outside public stocks and bonds: private equity buyouts, venture capital, private "
             "credit, infrastructure and hedge-fund strategies.",
     "why": "Access to returns not available in public markets, and diversification — at the cost of fees and "
            "illiquidity.",
     "drivers": ["Company growth and exits (IPOs, sales)", "Leverage and interest rates (buyouts)",
                 "Fund manager skill", "Fundraising cycles"],
     "risks": ["Illiquidity: money locked up for 7–10 years", "High fees", "Valuations that lag public markets",
               "VC power law: a few winners must pay for many losses"],
     "metrics": ["IRR", "MOIC / TVPI and DPI", "Burn multiple and unit economics (VC)",
                 "Entry and exit multiples (PE)"],
     "how_pros": "VC: screen many deals, back a few, and price rounds with the VC method. PE: model an LBO "
                 "(debt, operating improvement, exit multiple).",
     "in_vittantra": "Markets → Alternatives (listed PE, BDCs, infrastructure), Academy → Private Equity / VC desk.",
     "lessons": ["PV1", "PV2", "PV3", "PV4", "PV5", "PV6"]},
]

# ==============================================================
# 5. FACTORS: how professionals decide what matters
# ==============================================================

PRO_METHOD = [
    ("Start with a reason", "A factor should have an economic story: cheap stocks are cheap because investors "
                            "fear them; momentum persists because news is absorbed slowly. No story → likely luck."),
    ("Measure it point in time", "Score every stock using only data known on each date, then compare the scores "
                                 "with the returns that came after (the information coefficient, IC)."),
    ("Check it is not luck", "Look at the t-statistic: above about 2 means the result is unlikely to be chance. "
                             "Check the hit rate (share of periods the factor worked)."),
    ("Weight by evidence", "Give more weight to factors that have predicted returns and none to those that have "
                           "not — Vittantra's IC-weighted rating does exactly this."),
    ("Control the risk", "A factor bet is also a risk bet: size it within a tracking-error budget and watch how "
                         "much of the portfolio's risk it uses."),
    ("Keep testing", "Factors fade when everyone uses them and behave differently by regime. Re-test regularly; "
                     "a short sample is evidence, not proof."),
]

STOCK_FACTORS: List[dict] = [
    {"pillar": "fundamental", "name": "Fundamentals (value, quality, growth)",
     "what": "Is the company cheap (earnings, cash-flow and book yields), profitable and well financed (ROE, "
             "margins, leverage), and growing?",
     "why": "Value and quality are among the most studied factors: cheap, profitable companies have earned more "
            "than expensive, weak ones over long periods, though not every year.",
     "measure": "SEC filings point in time → value, quality, growth and health scores ranked against peers."},
    {"pillar": "technical", "name": "Technical (trend and momentum)",
     "what": "Has the price been rising over the past 12 months (skipping the last month) and is it above its "
             "200-day average?",
     "why": "Momentum: winners tend to keep winning for months because investors react slowly to news. It can "
            "crash sharply when markets turn.",
     "measure": "12-1 month momentum and the trend versus the 200-day average from daily prices."},
    {"pillar": "quant", "name": "Quant (machine-learning ranking)",
     "what": "A model trained on many signals ranks which stocks are likely to do best over the next 20 days.",
     "why": "Combines many weak signals; must be tested walk-forward so it never sees the future.",
     "measure": "Walk-forward ML ranking (Day 55) converted to a 0–100 score."},
    {"pillar": "economic", "name": "Economic (macro fit)",
     "what": "Does the stock's sector suit the current macro regime (risk-on or risk-off, rates, spreads)?",
     "why": "Sectors react differently to the cycle: defensives hold up in slowdowns, cyclicals lead recoveries. "
            "Timing the regime is hard.",
     "measure": "Sector sensitivities to the regime set by credit spreads and Treasury yields (FRED)."},
    {"pillar": "risk", "name": "Risk (low volatility)",
     "what": "Is the stock calmer than others: lower volatility, lower beta, smaller drawdowns?",
     "why": "The low-volatility anomaly: calmer stocks have often delivered similar returns with less risk. In "
            "strong rallies, riskier stocks usually win.",
     "measure": "One-year volatility, beta and drawdown, scored so calmer = higher."},
]

MACRO_FACTOR_LABELS = {
    "equity_market": "Equity market", "interest_rates": "Interest rates", "inflation_expectations":
    "Inflation expectations", "credit_spreads": "Credit spreads", "us_dollar": "US dollar", "oil": "Oil",
}


def factor_evidence(base: Path = BASE_DIR) -> Optional[pd.DataFrame]:
    """Which stock factors have actually predicted returns in Vittantra's tests (Day 77 IC summary)."""
    path = base / IC_SUMMARY
    if not path.exists():
        return None
    ic = pd.read_csv(path).set_index("signal")
    rows = []
    for factor in STOCK_FACTORS:
        p = factor["pillar"]
        if p not in ic.index:
            continue
        mean, t, hit = (float(ic.at[p, c]) for c in ("mean_ic", "ic_t_stat", "hit_rate"))
        verdict = ("Predictive so far" if mean > 0 and t >= 2 else
                   "Worked in reverse so far" if mean < 0 and t <= -2 else "Not proven yet")
        rows.append({"factor": factor["name"], "mean_ic": mean, "t_stat": t, "hit_rate": hit,
                     "periods": int(ic.at[p, "dates"]), "verdict": verdict})
    return pd.DataFrame(rows)


def macro_drivers(key: str, base: Path = BASE_DIR) -> Optional[pd.DataFrame]:
    """Which macro factors actually moved an asset class over the past year (median |t| of daily betas)."""
    path = base / MACRO_BETAS
    if not path.exists():
        return None
    betas = pd.read_csv(path)
    rows = betas[betas["asset_class"] == key]
    if rows.empty:
        return None
    out = []
    for factor, label in MACRO_FACTOR_LABELS.items():
        if f"t_{factor}" not in rows:
            continue
        t = pd.to_numeric(rows[f"t_{factor}"], errors="coerce")
        b = pd.to_numeric(rows[f"beta_{factor}"], errors="coerce")
        out.append({"factor": label, "median_abs_t": float(t.abs().median()),
                    "share_significant": float((t.abs() >= 2).mean()), "median_beta": float(b.median())})
    return pd.DataFrame(out).sort_values("median_abs_t", ascending=False).reset_index(drop=True)


# ==============================================================
# 6. GLOSSARY
# ==============================================================

GLOSSARY: Dict[str, str] = {
    "Active share": "How different a portfolio's holdings are from its benchmark (0% = identical, 100% = no overlap).",
    "Alpha": "Return above what the risk taken would explain; in Vittantra, expected alpha = IC × volatility × score.",
    "Attribution (Brinson)": "Splits active return into allocation (sector weights) and selection (stock picking).",
    "Beta": "Sensitivity to the market: beta 1.2 means about 12% move for a 10% market move.",
    "Burn multiple": "Cash burned ÷ new annual recurring revenue added; below 1–1.5 is efficient for a startup.",
    "Cap rate": "A property's net operating income ÷ its value; like an earnings yield for real estate.",
    "CAPM": "Cost of equity = risk-free rate + beta × equity risk premium.",
    "Convexity": "How a bond's duration changes as yields change; positive convexity cushions losses.",
    "Credit spread": "Extra yield a company bond pays over a government bond, for default risk.",
    "DCF": "Discounted cash flow: value = future free cash flows discounted at the cost of capital.",
    "DDM": "Dividend discount model: value = future dividends discounted at the cost of equity.",
    "Drawdown": "Fall from a peak to a trough; max drawdown is the worst such fall.",
    "Duration": "Approximate % price change of a bond for a 1 percentage-point change in yield.",
    "Euler risk contribution": "Each position's share of total portfolio risk; the shares add up to 100%.",
    "Expected shortfall (ES)": "The average loss on the days worse than VaR.",
    "FFO": "Funds from operations: REIT earnings with property depreciation added back.",
    "Information coefficient (IC)": "Correlation between a signal's scores and later returns; 0.05 is useful.",
    "Information ratio (IR)": "Active return ÷ tracking error: reward per unit of active risk.",
    "IPS": "Investment policy statement: the client's objectives, constraints and allowed investments.",
    "IRR": "The discount rate that makes the value of an investment's cash flows zero; its annualized return.",
    "LBO": "Leveraged buyout: buying a company mostly with debt, paid down from its cash flows.",
    "Liquidation preference": "Investors get their money back first in a sale (e.g. 1× non-participating).",
    "Look-ahead bias": "Using information in a backtest that was not available at the time; Vittantra avoids it.",
    "MOIC": "Multiple on invested capital: money returned ÷ money invested.",
    "Option-pool shuffle": "Creating the employee option pool before a round, which dilutes founders, not investors.",
    "Point in time": "Using data only as it was known on each date (e.g. filings by their filing date).",
    "Post-money valuation": "Pre-money valuation + the new investment.",
    "Residual income": "Value = book value + future profits above the cost of equity; used for banks.",
    "Reverse DCF": "Solving for the growth rate the current price implies.",
    "RevPAR": "Hotel revenue per available room = occupancy × average daily rate.",
    "Sharpe ratio": "Excess return over cash ÷ volatility.",
    "Suitability": "Advice must fit the client's profile and IPS (CFA Standard III(C)).",
    "Tracking error": "Volatility of a portfolio's return relative to its benchmark.",
    "TVPI / DPI": "Fund multiples: total value ÷ paid-in (TVPI) and distributions ÷ paid-in (DPI, cash returned).",
    "VaR": "Value at risk: a loss level exceeded on only, say, 1 day in 20 (95%) or 1 in 100 (99%).",
    "WACC": "Weighted average cost of capital: blended cost of equity and after-tax debt.",
    "Yield curve": "Yields by maturity; inverted (short above long) has often come before recessions.",
    "Yield to maturity": "The annual return on a bond held to maturity, if all payments are made.",
}

# ==============================================================
# LIVE NUMBERS (from saved Vittantra data only)
# ==============================================================


def asset_snapshot(key: str, base: Path = BASE_DIR) -> Optional[dict]:
    """Live summary of one asset class from the Day 76c analytics, or None if unavailable."""
    path = base / ANALYTICS
    if not path.exists():
        return None
    data = pd.read_csv(path)
    rows = data[data["asset_class"] == key]
    if rows.empty:
        return None
    ret, vol = pd.to_numeric(rows["return_12m"], errors="coerce"), pd.to_numeric(rows["volatility_1y"], errors="coerce")
    dd = pd.to_numeric(rows["max_drawdown_1y"], errors="coerce")
    best = rows.loc[ret.idxmax()] if ret.notna().any() else None
    worst = rows.loc[ret.idxmin()] if ret.notna().any() else None
    return {
        "instruments": int(len(rows)),
        "sub_classes": sorted(rows["sub_class"].dropna().unique().tolist()),
        "median_return_12m": float(ret.median()) if ret.notna().any() else None,
        "median_volatility": float(vol.median()) if vol.notna().any() else None,
        "worst_drawdown": float(dd.min()) if dd.notna().any() else None,
        "best": (best["name"], float(ret.max())) if best is not None else None,
        "worst": (worst["name"], float(ret.min())) if worst is not None else None,
        "as_of": str(rows["as_of"].dropna().max()) if "as_of" in rows else None,
    }


def search_glossary(query: str) -> Dict[str, str]:
    q = query.strip().lower()
    if not q:
        return dict(GLOSSARY)
    return {term: text for term, text in GLOSSARY.items() if q in term.lower() or q in text.lower()}
