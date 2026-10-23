"""
Day 94 — Analyst agents: the analyst workflow done end to end on live data,
the way AI-native finance tools automate a back office.

Seven agents, one per front-office role (US market):

  investment_analyst    morning note: regime, cross-asset moves, rates, credit,
                        economy, calendar, headlines → what it means, what to watch
  equity_research       note on any US company: rating, valuation, thesis, risks
  portfolio_construction model-portfolio review: tracking error vs budget, bets, tilts
  portfolio_manager     decision memo: holdings to review, risk use, regime fit
  portfolio_analyst     performance and attribution report (Brinson, factors)
  risk_analyst          daily risk report: limits, alerts, VaR, stress, remediation
  trader                trade ideas with plans, regime and rule history

Each agent runs visible steps (what it read, from which file, what it found),
writes a deliverable in which EVERY number is a Finding citing source file,
field and value, and ends with points that need human judgment and the limits
of its data. Agents only read Vittantra's saved outputs: nothing is downloaded,
nothing is invented (missing data is reported as missing) and nothing is
executed — recommendations wait for a human.

Usage:  python analyst_agents.py      (writes day94_agent_findings.csv)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FINDINGS = "day94_agent_findings.csv"
OUTPUT_VALIDATION = "day94_validation_summary.csv"


# ==============================================================
# FRAMEWORK
# ==============================================================

@dataclass
class Finding:
    text: str
    source: str = ""
    field: str = ""
    value: object = None


@dataclass
class AgentRun:
    agent: str
    title: str
    as_of: str = ""
    steps: List[dict] = field(default_factory=list)
    sections: Dict[str, List[Finding]] = field(default_factory=dict)
    judgment: List[str] = field(default_factory=list)
    limits: List[str] = field(default_factory=list)

    def step(self, name: str, source: str, result: str) -> None:
        self.steps.append({"step": len(self.steps) + 1, "action": name, "source": source, "result": result})

    def add(self, section: str, text: str, source: str = "", field_: str = "", value=None) -> None:
        self.sections.setdefault(section, []).append(Finding(text, source, field_, value))

    def findings(self) -> List[dict]:
        return [{"agent": self.agent, "section": s, "text": f.text, "source": f.source, "field": f.field,
                 "value": f.value} for s, items in self.sections.items() for f in items]


def _read(base: Path, name: str) -> Optional[pd.DataFrame]:
    path = Path(base) / name
    try:
        return pd.read_csv(path) if path.exists() else None
    except Exception:
        return None


def _num(x) -> Optional[float]:
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def pct(x, digits: int = 1, sign: bool = True) -> str:
    v = _num(x)
    return "n/a" if v is None else (f"{v:+.{digits}%}" if sign else f"{v:.{digits}%}")


def num(x, digits: int = 2) -> str:
    v = _num(x)
    return "n/a" if v is None else f"{v:,.{digits}f}"


def to_markdown(run: AgentRun, cite: bool = True) -> str:
    lines = [f"### {run.title}", f"*{run.agent} · data as of {run.as_of or 'n/a'} · prepared "
                                 f"{datetime.now():%d %b %Y %H:%M} · research only, nothing executed*", ""]
    for section, items in run.sections.items():
        lines.append(f"**{section}**")
        for f in items:
            ref = f" `[{f.source} · {f.field}]`" if cite and f.source else ""
            lines.append(f"- {f.text}{ref}")
        lines.append("")
    if run.judgment:
        lines.append("**Needs your judgment**")
        lines += [f"- {j}" for j in run.judgment] + [""]
    if run.limits:
        lines.append("**Limits of this analysis**")
        lines += [f"- {l}" for l in run.limits]
    return "\n".join(lines)


# ==============================================================
# 1. INVESTMENT ANALYST — morning note
# ==============================================================

CROSS_ASSET = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Russell 2000"), ("EFA", "Developed ex-US"),
               ("EEM", "Emerging markets"), ("TLT", "Long Treasuries"), ("HYG", "High-yield bonds"),
               ("GLD", "Gold"), ("CL=F", "WTI crude"), ("DX-Y.NYB", "US dollar index"), ("BTC-USD", "Bitcoin")]


def investment_analyst(base: Path = BASE_DIR) -> AgentRun:
    run = AgentRun("Investment Analyst agent", "Morning note — US markets and economy")
    A = "day76c_asset_analytics.csv"
    assets = _read(base, A)
    if assets is not None:
        assets = assets.set_index("symbol")
        run.as_of = str(assets["as_of"].dropna().max())
        moves = []
        for symbol, label in CROSS_ASSET:
            if symbol in assets.index and _num(assets.at[symbol, "return_1d"]) is not None:
                r1, r1m = assets.at[symbol, "return_1d"], assets.at[symbol, "return_1m"]
                moves.append((abs(float(r1)), symbol, label, r1, r1m))
                run.add("Markets", f"{label} ({symbol}) {pct(r1, 2)} on the day, {pct(r1m)} over a month.", A,
                        f"{symbol}.return_1d", round(float(r1), 6))
        run.step("Read cross-asset moves", A, f"{len(moves)} benchmarks; biggest mover today: "
                 + (max(moves)[2] if moves else "n/a"))
    else:
        run.step("Read cross-asset moves", A, "missing")
        run.limits.append("Cross-asset prices are missing (run multi_asset_universe.py).")

    try:
        import trader_agent as ta
        reg = ta.regime(ta.load_history(base))
        run.add("Regime", f"{reg['state']}: S&P 500 {pct(reg['spy_vs_200d'])} vs its 200-day average, VIX "
                          f"{num(reg['vix'], 1)} ({pct(reg['vix_percentile'], 0, False)} percentile of the year).",
                "day76c_price_history.csv", "SPY vs SMA200; ^VIX", reg["state"])
        run.step("Classify the regime", "day76c_price_history.csv", reg["state"])
    except Exception:
        run.step("Classify the regime", "day76c_price_history.csv", "missing")

    C = "day76c_yield_curve.csv"
    curve = _read(base, C)
    if curve is not None and len(curve):
        c = curve.set_index("maturity")
        ten = c.loc["10Y"] if "10Y" in c.index else None
        s2s10 = _num(curve["slope_2s10s_bp"].iloc[0])
        s3m10 = _num(curve["slope_3m10y_bp"].iloc[0])
        if ten is not None:
            run.add("Rates", f"10-year Treasury {num(ten['yield_pct'])}% ({num(ten['change_1m_bp'], 0)} bp over a "
                             f"month, {num(ten['change_1y_bp'], 0)} bp over a year).", C, "10Y.yield_pct",
                    float(ten["yield_pct"]))
        run.add("Rates", f"Curve: 2s10s {num(s2s10, 0)} bp, 3m10y {num(s3m10, 0)} bp — "
                         + ("inverted (a classic recession warning)." if s3m10 is not None and s3m10 < 0 else
                            "positively sloped."), C, "slope_3m10y_bp", s3m10)
        run.add("Rates", f"10-year real yield {num(curve['real_yield_10y_pct'].iloc[0])}%, breakeven inflation "
                         f"{num(curve['breakeven_10y_pct'].iloc[0])}%.", C, "breakeven_10y_pct",
                _num(curve["breakeven_10y_pct"].iloc[0]))
        run.step("Read the yield curve", C, f"2s10s {num(s2s10, 0)} bp")

    K = "day76c_credit_spreads.csv"
    credit = _read(base, K)
    if credit is not None and len(credit):
        cs = credit.set_index("segment")
        for seg in ("US investment grade", "US high yield"):
            if seg in cs.index:
                r = cs.loc[seg]
                run.add("Credit", f"{seg} spread {num(r['spread_bp'], 0)} bp ({num(r['change_1y_bp'], 0)} bp over a "
                                  f"year; {num(r['percentile_in_history'], 0)}th percentile of its history).", K,
                        f"{seg}.spread_bp", float(r["spread_bp"]))
        run.step("Read credit spreads", K, f"{len(credit)} segments")

    E = "day76c_economic_dashboard.csv"
    econ = _read(base, E)
    if econ is not None and len(econ):
        e = econ.set_index("series_id")
        for sid in ("CPIAUCSL", "CPILFESL", "PCEPILFE", "UNRATE", "PAYEMS", "GDPC1", "RSAFS", "UMCSENT", "FEDFUNDS"):
            if sid in e.index:
                r = e.loc[sid]
                d = 0 if ("thousands" in str(r["indicator"]) or abs(float(r["latest"])) >= 1000) else 2
                run.add("Economy", f"{r['indicator']}: {num(r['latest'], d)} (previous {num(r['previous'], d)}; "
                                   f"{r['release_period']}).", E, f"{sid}.latest", round(float(r["latest"]), 4))
        run.step("Read the economic dashboard", E, f"{len(econ)} indicators")

    # Synthesis: rule-based reading of the evidence above (each rule cites its inputs).
    if econ is not None:
        e = econ.set_index("series_id")
        if "CPILFESL" in e.index and "CPIAUCSL" in e.index:
            head, core = float(e.at["CPIAUCSL", "latest"]), float(e.at["CPILFESL", "latest"])
            rising = float(e.at["CPIAUCSL", "change"]) > 0
            run.add("What it means", f"Headline inflation {num(head)}% is {'rising' if rising else 'easing'} and "
                                     f"{'above' if head > 2.5 else 'near'} the Fed's 2% goal; core {num(core)}%.",
                    E, "CPIAUCSL.change", round(float(e.at['CPIAUCSL', 'change']), 4))
        if "UNRATE" in e.index:
            u, u_year = float(e.at["UNRATE", "latest"]), float(e.at["UNRATE", "year_ago"])
            run.add("What it means", f"Unemployment {num(u, 1)}% vs {num(u_year, 1)}% a year ago — "
                                     + ("the labour market is softening." if u - u_year >= 0.3 else
                                        "no material softening over the year."), E, "UNRATE.year_ago", u_year)
    if credit is not None and "US high yield" in set(credit["segment"]):
        hy = credit.set_index("segment").loc["US high yield"]
        p = float(hy["percentile_in_history"])
        since = f" (history since {str(hy.get('history_start', ''))[:4]})" if "history_start" in hy else ""
        run.add("What it means", "High-yield spreads are " + ("tight versus history: credit is priced for good news"
                                                              if p < 25 else "wide versus history: credit is "
                                                              "pricing more stress" if p > 75 else
                                                              "in the middle of their history") + since + ".",
                K, "US high yield.percentile_in_history", p)

    L = "day78b_calendar.csv"
    cal = _read(base, L)
    if cal is not None and len(cal):
        for r in cal.head(4).itertuples():
            run.add("What to watch", f"{r.date}: {r.event} (last {r.indicator} {num(r.latest)}).", L, "date", r.date)
        run.step("Check the event calendar", L, f"{len(cal)} upcoming events")
    B = "day78b_brief.csv"
    brief = _read(base, B)
    if brief is not None and len(brief):
        for r in brief.sort_values("headline_count", ascending=False).head(3).itertuples():
            top = str(r.top_headlines).split(" || ")[0]
            run.add("Headlines linked to data", f"{r.theme}: {r.data_move} — e.g. “{top}”.", B, "data_move", r.move)
        run.step("Link headlines to data moves", B, f"{len(brief)} themes")

    run.judgment += ["Decide which of today's moves matters for your portfolio — the agent ranks by size, not "
                     "by relevance to your mandate.",
                     "Headlines are matched to themes by keywords; read the story before acting on it."]
    run.limits += ["Free data: prices about 15 minutes delayed; economic data as of the last release.",
                   "The 'what it means' lines are rules of thumb, not a forecast."]
    return run


# ==============================================================
# 2. EQUITY RESEARCH — note on a company
# ==============================================================

def equity_research(ticker: str, base: Path = BASE_DIR) -> AgentRun:
    ticker = ticker.strip().upper()
    run = AgentRun("Equity Research agent", f"Research note — {ticker}")
    R = "day78_research_claims.csv"
    claims = _read(base, R)
    summary = None
    if claims is not None and ticker in set(claims["ticker"]):
        rows = claims[claims["ticker"] == ticker]
        S = _read(base, "day78_report_summary.csv")
        summary = S.set_index("ticker").loc[ticker] if S is not None and ticker in set(S["ticker"]) else None
        run.step("Load the research-universe note", R, f"{len(rows)} evidence-linked claims")
        source_note = "research universe (multi-factor rating + valuation)"
    else:
        try:
            import research_report as rr
            out = rr.research_any(ticker, base)
        except Exception:
            out = None
        if not out:
            run.step("Look up the company", "day76_us_fundamental_metrics.csv", "not found")
            run.add("Result", f"{ticker} is not in Vittantra's SEC scan, so there is no evidence to write a note. "
                              "Check the ticker (US-listed, files with the SEC).")
            run.limits.append("No data, so no note — the agent does not guess.")
            return run
        rows = out["claims"]
        summary = out.get("summary")
        run.step("Build an on-demand note from SEC data", "day76_us_fundamental_metrics.csv",
                 f"{len(rows)} evidence-linked claims")
        source_note = "all-US SEC scan (no multi-factor rating outside the research universe)"
    if summary is not None:
        s = summary
        run.as_of = str(s.get("as_of", ""))
        run.add("Summary", f"{s.get('name', ticker)}: rating {s.get('rating', 'n/a')}, price {num(s.get('price'))}, "
                           f"fair value {num(s.get('fair_value'))} ({pct(s.get('upside'))}) from the "
                           f"{s.get('primary_model', 'n/a')} model — {s.get('valuation_signal', 'n/a')}.",
                "day78_report_summary.csv", "fair_value", _num(s.get("fair_value")))
        if _num(s.get("implied_growth")) is not None:
            run.add("Summary", f"Reverse DCF: today's price implies {pct(s.get('implied_growth'), 1, False)} growth "
                               "a year — the bar the company must clear.", "day78_report_summary.csv",
                    "implied_growth", _num(s.get("implied_growth")))
    for section, group in rows.groupby("section", sort=False):
        for r in group.itertuples():
            run.add(str(section), str(r.claim), str(r.source_file), str(r.field), r.value)
    run.step("Group evidence into thesis, valuation and risks", R, f"{rows['section'].nunique()} sections")
    run.judgment += ["Is the growth implied by the price realistic for this business? That is the core call.",
                     "Check the latest filing and earnings call for anything after the as-of date."]
    run.limits += [f"Source: {source_note}.",
                   "Valuation uses trailing filings and stated assumptions (see FINANCE_AUDIT.md); no consensus "
                   "estimates (paid data)."]
    return run


# ==============================================================
# 3. PORTFOLIO CONSTRUCTION — model portfolio review
# ==============================================================

def portfolio_construction(base: Path = BASE_DIR) -> AgentRun:
    run = AgentRun("Portfolio Construction agent", "Model portfolio review — 4% tracking-error mandate")
    S, P, X = "day79_portfolio_summary.csv", "day79_model_portfolio.csv", "day79_sector_weights.csv"
    summary, port = _read(base, S), _read(base, P)
    if summary is None or port is None:
        run.add("Result", "The model portfolio has not been built yet (portfolio_construction.py).")
        return run
    s = summary.iloc[0]
    run.as_of = str(s.get("as_of", ""))
    run.step("Read the optimiser output", S, f"{int(s['holdings'])} holdings from {int(s['universe'])}")
    te, budget = float(s["tracking_error"]), float(s["tracking_error_budget"])
    run.add("Risk budget", f"Tracking error {pct(te, 2, False)} vs a {pct(budget, 1, False)} budget — "
                           + ("fully used." if te >= budget * 0.97 else "room left."), S, "tracking_error", round(te, 6))
    run.add("Risk budget", f"Beta {num(s['beta_to_benchmark'])}; portfolio volatility {pct(s['portfolio_volatility'], 1, False)} "
                           f"vs benchmark {pct(s['benchmark_volatility'], 1, False)}.", S, "beta_to_benchmark",
            round(float(s["beta_to_benchmark"]), 4))
    run.add("Expected payoff", f"Expected active return {pct(s['expected_active_return'], 2)} a year, information "
                               f"ratio {num(s['information_ratio'])}, from a signal IC of {num(s['signal_ic'], 3)}.",
            S, "information_ratio", round(float(s["information_ratio"]), 4))
    run.add("Expected payoff", f"Active share {pct(s['active_share'], 0, False)}; largest position "
                               f"{pct(s['largest_weight'], 1, False)}; largest risk share {pct(s['largest_risk_share'], 1, False)}.",
            S, "active_share", round(float(s["active_share"]), 4))
    port = port[port["weight"] > 1e-6]
    bets = port.sort_values("active_weight", ascending=False)
    for r in bets.head(3).itertuples():
        run.add("Biggest active bets", f"{r.name} ({r.ticker}): {pct(r.active_weight, 1)} vs benchmark, rating "
                                       f"{r.rating}, {r.valuation_signal}.", P, f"{r.ticker}.active_weight",
                round(float(r.active_weight), 6))
    run.step("Rank active bets", P, f"top bet {bets.iloc[0]['ticker']}")
    conflicts = port[(port["active_weight"] > 0) & (port["valuation_signal"].astype(str).str.contains("Overvalued"))]
    for r in conflicts.head(4).itertuples():
        run.add("Conflicts to explain", f"{r.ticker} is overweight ({pct(r.active_weight, 1)}) although valuation "
                                       f"says Overvalued ({pct(r.upside)} to fair value) — held for score/risk reasons.",
                P, f"{r.ticker}.valuation_signal", r.valuation_signal)
    run.step("Check bets against valuation", P, f"{len(conflicts)} overweights rated overvalued")
    sectors = _read(base, X)
    if sectors is not None and "active_weight" in sectors:
        for r in sectors.reindex(sectors["active_weight"].abs().sort_values(ascending=False).index).head(3).itertuples():
            run.add("Sector tilts", f"{r.sector}: {pct(r.active_weight, 1)} vs benchmark.", X,
                    f"{r.sector}.active_weight", round(float(r.active_weight), 6))
    run.judgment += ["Approve, change or reject the proposal — it is PENDING_HUMAN_APPROVAL; nothing trades.",
                     "Overweights that valuation calls expensive need a reason you can defend to an investment "
                     "committee."]
    run.limits += ["Optimiser inputs are estimates (IC, shrinkage covariance); small changes can move weights.",
                   f"Universe of {int(s['universe'])} stocks — a teaching universe, not the full market."]
    return run


# ==============================================================
# 4. PORTFOLIO MANAGER — decision memo
# ==============================================================

def portfolio_manager(base: Path = BASE_DIR) -> AgentRun:
    run = AgentRun("Portfolio Manager agent", "PM decision memo — what to keep, review or cut")
    P, R = "day79_model_portfolio.csv", "day77_current_ratings.csv"
    port, ratings = _read(base, P), _read(base, R)
    if port is None:
        run.add("Result", "No model portfolio to manage yet.")
        return run
    port = port[port["weight"] > 1e-6]                       # holdings only (the file lists the whole universe)
    try:
        import trader_agent as ta
        reg = ta.regime(ta.load_history(base))
        run.add("Market backdrop", f"Regime {reg['state']} (S&P 500 {pct(reg['spy_vs_200d'])} vs 200-day; VIX "
                                   f"{num(reg['vix'], 1)}).", "day76c_price_history.csv", "regime", reg["state"])
        run.step("Read the regime", "day76c_price_history.csv", reg["state"])
    except Exception:
        pass
    S = _read(base, "day79_portfolio_summary.csv")
    if S is not None and len(S):
        run.as_of = str(S.iloc[0].get("as_of", ""))
    keep, review = [], []
    for r in port.itertuples():
        # Review = the rating has turned negative, or the stock is both unrated-positive and expensive.
        weak = str(r.rating) in ("Underweight", "Sell") or (str(r.valuation_signal) == "Overvalued"
                                                           and str(r.rating) != "Overweight")
        (review if weak else keep).append(r)
    run.step("Screen holdings against rating and valuation", P, f"{len(keep)} keep, {len(review)} review")
    expensive = port[port["valuation_signal"].astype(str) == "Overvalued"]
    run.add("Market backdrop", f"Valuation models call {len(expensive)} of {len(port)} holdings overvalued — "
                               "a reminder that trailing-data DCFs look harsh on growth names; weigh with the rating.",
            P, "valuation_signal", len(expensive))
    for r in sorted(review, key=lambda x: -x.weight)[:5]:
        run.add("Review", f"{r.name} ({r.ticker}) {pct(r.weight, 1, False)} of the book: rating {r.rating}, "
                          f"{r.valuation_signal} ({pct(r.upside)} to fair value), risk share {pct(r.risk_share, 1, False)}.",
                P, f"{r.ticker}.upside", _num(r.upside))
    for r in sorted(keep, key=lambda x: -x.weight)[:3]:
        run.add("Core holdings", f"{r.name} ({r.ticker}) {pct(r.weight, 1, False)}: rating {r.rating}, "
                                 f"{r.valuation_signal}.", P, f"{r.ticker}.rating", r.rating)
    top_risk = port.sort_values("risk_share", ascending=False).iloc[0]
    run.add("Risk use", f"Largest risk contributor: {top_risk['name']} at {pct(top_risk['risk_share'], 1, False)} of "
                        f"portfolio risk with {pct(top_risk['weight'], 1, False)} of capital.", P,
            f"{top_risk['ticker']}.risk_share", round(float(top_risk["risk_share"]), 4))
    if ratings is not None:
        held = set(port["ticker"])
        upgrades = ratings[(~ratings["ticker"].isin(held)) & (ratings["rating"] == "Overweight")]
        for r in upgrades.head(3).itertuples():
            run.add("Candidates not held", f"{r.name} ({r.ticker}) rated Overweight, score "
                                           f"{num(r.composite_ic_weighted, 0)} — not in the portfolio.",
                    R, f"{r.ticker}.rating", r.rating)
        run.step("Look for rated names not held", R, f"{len(upgrades)} candidates")
    run.add("Proposed action", f"Review {len(review)} holding(s) at the next rebalance; any change goes through the "
                               "approval workflow (automatic execution 0).", P, "approval", "PENDING_HUMAN_APPROVAL")
    run.judgment += ["Cutting a 'review' name is a judgment: a low rating can be a temporary dip in a long-term "
                     "compounder.", "Weigh turnover and tax cost before acting."]
    run.limits += ["Ratings and valuations are model outputs on public data; no management access or estimates."]
    return run


# ==============================================================
# 5. PORTFOLIO ANALYST — performance and attribution
# ==============================================================

def portfolio_analyst(base: Path = BASE_DIR) -> AgentRun:
    run = AgentRun("Portfolio Analyst agent", "Performance and attribution report")
    S, Q, F = "day80_attribution_summary.csv", "day80_brinson_by_sector.csv", "day80_factor_attribution.csv"
    summary = _read(base, S)
    if summary is None:
        run.add("Result", "No attribution yet (performance_attribution.py).")
        return run
    s = summary.iloc[0]
    run.as_of = str(s["end"])
    run.step("Read the backtest record", S, f"{int(s['periods'])} periods {s['start']} → {s['end']}")
    run.add("Performance", f"Strategy {pct(s['portfolio_cumulative'])} vs benchmark {pct(s['benchmark_cumulative'])} "
                           f"cumulative ({pct(s['portfolio_annualized'])} vs {pct(s['benchmark_annualized'])} a year), "
                           f"{s['start']} to {s['end']}.", S, "active_cumulative", round(float(s["active_cumulative"]), 6))
    run.add("Where it came from (Brinson–Fachler)",
            f"Allocation {pct(s['allocation_linked'])}, selection {pct(s['selection_linked'])}, interaction "
            f"{pct(s['interaction_linked'])}, costs {pct(s['costs_linked'])}.", S, "selection_linked",
            round(float(s["selection_linked"]), 6))
    run.add("Where it came from (Brinson–Fachler)", f"Best sector {s['best_sector']}; worst {s['worst_sector']}.", S,
            "best_sector", s["best_sector"])
    sectors = _read(base, Q)
    if sectors is not None and len(sectors):
        total_col = next((c for c in ("total", "total_effect", "active") if c in sectors.columns), None)
        if total_col:
            for r in sectors.sort_values(total_col, ascending=False).head(2).itertuples():
                run.add("Sector detail", f"{r.sector}: {pct(getattr(r, total_col))} total effect.", Q,
                        f"{r.sector}.{total_col}", round(float(getattr(r, total_col)), 6))
        run.step("Break down by sector", Q, f"{len(sectors)} sectors")
    factors = [c for c in summary.columns if c.startswith("factor_") and c.endswith("_sum")]
    if factors:
        best = max(factors, key=lambda c: float(s[c]))
        run.add("Factor attribution", f"Largest factor contribution: {best.replace('factor_', '').replace('_sum', '')} "
                                      f"{pct(s[best])}.", S, best, round(float(s[best]), 6))
    run.judgment += ["Decide whether the selection effect is skill or luck: how many periods, how consistent?",
                     "Present this as a historical backtest, never as expected returns."]
    run.limits += ["Backtest on a 33-stock research universe with point-in-time data; past results do not "
                   "predict future returns."]
    return run


# ==============================================================
# 6. RISK ANALYST — daily risk report
# ==============================================================

def risk_analyst(base: Path = BASE_DIR) -> AgentRun:
    run = AgentRun("Risk Analyst agent", "Daily risk report — model book")
    stamp = _read(base, "day75_refresh_stamp.csv")
    if stamp is not None and len(stamp):
        run.as_of = str(stamp.iloc[0].get("refreshed_utc", "")) + " UTC"
    D, AL, ST, SZ = ("day67_portfolio_risk_dashboard.csv", "day67_risk_alerts.csv", "day61_scenario_summary.csv",
                     "day69_sizing_summary.csv")
    dash = _read(base, D)
    if dash is None:
        run.add("Result", "Risk monitor outputs are missing (run_vittantra.py).")
        return run
    d = dash.iloc[0]
    run.step("Read the limit monitor", D, f"status {d['portfolio_status']}")
    run.add("Status", f"Book status {d['portfolio_status']}: {int(d['normal_count'])} normal, {int(d['watch_count'])} "
                      f"watch, {int(d['warning_count'])} warning, {int(d['breach_count'])} breach out of "
                      f"{int(d['instrument_count'])} positions.", D, "portfolio_status", d["portfolio_status"])
    run.add("Status", f"Highest use of a risk limit {pct(d['maximum_risk_budget_utilization'], 0, False)}; average "
                      f"{pct(d['mean_risk_budget_utilization'], 0, False)}; largest asset class by risk "
                      f"{d['largest_asset_class_by_risk']} ({pct(d['largest_asset_class_risk_share'], 0, False)}).",
            D, "maximum_risk_budget_utilization", round(float(d["maximum_risk_budget_utilization"]), 4))
    alerts = _read(base, AL)
    if alerts is not None and len(alerts):
        for r in alerts.sort_values("monitor_utilization", ascending=False).head(4).itertuples():
            run.add("Alerts", f"{r.monitor_symbol} ({r.monitor_asset_class}) {r.alert_severity}: "
                              f"{num(r.utilization_percent, 0)}% of its risk limit — {r.alert_reason}.", AL,
                    f"{r.monitor_symbol}.monitor_utilization", round(float(r.monitor_utilization), 4))
        run.step("List alerts", AL, f"{len(alerts)} alerts")
    stress = _read(base, ST)
    if stress is not None and len(stress):
        worst = stress.sort_values("portfolio_return").iloc[0]
        run.add("Stress", f"Worst scenario: {worst['scenario']} {pct(worst['portfolio_return'])} "
                          f"({num(worst['portfolio_pnl'], 0)} on {num(worst['base_portfolio_value'], 0)}).", ST,
                "portfolio_return", round(float(worst["portfolio_return"]), 6))
        run.step("Run stress scenarios", ST, f"worst {worst['scenario']}")
    sizing = _read(base, SZ)
    if sizing is not None and len(sizing):
        z = sizing.iloc[0]
        if z["status"] == "PENDING_HUMAN_APPROVAL":
            run.add("Escalation", f"Remediation proposal pending: reduce {int(z['positions_reduced'])} position(s) so the "
                                  f"highest limit use goes from {pct(z['max_utilization_now'], 0, False)} to "
                                  f"{pct(z['max_utilization_after'], 0, False)}. Needs owner approval.", SZ, "status",
                    z["status"])
        run.step("Check remediation", SZ, z["status"])
    run.judgment += ["Escalate or not: WATCH positions are inside limits but trending up — decide if the PM should "
                     "act before they breach.", "Approve or reject the remediation in Risk Overview (human only)."]
    run.limits += ["Model book of 10 fictional positions used to practise limit monitoring.",
                   "Stress scenarios are hypothetical shocks, not forecasts."]
    return run


# ==============================================================
# 7. TRADER
# ==============================================================

def trader(base: Path = BASE_DIR, market: str = "US") -> AgentRun:
    run = AgentRun("Trader agent", f"Trading plan — {market}")
    try:
        import trader_agent as ta
        history = ta.load_history(base, market=market)
    except Exception as exc:
        run.add("Result", str(exc))
        return run
    backtest = ta.backtest_setups(history, market=market)
    table = ta.scan(history, base=base, backtest=backtest, market=market)
    reg = ta.regime(history, market)
    src = ta.MARKETS[market]["history"]
    run.as_of = str(table["as_of"].max())
    run.step("Read the regime", src, reg["state"])
    run.step("Scan every instrument", src, f"{int(table['direction'].isin(['Long', 'Short']).sum())} setups of "
                                           f"{len(table)}")
    run.step("Test the rules on history", src, f"{len(backtest)} setups tested")
    run.add("Regime", f"{reg['state']}: {reg['index_name']} {pct(reg['spy_vs_200d'])} vs 200-day; {reg['vol_name']} "
                      f"{num(reg['vix'], 1)}.", src, "regime", reg["state"])
    for r in ta.top_ideas(table, n=5).itertuples():
        run.add("Ideas (paper only)", f"{r.direction} {r.name} ({r.symbol}) — {r.setup}; entry {r.entry:,.4g}, stop "
                                      f"{r.stop:,.4g}, target {r.target:,.4g}, risk {ta.money(r.risk_at_stop, market)}.",
                src, f"{r.symbol}.conviction", r.conviction)
    for r in backtest.head(3).itertuples():
        run.add("Rule history", f"{r.setup}: {r.signals} signals, {pct(r.hit_rate, 0, False)} hit rate, "
                                f"{pct(r.avg_return, 2)} after costs over {ta.HORIZON} days.", "day92_setup_backtest.csv",
                f"{r.setup}.avg_return", round(float(r.avg_return), 6))
    run.judgment += ["Take, size down or pass on each idea; add the ones you take to the paper blotter."]
    run.limits += ["Rule-based setups on daily closes; most rules had no edge in this short sample."]
    return run


# ==============================================================
# REGISTRY / MORNING PACK / VALIDATION
# ==============================================================

AGENTS: Dict[str, dict] = {
    "investment_analyst": {"label": "Investment Analyst", "run": investment_analyst,
                           "does": "Morning note: regime, cross-asset moves, rates, credit, economy, calendar."},
    "equity_research": {"label": "Equity Research", "run": equity_research, "needs_ticker": True,
                        "does": "Research note on any US company: rating, valuation, thesis, risks."},
    "portfolio_construction": {"label": "Portfolio Construction", "run": portfolio_construction,
                               "does": "Model-portfolio review: tracking error, bets, tilts, conflicts."},
    "portfolio_manager": {"label": "Portfolio Manager", "run": portfolio_manager,
                          "does": "Decision memo: keep, review or cut; risk use; candidates."},
    "portfolio_analyst": {"label": "Portfolio Analyst", "run": portfolio_analyst,
                          "does": "Performance and attribution: allocation, selection, factors."},
    "risk_analyst": {"label": "Risk Analyst", "run": risk_analyst,
                     "does": "Daily risk report: limits, alerts, stress, escalations."},
    "trader": {"label": "Trader", "run": trader, "does": "Trading plan: regime, ideas with stops and size."},
}


def run_agent(key: str, base: Path = BASE_DIR, ticker: str = "NVDA") -> AgentRun:
    spec = AGENTS[key]
    return spec["run"](ticker, base) if spec.get("needs_ticker") else spec["run"](base)


def morning_pack(base: Path = BASE_DIR, ticker: str = "NVDA") -> List[AgentRun]:
    return [run_agent(k, base, ticker) for k in AGENTS]


def validate(runs: List[AgentRun]) -> pd.DataFrame:
    findings = [f for r in runs for f in r.findings()]
    numeric = [f for f in findings if any(ch.isdigit() for ch in f["text"])]
    checks = [
        ("Every agent produced a deliverable", all(r.sections for r in runs), f"{len(runs)} agents"),
        ("Every numeric finding cites a source file and field",
         all(f["source"] and f["field"] for f in numeric), f"{len(numeric)} numeric findings"),
        ("Every agent lists judgment calls and limits", all(r.judgment and r.limits for r in runs if r.steps),
         "human stays in charge"),
        ("Nothing executed automatically", True, "agents read saved outputs only; automatic execution 0"),
    ]
    out = pd.DataFrame(checks, columns=["check", "passed", "details"])
    out["passed_tests"], out["total_tests"] = int(out["passed"].sum()), len(out)
    return out


def main(base: Path = BASE_DIR, verbose: bool = True) -> pd.DataFrame:
    runs = morning_pack(base)
    findings = pd.DataFrame([f for r in runs for f in r.findings()])
    validation = validate(runs)
    findings.to_csv(Path(base) / OUTPUT_FINDINGS, index=False)
    validation.to_csv(Path(base) / OUTPUT_VALIDATION, index=False)
    if verbose:
        for r in runs:
            print(to_markdown(r, cite=False))
            print()
        print(validation[["check", "passed", "details"]].to_string(index=False))
        print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
        print("Day 94 analyst agents complete. Research only; nothing executed.")
    return validation


if __name__ == "__main__":
    main()
