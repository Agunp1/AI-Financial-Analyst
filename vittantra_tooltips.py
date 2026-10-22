"""
Hover explanations for every number in Vittantra.

`install()` makes every st.metric and every table column show a tooltip (the
small ⓘ / hover text) that says what the number is and why professionals use
it — without editing each page. Explicit help text on a page always wins.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator


# label (lower case) → "What it is. Why professionals use it."
TIPS: Dict[str, str] = {
    # --- risk ---------------------------------------------------------------
    "var": "Value at Risk: a loss that should be exceeded only on 1 day in 20 (95%) or 1 in 100 (99%). Risk "
           "managers use it to size positions and set daily loss limits.",
    "1-day 99% var": "The loss exceeded on only about 1 trading day in 100. Used to set limits and to check the "
                     "portfolio can survive a bad day.",
    "expected shortfall": "The average loss on the days worse than VaR. Regulators prefer it because it looks at "
                          "how bad the bad days are, not just where they start.",
    "var exceptions": "Days when the real loss was bigger than VaR. Too many (or bunched together) means the "
                      "risk model is underestimating risk — checked with the Kupiec and Christoffersen tests.",
    "p-value": "How likely the result would be if the model were right. Below 0.05 usually means 'reject the "
               "model'. Used to judge whether VaR breaches are just bad luck.",
    "volatility": "How much returns swing, per year. The basic measure of risk: it drives position sizes, VaR "
                  "and the Sharpe ratio.",
    "drawdown": "The fall from a peak to a trough. Investors feel drawdowns more than volatility; it shows the "
                "pain of holding through a bad period.",
    "beta": "How much the asset moves with the market: beta 1.2 ≈ 12% move for a 10% market move. Used for "
            "hedging and for the cost of equity (CAPM).",
    "beta to s&p 500": "Sensitivity to the US stock market. Shows how much of the risk is just market risk that "
                       "could be hedged with index futures.",
    "correlation": "How closely two assets move together (−1 to +1). Low correlation is what makes "
                   "diversification work.",
    "risk contribution": "The part of total portfolio risk coming from one position (Euler method; parts add up to "
                         "100%). Shows who really drives risk — often not the biggest holding.",
    "modeled risk contribution": "This position's share of the portfolio's total modeled risk. Compared with its "
                                 "limit to spot concentration.",
    "risk budget": "The maximum share of portfolio risk a position or asset class may use. Keeps one bet from "
                   "dominating the portfolio.",
    "utilization": "Risk used ÷ risk limit. Below 80% is comfortable, above 100% is a breach that must be fixed "
                   "and approved by a human.",
    "maximum utilization": "The highest risk-limit use of any position. Risk teams watch the worst position first.",
    "max risk utilization": "The highest risk-limit use of any position. Above 100% means a limit is breached.",
    "mean utilization": "Average use of risk limits across positions. A quick read of how 'full' the portfolio is.",
    "largest risk share": "The single position using the most of the portfolio's risk. A concentration check.",
    "top 3 risk share": "Share of total risk from the three riskiest positions. High = the portfolio depends on a "
                        "few bets.",
    "effective risk positions": "How many equally-sized risk positions the portfolio is equivalent to. Higher = "
                                "better diversified.",
    "budget breaches": "Positions using more risk than their limit. Each one needs a fix and human approval.",
    "positive budget excess": "Total risk above limits across all breaching positions — how much risk must be cut.",
    "portfolio state": "Overall risk status from the worst position: NORMAL, WATCH, WARNING, BREACH or CRITICAL. "
                       "Tells the team whether action is needed today.",
    "approval queue": "Decisions waiting for a human reviewer. Nothing changes until they are approved.",
    "immediate priority": "Fixes that should be decided first (largest breaches).",
    "blocked / review": "Positions where new risk is frozen or a reviewer must look before anything changes.",
    "workflow": "Where the decision process stands (e.g. awaiting dual approval). Shows governance is working.",
    # --- portfolio management --------------------------------------------
    "tracking error": "Volatility of the portfolio's return versus its benchmark. PMs get a tracking-error budget "
                      "(here 4%) that limits how far they can stray.",
    "information ratio": "Active return ÷ tracking error: reward per unit of active risk. Above 0.5 is good for a "
                         "manager; it is how PMs are judged.",
    "expected active return": "Expected return above the benchmark from the ratings (Grinold–Kahn alpha). The "
                              "reason to take active risk at all.",
    "active return": "Return above the benchmark. What an active manager is paid to deliver.",
    "active share": "How different the holdings are from the benchmark. Low active share with high fees = "
                    "'closet indexing'.",
    "holdings": "Number of positions in the portfolio. More holdings = more diversified, less stock-specific risk.",
    "turnover": "How much of the portfolio is traded. Trading costs money, so PMs keep turnover in check.",
    "largest weight": "The biggest position. Single-stock limits (here 8%) stop one company hurting the portfolio.",
    "portfolio (cumulative)": "Total return of the portfolio over the period. Historical, not a forecast.",
    "benchmark (cumulative)": "Total return of the benchmark over the same period, to compare against.",
    "scenario p&l": "Estimated profit or loss if the scenario happened: factor sensitivity × shock. Used to "
                    "prepare for events before they happen.",
    # --- research ---------------------------------------------------------
    "fundamental score": "0–100 score from SEC filings (value, quality, growth, health) versus peers. Higher = "
                         "stronger fundamentals.",
    "price": "Latest market price from free data (may be delayed).",
    "intrinsic value": "What the business is worth from its cash flows (DCF), book value and profits (residual "
                       "income) or dividends (DDM). Analysts compare it with the price.",
    "upside": "Intrinsic value ÷ price − 1. Positive = the model says it is cheap. A model estimate, not a promise.",
    "valuation": "Undervalued, fairly valued or overvalued versus intrinsic value (±15% band), or Low confidence "
                 "when the models disagree.",
    "market cap": "Share price × shares outstanding: what the market says the company is worth.",
    "revenue (ttm)": "Sales over the last 12 months (trailing twelve months). The starting point for growth and "
                     "margins.",
    "sector rank": "Position within its sector by fundamental score. Analysts compare companies with peers, not "
                   "with the whole market.",
    "rank": "Position by fundamental score within the research universe.",
    "companies scored": "Companies with enough SEC data to score.",
    "stocks valued": "Stocks with enough data for an intrinsic-value estimate.",
    "risk-free rate": "The 10-year US Treasury yield. The base of every cost of capital: higher rates lower "
                      "valuations.",
    "growth priced in": "The yearly growth the current price implies (reverse DCF). Compare with what the company "
                        "has actually done.",
    "implied growth": "The yearly growth the current price implies (reverse DCF).",
    "wacc": "Weighted average cost of capital: the return investors require. The discount rate in a DCF.",
    "cost of equity": "Return shareholders require = risk-free rate + beta × equity risk premium (CAPM).",
    "ic": "Information coefficient: correlation between a signal's scores and later returns. 0.05 is useful; "
          "it tells you whether a factor really predicts.",
    "mean ic": "Average information coefficient across test dates.",
    "average ic": "Average information coefficient across test dates.",
    "t-stat": "How sure we can be the result is not luck. Above about 2 = statistically meaningful.",
    "ic t-stat": "How sure we can be the factor's IC is not luck. Above about 2 = meaningful.",
    "hit rate": "Share of periods the signal worked. Above 50% is better than a coin flip.",
    "macro regime": "Risk-on or risk-off, from credit spreads and Treasury yields. Different sectors win in "
                    "each regime.",
    "overweight": "Rated to hold more than the benchmark.",
    "pe ratio": "Price ÷ earnings per share: how many years of profits you pay for.",
    "p/e": "Price ÷ earnings per share: how many years of profits you pay for.",
    "roe": "Return on equity: profit ÷ shareholders' equity. A quality measure.",
    "fcf yield": "Free cash flow ÷ market value: cash the business generates relative to its price.",
    # --- markets ----------------------------------------------------------
    "10y treasury": "The 10-year US government bond yield: the world's benchmark interest rate. Drives mortgage "
                    "rates, bond prices and stock valuations.",
    "2s10s slope": "10-year minus 2-year yield. Negative (inverted) has often come before recessions.",
    "3m–10y slope": "10-year minus 3-month yield; the Fed's favourite recession signal when negative.",
    "10y breakeven inflation": "Inflation the bond market expects over 10 years (nominal minus real yield). "
                               "Watched by the Fed and by bond investors.",
    "credit spread": "Extra yield on company bonds over government bonds. Widening = markets worry about defaults.",
    "momentum": "Return over the past 12 months excluding the last month. Winners tend to keep winning for months.",
    "instruments tracked": "Number of markets Vittantra follows in this asset class.",
    "median 12-month return": "The middle 12-month return across instruments in the class. Past, not a forecast.",
    "median volatility": "The middle volatility across instruments in the class.",
    "worst 1-year drawdown": "The deepest fall of any instrument in the class over the past year.",
    "latest price date": "The date of the most recent price; data refreshes every weekday evening.",
    # --- advisory ---------------------------------------------------------
    "risk profile": "The client's risk level = the lower of willingness (attitude) and capacity (ability to bear "
                    "losses). Advisers must not recommend more risk than this.",
    "expected return": "Long-run return assumption from capital market assumptions. An estimate, not a promise.",
    "bad year (1 in 20)": "A loss the portfolio could suffer in a bad year (about 1 year in 20). Helps clients "
                          "understand the downside before investing.",
    "goal probability": "Share of simulated futures (Monte Carlo) in which the client reaches the goal.",
    "chance of success": "Share of simulated futures in which the goal is reached.",
    "median outcome": "The middle result of the simulations: half better, half worse.",
    "poor case (10th pct)": "Only 1 in 10 simulations end worse than this. A planning floor.",
    # --- system / account -------------------------------------------------
    "portfolio return": "Change in value of your saved holdings since you saved them, at free (possibly delayed) "
                        "prices. Compared with the S&P 500 over the same days — a historical result, not a promise.",
    "s&p 500 (spy)": "Return of the S&P 500 ETF over the same period: the yardstick most investors compare against.",
    "value": "Market value of the saved holdings at the latest prices.",
    "portfolio value": "Market value of all holdings at the latest prices (free data, may be delayed).",
    "as of": "The date the data refers to.",
    "data checks": "Automated validation checks that passed. Professionals check data before trusting a number.",
    "checks": "Automated validation checks that passed.",
    "estimated account equity": "Value of the (paper) account: cash plus positions.",
    "available cash": "Cash not invested; a buffer for opportunities and withdrawals.",
    "cash allocation": "Share of the account held in cash; cash lowers risk but earns little.",
    # --- governance and workflow counts ----------------------------------
    "automatic execution": "Number of trades the system may make by itself. Always 0 in Vittantra: every decision "
                           "needs a human.",
    "breaches": "Positions above their risk limit. Each must be fixed or explicitly approved.",
    "warnings": "Positions close to their limit (above 95%). The risk team watches them before they breach.",
    "critical": "Positions far above their limit (120%+). Escalated to management the same day.",
    "requires review": "Items a human must look at before anything changes.",
    "pending review": "Decisions still waiting for a reviewer.",
    "decision tickets": "One ticket per position with its proposed action — the audit trail of every decision.",
    "dual approval required": "Tickets needing two reviewers (risk and portfolio). Four eyes stop single-person "
                              "mistakes.",
    "dual approvals": "Tickets needing two reviewers (risk and portfolio). Four eyes stop single-person mistakes.",
    "risk reviews": "Tickets the risk reviewer must sign off.",
    "portfolio reviews": "Tickets the portfolio reviewer must sign off.",
    "risk reduction tickets": "Proposed actions that cut risk. They must never increase modeled risk.",
    "modeled reduction": "How much total modeled risk the proposed fix removes.",
    "estimated post-remediation": "Worst limit use after the proposed fix. Below 100% means the fix works.",
    "post-remediation estimate": "Worst limit use after the proposed fix. Below 100% means the fix works.",
    "portfolio status": "Overall risk status from the worst position: NORMAL, WATCH, WARNING, BREACH or CRITICAL.",
    "data checks passed": "Automated checks the data passed before it was used. Professionals verify inputs first.",
    "tickers priced": "Instruments with a fresh market price.",
    "fresh": "Instruments updated recently; stale prices give wrong risk numbers.",
    "connected modules": "Parts of the pipeline whose outputs are available.",
    "instruments": "Number of positions or markets covered.",
    "sectors": "Number of industry groups; analysts compare companies within a sector.",
    "asset classes": "Number of asset-class groups (stocks, bonds, FX...). More classes = more diversification.",
    "period": "The time window the numbers cover.",
    # --- Academy roles -----------------------------------------------------
    "today's steps": "How many of today's three Job Tracker steps (desk duty, CFA item set, lesson) are done. "
                     "Small daily practice is how professionals keep skills sharp between real deals and reviews.",
    "streak": "Consecutive days with at least one piece of saved work. Consistency matters more than long "
              "sessions when preparing for exams and interviews.",
    "last 7 days": "Desk tasks, CFA item sets and lessons completed in the past week — a quick check that every "
                   "desk is getting attention.",
    "cfa exam in": "Days until the Level II exam date you set. Candidates plan backwards from it so every topic "
                   "is covered before the final review weeks.",
    "readiness": "Share of a role's core responsibilities you have demonstrated with graded work scoring 70 or "
                 "more — the evidence an interviewer can ask you to walk through.",
    "exam weight (approx.)": "Approximate share of the Level II exam for the topic (CFA Institute ranges, which "
                             "change by year). Candidates weight study time towards heavier topics.",
    "regime": "Risk-on, neutral or risk-off, from the S&P 500 vs its 200-day average and the VIX. Traders cut "
              "size when the market is falling and volatile, because losses cluster in those periods.",
    "vix": "Expected 30-day S&P 500 volatility implied by option prices (the 'fear gauge'). Traders watch it to "
           "judge how big daily moves are likely to be and to size positions.",
    "conviction": "The agent's 0–100 score: trend alignment, momentum agreeing, room in RSI, calm volatility, and "
                  "a penalty if the setup had no positive record. A ranking aid, not a probability.",
    "risk at stop (usd)": "What the paper trade loses if the stop is hit (quantity × distance to stop). Traders fix "
                          "this first — 0.5% of the book here — and size the position from it.",
    "r multiple": "Profit or loss divided by the risk taken at entry. +2R means the trade made twice what it "
                  "risked; traders judge a process by its average R, not single wins.",
    "average r": "Average profit per trade in units of risk taken. Above zero over many trades means the process "
                 "has an edge after losses; a high hit rate with negative average R does not.",
    "paper p&l": "Profit or loss of your paper trades marked on daily closes. Paper only — nothing was executed.",
    "paper trades": "Trades you added to the paper blotter from the agent's ideas. Practice that builds a track "
                    "record of decisions you can explain in interviews.",
    "directional setups": "Instruments where the agent's rules see a long or short setup today, out of all it "
                          "scanned. Breadth shows whether trends are broad or narrow.",
    "s&p 500 vs 200-day": "How far the S&P 500 is above or below its 200-day average. A classic trend filter: many "
                          "risk managers reduce exposure when the market is below it.",
    "setup": "The pattern the trader agent sees: trend continuation, pullback in uptrend, breakout, downtrend and so "
             "on. Each setup has a rule for entry, stop and target.",
    "historical edge": "Whether this setup made money on average after costs in the saved history (at least 30 "
                       "signals). Professionals only trust rules with evidence, and re-test them.",
    "rsi (14)": "Relative Strength Index over 14 days (0–100): above 70 is stretched up, below 30 stretched down. "
                "Traders use it to time entries inside a trend.",
    "stop": "The price at which the trade is closed to cap the loss (2 ATR from entry here). Set before entering, "
            "never moved further away.",
    "target": "The price at which profit is taken (3 ATR from entry here, 1.5× the risk). Planning it in advance "
              "keeps reward-to-risk positive.",
    "entry": "The planned entry price — the last close for the agent's ideas. Real fills differ by spread and "
             "market impact (see implementation shortfall).",
    "vs 200-day": "Price relative to its 200-day moving average. Above means a long-term uptrend; the most common "
                  "trend filter in time-series momentum strategies.",
    "average return": "Average return per signal over the holding period after costs. Shows whether a rule paid "
                      "off, not just how often it was right.",
    "signals": "How many times the rule fired in the saved history. Fewer than about 30 is too few to judge.",
    "implementation shortfall": "Execution cost: the gap between the price when you decided to trade (arrival) and "
                                "the average fill, in basis points. The standard measure of trading cost.",
    "risk at stop (inr)": "What the paper trade loses in rupees if the stop is hit (quantity × distance to stop). "
                          "Traders fix this first — 0.5% of the book — and size the position from it.",
    "p&l (inr)": "Profit or loss of the paper trade in rupees, marked on daily closes. Paper only.",
    "p&l (usd)": "Profit or loss of the paper trade in dollars, marked on daily closes. Paper only.",
    "india vix": "Expected 30-day Nifty 50 volatility implied by NSE option prices. Indian traders watch it to judge "
                 "how big daily moves are likely to be and to size positions.",
    "nifty 50 vs 200-day": "How far the Nifty 50 is above or below its 200-day average — the trend filter the India "
                           "trader agent uses to set the regime.",
    "beta to nifty 50": "How much the instrument moves when the Nifty 50 moves 1%. Indian PMs use it to see market "
                        "exposure and to hedge with Nifty futures.",
    "price (inr)": "Latest price in Indian rupees from Yahoo Finance (NSE/BSE), about 15 minutes delayed.",
    "role level": "Your level in this role (Junior → Analyst → Senior → Lead) from XP earned on graded desk tasks.",
}

# Word-level fallbacks for labels not listed exactly (longest match wins).
KEYWORDS = ["scenario p&l", "expected shortfall", "risk contribution", "tracking error", "information ratio", "risk budget",
            "utilization", "drawdown", "volatility", "intrinsic value", "credit spread", "growth priced in",
            "cost of equity", "risk-free rate", "momentum", "correlation", "turnover", "upside", "beta", "wacc",
            "var", "ic", "roe", "p/e", "price", "market cap", "valuation", "t-stat", "hit rate"]


def _norm(label: str) -> str:
    text = re.sub(r"\(.*?\)", lambda m: m.group(0) if "ttm" in m.group(0).lower() or "1 in 20" in m.group(0)
                  or "10th" in m.group(0) else "", str(label))
    return re.sub(r"\s+", " ", text.replace("_", " ").replace(":", "")).strip().lower()


ROLE_LABELS = {"investment analyst", "equity research analyst", "portfolio / risk analyst", "portfolio manager",
               "investment advisor", "private equity / venture capital analyst", "trader"}


def tip(label: str) -> Optional[str]:
    """The explanation for a label, or None."""
    if not isinstance(label, str) or not label.strip():
        return None
    key = _norm(label)
    if key in ROLE_LABELS:
        return TIPS["role level"]
    if key in TIPS:
        return TIPS[key]
    full = re.sub(r"\s+", " ", str(label).replace("_", " ")).strip().lower()
    if full in TIPS:
        return TIPS[full]
    for word in sorted(KEYWORDS, key=len, reverse=True):
        if re.search(rf"(^|[^a-z]){re.escape(word)}([^a-z]|$)", key):
            return TIPS.get(word)
    return None


def _column_help(data, column_config):
    columns = list(data.columns) if isinstance(data, pd.DataFrame) else \
        list(data.data.columns) if hasattr(data, "data") and isinstance(getattr(data, "data"), pd.DataFrame) else []
    if not columns:
        return column_config
    config = dict(column_config or {})
    for column in columns:
        text = tip(str(column))
        if not text:
            continue
        current = config.get(column)
        if current is None:
            config[column] = st.column_config.Column(help=text)
        elif isinstance(current, dict) and not current.get("help"):
            config[column] = {**current, "help": text}
    return config


_installed = False


def install() -> None:
    """Add hover explanations to every metric and table column (idempotent)."""
    global _installed
    if _installed:
        return
    original_metric, original_dataframe = DeltaGenerator.metric, DeltaGenerator.dataframe

    def metric(self, label, value, *args, **kwargs):
        if not kwargs.get("help"):
            text = tip(label)
            if text:
                kwargs["help"] = text
        return original_metric(self, label, value, *args, **kwargs)

    def dataframe(self, data=None, *args, **kwargs):
        try:
            kwargs["column_config"] = _column_help(data, kwargs.get("column_config"))
        except Exception:
            pass                       # tooltips must never break a page
        return original_dataframe(self, data, *args, **kwargs)

    DeltaGenerator.metric, DeltaGenerator.dataframe = metric, dataframe
    main = st._main
    st.metric = lambda *a, **k: metric(main, *a, **k)
    st.dataframe = lambda *a, **k: dataframe(main, *a, **k)
    _installed = True
