"""
Day 75 — Vittantra Data Hub

Collects real market and economic data from FREE sources, stores it in
a local SQLite database and publishes the CSV snapshots the rest of
Vittantra reads.

Free sources (no paid subscription required)
--------------------------------------------
- Yahoo Finance via yfinance: stocks, ETFs, futures, FX, crypto.
  Daily history plus intraday quotes (usually delayed ~15 minutes).
- FRED public CSV download: Treasury yields, BBB credit spreads, VIX,
  CPI, unemployment, Fed funds, real GDP. No API key needed.

What it produces
----------------
vittantra_market.db                  local store (git-ignored)
day75_market_snapshot.csv            latest price for every ticker
day75_macro_snapshot.csv             latest value for every macro series
day75_live_instrument_prices.csv     live prices for the risk portfolio
day75_instrument_price_history.csv   aligned real history for risk models
day75_risk_free_rate_history.csv     3-month T-bill yield history (Sharpe ratios)
day75_refresh_log.csv                audit trail of every refresh job
day75_validation_summary.csv         data-quality checks

Usage
-----
python vittantra_data_hub.py                 # one refresh
python vittantra_data_hub.py --loop 15       # refresh every 15 minutes

Research infrastructure only. No trades are submitted or executed.
"""

from __future__ import annotations

import argparse
import io
import math
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from vittantra_pricing import black_scholes_price, bond_price


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "vittantra_market.db"

HISTORY_START = "2022-01-01"
HISTORY_OBSERVATIONS = 320
FRESH_CALENDAR_DAYS = 4          # covers weekends and a market holiday
MACRO_REFRESH_HOURS = 6
HISTORY_REFRESH_HOURS = 6
BENCHMARK_COLUMN = "VITTANTRA_BENCHMARK"
BENCHMARK_TICKER = "SPY"

OUTPUT_MARKET_SNAPSHOT = "day75_market_snapshot.csv"
OUTPUT_MACRO_SNAPSHOT = "day75_macro_snapshot.csv"
OUTPUT_LIVE_PRICES = "day75_live_instrument_prices.csv"
OUTPUT_PRICE_HISTORY = "day75_instrument_price_history.csv"
OUTPUT_REFRESH_LOG = "day75_refresh_log.csv"
OUTPUT_VALIDATION = "day75_validation_summary.csv"
OUTPUT_RISK_FREE_HISTORY = "day75_risk_free_rate_history.csv"


# ==============================================================
# INSTRUMENT DATA MAP
# ==============================================================

@dataclass(frozen=True)
class InstrumentSource:
    symbol: str
    ticker: Optional[str]
    method: str        # DIRECT, PROXY, MODEL, CONSTANT
    note: str


INSTRUMENT_SOURCES: Dict[str, InstrumentSource] = {
    "AAPL": InstrumentSource("AAPL", "AAPL", "DIRECT", "Apple common stock"),
    "SPY": InstrumentSource("SPY", "SPY", "DIRECT", "SPDR S&P 500 ETF"),
    "ES": InstrumentSource("ES", "ES=F", "DIRECT", "E-mini S&P 500 front-month future"),
    "EURUSD": InstrumentSource("EURUSD", "EURUSD=X", "DIRECT", "EUR/USD spot rate"),
    "GOLD": InstrumentSource("GOLD", "GC=F", "DIRECT", "COMEX gold front-month future (USD/oz)"),
    "BTC": InstrumentSource("BTC", "BTC-USD", "DIRECT", "Bitcoin in USD"),
    "REIT": InstrumentSource("REIT", "VNQ", "PROXY", "Vanguard Real Estate ETF as REIT proxy"),
    "CORP_BOND": InstrumentSource(
        "CORP_BOND", "LQD", "MODEL",
        "Priced from 5Y Treasury + BBB spread (FRED); history from LQD returns",
    ),
    "AAPL_CALL": InstrumentSource(
        "AAPL_CALL", "AAPL", "MODEL",
        "Black-Scholes on live AAPL; implied volatility is an assumption",
    ),
    "USD": InstrumentSource("USD", None, "CONSTANT", "US dollar cash"),
}

# Assumption used for the option model. Free sources do not provide a
# reliable implied volatility, so it is stated explicitly here.
OPTION_IMPLIED_VOLATILITY = 0.28

