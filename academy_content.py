"""
Vittantra Academy — curriculum content.

ROLES: what each job is, its framework, duties by frequency, outputs,
tools, career path and credentials.
LESSONS: concept → formula → live example (academy_live) → where in the
code → on the job → exercise → interview questions with model answers.

Content is general industry practice for learning purposes; firms differ.
"""

ROLES = {
    "investment_analyst": {
        "title": "Investment Analyst (multi-asset / macro)",
        "mission": "Form views on asset classes and markets — rates, credit, currencies, commodities, "
                   "equities — and explain what is priced in and what could change it.",
        "framework": [
            "**Top-down:** economy → policy (central banks) → asset classes → regions/sectors → instruments.",
            "**Valuation vs. momentum vs. sentiment:** is it cheap, is it trending, how crowded is it?",
            "**Scenario thinking:** base, bull and bear cases with probabilities and signposts.",
            "**Risk-adjusted view:** return per unit of risk, correlation to the rest of the portfolio.",
        ],
        "duties": {
            "Daily": ["Read overnight markets and news; write a morning brief",
                      "Track yields, spreads, FX, commodities, volatility for unusual moves",
                      "Answer portfolio managers' questions quickly with data"],
            "Weekly": ["Asset-class dashboard and notes; economic data previews and reviews",
                       "Update models (curve, carry, momentum, valuation)"],
            "Monthly": ["Asset-allocation view: overweight / neutral / underweight with reasons",
                        "Present to the investment committee"],
            "Quarterly": ["Deep dives (e.g. 'Is credit too expensive?'); scenario and stress refresh"],
        },
        "outputs": ["Morning brief", "Market dashboard", "Asset-allocation recommendation", "Research notes"],
        "tools": ["Bloomberg/Refinitiv (Vittantra uses free Yahoo/FRED)", "Excel/Python", "Economic calendars"],
        "kpis": ["Accuracy and usefulness of views", "Speed and clarity", "Contribution to portfolio decisions"],
        "career": "Analyst → Senior analyst / strategist → Portfolio manager or CIO office",
        "credentials": "CFA is the common standard; CAIA for alternatives.",
        "vittantra": "Markets page, Data hub, Command Center",
    },
    "equity_researcher": {
        "title": "Equity Research Analyst",
        "mission": "Become the expert on a set of companies and sectors; estimate what each company is worth "
                   "and recommend buy / hold / sell with evidence.",
        "framework": [
            "**Business quality:** what it sells, competitive advantage (moat), management, unit economics.",
            "**Financial analysis:** income statement, balance sheet, cash flow; growth, margins, returns, leverage.",
            "**Valuation:** multiples (P/E, EV/EBIT, FCF yield) vs. peers and history; discounted cash flow (DCF).",
            "**Thesis + catalysts + risks:** why the market is wrong, what will prove it, what would break it.",
        ],
        "duties": {
            "Daily": ["Monitor news, filings and price moves for covered companies",
                      "Update notes; answer sales/PM questions"],
            "Weekly": ["Maintain financial models; industry data checks; management or expert calls"],
            "Quarterly": ["Earnings season: preview, read results and the call, update model and rating within hours",
                          "Publish earnings notes"],
            "Annually": ["Initiation reports and sector deep dives; review every thesis"],
        },
        "outputs": ["Financial model", "Earnings note", "Initiation report", "Rating and price target"],
        "tools": ["SEC filings (EDGAR)", "Excel models", "Earnings call transcripts", "Industry data"],
        "kpis": ["Rating and target accuracy", "Insight quality", "Client/PM feedback"],
        "career": "Associate → Analyst → Senior analyst / sector head → Portfolio manager",
        "credentials": "CFA; in the US, FINRA Series 86/87 for sell-side research analysts.",
        "vittantra": "Research page, fundamental_engine.py, us_fundamental_engine.py",
    },
    "portfolio_analyst": {
        "title": "Portfolio / Risk Analyst",
        "mission": "Measure, explain and control the risk of portfolios so that losses stay within what the "
                   "client and the firm agreed to.",
        "framework": [
            "**Identify:** what risks exist — market, credit, liquidity, concentration, model, operational.",
            "**Measure:** volatility, VaR/Expected Shortfall, stress tests, sensitivities (duration, Greeks).",
            "**Attribute:** which positions and factors create the risk (risk contributions).",
            "**Control & report:** limits and budgets, breach escalation, governance, audit trail.",
        ],
        "duties": {
            "Daily": ["Run risk reports; check limits and breaches; escalate exceptions",
                      "Reconcile positions and prices (bad data = wrong risk)"],
            "Weekly": ["Stress tests and scenario analysis; risk commentary for PMs"],
            "Monthly": ["Risk committee pack; VaR backtesting; risk-budget review"],
            "Quarterly": ["Model validation; limit framework review; regulatory reporting support"],
        },
        "outputs": ["Daily risk report", "Breach log", "Stress-test pack", "Risk committee presentation"],
        "tools": ["Risk systems (e.g. MSCI RiskMetrics, Aladdin)", "Python/SQL", "Excel"],
        "kpis": ["Timely, accurate reporting", "No missed breaches", "Clear explanations"],
        "career": "Risk analyst → Risk manager → Head of risk / CRO",
        "credentials": "FRM is the common risk credential; CFA also valued.",
        "vittantra": "Risk Intelligence, Governance, Remediation pages; Days 35–70",
    },
    "portfolio_manager": {
        "title": "Portfolio Manager",
        "mission": "Turn research into a portfolio that meets the client's objective and risk limits, and be "
                   "accountable for its performance.",
        "framework": [
            "**Objective & constraints:** return target, risk limits, benchmark, liquidity, horizon (from the IPS).",
            "**Portfolio construction:** position sizing from conviction and risk, diversification, risk budgets.",
            "**Implementation:** trading costs, turnover, timing; rebalancing rules.",
            "**Review:** performance and attribution — was it skill (alpha) or exposure (beta/factors) or luck?",
        ],
        "duties": {
            "Daily": ["Review markets, risk and positions; decide trades with traders; read research"],
            "Weekly": ["Team meeting with analysts; idea pipeline; check risk budget use"],
            "Monthly": ["Performance and attribution review; client/consultant reporting"],
            "Quarterly": ["Strategy review; rebalance to targets; investment committee"],
        },
        "outputs": ["Portfolio decisions and trade list", "Performance & attribution report", "Client letters"],
        "tools": ["Order management system", "Risk system", "Optimizer", "Research"],
        "kpis": ["Risk-adjusted return vs. benchmark (Sharpe, information ratio)", "Staying within limits"],
        "career": "Analyst → Associate PM → PM → Senior PM / CIO",
        "credentials": "CFA is the most common.",
        "vittantra": "Portfolio page; Days 56–66; Day 79–80 (coming)",
    },
    "advisor": {
        "title": "Investment Advisor (retail and institutional)",
        "mission": "Understand a client's goals and limits, recommend a suitable plan, and keep acting in "
                   "the client's best interest over time.",
        "framework": [
            "**Know your client (KYC):** goals, horizon, income, assets, liabilities, risk tolerance and capacity.",
            "**Investment Policy Statement (IPS):** objectives, constraints, asset allocation, review rules.",
            "**Suitability / best interest:** every recommendation must fit that client and be documented.",
            "**Ongoing review & communication:** rebalance, report clearly, adjust when life changes.",
        ],
        "duties": {
            "Daily": ["Client calls and meetings; answer questions in plain language; document advice"],
            "Weekly": ["Prepare client reviews; monitor portfolios against their IPS"],
            "Quarterly": ["Client reports and review meetings; rebalancing proposals"],
            "Annually": ["Full plan review: goals, risk profile, tax and estate considerations"],
        },
        "outputs": ["Risk profile", "IPS / financial plan", "Suitability record", "Client report"],
        "tools": ["Planning software", "Portfolio reporting", "CRM"],
        "kpis": ["Client outcomes and retention", "Compliance record", "Trust"],
        "career": "Associate → Advisor → Senior advisor / wealth manager → Head of advisory",
        "credentials": "US: Series 65 (or 66) and often CFP. India: NISM Investment Adviser certification "
                       "and SEBI RIA registration.",
        "vittantra": "Governance & approval workflow; Days 82–84 (coming)",
    },
}


