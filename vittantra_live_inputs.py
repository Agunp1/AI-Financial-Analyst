"""
Day 75 — Live Market Inputs

Small, dependency-light reader for the files written by
vittantra_data_hub.py. The multi-asset risk chain (Days 59-70)
uses it to replace illustrative sample prices with real market
data when that data is available.

Data modes
----------
LIVE    day75_live_instrument_prices.csv exists and
        VITTANTRA_DATA_MODE is not "sample".
SAMPLE  Original illustrative prices and synthetic history.

Set VITTANTRA_DATA_MODE=sample to force the original behaviour.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

LIVE_PRICES_FILE = BASE_DIR / "day75_live_instrument_prices.csv"
PRICE_HISTORY_FILE = BASE_DIR / "day75_instrument_price_history.csv"
MACRO_SNAPSHOT_FILE = BASE_DIR / "day75_macro_snapshot.csv"

USABLE_STATUSES = {"FRESH", "STALE"}
BENCHMARK_COLUMN = "VITTANTRA_BENCHMARK"


def live_mode_enabled(
    prices_file: Path = LIVE_PRICES_FILE,
) -> bool:
    requested = os.getenv("VITTANTRA_DATA_MODE", "live").strip().lower()
    return requested != "sample" and Path(prices_file).exists()


def data_mode_label(
    prices_file: Path = LIVE_PRICES_FILE,
) -> str:
    return "LIVE" if live_mode_enabled(prices_file) else "SAMPLE"


def load_live_prices(
    prices_file: Path = LIVE_PRICES_FILE,
) -> Dict[str, dict]:
    """Return {symbol: row} for instruments with a usable live price."""
    if not live_mode_enabled(prices_file):
        return {}
    df = pd.read_csv(prices_file)
    usable = df[
        df["status"].isin(USABLE_STATUSES)
        & pd.to_numeric(df["price"], errors="coerce").gt(0)
    ]
    return {
        str(row["symbol"]): row.to_dict()
        for _, row in usable.iterrows()
    }


def load_live_macro(
    macro_file: Path = MACRO_SNAPSHOT_FILE,
    prices_file: Path = LIVE_PRICES_FILE,
) -> Dict[str, float]:
    """Return {FRED series id: latest value} when live mode is on."""
    if not live_mode_enabled(prices_file) or not Path(macro_file).exists():
        return {}
    df = pd.read_csv(macro_file)
    values = pd.to_numeric(df["latest_value"], errors="coerce")
    return {
        str(series): float(value)
        for series, value in zip(df["series_id"], values)
        if value is not None and math.isfinite(value)
    }


def live_valuation_date(
    prices_file: Path = LIVE_PRICES_FILE,
) -> Optional[pd.Timestamp]:
    """Most recent as-of date among usable live prices."""
    prices = load_live_prices(prices_file)
    dates = pd.to_datetime(
        [row.get("as_of_date") for row in prices.values()],
        errors="coerce",
    )
    dates = dates.dropna()
    return dates.max().normalize() if len(dates) else None


def load_price_history(
    symbols: Iterable[str],
    min_observations: int = 250,
    history_file: Path = PRICE_HISTORY_FILE,
    prices_file: Path = LIVE_PRICES_FILE,
) -> Optional[pd.DataFrame]:
    """
    Real aligned price history for the given symbols plus the
    benchmark column, or None when it is unavailable or incomplete
    (callers then fall back to synthetic validation history).
    """
    if not live_mode_enabled(prices_file) or not Path(history_file).exists():
        return None
    history = pd.read_csv(history_file, parse_dates=["date"]).set_index("date")
    required = list(dict.fromkeys(list(symbols) + [BENCHMARK_COLUMN]))
    if any(symbol not in history.columns for symbol in required):
        return None
    history = history[required].apply(pd.to_numeric, errors="coerce").dropna()
    if len(history) < min_observations or (history <= 0).any().any():
        return None
    return history


def apply_live_prices(instruments: list, prices_file: Path = LIVE_PRICES_FILE) -> list:
    """
    Overwrite instrument prices with usable live prices in place.
    Instruments without a usable live price keep their sample price
    and are labelled as such.
    """
    prices = load_live_prices(prices_file)
    if not prices:
        return instruments
    for instrument in instruments:
        if instrument.metadata is None:
            instrument.metadata = {}
        row = prices.get(instrument.symbol)
        if row is None:
            instrument.metadata["price_source"] = "SAMPLE (no live price)"
            continue
        instrument.price = float(row["price"])
        instrument.market_value = None
        ytm = pd.to_numeric(row.get("model_yield"), errors="coerce")
        if pd.notna(ytm) and ytm > 0:
            instrument.yield_to_maturity = float(ytm)
        instrument.metadata["price_source"] = f'{row["method"]}: {row["source"]}'
        instrument.metadata["price_as_of"] = str(row["as_of_date"])
        instrument.metadata["price_status"] = str(row["status"])
    return instruments
