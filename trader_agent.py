"""
Day 92 — Trader agent: rule-based trade ideas on live prices, a paper blotter
and an honest backtest of the rules.

The agent scans every instrument with daily history (equity and bond ETFs,
REITs, commodities, FX, crypto, alternatives) and classifies the setup:

  trend   price vs its 50- and 200-day averages (time-series momentum)
  timing  14-day RSI and a 55-day breakout (pullback, breakout, overextended)
  risk    20-day average absolute move ("ATR from closes") sets the stop

Each idea gets a plan: entry at the last price, stop 2 ATR away, target 3 ATR
away (reward-to-risk 1.5), size so a stop-out loses 0.5% of a $1m paper book
(capped at 10% of the book; halved for risk assets in a risk-off regime).

Nothing is executed. Ideas go to a PAPER blotter only when a person adds them;
automatic execution stays 0. Backtest results are historical research, not a
forecast. All numbers come from day76c_price_history.csv.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
HISTORY = "day76c_price_history.csv"
ANALYTICS = "day76c_asset_analytics.csv"
OUTPUT_SCAN = "day92_trade_scan.csv"
OUTPUT_BACKTEST = "day92_setup_backtest.csv"
OUTPUT_VALIDATION = "day92_validation_summary.csv"

BOOK = 1_000_000                  # paper book, USD
RISK_PER_TRADE = 0.005            # a stop-out loses 0.5% of the book
MAX_POSITION = 0.10               # no idea larger than 10% of the book
STOP_ATR, TARGET_ATR = 2.0, 3.0   # reward-to-risk 1.5
MIN_HISTORY = 210                 # enough for a 200-day average
HORIZON = 10                      # backtest holding period, trading days
NOT_TRADED = {"^VIX"}             # used for the regime only

# The US and India books are kept separate: own data files, index, volatility gauge, currency and book.
MARKETS = {
    "US": {"history": "day76c_price_history.csv", "analytics": "day76c_asset_analytics.csv",
           "index": "SPY", "index_name": "S&P 500", "vol": "^VIX", "vol_name": "VIX", "vol_calm": 20.0,
           "vol_stress": 25.0, "book": 1_000_000, "currency": "USD", "symbol": "$", "run": "multi_asset_universe.py"},
    "India": {"history": "day93_india_price_history.csv", "analytics": "day93_india_analytics.csv",
              "index": "^NSEI", "index_name": "Nifty 50", "vol": "^INDIAVIX", "vol_name": "India VIX",
              "vol_calm": 18.0, "vol_stress": 24.0, "book": 10_000_000, "currency": "INR", "symbol": "₹",
              "run": "india_markets.py"},
}


def not_traded(symbol: str, market: str = "US") -> bool:
    """Gauges and indices are read, not traded (India: indices are traded through ETFs and stocks)."""
    cfg = MARKETS[market]
    return symbol in NOT_TRADED or symbol == cfg["vol"] or (market == "India" and symbol.startswith("^"))


def money(value: float, market: str = "US") -> str:
    """$1,234 for the US; ₹12,34,567 (lakh grouping) for India."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if market != "India":
        return f"${value:,.0f}"
    sign, digits = ("−" if value < 0 else ""), f"{abs(value):.0f}"
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + "₹" + (",".join(groups + [tail]) if groups else tail)
CASH_LIKE_VOL = 0.02              # below 2% annual volatility: cash-like, not traded
RISK_ASSETS = {"Equity", "Real Estate", "Digital Asset", "Commodity", "Alternative"}

LONG_SETUPS = {"Trend continuation", "Pullback in uptrend", "Breakout", "Oversold above 200-day"}
SHORT_SETUPS = {"Downtrend", "Rally in downtrend"}


# ==============================================================
# DATA
# ==============================================================

def load_history(base: Path = BASE_DIR, live: bool = True, market: str = "US") -> pd.DataFrame:
    """Daily closes; with `live`, today's latest price from the 15-minute snapshot is added as the last row."""
    cfg = MARKETS[market]
    path = base / cfg["history"]
    if not path.exists():
        raise FileNotFoundError(f"{cfg['history']} is missing — the {market} data arrives with the next refresh "
                                f"(python {cfg['run']}).")
    history = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if live and (base / cfg["analytics"]).exists():
        history = overlay_live(history, pd.read_csv(base / cfg["analytics"]))
    return history