def _q(question, answer):
    return {"question": question, "answer": answer}


LESSONS = [
    # ---------------- Investment Analyst ----------------
    {
        "id": "IA1", "role": "investment_analyst", "title": "Returns: how much did it make?",
        "concept": "A return is the percentage gain or loss over a period. Simple returns add across assets "
                   "in a portfolio; compounding links them across time. Annualizing makes different "
                   "periods comparable. Total return includes dividends/coupons (Vittantra uses adjusted prices).",
        "formulas": [("Simple return", r"R_t = \frac{P_t}{P_{t-1}} - 1"),
                     ("Compounding", r"1 + R_{0,T} = \prod_{t=1}^{T}(1 + R_t)"),
                     ("Annualized (CAGR)", r"R_{ann} = (1 + R_{0,T})^{1/\text{years}} - 1")],
        "live": "ia_returns", "code": ["multi_asset_universe.py → instrument_analytics"],
        "on_the_job": "Every morning brief starts with 'what moved and how much' across asset classes.",
        "exercise": "If an asset rises 50% then falls 50%, what is the total return? Why is it not zero?",
        "interview": [_q("Why do analysts compound returns instead of adding them?",
                         "Because each period's return is earned on a changing base; +50% then −50% is −25%, not 0%."),
                      _q("What is the difference between price return and total return?",
                         "Total return adds income (dividends, coupons) reinvested; price return ignores it.")],
    },
    {
        "id": "IA2", "role": "investment_analyst", "title": "Volatility: how bumpy is the ride?",
        "concept": "Volatility is the standard deviation of returns — how widely returns swing around their "
                   "average. It is annualized with the square root of the number of trading periods per year, "
                   "because variance grows with time.",
        "formulas": [("Sample volatility", r"\sigma = \sqrt{\frac{1}{n-1}\sum_{t=1}^{n}(R_t-\bar R)^2}"),
                     ("Annualize", r"\sigma_{ann} = \sigma_{daily}\sqrt{N},\; N\approx 252 \text{ (stocks)}, 365 \text{ (crypto)}")],
        "live": "ia_volatility", "code": ["multi_asset_universe.py → instrument_analytics"],
        "on_the_job": "Volatility sizes positions and sets expectations: a 20% vol asset moving 3% in a day is normal.",
        "exercise": "A stock has 1.5% daily volatility. What is its annual volatility? (Answer: ≈23.8%)",
        "interview": [_q("Why multiply by the square root of time?",
                         "If returns are independent, variances add over time, so standard deviation grows with √time."),
                      _q("Is volatility the same as risk?",
                         "No — it ignores the size of tail losses, liquidity and permanent loss; it is one measure.")],
    },
    {
        "id": "IA3", "role": "investment_analyst", "title": "The yield curve",
        "concept": "The yield curve plots government bond yields by maturity. Normally longer maturities pay "
                   "more. When short rates exceed long rates (inversion), markets expect rate cuts — "
                   "historically a recession warning. Nominal yield ≈ real yield + expected inflation.",
        "formulas": [("Slope", r"\text{2s10s} = y_{10Y} - y_{2Y},\quad \text{3m10y} = y_{10Y} - y_{3M}"),
                     ("Fisher relation", r"(1 + i) = (1 + r)(1 + \pi^e) \;\Rightarrow\; i \approx r + \pi^e")],
        "live": "ia_yield_curve", "code": ["multi_asset_universe.py → yield_curve_table, curve_summary"],
        "on_the_job": "Curve moves drive mortgage rates, bank profits, equity valuations and bond fund returns.",
        "exercise": "If 10Y nominal is 5.2% and 10Y breakeven inflation is 2.4%, what real yield is implied?",
        "interview": [_q("Why can an inverted curve signal recession?",
                         "Investors expect the central bank to cut rates because growth will slow; banks' lending "
                         "margins also shrink."),
                      _q("What does breakeven inflation measure?",
                         "The inflation rate at which nominal Treasuries and TIPS give the same return.")],
    },
    {
        "id": "IA4", "role": "investment_analyst", "title": "Credit spreads",
        "concept": "A credit spread is the extra yield a company pays over a government bond of similar maturity "
                   "to compensate for default risk and illiquidity. Spreads widen in stress and tighten in calm.",
        "formulas": [("Spread", r"s = y_{corp} - y_{gov}"),
                     ("Expected-loss intuition", r"s \approx PD \times (1 - \text{Recovery}) + \text{risk premium}")],
        "live": "ia_credit", "code": ["multi_asset_universe.py → credit_table"],
        "on_the_job": "Credit spreads are a real-time gauge of risk appetite; they often move before equities.",
        "exercise": "If default probability is 3% a year and recovery is 40%, what spread covers expected loss?",
        "interview": [_q("Why might CCC spreads widen while AAA spreads stay calm?",
                         "Stress hits the weakest borrowers first — refinancing risk rises for them."),
                      _q("What is a 'percentile in history' telling you?",
                         "Whether spreads are tight (credit expensive) or wide (cheap) relative to the past.")],
    },
    {
        "id": "IA5", "role": "investment_analyst", "title": "FX and carry",
        "concept": "Holding a currency earns its interest rate. Long a pair = long the base currency, short the "
                   "quote currency, so carry ≈ base rate − quote rate (covered interest parity sets forward "
                   "points). Carry pays only if the exchange rate does not move against you.",
        "formulas": [("Carry", r"\text{carry} \approx r_{base} - r_{quote}"),
                     ("Forward (CIP)", r"F = S \times \frac{1 + r_{quote}}{1 + r_{base}}")],
        "live": "ia_fx_carry", "code": ["multi_asset_universe.py → fx_carry_table"],
        "on_the_job": "Carry trades are popular in calm markets and unwind violently in crises.",
        "exercise": "Long USD/JPY with US rates 4% and Japanese 0.5%: what carry, and what is the main risk?",
        "interview": [_q("Why do carry trades crash suddenly?",
                         "Everyone exits at once when risk appetite falls, so high-yield currencies drop together."),
                      _q("What does carry-to-volatility measure?",
                         "Income per unit of currency risk — a Sharpe-like ratio for the trade.")],
    },
    {
        "id": "IA6", "role": "investment_analyst", "title": "Reading the news like a professional",
        "concept": "Prices move first; the story arrives later. Start from the data (what moved, how much versus "
                   "normal), then look for the news that could explain it, then ask whether it changes the outlook "
                   "or is noise. Central-bank statements, inflation and jobs releases, and earnings move the most "
                   "assets. Always know what is on the calendar this week.",
        "formulas": [("Surprise", r"\text{surprise} = \text{actual} - \text{expected}"),
                     ("Size of a move", r"z = \frac{r_t}{\sigma_{\text{daily}}}")],
        "live": "ia_world_brief", "code": ["world_brief.py → collect_headlines, build_brief, build_calendar"],
        "on_the_job": "Morning meetings open with 'what happened overnight and why'; a good analyst separates "
                      "the cause from the coincidence and flags the event that matters this week.",
        "exercise": "Pick today's biggest data move in the brief. Find one headline that could explain it and "
                    "one reason it might be a coincidence.",
        "interview": [_q("Why do markets sometimes fall on good news?",
                         "Prices react to the surprise versus expectations, not the news itself; 'good' data can "
                         "also mean higher rates for longer."),
                      _q("Which scheduled releases move US markets most?",
                         "FOMC decisions, CPI, the jobs report (Employment Situation), GDP and PCE inflation.")],
    },
    # ---------------- Equity Researcher ----------------
    {
        "id": "ER1", "role": "equity_researcher", "title": "Reading the three statements (from SEC filings)",
        "concept": "Income statement = performance over a period; balance sheet = what the company owns and owes "
                   "at a date; cash-flow statement = actual cash in and out. Analysts use trailing twelve months "
                   "(TTM) so every company is compared over a full year.",
        "formulas": [("TTM", r"\text{TTM} = \text{FY}_{last} + \text{YTD}_{now} - \text{YTD}_{last\ year}"),
                     ("Free cash flow", r"FCF = \text{Operating cash flow} - \text{Capex}")],
        "live": "er_statements", "code": ["fundamental_engine.py → ttm_value, compute_company_metrics"],
        "on_the_job": "Earnings season means reading 10-Qs within hours and updating the model.",
        "exercise": "Why is free cash flow sometimes far below net income? Name two reasons.",
        "interview": [_q("Walk me through how depreciation flows through the three statements.",
                         "It lowers operating income and net income, is added back in operating cash flow, and "
                         "reduces the asset's book value (PP&E) on the balance sheet."),
                      _q("Why use TTM instead of the last annual report?",
                         "It uses the most recent four quarters, so numbers are current and comparable.")],
    },
    {
        "id": "ER2", "role": "equity_researcher", "title": "Valuation multiples",
        "concept": "Multiples compare price to a fundamental. P/E uses earnings; EV/EBIT compares the whole firm "
                   "(debt + equity − cash) to operating profit, so companies with different debt levels compare "
                   "fairly. Yields (E/P, FCF/P) rank correctly even when earnings are negative.",
        "formulas": [("P/E and earnings yield", r"P/E = \frac{\text{Market cap}}{\text{Net income}},\quad E/P = \frac{1}{P/E}"),
                     ("Enterprise value", r"EV = \text{Market cap} + \text{Debt} - \text{Cash}"),
                     ("FCF yield", r"\frac{FCF}{\text{Market cap}}")],
        "live": "er_valuation", "code": ["fundamental_engine.py → compute_company_metrics (value section)"],
        "on_the_job": "Every rating comes with a valuation table against peers and the company's own history.",
        "exercise": "Two companies earn the same EBIT; one has lots of debt. Which looks cheaper on P/E, and which on EV/EBIT?",
        "interview": [_q("When is P/E misleading?",
                         "With negative or one-off earnings, very different leverage, or heavy non-cash charges."),
                      _q("Why use EV instead of market cap with EBIT?",
                         "EBIT belongs to both debt and equity holders, so it must be compared with the value of both.")],
    },
    {
        "id": "ER3", "role": "equity_researcher", "title": "Business quality: returns and margins",
        "concept": "Quality businesses earn high returns on capital and convert profit into cash. ROE can be "
                   "split (DuPont) into margin × asset turnover × leverage, which shows *why* ROE is high. "
                   "Accruals (profit not backed by cash) are a warning sign.",
        "formulas": [("ROE (DuPont)", r"ROE = \frac{NI}{Sales}\times\frac{Sales}{Assets}\times\frac{Assets}{Equity}"),
                     ("Accruals ratio", r"\frac{NI - CFO}{\text{Average assets}}")],
        "live": "er_quality", "code": ["fundamental_engine.py → compute_company_metrics (quality section)"],
        "on_the_job": "A high ROE driven by leverage is very different from one driven by margins.",
        "exercise": "Company A: margin 5%, turnover 2.5×, leverage 2×. Company B: margin 25%, turnover 0.5×, leverage 2×. Compare ROE.",
        "interview": [_q("Why can ROE be meaningless for some companies?",
                         "If equity is negative or tiny (e.g. after big buybacks), ROE becomes huge or flips sign."),
                      _q("What do high accruals suggest?",
                         "Earnings are not turning into cash — possible aggressive accounting or working-capital strain.")],
    },
    {
        "id": "ER4", "role": "equity_researcher", "title": "Financial health and leverage",
        "concept": "Leverage magnifies returns and risk. Analysts check how much debt exists, whether profits "
                   "cover interest comfortably, and how many years of EBITDA would repay net debt. Banks are "
                   "judged differently — on capital strength — because borrowing is their business model.",
        "formulas": [("Interest coverage", r"\frac{EBIT}{\text{Interest expense}}"),
                     ("Net debt / EBITDA", r"\frac{\text{Debt} - \text{Cash}}{EBIT + D\&A}"),
                     ("Capital strength", r"\frac{\text{Equity}}{\text{Assets}}")],
        "live": "er_health", "code": ["fundamental_engine.py → compute_company_metrics (health section)"],
        "on_the_job": "Leverage checks matter most when rates rise and debt must be refinanced.",
        "exercise": "EBIT $500M, interest $200M, net debt $3B, D&A $250M: compute coverage and net debt/EBITDA.",
        "interview": [_q("Why not use debt/equity for a bank?",
                         "Deposits and borrowing are a bank's raw material; capital ratios measure its safety instead."),
                      _q("What level of net debt/EBITDA worries you?",
                         "It depends on the industry's stability; above roughly 3–4× is often a warning for cyclicals.")],
    },
    {
        "id": "ER5", "role": "equity_researcher", "title": "Point-in-time data and look-ahead bias",
        "concept": "A backtest may only use information that was public at that date. Quarterly results arrive "
                   "weeks after the quarter ends, and restatements arrive later still. Using them early makes a "
                   "strategy look better than it could ever have been.",
        "formulas": [("Rule", r"\text{use fact at date } t \iff \text{filed}(fact) \le t")],
        "live": "er_point_in_time", "code": ["fundamental_engine.py → facts_frame"],
        "on_the_job": "Quant and fundamental teams both lose credibility if a backtest leaks future data.",
        "exercise": "A company's Q2 ends June 30 and is filed August 5. On July 15, which quarter's data may you use?",
        "interview": [_q("Name two forms of look-ahead bias.",
                         "Using data before its publication date; using today's index members (survivorship) in the past."),
                      _q("How did Vittantra prevent it in fundamentals?",
                         "Each fact is used only if its SEC filing date is on or before the analysis date.")],
    },
    {
        "id": "ER6", "role": "equity_researcher", "title": "Intrinsic value: DCF, residual income and DDM",
        "concept": "A share is worth the present value of the cash it will produce. Three standard routes: discount "
                   "free cash flow to the firm at the WACC (DCF), add the present value of profits above the cost "
                   "of equity to book value (residual income), or discount dividends (DDM). Choose the model that "
                   "fits the business: banks → residual income, steady dividend payers → DDM, most others → DCF. "
                   "Then run it backwards: what growth does today's price imply?",
        "formulas": [("FCFF", r"FCFF = CFO + Int(1-t) - \text{Capex}"),
                     ("WACC", r"WACC = \tfrac{E}{V} r_e + \tfrac{D}{V} r_d (1-t)"),
                     ("CAPM", r"r_e = r_f + \beta \times ERP"),
                     ("Terminal value", r"TV_N = \frac{FCFF_N (1+g)}{WACC - g}"),
                     ("Residual income", r"V_0 = B_0 + \sum_t \frac{(ROE_t - r_e) B_{t-1}}{(1+r_e)^t}"),
                     ("Gordon growth", r"V_0 = \frac{D_1}{r - g}")],
        "live": "er_intrinsic_value", "code": ["valuation_engine.py → value_company",
                                               "vittantra_pricing.py → two_stage_value, residual_income_value"],
        "on_the_job": "Every initiation report has a valuation section with a DCF, a sensitivity table and a "
                      "cross-check; the reverse DCF is how buy-side PMs test whether expectations are too high.",
        "exercise": "FCFF next year $5bn, WACC 9%, growth 3% forever, debt $20bn, cash $5bn, 1bn shares. "
                    "What is the value per share?",
        "interview": [_q("Why not use a DCF for a bank?",
                         "Debt is a bank's raw material, not financing, so FCFF and WACC are not meaningful; use "
                         "residual income or dividends on equity."),
                      _q("What share of a DCF usually comes from the terminal value, and why does it matter?",
                         "Often 60–80%; small changes in WACC or terminal growth move the value a lot, so show a "
                         "sensitivity table."),
                      _q("What is a reverse DCF?",
                         "Solving for the growth rate that makes the DCF value equal the market price — it shows "
                         "what the market already expects.")],
    },
    {
        "id": "ER7", "role": "equity_researcher", "title": "Writing an evidence-linked research note",
        "concept": "A professional note states a rating, the thesis, the valuation, a bull case, a bear case and the "
                   "key risks — and every claim is traceable to data. Separate facts (numbers from filings and "
                   "markets) from opinions (your forecast). Say what you do not know.",
        "formulas": [("Rule", r"\text{claim} \Rightarrow (\text{source}, \text{field}, \text{value})")],
        "live": "er_research_note", "code": ["research_report.py → build_report, report_markdown"],
        "on_the_job": "Compliance reviews notes for a reasonable basis; PMs read the bear case first.",
        "exercise": "Read a Vittantra note. Which single piece of evidence would change your view most, and why?",
        "interview": [_q("What does CFA Standard V(A) require of a research report?",
                         "Diligence and a reasonable and adequate basis, supported by appropriate research."),
                      _q("What does Standard V(B) require?",
                         "Disclose the basic process and key risks, and distinguish fact from opinion.")],
    },
    # ---------------- Portfolio / Risk Analyst ----------------
    {
        "id": "RA1", "role": "portfolio_analyst", "title": "Value at Risk and Expected Shortfall",
        "concept": "Historical VaR revalues today's portfolio under each past day's returns and reads off a loss "
                   "quantile. Expected Shortfall is the average loss beyond VaR — it describes the tail VaR ignores.",
        "formulas": [("VaR", r"\text{VaR}_\alpha = \text{quantile}_\alpha(\text{Loss})"),
                     ("Expected Shortfall", r"ES_\alpha = E[\text{Loss} \mid \text{Loss} \ge \text{VaR}_\alpha]")],
        "live": "ra_var", "code": ["var_engine.py → calculate_historical_var"],
        "on_the_job": "VaR is in every daily risk report; limits are often set on it.",
        "exercise": "If 95% 1-day VaR is $10,000, roughly how often should losses exceed it over 250 days?",
        "interview": [_q("What are VaR's main weaknesses?",
                         "It says nothing about losses beyond the threshold, depends on the history window, and "
                         "is not sub-additive in general."),
                      _q("Why do regulators prefer Expected Shortfall?",
                         "It captures tail severity and is a coherent risk measure.")],
    },
    {
        "id": "RA2", "role": "portfolio_analyst", "title": "Backtesting VaR (Kupiec test)",
        "concept": "A VaR model should be breached about as often as promised. The Kupiec test compares the "
                   "observed breach rate with the expected one; Christoffersen adds a check that breaches do not cluster.",
        "formulas": [("Kupiec LR", r"LR = -2\ln\frac{(1-p)^{T-x}p^{x}}{(1-\hat p)^{T-x}\hat p^{x}} \sim \chi^2_1")],
        "live": "ra_backtest", "code": ["var_validation.py → kupiec_pof_test, christoffersen_independence_test"],
        "on_the_job": "Monthly model validation; too many breaches forces a model review.",
        "exercise": "Over 500 days at 99% VaR, how many breaches are expected? Would 12 worry you?",
        "interview": [_q("What if a VaR model has too few breaches?",
                         "It is too conservative — capital is wasted; Kupiec rejects both too many and too few."),
                      _q("Why test clustering?",
                         "Breaches bunched together mean the model reacts too slowly to changing volatility.")],
    },
    {
        "id": "RA3", "role": "portfolio_analyst", "title": "Stress testing and bond duration",
        "concept": "Stress tests apply severe but plausible shocks. For bonds, duration measures sensitivity to "
                   "yield changes and convexity corrects for curvature; full repricing is most accurate.",
        "formulas": [("Price change", r"\frac{\Delta P}{P} \approx -D_{mod}\,\Delta y + \tfrac{1}{2} C\,(\Delta y)^2"),
                     ("DV01", r"DV01 = MV \times D_{mod} \times 0.0001")],
        "live": "ra_stress_duration", "code": ["cross_asset_stress.py → full_revaluation_effects",
                                               "vittantra_pricing.py → bond_analytics"],
        "on_the_job": "Stress packs go to the risk committee monthly; regulators require them.",
        "exercise": "A bond fund with duration 6 faces a 150bp rate rise. Estimate the loss (ignore convexity).",
        "interview": [_q("Why did Vittantra's original stress test show 0% bond loss?",
                         "Duration was never passed to the stress engine, so the rate sensitivity silently became zero."),
                      _q("Macaulay vs. modified duration?",
                         "Macaulay is a weighted-average time; modified duration = Macaulay ÷ (1 + y/f) and measures price sensitivity.")],
    },
    {
        "id": "RA4", "role": "portfolio_analyst", "title": "Option Greeks and delta-adjusted exposure",
        "concept": "Options are non-linear. Delta is the change in option value per $1 move in the underlying; "
                   "exposure should be measured as delta × underlying value, not the premium paid.",
        "formulas": [("Black-Scholes call", r"C = S N(d_1) - K e^{-rT} N(d_2)"),
                     ("Delta exposure", r"\Delta \times S \times \text{contracts} \times \text{multiplier}")],
        "live": "ra_greeks", "code": ["vittantra_pricing.py → black_scholes_price, black_scholes_delta",
                                      "vittantra_risk_model.py → economic_exposure"],
        "on_the_job": "Risk reports show option books in delta-equivalent terms plus gamma and vega.",
        "exercise": "A call has delta 0.6; the stock is $200; you hold 10 contracts of 100 shares. What is the delta exposure?",
        "interview": [_q("Why is the premium a bad measure of option risk?",
                         "A small premium can control a large underlying position; losses follow the underlying via delta."),
                      _q("What does gamma tell you?",
                         "How fast delta changes — the risk of exposure shifting as the price moves.")],
    },
    {
        "id": "RA5", "role": "portfolio_analyst", "title": "Risk contributions and risk budgets",
        "concept": "Portfolio risk is not the sum of position risks because of correlation. Euler contributions "
                   "split total volatility into parts that add up exactly; risk budgets cap each part.",
        "formulas": [("Portfolio volatility", r"\sigma_p = \sqrt{x^\top \Sigma x}"),
                     ("Euler contribution", r"RC_i = x_i \frac{(\Sigma x)_i}{\sigma_p},\quad \sum_i RC_i = \sigma_p")],
        "live": "ra_risk_contribution", "code": ["vittantra_risk_model.py → euler_risk_contributions",
                                                 "portfolio_risk_budgeting.py"],
        "on_the_job": "Risk budgeting tells a PM where the next unit of risk should go.",
        "exercise": "Why can a position with a large weight have a small (or negative) risk contribution?",
        "interview": [_q("Why not just use position weights?",
                         "A 10% position in a volatile, correlated asset can carry far more risk than 30% in a stable hedge."),
                      _q("What does a negative risk contribution mean?",
                         "The position hedges the rest of the portfolio — adding a little reduces total risk.")],
    },
    # ---------------- Portfolio Manager ----------------
    {
        "id": "PM1", "role": "portfolio_manager", "title": "Diversification",
        "concept": "Combining assets that do not move together reduces risk without necessarily reducing "
                   "expected return. The lower the correlation, the bigger the benefit.",
        "formulas": [("Two-asset variance", r"\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\rho\sigma_1\sigma_2")],
        "live": "pm_diversification", "code": ["vittantra_risk_model.py → euler_risk_contributions"],
        "on_the_job": "Correlations change in crises (often rising), so diversification must be stress-tested.",
        "exercise": "Two assets each 20% vol, 50/50: compute portfolio vol for ρ = 1, 0 and −0.5.",
        "interview": [_q("Is diversification a 'free lunch'?",
                         "Largely yes for uncorrelated risk, but correlations can jump to 1 in crises."),
                      _q("What risk cannot be diversified away?",
                         "Systematic (market) risk — that is what investors are paid a premium for.")],
    },
    {
        "id": "PM2", "role": "portfolio_manager", "title": "Risk-adjusted performance: Sharpe and Sortino",
        "concept": "Returns mean little without risk. Sharpe divides excess return over the risk-free rate by "
                   "volatility; Sortino penalizes only downside volatility.",
        "formulas": [("Sharpe", r"S = \frac{E[R - R_f]}{\sigma(R - R_f)}\sqrt{N}"),
                     ("Sortino", r"\frac{E[R - R_f]}{\sqrt{E[\min(R - R_f, 0)^2]}}\sqrt{N}")],
        "live": "pm_sharpe", "code": ["ml_portfolio_backtest.py → sharpe_ratio, sortino_ratio"],
        "on_the_job": "Clients and consultants compare managers on these ratios every quarter.",
        "exercise": "Return 12%, T-bill 4.5%, volatility 15%: compute Sharpe. What if you forgot the T-bill?",
        "interview": [_q("Why subtract the risk-free rate?",
                         "An investor can earn it without risk; only the excess rewards taking risk."),
                      _q("When is Sortino more informative than Sharpe?",
                         "When returns are skewed — e.g. strategies with rare large losses or large gains.")],
    },
    {
        "id": "PM3", "role": "portfolio_manager", "title": "Transaction costs and turnover",
        "concept": "Every trade costs money (spread, commission, market impact). High-turnover strategies need a "
                   "large gross edge to survive costs. Costs apply to every dollar bought and sold.",
        "formulas": [("One-way turnover", r"\tau = \tfrac{1}{2}\sum_i |\Delta w_i|"),
                     ("Cost", r"\text{cost} = \sum_i |\Delta w_i| \times c = 2\tau c")],
        "live": "pm_costs", "code": ["ml_portfolio_backtest.py → calculate_turnover, build_portfolios",
                                     "ml_portfolio_robustness.py → transaction_cost_test"],
        "on_the_job": "PMs ask 'what is the break-even cost?' before approving any new strategy.",
        "exercise": "A strategy replaces 70% of its holdings monthly at 10 bps per trade. Estimate annual cost drag.",
        "interview": [_q("What mistake did Vittantra's first backtest make on costs?",
                         "It charged costs on one-way turnover (half the traded dollars), understating costs by 2×."),
                      _q("What is market impact?",
                         "The price moving against you because of your own trade size.")],
    },
    {
        "id": "PM4", "role": "portfolio_manager", "title": "Attribution: skill or exposure?",
        "concept": "Factor regression separates returns explained by known exposures (market, value, momentum…) "
                   "from alpha. Alpha must be statistically significant to be called skill.",
        "formulas": [("Factor model", r"R_t - R_f = \alpha + \sum_k \beta_k F_{k,t} + \varepsilon_t"),
                     ("t-statistic", r"t = \hat\alpha / SE(\hat\alpha)")],
        "live": "pm_attribution", "code": ["ml_factor_attribution.py → calculate_ols"],
        "on_the_job": "Quarterly reviews ask whether outperformance came from skill or from tilts the client could buy cheaply.",
        "exercise": "Alpha 3% a year with t = 0.6 over 3 years: what do you tell the investment committee?",
        "interview": [_q("What t-statistic do you want before claiming alpha?",
                         "Commonly above 2 (5% significance); higher when many strategies were tried."),
                      _q("What is the danger of testing many strategies?",
                         "Data mining — some will look significant by chance.")],
    },
    {
        "id": "PM5", "role": "portfolio_manager", "title": "Rebalancing within constraints",
        "concept": "Portfolios drift as prices move. Rebalancing restores targets and limits, but each trade costs "
                   "money, so PMs use bands, turnover caps and risk limits.",
        "formulas": [("Drifted weight", r"w_i' = \frac{w_i(1 + R_i)}{\sum_j w_j(1 + R_j)}")],
        "live": "pm_rebalance", "code": ["exposure_aware_rebalancer.py → apply_risk_contribution_limit"],
        "on_the_job": "Quarterly rebalancing is a core PM routine; risk breaches can force interim trades.",
        "exercise": "A 60/40 portfolio: stocks +20%, bonds 0%. What are the new weights and the trade back to 60/40?",
        "interview": [_q("Calendar vs. threshold rebalancing?",
                         "Calendar trades on fixed dates; threshold trades when weights drift beyond a band."),
                      _q("Why can a risk-based limit need several passes?",
                         "Shrinking one position changes everyone's risk share, so contributions must be recomputed.")],
    },
    {
        "id": "PM6", "role": "portfolio_manager", "title": "Combining signals: IC and the fundamental law",
        "concept": "A signal's information coefficient (IC) is the rank correlation between its scores and the "
                   "next period's returns. Small ICs (0.05) can be valuable if applied to many independent bets. "
                   "Combining signals helps only if they are not redundant and each adds predictive power; "
                   "weighting by past IC must use only outcomes already known.",
        "formulas": [("Information coefficient", r"IC_t = \rho_{\text{Spearman}}(\text{score}_t, R_{t \to t+1})"),
                     ("IC t-statistic", r"t = \frac{\overline{IC}}{s_{IC}/\sqrt{n}}"),
                     ("Fundamental law of active management", r"IR \approx IC \times \sqrt{\text{Breadth}}")],
        "live": "pm_signals", "code": ["multi_factor_rating.py → ic_summary, add_ic_weighted_composite"],
        "on_the_job": "Quant and fundamental teams track the IC of every signal; signals that stop working are retired.",
        "exercise": "A signal has IC 0.05 applied to 400 independent bets a year. Estimate its information ratio.",
        "interview": [_q("Why can a low IC still be valuable?",
                         "Because the information ratio grows with breadth: IC 0.05 × √400 = 1.0."),
                      _q("Why did Vittantra's equal-weight composite underperform its best pillar?",
                         "A pillar with negative IC (low volatility in a rising market) diluted the signal; "
                         "IC-weighting reduced that.")],
    },
    # ---------------- Advisor ----------------
    {
        "id": "AD1", "role": "advisor", "title": "The advisory process",
        "concept": "Advice follows a disciplined loop: know the client → define objectives and constraints (IPS) "
                   "→ recommend a suitable allocation → implement → monitor and review. Every step is documented.",
        "formulas": [("IPS essentials", r"\text{Return objective} + \text{Risk tolerance} + \text{Time horizon} + \text{Liquidity} + \text{Legal/tax} + \text{Unique needs}")],
        "live": "ad_process", "code": ["portfolio_approval_workflow.py (human approval, audit log)"],
        "on_the_job": "Regulators expect a written record of why each recommendation suits the client.",
        "exercise": "List the six IPS constraints for a 30-year-old saving for a house in 5 years.",
        "interview": [_q("What is suitability?",
                         "A recommendation must fit the client's objectives, risk profile and situation, and be documented."),
                      _q("What is a fiduciary duty?",
                         "Acting in the client's best interest, putting their interests ahead of the advisor's.")],
    },
    {
        "id": "AD2", "role": "advisor", "title": "Risk tolerance vs. risk capacity",
        "concept": "Tolerance is how much loss a client is willing to bear emotionally; capacity is how much they "
                   "can afford financially (income, wealth, horizon, obligations). Advice follows the lower of the two.",
        "formulas": [("Rule of thumb", r"\text{Recommended risk} = \min(\text{tolerance}, \text{capacity})")],
        "live": "ad_risk_profile", "code": ["var_engine.py (VaR translated into client language)"],
        "on_the_job": "Risk questionnaires plus a conversation about real loss amounts in money, not percentages.",
        "exercise": "A wealthy retiree is very anxious about losses; a young student is a risk-lover with no savings. What do you recommend for each?",
        "interview": [_q("Why use the lower of tolerance and capacity?",
                         "Exceeding tolerance makes clients sell at the bottom; exceeding capacity risks real hardship."),
                      _q("How do you explain VaR to a client?",
                         "In money and frequency: 'on about one day in twenty you could lose more than X.'")],
    },
    {
        "id": "AD3", "role": "advisor", "title": "Time value of money and goal planning",
        "concept": "Money grows by compounding. Planning works backwards from a goal: what today's savings will "
                   "grow to, and how much must be saved each year to close the gap. Return assumptions must be "
                   "stated, conservative and stress-tested.",
        "formulas": [("Future value", r"FV = PV(1 + r)^n"),
                     ("Required yearly saving", r"PMT = \frac{(FV_{goal} - PV(1+r)^n)\, r}{(1+r)^n - 1}")],
        "live": "ad_goal_planning", "code": ["(Day 84 goals engine — coming)"],
        "on_the_job": "Retirement and education planning are the core of retail advice.",
        "exercise": "Recompute the live example with a 4% return. How much more must the client save?",
        "interview": [_q("Why stress-test a plan's return assumption?",
                         "Real returns vary; sequence-of-returns risk can derail a plan near retirement."),
                      _q("What is the rule of 72?",
                         "Years to double ≈ 72 ÷ annual return in percent.")],
    },
    {
        "id": "AD4", "role": "advisor", "title": "Strategic asset allocation",
        "concept": "Asset allocation — the mix of stocks, bonds, cash and alternatives — explains most of the "
                   "variation in long-run portfolio returns. It should match the client's goals and risk profile "
                   "and usually becomes more conservative as the goal approaches (glide path).",
        "formulas": [("Portfolio expected return", r"E[R_p] = \sum_i w_i E[R_i]")],
        "live": "ad_allocation", "code": ["multi_asset_universe.py (asset-class risk)"],
        "on_the_job": "Advisors build model portfolios (conservative → aggressive) and map clients to them.",
        "exercise": "Design conservative, balanced and growth allocations using the volatilities in the live example.",
        "interview": [_q("What is a glide path?",
                         "A schedule that reduces risk as the target date approaches."),
                      _q("Why include bonds if stocks return more?",
                         "To reduce volatility and drawdowns so the client can stay invested.")],
    },
    {
        "id": "AD5", "role": "advisor", "title": "Communicating risk clearly",
        "concept": "Clients act on what they understand. Good advisors translate jargon into money, frequency and "
                   "trade-offs, never promise returns, and disclose risks and costs plainly.",
        "formulas": [("Duration in plain words", r"\text{Price change} \approx -\text{Duration} \times \text{rate change}")],
        "live": "ad_communication", "code": ["vittantra_ai_analyst.py (plain-language explanations)"],
        "on_the_job": "Quarterly letters and review meetings; complaints usually come from surprises, not losses.",
        "exercise": "Rewrite: 'Elevated credit spread volatility warrants defensive positioning' for a retail client.",
        "interview": [_q("What should never appear in client communication?",
                         "Guaranteed or promised returns, or past performance presented as a promise."),
                      _q("How do you deliver bad news?",
                         "Early, in plain terms, with context, what it means for their goals, and the plan.")],
    },
]