MACRO_SERIES: Dict[str, str] = {
    "DGS3MO": "3-Month Treasury yield (%)",
    "DGS2": "2-Year Treasury yield (%)",
    "DGS5": "5-Year Treasury yield (%)",
    "DGS10": "10-Year Treasury yield (%)",
    "BAMLC0A4CBBB": "ICE BofA BBB corporate option-adjusted spread (%)",
    "VIXCLS": "CBOE VIX volatility index",
    "CPIAUCSL": "Consumer Price Index (index level)",
    "UNRATE": "Unemployment rate (%)",
    "FEDFUNDS": "Effective Fed funds rate (%)",
    "GDPC1": "Real GDP (billions, chained dollars)",
}


def research_universe_tickers() -> List[str]:
    """The 33-equity research universe from Day 53, if importable."""
    try:
        from market_universe_ingestion import UNIVERSE
        return list(UNIVERSE)
    except Exception:
        return []


def all_market_tickers() -> List[str]:
    tickers = [s.ticker for s in INSTRUMENT_SOURCES.values() if s.ticker]
    tickers += research_universe_tickers()
    return list(dict.fromkeys(tickers))


# ==============================================================
# FREE DATA FETCHERS (replaceable in tests)
# ==============================================================

def _yf_frame_to_long(raw: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    frames = []
    if isinstance(raw.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            part = raw[ticker].copy()
            part["ticker"] = ticker
            frames.append(part)
    else:
        part = raw.copy()
        part["ticker"] = tickers[0]
        frames.append(part)
    df = pd.concat(frames).reset_index()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"datetime": "date", "index": "date"})
    return df