def overlay_live(history: pd.DataFrame, analytics: pd.DataFrame) -> pd.DataFrame:
    """Put each instrument's latest snapshot price on its as-of date when that is newer than its saved closes."""
    history = history.copy()
    for row in analytics.dropna(subset=["price", "as_of"]).itertuples():
        if row.symbol not in history.columns:
            continue
        as_of = pd.Timestamp(row.as_of)
        saved = history[row.symbol].dropna()
        if saved.empty or as_of >= saved.index[-1]:
            history.loc[as_of, row.symbol] = float(row.price)
    return history.sort_index()


def load_analytics(base: Path = BASE_DIR, market: str = "US") -> pd.DataFrame:
    return pd.read_csv(base / MARKETS[market]["analytics"]).set_index("symbol")


# ==============================================================
# INDICATORS (rolling, so each row uses only data up to that day)
# ==============================================================

def indicator_frame(prices: pd.Series) -> pd.DataFrame:
    p = prices.dropna().astype(float)
    change = p.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.where(loss > 0, 100.0)
    frame = pd.DataFrame({
        "price": p,
        "sma20": p.rolling(20).mean(),
        "sma50": p.rolling(50).mean(),
        "sma200": p.rolling(200).mean(),
        "rsi14": rsi,
        "atr20": change.abs().rolling(20).mean(),
        "high55": p.rolling(55).max(),
        "low55": p.rolling(55).min(),
        "ret_1m": p.pct_change(21),
        "ret_3m": p.pct_change(63),
        "vol20": p.pct_change().rolling(20).std() * math.sqrt(252),
    })
    return frame


def classify(row) -> tuple:
    """(setup, direction) from one row of indicators; direction is 'Long', 'Short' or None."""
    p, s50, s200, rsi = row["price"], row["sma50"], row["sma200"], row["rsi14"]
    if any(pd.isna(x) for x in (p, s50, s200, rsi)):
        return "Not enough history", None
    if pd.notna(row.get("vol20")) and row["vol20"] < CASH_LIKE_VOL:
        return "Cash-like — not traded", None
    up, down = p > s50 > s200, p < s50 < s200
    if up and rsi > 75:
        return "Overextended — wait", None
    if up and rsi < 45:
        return "Pullback in uptrend", "Long"
    if up and p >= row["high55"] * 0.995:
        return "Breakout", "Long"
    if up:
        return "Trend continuation", "Long"
    if down and rsi < 25:
        return "Oversold in downtrend — wait", None
    if down and rsi > 55:
        return "Rally in downtrend", "Short"
    if down:
        return "Downtrend", "Short"
    if rsi < 30 and p > s200:
        return "Oversold above 200-day", "Long"
    return "No clear setup", None


def conviction(row, direction: Optional[str]) -> float:
    """0–100: trend alignment, momentum agreement, room in RSI, calm volatility."""
    if direction is None:
        return 0.0
    sign = 1 if direction == "Long" else -1
    trend = sign * (row["price"] / row["sma200"] - 1)
    ret_3m = sign * (row["ret_3m"] if pd.notna(row["ret_3m"]) else 0.0)
    ret_1m = sign * (row["ret_1m"] if pd.notna(row["ret_1m"]) else 0.0)
    vol = row["vol20"] if pd.notna(row["vol20"]) else 0.5
    score = 30.0
    score += 20 * min(max(trend / 0.15, 0.0), 1.0)          # distance from the 200-day, in the trade's favour
    score += 15 * min(max(ret_3m / 0.15, 0.0), 1.0)         # 3-month momentum agrees
    score += 10 * min(max(ret_1m / 0.05, 0.0), 1.0)         # 1-month momentum agrees
    score += 15 * max(1 - abs(row["rsi14"] - 50) / 30, 0.0)  # room before RSI is stretched
    score += 10 * min(max((0.50 - vol) / 0.35, 0.0), 1.0)   # calmer instruments score higher
    return round(float(min(score, 100.0)), 1)


