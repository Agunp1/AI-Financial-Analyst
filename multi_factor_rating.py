"""
Day 77 — Vittantra Multi-Factor Rating

Combines five independent pillars into one research rating for the
33-stock research universe, and tests — point in time — whether the
combination predicted returns better than each pillar alone.

Pillars (cross-sectional percentile scores, 0–100, at each date)
-----------------------------------------------------------------
Fundamental  Day 76 composite (value, growth, quality, health), rebuilt
             from SEC facts FILED on or before the date
Technical    12-1 momentum and price vs. its 200-day average
Quant        Day 55 walk-forward ML probability of a positive 20-day return
Economic     Regime tilt: in risk-on markets favour higher beta, in
             risk-off markets favour lower beta. Regime = credit spreads
             above their 1-year median, or an inverted 3m–10y curve
Risk         Low volatility (lower 1-year volatility scores higher)

Composite = equal-weighted average of available pillars; a second
"IC-weighted" composite weights pillars by their past information
coefficient, using only dates whose outcomes were known (no look-ahead). Rating:
Overweight (top 30%), Neutral, Underweight (bottom 30%) — research labels,
not trade instructions.

Testing (no look-ahead)
-----------------------
At each Day 55 rebalance date t, every input uses data dated ≤ t, and
performance uses the following 20 trading days.
- Information coefficient (IC): Spearman rank correlation between score
  and the next 20-day return; mean IC and its t-statistic across dates.
- Portfolios: top-quintile long and top-minus-bottom long/short, equal
  weight, 10 bps per dollar traded; Sharpe vs. T-bills for long-only.

Usage:  python multi_factor_rating.py
Research only. No trades are submitted or executed.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

import fundamental_engine as fe
import ml_portfolio_backtest as bt


BASE_DIR = Path(__file__).resolve().parent
HEDGE_FUND_DB = BASE_DIR / "hedge_fund.db"
MARKET_DB = BASE_DIR / "vittantra_market.db"
RANKINGS_FILE = BASE_DIR / "day55_cross_sectional_rankings.csv"

PILLARS = ["fundamental", "technical", "quant", "economic", "risk"]
OVERWEIGHT_SHARE = 0.30
QUINTILE = 0.20
MIN_STOCKS = 10

OUTPUT_RATINGS = "day77_current_ratings.csv"
OUTPUT_SCORES_HISTORY = "day77_score_history.csv"
OUTPUT_IC = "day77_information_coefficients.csv"
OUTPUT_IC_SUMMARY = "day77_ic_summary.csv"
OUTPUT_IC_WEIGHTS = "day77_ic_weights.csv"
OUTPUT_BACKTEST = "day77_backtest_summary.csv"
OUTPUT_VALIDATION = "day77_validation_summary.csv"


# ==============================================================
# DATA
# ==============================================================

def load_prices() -> Tuple[pd.DataFrame, str]:
    """Wide daily closes (dates × tickers) and a description of the source."""
    frames, sources = [], []
    if HEDGE_FUND_DB.exists():
        try:
            with sqlite3.connect(HEDGE_FUND_DB) as conn:
                df = pd.read_sql("SELECT date, ticker, close_price AS close FROM daily_prices", conn)
            frames.append(df)
            sources.append("hedge_fund.db daily prices")
        except Exception:
            pass
    if MARKET_DB.exists():
        try:
            with sqlite3.connect(MARKET_DB) as conn:
                df = pd.read_sql("SELECT date, ticker, COALESCE(adj_close, close) AS close FROM price_history", conn)
            frames.append(df)
            sources.append("vittantra_market.db (Yahoo)")
        except Exception:
            pass
    universe = set(fe.load_universe())
    usable = [(f, src) for f, src in zip(frames, sources)
              if f["ticker"].isin(universe).groupby(f["ticker"]).any().sum() >= len(universe) / 2]
    frames, sources = [f for f, _ in usable], [src for _, src in usable]
    if frames:
        long = pd.concat(frames).dropna()
        long["date"] = pd.to_datetime(long["date"])
        wide = long.drop_duplicates(["date", "ticker"], keep="last").pivot(
            index="date", columns="ticker", values="close").sort_index()
        return wide, " + ".join(sources)
    ranks = pd.read_csv(RANKINGS_FILE, parse_dates=["date"])
    wide = ranks.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide, "Day 55 closes (20-day sampling; coarse — run on a machine with hedge_fund.db)"


def load_macro() -> Dict[str, pd.Series]:
    if not MARKET_DB.exists():
        return {}
    try:
        with sqlite3.connect(MARKET_DB) as conn:
            df = pd.read_sql("SELECT series_id, date, value FROM macro_observations", conn, parse_dates=["date"])
    except Exception:
        return {}
    return {s: g.set_index("date")["value"].sort_index() for s, g in df.groupby("series_id")}


def _on_or_before(series: pd.Series, date: pd.Timestamp) -> Optional[float]:
    before = series[series.index <= date].dropna()
    return float(before.iloc[-1]) if len(before) else None


# ==============================================================
# PILLAR INPUTS AT A DATE (point in time)
# ==============================================================

def price_features(prices: pd.DataFrame, date: pd.Timestamp, benchmark: Optional[pd.Series]) -> pd.DataFrame:
    """Momentum, trend, volatility and beta per ticker using prices dated ≤ date."""
    past = prices[prices.index <= date]
    rows = {}
    bench = benchmark[benchmark.index <= date] if benchmark is not None else past.mean(axis=1)
    bench_returns = bench.pct_change()
    for ticker in past.columns:
        s = past[ticker].dropna()
        if len(s) < 5:
            continue
        p_now = s.iloc[-1]
        p_1m = _on_or_before(s, date - pd.DateOffset(months=1))
        p_12m = _on_or_before(s, date - pd.DateOffset(months=12))
        year = s[s.index > date - pd.Timedelta(days=365)]
        returns = year.pct_change().dropna()
        per_year = max(len(returns), 1)
        trend_window = s[s.index > date - pd.Timedelta(days=290)]       # ≈ 200 trading days
        aligned = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
        beta = (aligned.cov().iloc[0, 1] / aligned.iloc[:, 1].var()
                if len(aligned) > 8 and aligned.iloc[:, 1].var() > 0 else np.nan)
        rows[ticker] = {
            "momentum_12_1": p_1m / p_12m - 1 if p_1m and p_12m else np.nan,
            "trend_vs_200d": p_now / trend_window.mean() - 1 if len(trend_window) > 5 else np.nan,
            "volatility_1y": returns.std(ddof=1) * math.sqrt(per_year) if len(returns) > 5 else np.nan,
            "beta": beta,
            "price": p_now,
        }
    columns = ["momentum_12_1", "trend_vs_200d", "volatility_1y", "beta", "price"]
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=columns)


def macro_regime(macro: Dict[str, pd.Series], date: pd.Timestamp) -> str:
    """'risk_off', 'risk_on' or 'unknown' from data dated ≤ date."""
    spread = macro.get("BAMLH0A0HYM2", macro.get("BAMLC0A4CBBB"))
    ten, three = macro.get("DGS10"), macro.get("DGS3MO")
    if spread is None:
        return "unknown"
    history = spread[(spread.index <= date) & (spread.index > date - pd.Timedelta(days=365))].dropna()
    if len(history) < 20:
        return "unknown"
    wide_spreads = history.iloc[-1] > history.median()
    inverted = False
    if ten is not None and three is not None:
        t, s = _on_or_before(ten, date), _on_or_before(three, date)
        inverted = t is not None and s is not None and t < s
    return "risk_off" if (wide_spreads or inverted) else "risk_on"


def fundamental_scores_at(date: pd.Timestamp, facts: Dict[str, dict], universe: Dict[str, dict],
                          prices: pd.Series) -> pd.Series:
    """Day 76 composite rebuilt from SEC facts filed on or before `date`."""
    rows = []
    for ticker, company_facts in facts.items():
        price = prices.get(ticker)
        row = {"ticker": ticker, "sector": universe[ticker]["sector"]}
        try:
            row.update(fe.compute_company_metrics(company_facts, date,
                                                  float(price) if price == price else None,
                                                  universe[ticker]["sector"]))
        except Exception:
            pass
        rows.append(row)
    metrics = pd.DataFrame(rows).set_index("ticker")
    for pillar in fe.PILLARS.values():
        for metric, _, _ in pillar:
            if metric not in metrics.columns:
                metrics[metric] = np.nan
    return fe.percentile_scores(metrics)["fundamental_score"]


def load_point_in_time_facts(universe: Dict[str, dict]) -> Dict[str, dict]:
    """SEC company facts from the local cache only (no downloads during a backtest)."""
    facts = {}
    try:
        ticker_map = fe.fetch_ticker_map()
    except Exception:
        return facts
    for ticker in universe:
        cik = ticker_map.get(ticker)
        path = fe.CACHE_DIR / f"CIK{cik:010d}.json" if cik else None
        if path is not None and path.exists():
            import json
            facts[ticker] = json.loads(path.read_text())
    return facts


# ==============================================================
# SCORING
# ==============================================================

def pct_rank(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").rank(pct=True, ascending=higher_is_better) * 100


def pillar_scores(features: pd.DataFrame, ml: pd.Series, fundamental: Optional[pd.Series],
                  regime: str) -> pd.DataFrame:
    scores = pd.DataFrame(index=features.index, dtype=float)
    scores["technical"] = pd.concat([pct_rank(features["momentum_12_1"]),
                                     pct_rank(features["trend_vs_200d"])], axis=1).mean(axis=1)
    scores["quant"] = pct_rank(ml.reindex(features.index))
    if regime == "risk_on":
        scores["economic"] = pct_rank(features["beta"], higher_is_better=True)
    elif regime == "risk_off":
        scores["economic"] = pct_rank(features["beta"], higher_is_better=False)
    else:
        scores["economic"] = np.nan
    scores["risk"] = pct_rank(features["volatility_1y"], higher_is_better=False)
    scores["fundamental"] = fundamental.reindex(features.index) if fundamental is not None else np.nan
    scores["composite"] = scores[PILLARS].mean(axis=1, skipna=True)
    scores.loc[scores[PILLARS].notna().sum(axis=1) < 3, "composite"] = np.nan
    return scores


def ratings_from_scores(composite: pd.Series) -> pd.Series:
    rank = composite.rank(pct=True)
    return pd.Series(np.select([rank > 1 - OVERWEIGHT_SHARE, rank <= OVERWEIGHT_SHARE],
                               ["Overweight", "Underweight"], "Neutral"), index=composite.index).where(composite.notna())


# ==============================================================
# BACKTEST
# ==============================================================

def spearman(a: pd.Series, b: pd.Series) -> Optional[float]:
    frame = pd.concat([a, b], axis=1).dropna()
    if len(frame) < MIN_STOCKS:
        return None
    return float(frame.rank().corr().iloc[0, 1])


def run_history(rankings: pd.DataFrame, prices: pd.DataFrame, benchmark: Optional[pd.Series],
                macro: Dict[str, pd.Series], facts: Dict[str, dict], universe: Dict[str, dict]) -> pd.DataFrame:
    history = []
    for date, group in rankings.groupby("date"):
        group = group.set_index("ticker")
        features = price_features(prices, date, benchmark).reindex(group.index)
        fundamental = None
        if facts:
            price_at = prices[prices.index <= date].ffill().iloc[-1] if len(prices[prices.index <= date]) else pd.Series()
            fundamental = fundamental_scores_at(date, facts, universe, price_at)
        regime = macro_regime(macro, date)
        scores = pillar_scores(features, group["up_probability"], fundamental, regime)
        scores["forward_return_20d"] = group["forward_return_20d"]
        scores["regime"] = regime
        scores["date"] = date
        history.append(scores.reset_index().rename(columns={"index": "ticker"}))
    return pd.concat(history, ignore_index=True)


MIN_IC_HISTORY = 6
SIGNALS = PILLARS + ["composite", "composite_ic_weighted"]


def add_ic_weighted_composite(history: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Second composite that weights pillars by their past predictive power.

    At date t the weights use only ICs from earlier dates, whose 20-day
    forward windows have already ended by t (no look-ahead):
        w_k ∝ max(mean past IC_k, 0); equal weights until enough history.
    """
    history = history.copy()
    history["composite_ic_weighted"] = np.nan
    dates = sorted(history["date"].unique())
    past_ics = []
    weight_rows = []
    for date in dates:
        mask = history["date"] == date
        g = history[mask].copy()
        g[PILLARS] = g[PILLARS].apply(pd.to_numeric, errors="coerce").astype(float)
        if len(past_ics) >= MIN_IC_HISTORY:
            means = pd.DataFrame(past_ics)[PILLARS].mean().clip(lower=0).fillna(0)
            weights = means / means.sum() if means.sum() > 0 else pd.Series(1 / len(PILLARS), index=PILLARS)
        else:
            weights = pd.Series(1 / len(PILLARS), index=PILLARS)
        available = g[PILLARS].notna()
        w = available.mul(weights, axis=1)
        totals = w.sum(axis=1).replace(0, np.nan)
        composite = ((g[PILLARS].fillna(0) * w).sum(axis=1) / totals).where(available.sum(axis=1) >= 3)
        history.loc[mask, "composite_ic_weighted"] = composite.astype(float).to_numpy()
        weight_rows.append({"date": date, **weights.to_dict()})
        realized = g.dropna(subset=["forward_return_20d"]).set_index("ticker")
        if len(realized) >= MIN_STOCKS:
            past_ics.append({k: spearman(realized[k], realized["forward_return_20d"]) for k in PILLARS})
    return history, pd.DataFrame(weight_rows)