SIMULATOR_TASKS = {
    "investment_analyst": {
        "title": "Morning market brief (08:00)",
        "brief": "Your PM wants three bullet points before the morning meeting: what moved, what matters, "
                 "and one thing to watch. Use the market snapshot below.",
        "checklist": ["Mentions the biggest mover with a number", "Covers more than one asset class",
                      "Links a move to a reason or risk (rates, credit, FX)", "Ends with something to watch",
                      "Under 100 words, no jargon without explanation"],
    },
    "equity_researcher": {
        "title": "Company tear sheet",
        "brief": "Sales wants your quick view on the company below: rate each pillar (cheap? growing? quality? "
                 "safe?) and give an overall view with the single most important reason.",
        "checklist": ["Uses at least one valuation number", "Uses growth and quality numbers",
                      "Checks leverage / financial health", "Names a key risk",
                      "View is consistent with the evidence"],
    },
    "portfolio_analyst": {
        "title": "Daily risk check (09:30)",
        "brief": "Review today's risk dashboard: which positions breach their budgets, how serious is it, and "
                 "what do you escalate to the PM?",
        "checklist": ["Identifies every breach", "Quantifies how far over budget",
                      "Explains the cause (e.g. delta exposure, concentration)", "Recommends an action",
                      "States that execution needs human approval"],
    },
    "portfolio_manager": {
        "title": "Rebalance proposal",
        "brief": "Risk has flagged breaches. Propose trades that bring risk back within limits while respecting "
                 "turnover limits, and explain the trade-off.",
        "checklist": ["Reduces the largest risk contributors", "Respects turnover/cost limits",
                      "Considers what replaces the risk (or holds cash)", "Explains impact on expected return",
                      "Notes approval and documentation"],
    },
    "advisor": {
        "title": "Client meeting",
        "brief": "Read the client profile below. Recommend an allocation (stocks / bonds / cash / alternatives), "
                 "explain why it is suitable, and how you would describe the risk in plain words.",
        "checklist": ["Considers both risk tolerance and capacity", "Matches the time horizon and goal",
                      "Keeps an emergency/liquidity reserve", "Explains risk in money terms",
                      "Makes no promise of returns"],
    },
}