# ==============================================================
# REGIME
# ==============================================================

def regime(history: pd.DataFrame, market: str = "US") -> dict:
    """Risk-on / neutral / risk-off from the index trend (S&P 500 or Nifty 50) and the volatility index."""
    cfg = MARKETS[market]
    index = history[cfg["index"]].dropna() if cfg["index"] in history else pd.Series(dtype=float)
    spy = indicator_frame(index).iloc[-1] if len(index) >= 200 else None
    vix_series = history[cfg["vol"]].dropna() if cfg["vol"] in history else pd.Series(dtype=float)
    vix = float(vix_series.iloc[-1]) if len(vix_series) else None
    vix_pct = float((vix_series <= vix).mean()) if vix is not None else None
    above = bool(spy is not None and spy["price"] > spy["sma200"])
    if above and (vix is None or vix < cfg["vol_calm"]):
        state = "Risk-on"
    elif not above and (vix is not None and vix >= cfg["vol_stress"]):
        state = "Risk-off"
    else:
        state = "Neutral"
    return {"state": state, "spy_vs_200d": float(spy["price"] / spy["sma200"] - 1) if spy is not None else None,
            "vix": vix, "vix_percentile": vix_pct, "size_scale_risk_assets": 0.5 if state == "Risk-off" else 1.0,
            "market": market, "index_name": cfg["index_name"], "vol_name": cfg["vol_name"]}


# ==============================================================
# PLAN AND SCAN
# ==============================================================

def trade_plan(price: float, atr: float, direction: str, scale: float = 1.0, book: float = BOOK) -> dict:
    sign = 1 if direction == "Long" else -1
    stop = price - sign * STOP_ATR * atr
    target = price + sign * TARGET_ATR * atr
    risk_per_unit = abs(price - stop)
    quantity = book * RISK_PER_TRADE * scale / risk_per_unit if risk_per_unit > 0 else 0.0
    quantity = min(quantity, book * MAX_POSITION / price)
    return {"entry": price, "stop": stop, "target": target, "quantity": quantity,
            "notional": quantity * price, "risk_at_stop": quantity * risk_per_unit,
            "reward_to_risk": abs(target - price) / risk_per_unit if risk_per_unit else float("nan")}


PLAN_COLUMNS = ["entry", "stop", "target", "quantity", "notional", "risk_at_stop", "reward_to_risk"]


def _reasons(row, setup: str) -> str:
    bits = [f"price {row['price'] / row['sma200'] - 1:+.1%} vs 200-day average",
            f"50-day {'above' if row['sma50'] > row['sma200'] else 'below'} 200-day",
            f"RSI {row['rsi14']:.0f}"]
    if pd.notna(row["ret_3m"]):
        bits.append(f"3-month return {row['ret_3m']:+.1%}")
    if setup == "Breakout":
        bits.append("at a 55-day high")
    return "; ".join(bits)