def ic_table(history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, g in history.dropna(subset=["forward_return_20d"]).groupby("date"):
        g = g.set_index("ticker")
        row = {"date": date}
        for signal in SIGNALS:
            row[signal] = spearman(g[signal], g["forward_return_20d"])
        rows.append(row)
    return pd.DataFrame(rows)


def ic_summary(ics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for signal in SIGNALS:
        values = pd.to_numeric(ics[signal], errors="coerce").dropna()
        n = len(values)
        mean = values.mean() if n else np.nan
        std = values.std(ddof=1) if n > 1 else np.nan
        rows.append({
            "signal": signal, "dates": n, "mean_ic": mean,
            "ic_t_stat": mean / (std / math.sqrt(n)) if n > 1 and std > 0 else np.nan,
            "hit_rate": (values > 0).mean() if n else np.nan,
            # Information ratio of the signal (annualized IC consistency)
            "ic_ir_annualized": mean / std * math.sqrt(bt.PERIODS_PER_YEAR) if n > 1 and std > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def portfolio_backtest(history: pd.DataFrame) -> pd.DataFrame:
    periods = history.dropna(subset=["forward_return_20d"])
    dates = sorted(periods["date"].unique())
    rf, _ = bt.period_risk_free(pd.Series(pd.to_datetime(dates)))
    rf.index = range(len(dates))
    rows = []
    for signal in SIGNALS:
        previous = {"long": {}, "long_short": {}}
        returns = {"long": [], "long_short": []}
        for date in dates:
            g = periods[periods["date"] == date].dropna(subset=[signal])
            if len(g) < MIN_STOCKS:
                returns["long"].append(np.nan)
                returns["long_short"].append(np.nan)
                continue
            n = max(1, int(round(len(g) * QUINTILE)))
            ranked = g.sort_values(signal, ascending=False)
            top, bottom = ranked.head(n), ranked.tail(n)
            weights = {
                "long": {t: 1 / n for t in top["ticker"]},
                "long_short": {**{t: 0.5 / n for t in top["ticker"]}, **{t: -0.5 / n for t in bottom["ticker"]}},
            }
            realized = dict(zip(g["ticker"], g["forward_return_20d"]))
            for book in ("long", "long_short"):
                gross = sum(w * realized[t] for t, w in weights[book].items())
                turnover = bt.calculate_turnover(previous[book], weights[book])
                returns[book].append(gross - 2 * turnover * bt.TRANSACTION_COST_RATE)
                previous[book] = weights[book]
        for book, label in (("long", "top quintile long"), ("long_short", "long/short")):
            series = pd.Series(returns[book], dtype=float)
            rows.append({
                "signal": signal, "portfolio": label, "periods": int(series.notna().sum()),
                "annualized_return": bt.annualized_return(series),
                "annualized_volatility": bt.annualized_volatility(series),
                "sharpe_ratio": bt.sharpe_ratio(series, rf if book == "long" else None),
                "max_drawdown": bt.maximum_drawdown(series.dropna()) if series.notna().any() else np.nan,
            })
    return pd.DataFrame(rows)


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day77(current: pd.DataFrame, history: pd.DataFrame, ic_sum: pd.DataFrame,
                   price_source: str, facts_available: bool) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add("Current ratings for the research universe", current["composite"].notna().mean() >= 0.9,
        f"{int(current['composite'].notna().sum())} of {len(current)} stocks rated")
    values = pd.to_numeric(history[SIGNALS].stack(), errors="coerce").dropna()
    add("Scores between 0 and 100", values.between(0, 100).all(), "All pillar and composite scores")
    counts = current["rating"].value_counts(normalize=True)
    add("Rating distribution about 30 / 40 / 30", abs(counts.get("Overweight", 0) - 0.3) <= 0.06
        and abs(counts.get("Underweight", 0) - 0.3) <= 0.06, counts.round(2).to_dict())
    composite_dates = int(ic_sum.set_index("signal").loc["composite", "dates"])
    add("Enough history for IC testing", composite_dates >= 20, f"{composite_dates} dates")
    add("Fundamentals point in time in backtest", facts_available,
        "SEC facts filed ≤ each date" if facts_available else "SEC cache not found: fundamental pillar "
        "excluded from the backtest (current rating still uses Day 76)")
    add("Daily price history", "coarse" not in price_source, price_source)
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_multi_factor(out_dir: Path = BASE_DIR, prices: Optional[pd.DataFrame] = None,
                     price_source: Optional[str] = None, macro: Optional[Dict[str, pd.Series]] = None,
                     facts: Optional[Dict[str, dict]] = None, verbose: bool = True):
    universe = fe.load_universe()
    rankings = pd.read_csv(RANKINGS_FILE, parse_dates=["date"])
    if prices is None:
        prices, price_source = load_prices()
    macro = load_macro() if macro is None else macro
    facts = load_point_in_time_facts(universe) if facts is None else facts
    benchmark = prices["SPY"] if "SPY" in prices.columns else None
    stock_prices = prices[[t for t in prices.columns if t in universe]]

    history = run_history(rankings, stock_prices, benchmark, macro, facts, universe)
    history, ic_weights = add_ic_weighted_composite(history)
    ics = ic_table(history)
    ic_sum = ic_summary(ics)
    backtest = portfolio_backtest(history)

    # Current ratings: latest prices, latest ML ranking, Day 76 fundamentals
    as_of = max(stock_prices.index.max(), rankings["date"].max())
    latest_rank = rankings[rankings["date"] == rankings["date"].max()].set_index("ticker")
    features = price_features(stock_prices, as_of, benchmark)
    day76 = BASE_DIR / fe.OUTPUT_SCORES
    fundamental = (pd.read_csv(day76).set_index("ticker")["fundamental_score"] if day76.exists() else None)
    regime = macro_regime(macro, as_of)
    current = pillar_scores(features.reindex(list(universe)), latest_rank["up_probability"], fundamental, regime)
    if len(ic_weights):
        latest_weights = ic_weights.iloc[-1][PILLARS].astype(float)
        available = current[PILLARS].notna()
        w = available.mul(latest_weights, axis=1)
        current["composite_ic_weighted"] = ((current[PILLARS].fillna(0) * w).sum(axis=1)
                                            / w.sum(axis=1).replace(0, np.nan))
    current["rating"] = ratings_from_scores(current["composite"])
    current["strongest_pillar"] = current[PILLARS].idxmax(axis=1, skipna=True)
    current["weakest_pillar"] = current[PILLARS].idxmin(axis=1, skipna=True)
    current["regime"] = regime
    current["as_of"] = as_of.date()
    current.insert(0, "sector", [universe[t]["sector"] for t in current.index])
    current.insert(0, "name", [universe[t]["name"] for t in current.index])
    current = current.sort_values("composite", ascending=False)
    current.index.name = "ticker"
    validation = validate_day77(current, history, ic_sum, price_source, bool(facts))

    out_dir = Path(out_dir)
    current.to_csv(out_dir / OUTPUT_RATINGS)
    history.to_csv(out_dir / OUTPUT_SCORES_HISTORY, index=False)
    ics.to_csv(out_dir / OUTPUT_IC, index=False)
    ic_weights.to_csv(out_dir / OUTPUT_IC_WEIGHTS, index=False)
    ic_sum.to_csv(out_dir / OUTPUT_IC_SUMMARY, index=False)
    backtest.to_csv(out_dir / OUTPUT_BACKTEST, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(current, ic_sum, backtest, validation, price_source, regime)
    return current, ic_sum, backtest, validation


def print_report(current, ic_sum, backtest, validation, price_source, regime) -> None:
    line = "=" * 92
    pd.set_option("display.width", 220)
    print(line)
    print("VITTANTRA — DAY 77 MULTI-FACTOR RATING")
    print(line)
    print(f"Prices: {price_source} | macro regime now: {regime}")
    print("\nCurrent ratings")
    print(current[["name", "sector", *PILLARS, "composite", "rating"]].round(0).to_string())
    print("\nDoes each signal predict the next 20-day return? (information coefficient)")
    print(ic_sum.round(3).to_string(index=False))
    print("\nPortfolio backtest (10 bps per dollar traded)")
    print(backtest.round(3).to_string(index=False))
    composite = ic_sum.set_index("signal").loc["composite"]
    best_single = ic_sum[ic_sum["signal"] != "composite"].sort_values("mean_ic", ascending=False).iloc[0]
    print(f"\nComposite mean IC {composite['mean_ic']:.3f} (t = {composite['ic_t_stat']:.2f}) vs best single "
          f"pillar {best_single['signal']} {best_single['mean_ic']:.3f} (t = {best_single['ic_t_stat']:.2f}). "
          "|t| below ~2 means the evidence is not statistically strong.")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 77 multi-factor rating complete. Ratings are research labels, not recommendations.")
    print(line)


if __name__ == "__main__":
    run_multi_factor()