def fetch_price_history_yfinance(tickers: List[str], start: str) -> pd.DataFrame:
    """Daily OHLCV history: columns ticker, date, open, high, low, close, adj_close, volume."""
    import yfinance as yf

    raw = yf.download(
        tickers, start=start, auto_adjust=False, group_by="ticker",
        progress=False, threads=True,
    )
    df = _yf_frame_to_long(raw, tickers)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    return df[["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]]


def fetch_latest_quotes_yfinance(tickers: List[str]) -> pd.DataFrame:
    """Latest intraday price: columns ticker, price, quote_time_utc."""
    import yfinance as yf

    raw = yf.download(
        tickers, period="5d", interval="5m", auto_adjust=False,
        group_by="ticker", progress=False, threads=True, prepost=False,
    )
    df = _yf_frame_to_long(raw, tickers)
    if df.empty:
        return pd.DataFrame(columns=["ticker", "price", "quote_time_utc"])
    df = df.dropna(subset=["close"])
    time_col = pd.to_datetime(df["date"], utc=True)
    df = df.assign(quote_time_utc=time_col).sort_values("quote_time_utc")
    latest = df.groupby("ticker").tail(1)
    return pd.DataFrame({
        "ticker": latest["ticker"],
        "price": latest["close"].astype(float),
        "quote_time_utc": latest["quote_time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })


def fetch_fred_series(series_id: str) -> pd.DataFrame:
    """FRED public CSV (no API key): columns date, value."""
    import requests

    response = requests.get(
        "https://fred.stlouisfed.org/graph/fredgraph.csv",
        params={"id": series_id}, timeout=30,
    )
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text))
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "date", series_id: "value"})
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"])[["date", "value"]]


@dataclass
class DataFetchers:
    price_history: Callable[[List[str], str], pd.DataFrame] = fetch_price_history_yfinance
    latest_quotes: Callable[[List[str]], pd.DataFrame] = fetch_latest_quotes_yfinance
    fred_series: Callable[[str], pd.DataFrame] = fetch_fred_series


# ==============================================================
# DATABASE
# ==============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    ticker TEXT NOT NULL, date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
    source TEXT, fetched_at_utc TEXT,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS latest_quotes (
    ticker TEXT PRIMARY KEY, price REAL, quote_time_utc TEXT,
    source TEXT, fetched_at_utc TEXT
);
CREATE TABLE IF NOT EXISTS macro_observations (
    series_id TEXT NOT NULL, date TEXT NOT NULL, value REAL,
    source TEXT, fetched_at_utc TEXT,
    PRIMARY KEY (series_id, date)
);
CREATE TABLE IF NOT EXISTS refresh_log (
    run_id TEXT, job TEXT, started_at_utc TEXT, finished_at_utc TEXT,
    status TEXT, rows INTEGER, detail TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def log_job(conn, run_id, job, started, status, rows, detail=""):
    conn.execute(
        "INSERT INTO refresh_log VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, job, started, utc_now(), status, int(rows), str(detail)[:500]),
    )
    conn.commit()


def last_successful_job(conn, job: str) -> Optional[pd.Timestamp]:
    row = conn.execute(
        "SELECT MAX(finished_at_utc) FROM refresh_log WHERE job = ? AND status = 'OK'",
        (job,),
    ).fetchone()
    return pd.Timestamp(row[0]) if row and row[0] else None


def hours_since(timestamp: Optional[pd.Timestamp]) -> float:
    if timestamp is None:
        return math.inf
    return (pd.Timestamp.now(tz="UTC") - timestamp).total_seconds() / 3600


# ==============================================================
# REFRESH JOBS
# ==============================================================

def refresh_price_history(conn, run_id, fetchers, tickers) -> int:
    started = utc_now()
    try:
        last = conn.execute("SELECT MAX(date) FROM price_history").fetchone()[0]
        start = HISTORY_START
        if last:
            # Re-download a short overlap so revised closes are corrected.
            start = (pd.Timestamp(last) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        df = fetchers.price_history(tickers, start)
        df = df.dropna(subset=["close"])
        df = df[df["close"] > 0]
        fetched = utc_now()
        rows = [
            (r.ticker, pd.Timestamp(r.date).strftime("%Y-%m-%d"), r.open, r.high, r.low,
             r.close, r.adj_close, r.volume, "yfinance", fetched)
            for r in df.itertuples(index=False)
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)", rows,
        )
        conn.commit()
        missing = sorted(set(tickers) - set(df["ticker"]))
        status = "OK" if rows else "FAILED"
        detail = f"from {start}; missing: {', '.join(missing) or 'none'}"
        log_job(conn, run_id, "price_history", started, status, len(rows), detail)
        return len(rows)
    except Exception as exc:
        log_job(conn, run_id, "price_history", started, "FAILED", 0, repr(exc))
        return 0


def refresh_latest_quotes(conn, run_id, fetchers, tickers) -> int:
    started = utc_now()
    try:
        df = fetchers.latest_quotes(tickers)
        df = df[pd.to_numeric(df["price"], errors="coerce") > 0]
        fetched = utc_now()
        conn.executemany(
            "INSERT OR REPLACE INTO latest_quotes VALUES (?,?,?,?,?)",
            [(r.ticker, float(r.price), r.quote_time_utc, "yfinance intraday (delayed)", fetched)
             for r in df.itertuples(index=False)],
        )
        conn.commit()
        log_job(conn, run_id, "latest_quotes", started, "OK" if len(df) else "FAILED", len(df))
        return len(df)
    except Exception as exc:
        log_job(conn, run_id, "latest_quotes", started, "FAILED", 0, repr(exc))
        return 0


def refresh_macro(conn, run_id, fetchers) -> int:
    started = utc_now()
    total, failed = 0, []
    for series_id in MACRO_SERIES:
        try:
            df = fetchers.fred_series(series_id)
            fetched = utc_now()
            conn.executemany(
                "INSERT OR REPLACE INTO macro_observations VALUES (?,?,?,?,?)",
                [(series_id, pd.Timestamp(r.date).strftime("%Y-%m-%d"), float(r.value),
                  "FRED", fetched) for r in df.itertuples(index=False)],
            )
            total += len(df)
        except Exception as exc:
            failed.append(f"{series_id} ({type(exc).__name__})")
    conn.commit()
    status = "OK" if total and not failed else ("PARTIAL" if total else "FAILED")
    log_job(conn, run_id, "macro", started, status, total,
            f"failed: {', '.join(failed) or 'none'}")
    return total


# ==============================================================
# SNAPSHOT BUILDERS
# ==============================================================

def load_close_matrix(conn) -> pd.DataFrame:
    df = pd.read_sql("SELECT ticker, date, close FROM price_history", conn, parse_dates=["date"])
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="date", columns="ticker", values="close").sort_index()


def load_latest_quotes(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM latest_quotes", conn)


def load_macro_matrix(conn) -> pd.DataFrame:
    df = pd.read_sql("SELECT series_id, date, value FROM macro_observations", conn,
                     parse_dates=["date"])
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="date", columns="series_id", values="value").sort_index()


def freshness_status(as_of: Optional[pd.Timestamp], today: pd.Timestamp) -> str:
    if as_of is None or pd.isna(as_of):
        return "MISSING"
    age = (today.normalize() - pd.Timestamp(as_of).normalize()).days
    return "FRESH" if age <= FRESH_CALENDAR_DAYS else "STALE"


def latest_price(ticker, closes, quotes) -> tuple:
    """(price, as_of timestamp, source) preferring an intraday quote newer than the close."""
    price, as_of, source = None, None, None
    if not closes.empty and ticker in closes.columns:
        series = closes[ticker].dropna()
        if len(series):
            price, as_of, source = float(series.iloc[-1]), series.index[-1], "daily close"
    if not quotes.empty:
        match = quotes[quotes["ticker"] == ticker]
        if len(match):
            q_time = pd.Timestamp(match["quote_time_utc"].iloc[0]).tz_localize(None)
            if as_of is None or q_time.normalize() >= pd.Timestamp(as_of).normalize():
                price, as_of, source = float(match["price"].iloc[0]), q_time, "intraday quote"
    return price, as_of, source


def build_market_snapshot(conn, today) -> pd.DataFrame:
    closes, quotes = load_close_matrix(conn), load_latest_quotes(conn)
    rows = []
    for ticker in all_market_tickers():
        price, as_of, source = latest_price(ticker, closes, quotes)
        prev_close = None
        if not closes.empty and ticker in closes.columns:
            series = closes[ticker].dropna()
            if as_of is not None:
                series = series[series.index < pd.Timestamp(as_of).normalize()]
            prev_close = float(series.iloc[-1]) if len(series) else None
        change = (price / prev_close - 1) if price and prev_close else None
        rows.append({
            "ticker": ticker,
            "price": price,
            "previous_close": prev_close,
            "change_pct": change,
            "as_of": None if as_of is None else pd.Timestamp(as_of).strftime("%Y-%m-%d %H:%M"),
            "price_source": source,
            "status": freshness_status(as_of, today),
            "data_source": "Yahoo Finance (free, may be delayed)",
        })
    return pd.DataFrame(rows)


def build_macro_snapshot(conn, today) -> pd.DataFrame:
    macro = load_macro_matrix(conn)
    rows = []
    for series_id, description in MACRO_SERIES.items():
        series = macro[series_id].dropna() if series_id in macro.columns else pd.Series(dtype=float)
        latest = float(series.iloc[-1]) if len(series) else None
        previous = float(series.iloc[-2]) if len(series) > 1 else None
        rows.append({
            "series_id": series_id,
            "description": description,
            "latest_value": latest,
            "latest_date": series.index[-1].strftime("%Y-%m-%d") if len(series) else None,
            "previous_value": previous,
            "change": (latest - previous) if latest is not None and previous is not None else None,
            "data_source": "FRED (St. Louis Fed, free)",
        })
    return pd.DataFrame(rows)


def build_live_instrument_prices(conn, today, instruments) -> pd.DataFrame:
    """Live price for each risk-portfolio instrument, with its method and freshness."""
    closes, quotes = load_close_matrix(conn), load_latest_quotes(conn)
    macro = build_macro_snapshot(conn, today).set_index("series_id")["latest_value"]
    by_symbol = {i.symbol: i for i in instruments}
    rows = []
    for symbol, source in INSTRUMENT_SOURCES.items():
        instrument = by_symbol.get(symbol)
        price, as_of, origin, model_yield, note = None, None, None, None, source.note
        if source.method == "CONSTANT":
            price, as_of, origin = 1.0, today, "constant"
        elif symbol == "AAPL_CALL" and instrument is not None:
            spot, as_of, origin = latest_price("AAPL", closes, quotes)
            rate = macro.get("DGS3MO")
            if spot and rate is not None and pd.notna(rate):
                years = (pd.Timestamp(instrument.expiration_date) - today.normalize()).days / 365.0
                price = black_scholes_price(spot, instrument.strike, years, rate / 100,
                                            OPTION_IMPLIED_VOLATILITY, instrument.option_type)
                origin = f"Black-Scholes on AAPL {origin}"
        elif symbol == "CORP_BOND" and instrument is not None:
            treasury, spread = macro.get("DGS5"), macro.get("BAMLC0A4CBBB")
            if treasury is not None and spread is not None and pd.notna(treasury) and pd.notna(spread):
                model_yield = (treasury + spread) / 100
                years = (pd.Timestamp(instrument.maturity_date) - today.normalize()).days / 365.25
                price = bond_price(instrument.coupon_rate, model_yield, years)
                as_of = macro_as_of(conn, ["DGS5", "BAMLC0A4CBBB"])
                origin = "5Y Treasury + BBB OAS (FRED)"
        else:
            price, as_of, origin = latest_price(source.ticker, closes, quotes)
        rows.append({
            "symbol": symbol,
            "price": price,
            "sample_price": None if instrument is None else instrument.price,
            "as_of_date": None if as_of is None else pd.Timestamp(as_of).strftime("%Y-%m-%d"),
            "method": source.method,
            "source": origin or "unavailable",
            "proxy_ticker": source.ticker,
            "model_yield": model_yield,
            "status": freshness_status(as_of, today) if price else "MISSING",
            "note": note,
        })
    return pd.DataFrame(rows)


def macro_as_of(conn, series_ids) -> Optional[pd.Timestamp]:
    macro = load_macro_matrix(conn)
    dates = [macro[s].dropna().index[-1] for s in series_ids
             if s in macro.columns and macro[s].notna().any()]
    return min(dates) if dates else None


def build_instrument_price_history(conn, live_prices, instruments,
                                   observations=HISTORY_OBSERVATIONS) -> pd.DataFrame:
    """
    Aligned daily history for every risk-portfolio instrument on the
    benchmark's trading calendar. Each path is rebased so it ends at the
    instrument's live price. Option history is re-priced with
    Black-Scholes along the real AAPL path.
    """
    closes = load_close_matrix(conn)
    if closes.empty or BENCHMARK_TICKER not in closes.columns:
        return pd.DataFrame()
    calendar = closes[BENCHMARK_TICKER].dropna().index
    aligned = closes.reindex(closes.index.union(calendar)).ffill(limit=5).reindex(calendar)
    live = live_prices.set_index("symbol")
    by_symbol = {i.symbol: i for i in instruments}
    rates = load_macro_matrix(conn)
    rate_series = (rates["DGS3MO"].reindex(calendar, method="ffill") / 100
                   if "DGS3MO" in rates.columns else pd.Series(0.04, index=calendar))
    history = pd.DataFrame(index=calendar)
    for symbol, source in INSTRUMENT_SOURCES.items():
        live_price = live["price"].get(symbol)
        if source.method == "CONSTANT":
            history[symbol] = 1.0
        elif symbol == "AAPL_CALL":
            inst = by_symbol.get(symbol)
            if inst is None or "AAPL" not in aligned.columns:
                continue
            spot = aligned["AAPL"]
            years = (pd.Timestamp(inst.expiration_date) - calendar).days / 365.0
            history[symbol] = [
                black_scholes_price(s, inst.strike, t, r if pd.notna(r) else 0.04,
                                    OPTION_IMPLIED_VOLATILITY, inst.option_type)
                if pd.notna(s) else np.nan
                for s, t, r in zip(spot, years, rate_series)
            ]
        elif source.ticker in aligned.columns:
            path = aligned[source.ticker]
            last = path.dropna()
            if len(last) and live_price and pd.notna(live_price):
                path = path / last.iloc[-1] * float(live_price)
            history[symbol] = path
    history[BENCHMARK_COLUMN] = aligned[BENCHMARK_TICKER]
    history = history.dropna().tail(observations)
    history.index.name = "date"
    return history


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day75(market, macro, live_prices, history, today) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    priced = market["price"].notna()
    add("Market prices loaded", priced.any(),
        f"{int(priced.sum())} of {len(market)} tickers priced")
    add("No non-positive prices", (market.loc[priced, "price"] > 0).all(),
        "All loaded prices are positive")
    as_of = pd.to_datetime(market["as_of"], errors="coerce")
    add("No future-dated prices", (as_of.dropna() <= today + pd.Timedelta(days=1)).all(),
        f"Latest as-of: {as_of.max()}")
    fresh_share = (market["status"] == "FRESH").mean() if len(market) else 0.0
    add("Market data freshness", fresh_share >= 0.8,
        f"{fresh_share:.0%} of tickers updated within {FRESH_CALENDAR_DAYS} days")
    missing = live_prices.loc[live_prices["status"] == "MISSING", "symbol"].tolist()
    add("Every risk instrument has a live price", not missing,
        f"Missing: {', '.join(missing) or 'none'}")
    model_rows = live_prices[live_prices["method"] == "MODEL"]
    model_ok = pd.to_numeric(model_rows["price"], errors="coerce").gt(0).all()
    add("Model prices are positive and finite", model_ok,
        "; ".join(f"{r.symbol}={r.price}" for r in model_rows.itertuples()))
    add("Aligned price history long enough for VaR", len(history) >= 250,
        f"{len(history)} aligned observations (need 250)")
    add("Price history has no gaps", not history.isna().any().any() if len(history) else False,
        "No missing values after alignment")
    loaded = macro["latest_value"].notna()
    add("Macro series loaded", loaded.all(),
        f"{int(loaded.sum())} of {len(macro)} FRED series")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_refresh(db_path: Path = DB_PATH, out_dir: Path = BASE_DIR,
                fetchers: Optional[DataFetchers] = None, force: bool = False,
                today: Optional[pd.Timestamp] = None, verbose: bool = True) -> pd.DataFrame:
    """One refresh cycle. Returns the validation summary."""
    from multi_asset_risk import build_sample_instruments

    fetchers = fetchers or DataFetchers()
    today = (today or pd.Timestamp.now()).normalize()
    out_dir = Path(out_dir)
    run_id = uuid.uuid4().hex[:12]
    tickers = all_market_tickers()
    conn = connect(db_path)
    try:
        if force or hours_since(last_successful_job(conn, "price_history")) >= HISTORY_REFRESH_HOURS:
            refresh_price_history(conn, run_id, fetchers, tickers)
        refresh_latest_quotes(conn, run_id, fetchers, tickers)
        if force or hours_since(last_successful_job(conn, "macro")) >= MACRO_REFRESH_HOURS:
            refresh_macro(conn, run_id, fetchers)

        instruments = build_sample_instruments(use_live_data=False)
        market = build_market_snapshot(conn, today)
        macro = build_macro_snapshot(conn, today)
        live_prices = build_live_instrument_prices(conn, today, instruments)
        history = build_instrument_price_history(conn, live_prices, instruments)
        validation = validate_day75(market, macro, live_prices, history, today)

        market.to_csv(out_dir / OUTPUT_MARKET_SNAPSHOT, index=False)
        macro.to_csv(out_dir / OUTPUT_MACRO_SNAPSHOT, index=False)
        if live_prices["price"].notna().any():
            live_prices.to_csv(out_dir / OUTPUT_LIVE_PRICES, index=False)
        if len(history):
            history.to_csv(out_dir / OUTPUT_PRICE_HISTORY)
        rates = load_macro_matrix(conn)
        if "DGS3MO" in rates.columns:
            rates["DGS3MO"].dropna().rename("dgs3mo_percent").to_csv(
                out_dir / OUTPUT_RISK_FREE_HISTORY, index_label="date",
            )
        pd.read_sql("SELECT * FROM refresh_log ORDER BY started_at_utc DESC LIMIT 200",
                    conn).to_csv(out_dir / OUTPUT_REFRESH_LOG, index=False)
        validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    finally:
        conn.close()

    if verbose:
        print_report(run_id, live_prices, macro, validation)
    return validation


def print_report(run_id, live_prices, macro, validation) -> None:
    line = "=" * 78
    print(line)
    print("VITTANTRA — DAY 75 DATA HUB")
    print(line)
    print(f"Run: {run_id}   Sources: Yahoo Finance + FRED (free)\n")
    print("Risk-portfolio instruments")
    cols = ["symbol", "price", "sample_price", "as_of_date", "method", "status"]
    print(live_prices[cols].to_string(index=False))
    print("\nMacro")
    print(macro[["series_id", "latest_value", "latest_date"]].to_string(index=False))
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    passed = int(validation["passed"].sum())
    print(f"\nPassed: {passed}/{len(validation)}")
    print("\nDay 75 data refresh complete. No trades were submitted or executed.")
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vittantra free market-data hub")
    parser.add_argument("--loop", type=float, metavar="MINUTES",
                        help="keep refreshing every N minutes (Ctrl+C to stop)")
    parser.add_argument("--force", action="store_true",
                        help="refresh history and macro even if refreshed recently")
    args = parser.parse_args()

    if not args.loop:
        run_refresh(force=args.force)
        return
    print(f"Refreshing every {args.loop:g} minutes. Press Ctrl+C to stop.")
    try:
        while True:
            run_refresh(force=args.force)
            time.sleep(max(args.loop, 1) * 60)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