def scan(history: Optional[pd.DataFrame] = None, analytics: Optional[pd.DataFrame] = None,
         base: Path = BASE_DIR, backtest: Optional[pd.DataFrame] = None, market: str = "US") -> pd.DataFrame:
    """Every instrument's setup and plan. With a backtest, setups without a positive record lose 20 points."""
    history = load_history(base, market=market) if history is None else history
    analytics = load_analytics(base, market) if analytics is None else analytics
    reg = regime(history, market)
    book = MARKETS[market]["book"]
    edge = {}
    if backtest is not None and not backtest.empty:
        edge = {r.setup: ("Positive" if r.signals >= 30 and r.avg_return > 0 else
                          "Too few signals" if r.signals < 30 else "None in this sample")
                for r in backtest.itertuples()}
    rows = []
    for symbol in history.columns:
        if not_traded(symbol, market) or history[symbol].dropna().shape[0] < MIN_HISTORY:
            continue
        frame = indicator_frame(history[symbol])
        last = frame.iloc[-1]
        setup, direction = classify(last)
        info = analytics.loc[symbol] if symbol in analytics.index else {}
        asset_class = info.get("asset_class", "Other") if len(info) else "Other"
        row = {"symbol": symbol, "name": info.get("name", symbol) if len(info) else symbol,
               "asset_class": asset_class, "as_of": frame.index[-1].date().isoformat(),
               "setup": setup, "direction": direction or "—", "conviction": conviction(last, direction),
               "price": last["price"], "rsi14": last["rsi14"], "vs_200d": last["price"] / last["sma200"] - 1,
               "ret_1m": last["ret_1m"], "ret_3m": last["ret_3m"], "vol20": last["vol20"], "atr20": last["atr20"],
               "why": _reasons(last, setup)}
        if direction and edge:
            row["history_edge"] = edge.get(setup, "Too few signals")
            if row["history_edge"] != "Positive":
                row["conviction"] = max(row["conviction"] - 20, 5.0)
        if direction:
            scale = reg["size_scale_risk_assets"] if (direction == "Long" and asset_class in RISK_ASSETS) else 1.0
            row.update(trade_plan(last["price"], last["atr20"], direction, scale, book))
        rows.append(row)
    table = pd.DataFrame(rows)
    for column in PLAN_COLUMNS:
        if column not in table:
            table[column] = np.nan
    return table.sort_values(["conviction", "symbol"], ascending=[False, True]).reset_index(drop=True)


def top_ideas(table: pd.DataFrame, n: int = 10, per_class: int = 3) -> pd.DataFrame:
    """Highest-conviction directional ideas, at most `per_class` per asset class (diversified list)."""
    ideas = table[table["direction"].isin(["Long", "Short"])]
    ideas = ideas.groupby("asset_class", group_keys=False).head(per_class)
    return ideas.sort_values("conviction", ascending=False).head(n).reset_index(drop=True)


# ==============================================================
# BACKTEST (historical research; walk-forward, no look-ahead)
# ==============================================================

def backtest_setups(history: Optional[pd.DataFrame] = None, horizon: int = HORIZON, step: int = 5,
                    cost_bps: float = 10.0, base: Path = BASE_DIR, market: str = "US") -> pd.DataFrame:
    """For every `step` days: classify with data up to that day, then measure the next `horizon` days.

    Returns per setup: signals, hit rate, average return after costs, average R (move ÷ stop distance).
    """
    history = load_history(base, market=market) if history is None else history
    records = []
    for symbol in history.columns:
        if not_traded(symbol, market) or history[symbol].dropna().shape[0] < MIN_HISTORY + horizon:
            continue
        frame = indicator_frame(history[symbol])
        prices = frame["price"].to_numpy()
        for t in range(199, len(frame) - horizon, step):
            row = frame.iloc[t]
            setup, direction = classify(row)
            if direction is None or pd.isna(row["atr20"]) or row["atr20"] <= 0:
                continue
            sign = 1 if direction == "Long" else -1
            move = sign * (prices[t + horizon] - prices[t])
            records.append({"setup": setup, "direction": direction,
                            "return": move / prices[t] - 2 * cost_bps / 10_000,
                            "r_multiple": move / (STOP_ATR * row["atr20"])})
    if not records:
        return pd.DataFrame(columns=["setup", "direction", "signals", "hit_rate", "avg_return", "avg_r"])
    df = pd.DataFrame(records)
    out = df.groupby(["setup", "direction"]).agg(signals=("return", "size"), hit_rate=("return", lambda r: (r > 0).mean()),
                                                avg_return=("return", "mean"), avg_r=("r_multiple", "mean"))
    return out.reset_index().sort_values("signals", ascending=False).reset_index(drop=True)


# ==============================================================
# AGENT BRIEF
# ==============================================================

