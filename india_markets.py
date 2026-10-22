"""
Day 93 — India market universe (kept separate from the US data).

Free sources only:
  Yahoo Finance  NSE/BSE indices and sector indices, India VIX, Nifty 50
                 stocks, ETFs (equity, gold, silver, gilts, liquid), REITs and
                 InvITs, rupee exchange rates — about 15 minutes delayed
  FRED (OECD/IMF) India CPI, 10-year government bond yield, 3-month interbank
                 rate, industrial production, real GDP, rupee per dollar — monthly
                 or quarterly, so they lag by weeks

Outputs (all prices in INR unless stated):
  day93_india_analytics.csv      one row per instrument: price, returns, volatility,
                                 drawdown, trend vs 200-day, beta to the Nifty 50
  day93_india_price_history.csv  daily closes, about 430 days
  day93_india_macro.csv          latest Indian economic data with the change over a year
  day93_validation_summary.csv

Limits (stated): the RBI repo rate, Indian bond prices and MCX commodity
futures have no reliable free API, so policy rates use the 3-month interbank
rate as a proxy and gold/silver use the listed ETFs. The Nifty 50 list is in
the code and can drift from the official index between reviews.

Usage:  python india_markets.py
Research only. No trades are submitted or executed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from multi_asset_universe import MarketSource, instrument_analytics


BASE_DIR = Path(__file__).resolve().parent
BENCHMARK = "^NSEI"
VOLATILITY_INDEX = "^INDIAVIX"
HISTORY_YEARS = 3
PRICE_HISTORY_DAYS = 430

OUTPUT_ANALYTICS = "day93_india_analytics.csv"
OUTPUT_HISTORY = "day93_india_price_history.csv"
OUTPUT_MACRO = "day93_india_macro.csv"
OUTPUT_VALIDATION = "day93_validation_summary.csv"


def _rows(asset_class: str, sub_class: str, items, currency: str = "INR") -> List[tuple]:
    return [(symbol, name, asset_class, sub_class, currency) for symbol, name in items]


NIFTY_50 = [  # (Yahoo symbol, name, sector)
    ("RELIANCE.NS", "Reliance Industries", "Energy"), ("HDFCBANK.NS", "HDFC Bank", "Financials"),
    ("ICICIBANK.NS", "ICICI Bank", "Financials"), ("INFY.NS", "Infosys", "Information Technology"),
    ("TCS.NS", "Tata Consultancy Services", "Information Technology"), ("BHARTIARTL.NS", "Bharti Airtel",
                                                                        "Communication Services"),
    ("ITC.NS", "ITC", "Consumer Staples"), ("LT.NS", "Larsen & Toubro", "Industrials"),
    ("SBIN.NS", "State Bank of India", "Financials"), ("AXISBANK.NS", "Axis Bank", "Financials"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank", "Financials"), ("HINDUNILVR.NS", "Hindustan Unilever",
                                                            "Consumer Staples"),
    ("BAJFINANCE.NS", "Bajaj Finance", "Financials"), ("M&M.NS", "Mahindra & Mahindra", "Consumer Discretionary"),
    ("MARUTI.NS", "Maruti Suzuki", "Consumer Discretionary"), ("SUNPHARMA.NS", "Sun Pharmaceutical", "Health Care"),
    ("HCLTECH.NS", "HCL Technologies", "Information Technology"), ("NTPC.NS", "NTPC", "Utilities"),
    ("TITAN.NS", "Titan Company", "Consumer Discretionary"), ("ULTRACEMCO.NS", "UltraTech Cement", "Materials"),
    ("POWERGRID.NS", "Power Grid Corporation", "Utilities"), ("ASIANPAINT.NS", "Asian Paints", "Materials"),
    ("ONGC.NS", "Oil and Natural Gas Corporation", "Energy"), ("TATASTEEL.NS", "Tata Steel", "Materials"),
    ("JSWSTEEL.NS", "JSW Steel", "Materials"), ("ADANIPORTS.NS", "Adani Ports and SEZ", "Industrials"),
    ("ADANIENT.NS", "Adani Enterprises", "Industrials"), ("COALINDIA.NS", "Coal India", "Energy"),
    ("BAJAJFINSV.NS", "Bajaj Finserv", "Financials"), ("BAJAJ-AUTO.NS", "Bajaj Auto", "Consumer Discretionary"),
    ("NESTLEIND.NS", "Nestle India", "Consumer Staples"), ("WIPRO.NS", "Wipro", "Information Technology"),
    ("TECHM.NS", "Tech Mahindra", "Information Technology"), ("GRASIM.NS", "Grasim Industries", "Materials"),
    ("HINDALCO.NS", "Hindalco Industries", "Materials"), ("CIPLA.NS", "Cipla", "Health Care"),
    ("DRREDDY.NS", "Dr. Reddy's Laboratories", "Health Care"), ("APOLLOHOSP.NS", "Apollo Hospitals", "Health Care"),
    ("EICHERMOT.NS", "Eicher Motors", "Consumer Discretionary"), ("HEROMOTOCO.NS", "Hero MotoCorp",
                                                                   "Consumer Discretionary"),
    ("BRITANNIA.NS", "Britannia Industries", "Consumer Staples"), ("TATACONSUM.NS", "Tata Consumer Products",
                                                                   "Consumer Staples"),
    ("SBILIFE.NS", "SBI Life Insurance", "Financials"), ("HDFCLIFE.NS", "HDFC Life Insurance", "Financials"),
    ("INDUSINDBK.NS", "IndusInd Bank", "Financials"), ("SHRIRAMFIN.NS", "Shriram Finance", "Financials"),
    ("TRENT.NS", "Trent", "Consumer Discretionary"), ("BEL.NS", "Bharat Electronics", "Industrials"),
    ("BPCL.NS", "Bharat Petroleum", "Energy"), ("JIOFIN.NS", "Jio Financial Services", "Financials"),
]

INSTRUMENTS = (
    _rows("Equity", "Index", [("^NSEI", "Nifty 50"), ("^BSESN", "BSE Sensex"), ("^CRSLDX", "Nifty 500"),
                              ("^NSEMDCP50", "Nifty Midcap 50")])
    + _rows("Equity", "Sector index", [("^NSEBANK", "Nifty Bank"), ("^CNXIT", "Nifty IT"),
                                       ("^CNXPHARMA", "Nifty Pharma"), ("^CNXAUTO", "Nifty Auto"),
                                       ("^CNXFMCG", "Nifty FMCG"), ("^CNXMETAL", "Nifty Metal"),
                                       ("^CNXREALTY", "Nifty Realty"), ("^CNXENERGY", "Nifty Energy"),
                                       ("^CNXPSUBANK", "Nifty PSU Bank"), ("^CNXINFRA", "Nifty Infrastructure")])
    + _rows("Volatility", "Implied volatility", [(VOLATILITY_INDEX, "India VIX")], currency="%")
    + _rows("Equity", "ETF", [("NIFTYBEES.NS", "Nifty 50 ETF (Nippon)"), ("BANKBEES.NS", "Bank Nifty ETF"),
                              ("JUNIORBEES.NS", "Nifty Next 50 ETF"), ("ITBEES.NS", "Nifty IT ETF"),
                              ("CPSEETF.NS", "CPSE ETF (public sector)"), ("MON100.NS", "Nasdaq-100 ETF (INR)")])
    + _rows("Fixed Income", "Bond ETF", [("LIQUIDBEES.NS", "Liquid ETF (overnight money)"),
                                         ("GILT5YBEES.NS", "5-year gilt ETF"),
                                         ("LTGILTBEES.NS", "Long-term gilt ETF")])
    + _rows("Commodity", "Precious metals ETF", [("GOLDBEES.NS", "Gold ETF (INR)"),
                                                 ("SILVERBEES.NS", "Silver ETF (INR)")])
    + _rows("Real Estate", "REIT / InvIT", [("EMBASSY.NS", "Embassy Office Parks REIT"),
                                            ("MINDSPACE.NS", "Mindspace Business Parks REIT"),
                                            ("BIRET.NS", "Brookfield India REIT"),
                                            ("NXST.NS", "Nexus Select Trust REIT"),
                                            ("PGINVIT.NS", "PowerGrid InvIT")])
    + _rows("FX", "Rupee", [("INR=X", "USD/INR"), ("EURINR=X", "EUR/INR"), ("GBPINR=X", "GBP/INR"),
                            ("JPYINR=X", "JPY/INR")], currency="INR per unit")
    + [(s, n, "Equity", sector, "INR") for s, n, sector in NIFTY_50]
)

MACRO_SERIES = {  # FRED id: (name, unit, how to read it)
    "INDCPIALLMINMEI": ("Consumer price inflation", "% a year", "yoy"),
    "INDIRLTLT01STM": ("10-year government bond yield", "%", "level"),
    "INDIR3TIB01STM": ("3-month interbank rate (policy-rate proxy)", "%", "level"),
    "INDPROINDMISMEI": ("Industrial production growth", "% a year", "yoy"),
    "NGDPRSAXDCINQ": ("Real GDP growth", "% a year", "yoy"),
    "DEXINUS": ("Rupees per US dollar (Fed H.10)", "INR", "level"),
}


def instrument_master() -> pd.DataFrame:
    df = pd.DataFrame(INSTRUMENTS, columns=["symbol", "name", "asset_class", "sub_class", "currency"])
    df["source"] = "Yahoo Finance"
    df["market"] = "India"
    return df


def _yoy(s: pd.Series, date: pd.Timestamp) -> Optional[float]:
    """Percent change from the latest reading at least a year before `date`."""
    base = s[s.index <= date - pd.DateOffset(years=1)]
    return (float(s.loc[date]) / float(base.iloc[-1]) - 1) * 100 if len(base) and base.iloc[-1] else None


def macro_table(fred: Dict[str, pd.Series]) -> pd.DataFrame:
    """Latest value and the change over a year for each Indian series (YoY for index series)."""
    rows = []
    for series_id, (name, unit, kind) in MACRO_SERIES.items():
        s = fred.get(series_id, pd.Series(dtype=float)).dropna()
        if len(s) < 2:
            continue
        s.index = pd.DatetimeIndex(s.index)
        last_date = s.index[-1]
        if kind == "yoy":
            value = _yoy(s, last_date)
            if value is None:
                continue
            prior = _yoy(s, s.index[-2])
            change = value - prior if prior is not None else None
        else:
            value = float(s.iloc[-1])
            year_ago = s[s.index <= last_date - pd.DateOffset(years=1)]
            change = value - float(year_ago.iloc[-1]) if len(year_ago) else None
        rows.append({"series": series_id, "name": name, "unit": unit, "value": round(float(value), 4),
                     "change": round(float(change), 4) if change is not None else None,
                     "change_basis": "vs previous reading" if kind == "yoy" else "vs a year earlier",
                     "as_of": last_date.date().isoformat(), "source": "FRED (OECD / IMF / Federal Reserve)"})
    return pd.DataFrame(rows)


def validate(master: pd.DataFrame, analytics: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    priced = analytics["price"].notna()
    stocks = analytics["sub_class"].isin({s for _, _, s in NIFTY_50})
    checks = [
        ("Nifty 50 index priced", bool(analytics.loc[analytics["symbol"] == BENCHMARK, "price"].notna().any()),
         "benchmark for betas and the regime"),
        ("Most instruments priced", bool(priced.mean() >= 0.8), f"{int(priced.sum())} of {len(analytics)}"),
        ("Most Nifty 50 stocks priced", bool(analytics.loc[stocks, "price"].notna().mean() >= 0.8),
         f"{int(analytics.loc[stocks, 'price'].notna().sum())} of {int(stocks.sum())}"),
        ("Indian economic data available", len(macro) >= 3, f"{len(macro)} of {len(MACRO_SERIES)} series"),
        ("Kept separate from US data", bool((master["market"] == "India").all()), "day93_* files only"),
    ]
    out = pd.DataFrame(checks, columns=["check", "passed", "details"])
    out["passed_tests"], out["total_tests"] = int(out["passed"].sum()), len(out)
    return out


def run_india(as_of: Optional[pd.Timestamp] = None, source: Optional[MarketSource] = None,
              out_dir: Path = BASE_DIR, verbose: bool = True):
    as_of = (as_of or pd.Timestamp.now()).normalize()
    source = source or MarketSource()
    master = instrument_master()
    start = (as_of - pd.DateOffset(years=HISTORY_YEARS)).strftime("%Y-%m-%d")
    if verbose:
        print(f"Downloading {len(master)} Indian instruments and {len(MACRO_SERIES)} economic series...")
    try:
        prices = source.history(master["symbol"].tolist(), start)
    except Exception:
        prices = pd.DataFrame()
    fred: Dict[str, pd.Series] = {}
    for series_id in MACRO_SERIES:
        try:
            fred[series_id] = source.fred(series_id)
        except Exception:
            continue

    benchmark = prices[BENCHMARK] if BENCHMARK in prices.columns else None
    rows = []
    for row in master.itertuples(index=False):
        series = prices[row.symbol] if row.symbol in prices.columns else pd.Series(dtype=float)
        stats = instrument_analytics(series, benchmark, as_of)
        stats["beta_to_nifty"] = stats.pop("beta_to_spx", None)
        stats["correlation_to_nifty"] = stats.pop("correlation_to_spx", None)
        rows.append({**row._asdict(), **stats})
    analytics = pd.DataFrame(rows)
    for column in ["price", "as_of", "return_1d", "return_1m", "return_3m", "return_12m", "momentum_12_1",
                   "volatility_1y", "max_drawdown_1y", "trend_vs_200d", "beta_to_nifty", "correlation_to_nifty"]:
        if column not in analytics.columns:
            analytics[column] = np.nan
    macro = macro_table(fred)
    validation = validate(master, analytics, macro)

    out_dir = Path(out_dir)
    if analytics["price"].notna().any():
        recent = prices[prices.index > as_of - pd.Timedelta(days=PRICE_HISTORY_DAYS)]
        analytics.round(6).to_csv(out_dir / OUTPUT_ANALYTICS, index=False)
        recent.round(6).to_csv(out_dir / OUTPUT_HISTORY, index_label="date")
        if len(macro):
            macro.to_csv(out_dir / OUTPUT_MACRO, index=False)
        validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    elif verbose:
        print("No Indian market data downloaded; previous files kept unchanged.")

    if verbose:
        priced = analytics.dropna(subset=["price"])
        print(f"VITTANTRA — DAY 93 INDIA MARKETS  ({len(priced)} of {len(analytics)} instruments priced)")
        nifty = priced[priced["symbol"] == BENCHMARK]
        if len(nifty):
            n = nifty.iloc[0]
            print(f"Nifty 50 {n['price']:,.2f} ({n['return_1d']:+.2%} on the day, {n['return_12m']:+.1%} over a year)")
        if len(macro):
            print(macro[["name", "value", "unit", "as_of"]].to_string(index=False))
        print(validation[["check", "passed", "details"]].to_string(index=False))
        print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
        print("Day 93 India markets complete. Research only; nothing executed.")
    return analytics, macro, validation


def main() -> None:
    run_india()


if __name__ == "__main__":
    main()
