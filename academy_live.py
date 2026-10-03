"""
Vittantra Academy — live examples.

Each function turns a lesson's formula into a worked example using the
data Vittantra already holds (CSV outputs of the engines). Functions return
Markdown. If the data is missing they say which engine to run; they never
invent numbers.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent


class MissingData(Exception):
    pass


def _csv(name: str, run: str) -> pd.DataFrame:
    path = BASE_DIR / name
    if not path.exists():
        raise MissingData(f"Live example needs `{name}`. Run `python {run}` first.")
    return pd.read_csv(path)


def _assets() -> pd.DataFrame:
    return _csv("day76c_asset_analytics.csv", "multi_asset_universe.py").set_index("symbol")


def _fund() -> pd.DataFrame:
    return _csv("day76_fundamental_metrics.csv", "fundamental_engine.py").set_index("ticker")


def _risk_metric(symbol: str, metric: str) -> float:
    df = _csv("day60_instrument_risk_results.csv", "run_vittantra.py")
    row = df[(df["symbol"] == symbol) & (df["metric"] == metric)]
    if row.empty:
        raise MissingData(f"No {metric} for {symbol} in Day 60 results.")
    return float(row["value"].iloc[0])


def pct(x, digits=1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{digits}f}%"


def money(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= size:
            return f"${x / size:,.1f}{unit}"
    return f"${x:,.0f}"


# ==============================================================
# INVESTMENT ANALYST
# ==============================================================

def ia_returns() -> str:
    a = _assets()
    rows = [s for s in ("SPY", "TLT", "GC=F", "BTC-USD") if s in a.index]
    lines = ["| Asset | 1M | 3M | 12M | 12-1 momentum |", "|---|---:|---:|---:|---:|"]
    for s in rows:
        r = a.loc[s]
        lines.append(f"| {r['name']} | {pct(r['return_1m'])} | {pct(r['return_3m'])} | "
                     f"{pct(r['return_12m'])} | {pct(r['momentum_12_1'])} |")
    spy = a.loc["SPY"]
    return ("\n".join(lines) + f"\n\nIf the S&P 500 ETF returned **{pct(spy['return_12m'])}** over 12 months, "
            f"$10,000 became **{money(10000 * (1 + spy['return_12m']))}**. Momentum 12-1 skips the last month "
            "because very recent winners often reverse briefly.")


def ia_volatility() -> str:
    a = _assets()
    lines = ["| Asset | Trading days / year | Annualized volatility | Typical daily move |",
             "|---|---:|---:|---:|"]
    for s in ("SPY", "TLT", "EURUSD=X", "GC=F", "BTC-USD"):
        if s in a.index:
            r = a.loc[s]
            n = r["observations_per_year"]
            daily = r["volatility_1y"] / math.sqrt(n) if n and r["volatility_1y"] == r["volatility_1y"] else float("nan")
            lines.append(f"| {r['name']} | {n:.0f} | {pct(r['volatility_1y'])} | ±{pct(daily, 2)} |")
    return ("\n".join(lines) + "\n\nBitcoin trades every day, so its yearly volatility uses √365, "
            "stocks use about √252. Using the wrong number would misstate risk.")


def ia_yield_curve() -> str:
    c = _csv("day76c_yield_curve.csv", "multi_asset_universe.py")
    by = c.set_index("maturity")
    first = c.iloc[0]
    state = "inverted (a classic recession warning)" if first["slope_3m10y_bp"] < 0 else "upward-sloping (normal)"
    return (f"Today: 3-month **{by.loc['3M', 'yield_pct']:.2f}%**, 2-year **{by.loc['2Y', 'yield_pct']:.2f}%**, "
            f"10-year **{by.loc['10Y', 'yield_pct']:.2f}%**.\n\n"
            f"- 2s10s = {by.loc['10Y', 'yield_pct']:.2f} − {by.loc['2Y', 'yield_pct']:.2f} = "
            f"**{first['slope_2s10s_bp']:.0f} bp**\n"
            f"- 3m10y = **{first['slope_3m10y_bp']:.0f} bp** → the curve is **{state}**.\n"
            f"- 10Y real yield (TIPS) **{first['real_yield_10y_pct']:.2f}%** + breakeven inflation "
            f"**{first['breakeven_10y_pct']:.2f}%** ≈ nominal 10Y (Fisher relation).")


def ia_credit() -> str:
    c = _csv("day76c_credit_spreads.csv", "multi_asset_universe.py").set_index("segment")
    lines = ["| Segment | Spread | 1Y change | Percentile in history |", "|---|---:|---:|---:|"]
    for seg in ("AAA", "BBB", "BB", "CCC & below", "US high yield"):
        if seg in c.index:
            r = c.loc[seg]
            lines.append(f"| {seg} | {r['spread_bp']:.0f} bp | {r['change_1y_bp']:+.0f} bp | "
                         f"{r['percentile_in_history']:.0f} |")
    return ("\n".join(lines) + "\n\nA BBB company borrowing for 10 years pays roughly the 10-year Treasury yield "
            "plus its spread. Wide spreads = investors demand more for default risk = stress.")


def ia_fx_carry() -> str:
    f = _csv("day76c_fx_carry.csv", "multi_asset_universe.py").dropna(subset=["carry_long_pair_pct"])
    f = f.reindex(f["carry_long_pair_pct"].abs().sort_values(ascending=False).index).head(5)
    lines = ["| Pair | Base rate | Quote rate | Carry (long pair) | Carry / volatility |", "|---|---:|---:|---:|---:|"]
    for r in f.itertuples():
        lines.append(f"| {r.pair} | {r.base_rate_pct:.2f}% | {r.quote_rate_pct:.2f}% | "
                     f"{r.carry_long_pair_pct:+.2f}% | {r.carry_to_vol:+.2f} |")
    return "\n".join(lines) + "\n\nCarry is earned only if the exchange rate does not move against you more than the rate gap."


def ia_world_brief() -> str:
    brief = _csv("day78b_brief.csv", "world_brief.py")
    lines = ["| Theme | Data this week | Headlines |", "|---|---|---:|"]
    lines += [f"| {r.theme} | {r.data_move.split(': ', 1)[-1]} | {r.headline_count} |" for r in brief.itertuples()]
    top = brief.iloc[0]
    first = str(top["top_headlines"]).split(" || ")[0] if top["headline_count"] else "no headlines"
    text = "\n".join(lines) + (f"\n\nMost covered theme: **{top['theme']}** ({top['data_move']}). "
                                f"Example headline: *{first}*. Ask: does it explain the size of the move, "
                                "and does it change the outlook?")
    calendar = BASE_DIR / "day78b_calendar.csv"
    if calendar.exists():
        cal = pd.read_csv(calendar).head(4)
        if len(cal):
            text += "\n\nComing up: " + "; ".join(f"**{r.date}** {r.event}" for r in cal.itertuples())
    return text


# ==============================================================
# EQUITY RESEARCHER
# ==============================================================

def er_statements() -> str:
    m = _fund()
    r = m.loc["AAPL"] if "AAPL" in m.index else m.iloc[0]
    return (f"**{r['name']}** — latest period ends {str(r['latest_period_end'])[:10]}, "
            f"filed {str(r['latest_filing_date'])[:10]}.\n\n"
            f"- Revenue (TTM): **{money(r['revenue_ttm'])}**\n"
            f"- Operating income (TTM): **{money(r['operating_income_ttm'])}**\n"
            f"- Net income (TTM): **{money(r['net_income_ttm'])}**\n"
            f"- Free cash flow (TTM): **{money(r['free_cash_flow_ttm'])}**\n"
            f"- Equity: **{money(r['equity'])}**, debt: **{money(r['total_debt'])}**, cash: **{money(r['cash'])}**\n\n"
            "TTM was built as last fiscal year + this year-to-date − last year's same year-to-date.")


def er_valuation() -> str:
    m = _fund()
    lines = ["| Company | P/E | Earnings yield | FCF yield | EBIT/EV |", "|---|---:|---:|---:|---:|"]
    for t in ("AAPL", "NVDA", "JPM", "XOM", "KO"):
        if t in m.index:
            r = m.loc[t]
            pe = f"{r['pe_ratio']:.1f}x" if r["pe_ratio"] == r["pe_ratio"] else "n/a"
            lines.append(f"| {t} | {pe} | {pct(r['earnings_yield'])} | {pct(r['fcf_yield'])} | {pct(r['ebit_to_ev'])} |")
    return ("\n".join(lines) + "\n\nEarnings yield is 1 ÷ P/E. Ranking by yield works even when earnings are "
            "negative; P/E becomes meaningless there.")


def er_quality() -> str:
    m = _fund()
    lines = ["| Company | ROE | ROA | Gross margin | Operating margin | Accruals |", "|---|---:|---:|---:|---:|---:|"]
    for t in ("AAPL", "MSFT", "WMT", "HD", "MCD"):
        if t in m.index:
            r = m.loc[t]
            lines.append(f"| {t} | {pct(r['roe'])} | {pct(r['roa'])} | {pct(r['gross_margin'])} | "
                         f"{pct(r['operating_margin'])} | {pct(r['accruals_ratio'])} |")
    return ("\n".join(lines) + "\n\nWalmart's thin margin can still be a great business (high asset turnover). "
            "Companies with negative equity (buybacks) show ROE as n/a — the ratio is meaningless there.")


def er_health() -> str:
    m = _fund()
    lines = ["| Company | Debt/Equity | Interest coverage | Net debt/EBITDA | Equity/Assets |", "|---|---:|---:|---:|---:|"]
    for t in ("AAPL", "SO", "AMT", "JPM", "GS"):
        if t in m.index:
            r = m.loc[t]
            de = f"{r['debt_to_equity']:.2f}" if r["debt_to_equity"] == r["debt_to_equity"] else "n/a"
            ic = f"{r['interest_coverage']:.1f}x" if r["interest_coverage"] == r["interest_coverage"] else "n/a"
            nd = f"{r['net_debt_to_ebitda']:.2f}" if r["net_debt_to_ebitda"] == r["net_debt_to_ebitda"] else "n/a"
            lines.append(f"| {t} | {de} | {ic} | {nd} | {pct(r['equity_to_assets'])} |")
    return ("\n".join(lines) + "\n\nBanks (JPM, GS) show n/a for industrial ratios: borrowing is their raw material, "
            "so analysts judge them on capital (equity/assets) instead.")


def er_intrinsic_value() -> str:
    v = _csv("day78_valuation.csv", "valuation_engine.py").dropna(subset=["dcf_value", "implied_growth"])
    if v.empty:
        raise MissingData("No DCF valuations yet. Run `python valuation_engine.py`.")
    r = v.sort_values("upside", ascending=False).iloc[len(v) // 2]
    return (f"**{r['ticker']} — {r['name']}** at ${r['price']:,.2f}\n\n"
            f"| Input | Value |\n|---|---:|\n| FCFF (TTM) | {money(r['fcff_ttm'])} |\n"
            f"| Growth, years 1–5 | {pct(r['dcf_initial_growth'])} |\n| Terminal growth | {pct(r['terminal_growth'])} |\n"
            f"| Cost of equity (r_f {pct(r['risk_free'], 2)} + β {r['beta_adjusted']:.2f} × ERP) | "
            f"{pct(r['cost_of_equity'])} |\n| WACC | {pct(r['wacc'])} |\n"
            f"| Terminal value share of DCF | {pct(r['dcf_terminal_share'], 0)} |\n\n"
            f"DCF value **${r['dcf_value']:,.2f}** per share ({r['upside']:+.0%} vs price). Reverse DCF: the price "
            f"implies **{pct(r['implied_growth'])}** growth a year for five years, against "
            f"{pct(r['dcf_initial_growth'])} assumed. If you believe growth will beat the implied rate, the stock "
            "is cheap to you; if not, it is expensive.")


def er_research_note() -> str:
    from research_report import report_markdown
    claims = _csv("day78_research_claims.csv", "research_report.py")
    summary = _csv("day78_report_summary.csv", "research_report.py").set_index("ticker")
    ticker = summary.index[0]
    note = report_markdown(ticker, claims, summary.loc[ticker])
    return note.replace("$", "\\$").replace("\n## ", "\n##### ").replace("# ", "#### ", 1)


def er_point_in_time() -> str:
    m = _fund()
    filed = pd.to_datetime(m["latest_filing_date"], errors="coerce")
    period = pd.to_datetime(m["latest_period_end"], errors="coerce")
    lag = (filed - period).dt.days.dropna()
    return (f"Across {len(lag)} companies, results were filed a median **{lag.median():.0f} days** after the quarter "
            f"ended (range {lag.min():.0f}–{lag.max():.0f}). A backtest that uses a quarter's numbers on the day the "
            "quarter ends is using information nobody had yet — look-ahead bias.")


# ==============================================================
# PORTFOLIO ANALYST (RISK)
# ==============================================================

def _var_summary() -> dict:
    s = _csv("day60_portfolio_risk_summary.csv", "run_vittantra.py").set_index("metric")["value"]
    var = ast.literal_eval(s["existing_portfolio_var_result"])["summary"]
    return {"value": float(s["portfolio_value"]), "rows": var}


def ra_var() -> str:
    v = _var_summary()
    lines = []
    for row in v["rows"]:
        lines.append(f"- **{row['Confidence']} 1-day VaR: {money(row['Historical VaR ($)'])}** "
                     f"({pct(row['Historical VaR ($)'] / v['value'], 2)} of {money(v['value'])}); "
                     f"Expected Shortfall {money(row['Expected Shortfall ($)'])} "
                     f"from {row['Observations']} historical days.")
    return ("\n".join(lines) + "\n\nIn plain words for a client: *on about 1 trading day in 20, the portfolio "
            "could lose more than the 95% VaR; when that happens, the average loss is the Expected Shortfall.*")


def ra_backtest() -> str:
    from var_validation import kupiec_pof_test
    result = kupiec_pof_test(17, 250, 0.95)
    return (f"Example: 250 days at 95% → expect 12.5 breaches. Seeing **17** gives Kupiec LR = "
            f"**{result['Kupiec LR Statistic']:.2f}**, p-value **{result['P-Value']:.3f}** → "
            f"{'reject' if result['Reject at 5%'] else 'do not reject'} the model at 5%.")


def ra_stress_duration() -> str:
    d = _risk_metric("CORP_BOND", "modified_duration")
    c = _risk_metric("CORP_BOND", "convexity")
    dv01 = _risk_metric("CORP_BOND", "dv01")
    approx = -d * 0.02 + 0.5 * c * 0.02 ** 2
    s = _csv("day61_instrument_stress_results.csv", "run_vittantra.py")
    row = s[(s["symbol"] == "CORP_BOND") & (s["scenario"] == "Rates Up 200bp")]
    exact = float(row["rate_effect"].iloc[0]) if len(row) else float("nan")
    return (f"Corporate bond: modified duration **{d:.2f}**, convexity **{c:.1f}**, DV01 **${dv01:.2f}**.\n\n"
            f"Rates +200bp: −D·Δy + ½·C·Δy² = −{d:.2f}×0.02 + ½×{c:.1f}×0.02² = **{pct(approx, 2)}**. "
            f"Full repricing in Vittantra's stress test: **{pct(exact, 2)}** (the small gap is the stub period).")


def ra_greeks() -> str:
    delta = _risk_metric("AAPL_CALL", "delta")
    e = _csv("day64_instrument_exposures.csv", "run_vittantra.py").set_index("symbol")
    row = e.loc["AAPL_CALL"]
    return (f"AAPL call: delta **{delta:.2f}**, premium (market value) **{money(row['market_value'])}**, "
            f"delta-adjusted exposure **{money(row['signed_notional_exposure'])}** "
            f"= Δ × AAPL price × 5 contracts × 100.\n\nA risk report that showed only the premium would understate "
            "how much the portfolio moves with Apple.")


def ra_risk_contribution() -> str:
    b = _csv("day66_instrument_risk_budgets.csv", "run_vittantra.py")
    b = b.sort_values("target_risk_weight", ascending=False).head(5)
    lines = ["| Position | Risk share | Risk budget | Utilization | Status |", "|---|---:|---:|---:|---|"]
    for r in b.itertuples():
        lines.append(f"| {r.symbol} | {pct(r.target_risk_weight)} | {pct(r.instrument_risk_budget)} | "
                     f"{pct(r.risk_budget_utilization, 0)} | {r.risk_budget_status} |")
    return "\n".join(lines) + "\n\nShares come from Euler contributions, so they add up to 100% of portfolio risk."


def ra_what_if() -> str:
    portfolio = _csv("day79_model_portfolio.csv", "portfolio_construction.py")
    import whatif_engine as we
    model = we.RiskModel(we.load_prices(), we.load_fred())
    weights = portfolio[portfolio["weight"] > 0].set_index("ticker")["weight"].to_dict()
    risk = we.portfolio_risk(model, weights)
    if "error" in risk:
        raise MissingData("No overlapping price history for the model portfolio.")
    lines = [f"Model portfolio: volatility **{pct(risk['volatility_annual'])}**, 1-day 99% VaR "
             f"**{money(risk['var99_1d_parametric'])}** per $1m (ES {money(risk['es99_1d_parametric'])}), "
             f"largest risk share {pct(risk['largest_risk_share'])}."]
    if model.betas.empty:
        lines.append("Scenario P&L needs daily overlapping history (run on your machine with daily prices).")
    else:
        lines += ["", "| Scenario | P&L per $1m |", "|---|---:|"]
        for name, shocks in we.SCENARIOS.items():
            lines.append(f"| {name} | {money(we.scenario_pnl(model, weights, shocks)['pnl'].sum(min_count=1))} |")
    return "\n".join(lines)


# ==============================================================
# PORTFOLIO MANAGER
# ==============================================================

def pm_diversification() -> str:
    h = _csv("day75_instrument_price_history.csv", "vittantra_data_hub.py").set_index("date")
    cols = [c for c in ("AAPL", "SPY", "GOLD", "CORP_BOND", "BTC") if c in h.columns]
    corr = h[cols].pct_change().dropna().corr().round(2)
    vol = h[["SPY", "GOLD"]].pct_change().dropna()
    s1, s2 = vol.std() * math.sqrt(252)
    rho = vol.corr().iloc[0, 1]
    combo = math.sqrt(0.25 * s1 ** 2 + 0.25 * s2 ** 2 + 2 * 0.25 * rho * s1 * s2)
    header = "| | " + " | ".join(cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    body = "".join(f"| {r} | " + " | ".join(f"{corr.loc[r, c]:.2f}" for c in cols) + " |\n" for r in cols)
    return (header + body + f"\n\n50/50 S&P 500 + gold: volatilities {pct(s1)} and {pct(s2)}, correlation "
            f"{rho:.2f} → portfolio volatility **{pct(combo)}**, below the average {pct((s1 + s2) / 2)}. "
            "That gap is the diversification benefit.")


def pm_sharpe() -> str:
    s = _csv("day56_portfolio_summary.csv", "ml_portfolio_backtest.py").set_index("strategy")
    lines = ["| Strategy | Return | Volatility | Sharpe | Sortino | Max drawdown |", "|---|---:|---:|---:|---:|---:|"]
    for name, r in s.iterrows():
        lines.append(f"| {name} | {pct(r['annualized_return'])} | {pct(r['annualized_volatility'])} | "
                     f"{r['sharpe_ratio']:.2f} | {r['sortino_ratio']:.2f} | {pct(r['maximum_drawdown'])} |")
    return "\n".join(lines) + "\n\nLong-only Sharpe subtracts the actual T-bill rate; long/short is already an excess return."


def pm_costs() -> str:
    c = _csv("day57_cost_sensitivity.csv", "ml_portfolio_robustness.py")
    lines = ["| Cost per dollar traded | Annual return |", "|---|---:|"]
    for r in c.itertuples():
        lines.append(f"| {r.test} | {pct(r.annualized_return)} |")
    return "\n".join(lines) + "\n\nThe strategy's edge disappears somewhere between 50 and 75 bps — costs decide whether alpha is real."


def pm_attribution() -> str:
    s = _csv("day58_factor_regression_summary.csv", "ml_factor_attribution.py").set_index("metric")["value"]
    return (f"Annualized alpha **{float(s['annualized_alpha_simple']) * 100:.1f}%**, t-statistic "
            f"**{float(s['alpha_t_statistic']):.2f}**, p-value **{float(s['alpha_p_value']):.2f}**, R² "
            f"**{float(s['r_squared']):.2f}** from {int(float(s['observations']))} periods.\n\n"
            "A |t| below about 2 means the alpha could easily be luck — say so before anyone else does.")


def pm_rebalance() -> str:
    t = _csv("day65_target_exposures.csv", "run_vittantra.py")
    t = t.reindex((t["target_risk_weight"] - t["risk_weight"]).abs().sort_values(ascending=False).index).head(4)
    lines = ["| Position | Capital weight now → target | Risk share now → target | Why |", "|---|---|---|---|"]
    for r in t.itertuples():
        lines.append(f"| {r.symbol} | {pct(r.capital_weight)} → {pct(r.target_capital_weight)} | "
                     f"{pct(r.risk_weight)} → {pct(r.target_risk_weight)} | {r.constraint_reason} |")
    return "\n".join(lines)


def pm_signals() -> str:
    ic = _csv("day77_ic_summary.csv", "multi_factor_rating.py").dropna(subset=["mean_ic"])
    lines = ["| Signal | Mean IC | t-stat | Hit rate |", "|---|---:|---:|---:|"]
    lines += [f"| {r.signal} | {r.mean_ic:.3f} | {r.ic_t_stat:.2f} | {pct(r.hit_rate, 0)} |" for r in ic.itertuples()]
    best = ic.sort_values("mean_ic", ascending=False).iloc[0]
    return ("\n".join(lines) + f"\n\nBest signal: **{best['signal']}** (IC {best['mean_ic']:.3f}). With 33 stocks "
            f"rebalanced about 12.6 times a year, breadth ≈ 33 × 12.6 = 416 bets, so IR ≈ IC × √416 ≈ "
            f"**{best['mean_ic'] * 416 ** 0.5:.2f}** (upper bound — bets are not fully independent).")


def pm_model_portfolio() -> str:
    s = _csv("day79_portfolio_summary.csv", "portfolio_construction.py").iloc[0]
    p = _csv("day79_model_portfolio.csv", "portfolio_construction.py")
    top = p.sort_values("weight", ascending=False).head(5)
    rows = ["| Stock | Score | Alpha | Weight | Risk share |", "|---|---:|---:|---:|---:|"]
    rows += [f"| {r.ticker} | {r.score:.0f} | {pct(r.alpha)} | {pct(r.weight)} | {pct(r.risk_share)} |"
             for r in top.itertuples()]
    return ("\n".join(rows) + f"\n\nExpected active return **{pct(s['expected_active_return'])}** a year at tracking "
            f"error **{pct(s['tracking_error'])}** (budget {pct(s['tracking_error_budget'], 0)}) → IR "
            f"**{s['information_ratio']:.2f}**. Beta {s['beta_to_benchmark']:.2f}, active share "
            f"{pct(s['active_share'], 0)}. Signal IC {s['signal_ic']:.3f}. Status: {s['approval_status']}.")


def pm_attribution_brinson() -> str:
    s = _csv("day80_attribution_summary.csv", "performance_attribution.py").iloc[0]
    sectors = _csv("day80_brinson_by_sector.csv", "performance_attribution.py")
    best, worst = sectors.iloc[0], sectors.iloc[-1]
    return (f"Research portfolio {pct(s['portfolio_cumulative'])} vs benchmark {pct(s['benchmark_cumulative'])} "
            f"({s['start']} → {s['end']}): active **{pct(s['active_cumulative'])}** = allocation "
            f"{pct(s['allocation_linked'])} + selection {pct(s['selection_linked'])} + interaction "
            f"{pct(s['interaction_linked'])} + costs {pct(s['costs_linked'])}.\n\nBest sector: **{best['sector']}** "
            f"({pct(best['total'])}); worst: **{worst['sector']}** ({pct(worst['total'])}).")


# ==============================================================
# ADVISOR
# ==============================================================

def ad_process() -> str:
    return ("Vittantra's own workflow mirrors the advisory process: data → analysis (risk engine) → "
            "recommendation (remediation) → **approval by a human** (Day 70 tickets) → record kept (audit log).")


def ad_risk_profile() -> str:
    v = _var_summary()
    worst = min((r for r in v["rows"]), key=lambda r: r["Confidence"])
    return (f"Translate risk into client language: with today's example portfolio of {money(v['value'])}, "
            f"a bad day (1 in 20) could cost more than **{money(worst['Historical VaR ($)'])}**. "
            "Ask the client: *would that make you sell?* Their answer measures risk tolerance; their income, "
            "savings and time horizon measure risk capacity.")


def ad_goal_planning() -> str:
    goal, years, rate, start = 1_000_000, 25, 0.06, 50_000
    fv_start = start * (1 + rate) ** years
    needed = goal - fv_start
    pmt = needed * rate / ((1 + rate) ** years - 1)
    return (f"Client goal: **{money(goal)}** in {years} years, has {money(start)} today, assumed return "
            f"{pct(rate, 0)} a year (an assumption to state, not a promise).\n\n"
            f"- Today's savings grow to {money(start)} × 1.06^{years} = **{money(fv_start)}**\n"
            f"- Gap: {money(needed)} → required saving **{money(pmt)} per year** "
            f"(annuity formula PMT = FV × r ÷ ((1+r)^n − 1)).")


def ad_allocation() -> str:
    s = _csv("day76c_asset_class_summary.csv", "multi_asset_universe.py")
    s = s.groupby("asset_class")["median_volatility"].median().sort_values()
    lines = ["| Asset class | Typical volatility (median of segments) |", "|---|---:|"]
    lines += [f"| {k} | {pct(v)} |" for k, v in s.items()]
    return "\n".join(lines) + "\n\nA cautious client's mix leans to the top rows; a long-horizon client can hold more of the bottom rows."


def ad_communication() -> str:
    c = _csv("day76c_yield_curve.csv", "multi_asset_universe.py").set_index("maturity")
    return (f"Instead of *“duration risk is elevated”*, say: *“Ten-year government bonds now pay "
            f"{c.loc['10Y', 'yield_pct']:.2f}% a year. If rates rise by one more percentage point, a typical "
            "10-year bond fund could fall about 8% in price, though it would then earn the higher rate.”*")


def ad_cma() -> str:
    cma = _csv("day82_capital_market_assumptions.csv", "advisory_engine.py")
    rows = ["| Sleeve | Expected return | Volatility | How |", "|---|---:|---:|---|"]
    rows += [f"| {r.sleeve} | {pct(r.expected_return)} | {pct(r.volatility)} | {r.method} |" for r in cma.itertuples()]
    alloc = _csv("day82_model_allocations.csv", "advisory_engine.py")
    m = alloc[alloc["profile"] == 3].iloc[0]
    return ("\n".join(rows) + f"\n\nModerate model: expected {pct(m['expected_return'])}, volatility "
            f"{pct(m['volatility'])}, equity {pct(m['equity_share'], 0)}, bad year about −{pct(m['bad_year_loss'], 0)}.")


def ad_suitability() -> str:
    profiles = _csv("day82_client_profiles.csv", "advisory_engine.py")
    rules = _csv("day83_suitability_results.csv", "advisory_engine.py")
    r = profiles.iloc[0]
    own = rules[rules["client_id"] == r["client_id"]]
    lines = [f"**{r['name']}** — profile **{r['profile_name']}**. {r['profile_note']}", ""]
    lines += [f"- {'✅' if x.passed else '⚠️'} {x.rule}: {x.detail}" for x in own.itertuples()]
    return "\n".join(lines) + f"\n\nVerdict: **{r['suitability']}**."


def ad_monte_carlo() -> str:
    goals = _csv("day84_goal_summary.csv", "advisory_engine.py")
    profiles = _csv("day82_client_profiles.csv", "advisory_engine.py").set_index("client_id")
    lines = ["| Client | Goal | Chance | Median (today's $) | Poor case |", "|---|---|---:|---:|---:|"]
    for g in goals.itertuples():
        lines.append(f"| {profiles.at[g.client_id, 'name']} | {profiles.at[g.client_id, 'goal']} | "
                     f"{pct(g.probability, 0)} | {money(g.median_real)} | {money(g.p10_real)} |")
    return "\n".join(lines) + "\n\n10,000 simulated paths per client; amounts in today's money."