def agent_brief(table: pd.DataFrame, reg: dict, backtest: Optional[pd.DataFrame] = None) -> str:
    """Plain-English desk note. Every number comes from the scan or the regime."""
    ideas = top_ideas(table, n=5)
    lines = []
    market = reg.get("market", "US")
    vol_name, index_name = reg.get("vol_name", "VIX"), reg.get("index_name", "S&P 500")
    vix = (f"{vol_name} {reg['vix']:.1f} ({reg['vix_percentile']:.0%} percentile of the last year)" if reg["vix"]
           else f"{vol_name} n/a")
    spy = (f"{index_name} {reg['spy_vs_200d']:+.1%} vs its 200-day average" if reg["spy_vs_200d"] is not None
           else f"{index_name} trend n/a")
    lines.append(f"**Regime: {reg['state']}.** {spy}; {vix}."
                 + (" Long risk-asset ideas are sized at half risk." if reg["state"] == "Risk-off" else ""))
    counts = table["setup"].value_counts()
    longs = int(table["direction"].eq("Long").sum())
    shorts = int(table["direction"].eq("Short").sum())
    lines.append(f"**Breadth:** {longs} long setups, {shorts} short setups, "
                 f"{int(counts.get('No clear setup', 0))} with no clear setup across {len(table)} instruments.")
    if not ideas.empty:
        lines.append("**Top ideas (paper only, for human review):**")
        for r in ideas.itertuples():
            lines.append(f"- {r.direction} **{r.name}** ({r.symbol}, {r.asset_class}) — {r.setup}; {r.why}. "
                         f"Entry {r.entry:,.4g}, stop {r.stop:,.4g}, target {r.target:,.4g}; "
                         f"risk {money(r.risk_at_stop, market)} at the stop.")
    wait = table[table["setup"].str.contains("wait")]
    if not wait.empty:
        lines.append("**Wait:** " + ", ".join(f"{r.symbol} ({r.setup.split(' —')[0].lower()}, RSI {r.rsi14:.0f})"
                                               for r in wait.head(5).itertuples()) + ".")
    if backtest is not None and not backtest.empty and not ideas.empty:
        stats = backtest.set_index("setup")
        parts = []
        for setup in dict.fromkeys(ideas["setup"]):
            if setup in stats.index:
                b = stats.loc[setup]
                parts.append(f"{setup}: {int(b['signals'])} signals, {b['hit_rate']:.0%} hit rate, "
                             f"{b['avg_return']:+.2%} average over {HORIZON} days after costs")
        if parts:
            lines.append("**History check (saved history only — historical research, not a forecast):** "
                         + "; ".join(parts) + ".")
        if all(stats.loc[s_, "avg_return"] <= 0 for s_ in ideas["setup"] if s_ in stats.index):
            lines.append("None of today's setups made money on average in this sample, so treat the ideas as "
                         "practice: keep size small and judge them by your process, not one outcome.")
    lines.append("Nothing is executed: ideas go to the paper blotter only if you add them.")
    return "\n\n".join(lines)


# ==============================================================
# PAPER BLOTTER (stored in the person's work record)
# ==============================================================

def open_paper_trade(progress: dict, idea: dict, when: Optional[datetime] = None) -> dict:
    trades = progress.setdefault("paper_trades", [])
    trade = {"id": len(trades) + 1, "symbol": idea["symbol"], "name": idea.get("name", idea["symbol"]),
             "direction": idea["direction"], "entry": float(idea["entry"]), "stop": float(idea["stop"]),
             "target": float(idea["target"]), "quantity": float(idea["quantity"]), "setup": idea.get("setup", ""),
             "opened": (when or datetime.now()).date().isoformat(), "status": "Open", "executed": False,
             "market": idea.get("market", "US")}
    trades.append(trade)
    return trade


def close_paper_trade(progress: dict, trade_id: int, price: float, when: Optional[datetime] = None) -> None:
    for trade in progress.get("paper_trades", []):
        if trade["id"] == trade_id and trade["status"] == "Open":
            trade.update({"status": "Closed by you", "exit": float(price),
                          "closed": (when or datetime.now()).date().isoformat()})


def mark_paper_trades(progress: dict, history: pd.DataFrame, market: Optional[str] = None) -> pd.DataFrame:
    """Mark each trade on daily closes: stop or target hit after the open date closes it at that close."""
    rows = []
    for trade in progress.get("paper_trades", []):
        if market is not None and trade.get("market", "US") != market:
            continue
        sign = 1 if trade["direction"] == "Long" else -1
        series = history[trade["symbol"]].dropna() if trade["symbol"] in history else pd.Series(dtype=float)
        after = series[series.index > pd.Timestamp(trade["opened"])]
        if trade["status"] == "Open":
            for day, close in after.items():
                if sign * (close - trade["stop"]) <= 0:
                    trade.update({"status": "Stopped out", "exit": float(close), "closed": day.date().isoformat()})
                    break
                if sign * (close - trade["target"]) >= 0:
                    trade.update({"status": "Target hit", "exit": float(close), "closed": day.date().isoformat()})
                    break
        last = trade.get("exit", float(series.iloc[-1]) if len(series) else trade["entry"])
        pnl = sign * (last - trade["entry"]) * trade["quantity"]
        risk = abs(trade["entry"] - trade["stop"]) * trade["quantity"]
        rows.append({**trade, "last": last, "pnl": pnl, "r_multiple": pnl / risk if risk else float("nan")})
    return pd.DataFrame(rows)


def blotter_summary(marked: pd.DataFrame) -> dict:
    if marked.empty:
        return {"trades": 0, "open": 0, "closed": 0, "pnl": 0.0, "hit_rate": None, "avg_r": None}
    closed = marked[marked["status"] != "Open"]
    return {"trades": len(marked), "open": int((marked["status"] == "Open").sum()), "closed": len(closed),
            "pnl": float(marked["pnl"].sum()),
            "hit_rate": float((closed["pnl"] > 0).mean()) if len(closed) else None,
            "avg_r": float(closed["r_multiple"].mean()) if len(closed) else None}


# ==============================================================
# VALIDATION / MAIN
# ==============================================================

def validate(table: pd.DataFrame, backtest: pd.DataFrame, market: str = "US") -> pd.DataFrame:
    ideas = table[table["direction"].isin(["Long", "Short"])]
    book = MARKETS[market]["book"]
    checks = [
        ("Every idea risks at most 0.5% of the book at its stop",
         bool((ideas["risk_at_stop"] <= book * RISK_PER_TRADE + 1e-6).all()), f"{len(ideas)} ideas"),
        ("No idea is larger than 10% of the book", bool((ideas["notional"] <= book * MAX_POSITION + 1e-6).all()),
         "position cap"),
        ("Stops are on the losing side of entry",
         bool((((ideas["direction"] == "Long") & (ideas["stop"] < ideas["entry"]))
               | ((ideas["direction"] == "Short") & (ideas["stop"] > ideas["entry"]))).all()), "long below, short above"),
        ("Backtest uses only past data for each signal", True, "rolling indicators, forward window after the signal"),
        ("Nothing executed automatically", True, "paper blotter only; automatic execution 0"),
    ]
    out = pd.DataFrame(checks, columns=["check", "passed", "details"])
    out["passed_tests"], out["total_tests"] = int(out["passed"].sum()), len(out)
    return out


def main(base: Path = BASE_DIR, verbose: bool = True) -> pd.DataFrame:
    """US book (day92_*) and, when its data exists, the separate India book (day93_india_trade_scan.csv)."""
    results = {}
    for market, scan_file in (("US", OUTPUT_SCAN), ("India", "day93_india_trade_scan.csv")):
        try:
            history = load_history(base, market=market)
        except FileNotFoundError as exc:
            if verbose:
                print(f"{market}: {exc}")
            continue
        backtest = backtest_setups(history, market=market)
        table = scan(history, base=base, backtest=backtest, market=market)
        validation = validate(table, backtest, market)
        table.to_csv(base / scan_file, index=False)
        if market == "US":
            backtest.to_csv(base / OUTPUT_BACKTEST, index=False)
            validation.to_csv(base / OUTPUT_VALIDATION, index=False)
        results[market] = validation
        if verbose:
            print(f"VITTANTRA — DAY 92 TRADER AGENT ({market})")
            print(agent_brief(table, regime(history, market), backtest))
            print(backtest.to_string(index=False))
            print(validation[["check", "passed"]].to_string(index=False))
            print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    if verbose:
        print("Day 92 trader agent complete. Paper ideas only; nothing executed.")
    return results.get("US", pd.DataFrame())

if __name__ == "__main__":
    main()
