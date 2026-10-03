"""
Day 76c — Vittantra Multi-Asset Universe

One master list covering every major asset class with FREE data, and the
analytics that fit each class:

  Rates        US Treasury curve 1M–30Y, TIPS real yields, breakeven inflation (FRED)
  Credit       ICE BofA option-adjusted spreads AAA → CCC, IG, HY, EM (FRED)
  Bond ETFs    Treasuries, TIPS, IG, HY, munis, MBS, loans, international, EM
  FX           Majors, crosses, emerging-market pairs, dollar index; carry from
               OECD 3-month interbank rates (FRED)
  Commodities  Energy, metals, grains, softs, livestock futures and ETFs
  Digital      Major cryptocurrencies, stablecoins, spot bitcoin/ether ETFs
  Real estate  REIT ETFs (individual REITs are in the US stock engine)
  Alternatives Listed proxies: private-equity managers, BDCs (private credit),
               infrastructure, MLPs, managed futures, hedge-fund replication,
               volatility, farmland, timber
  Equity       Broad US and international index ETFs

Analytics (all computed from prices, comparable across classes):
  returns 1M/3M/12M, 12-1 momentum, annualized volatility, 1-year maximum
  drawdown, trend vs 200-day average, beta and correlation to the S&P 500.
  Volatility is annualized with each instrument's own trading frequency
  (crypto trades 365 days a year; stocks about 252).

Limits (stated): individual corporate bonds have no free market-wide prices,
so credit is covered by spread indices and bond ETFs; private assets are
covered by listed proxies; commodity term structure (roll yield) needs
second-month futures that free sources do not provide.

Usage:  python multi_asset_universe.py
Research only. No trades are submitted or executed.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
HISTORY_START_YEARS = 3
BENCHMARK = "SPY"

OUTPUT_UNIVERSE = "day76c_asset_universe.csv"
OUTPUT_ANALYTICS = "day76c_asset_analytics.csv"
OUTPUT_CURVE = "day76c_yield_curve.csv"
OUTPUT_CREDIT = "day76c_credit_spreads.csv"
OUTPUT_FX_CARRY = "day76c_fx_carry.csv"
OUTPUT_CLASS_SUMMARY = "day76c_asset_class_summary.csv"
OUTPUT_VALIDATION = "day76c_validation_summary.csv"
OUTPUT_ECONOMY = "day76c_economic_dashboard.csv"
OUTPUT_PRICE_HISTORY = "day76c_price_history.csv"
OUTPUT_FRED_HISTORY = "day76c_fred_daily_history.csv"


# ==============================================================
# INSTRUMENT MASTER (Yahoo Finance tickers)
# ==============================================================

def _rows(asset_class, sub_class, items, currency="USD"):
    return [(symbol, name, asset_class, sub_class, currency) for symbol, name in items]


MARKET_INSTRUMENTS = (
    _rows("Equity", "US broad", [("SPY", "S&P 500 ETF"), ("QQQ", "Nasdaq-100 ETF"),
                                 ("IWM", "Russell 2000 ETF"), ("DIA", "Dow Jones ETF"),
                                 ("RSP", "S&P 500 Equal Weight ETF")])
    + _rows("Equity", "International", [("EFA", "Developed ex-US ETF"), ("EEM", "Emerging Markets ETF"),
                                        ("VT", "Total World ETF"), ("INDA", "India ETF"),
                                        ("MCHI", "China ETF"), ("EWJ", "Japan ETF"), ("EWZ", "Brazil ETF"),
                                        ("EWG", "Germany ETF"), ("EWU", "United Kingdom ETF")])
    + _rows("Fixed Income", "Treasury ETF", [("SHY", "1-3Y Treasury ETF"), ("IEF", "7-10Y Treasury ETF"),
                                             ("TLT", "20+Y Treasury ETF"), ("BIL", "1-3M T-Bill ETF")])
    + _rows("Fixed Income", "Inflation-linked ETF", [("TIP", "TIPS ETF")])
    + _rows("Fixed Income", "Aggregate ETF", [("AGG", "US Aggregate Bond ETF"), ("BND", "Total Bond Market ETF")])
    + _rows("Fixed Income", "Investment grade ETF", [("LQD", "IG Corporate Bond ETF"),
                                                     ("VCSH", "Short-Term Corporate ETF"),
                                                     ("VCIT", "Intermediate Corporate ETF")])
    + _rows("Fixed Income", "High yield ETF", [("HYG", "High Yield Corporate ETF"),
                                               ("JNK", "High Yield Bond ETF"), ("BKLN", "Senior Loan ETF")])
    + _rows("Fixed Income", "Other bond ETF", [("MUB", "Municipal Bond ETF"), ("MBB", "Mortgage-Backed ETF"),
                                               ("BNDX", "International Bond ETF"),
                                               ("EMB", "EM Sovereign Bond ETF"), ("FLOT", "Floating Rate ETF")])
    + _rows("FX", "G10", [("EURUSD=X", "Euro / US dollar"), ("GBPUSD=X", "British pound / US dollar"),
                          ("USDJPY=X", "US dollar / Japanese yen"), ("USDCHF=X", "US dollar / Swiss franc"),
                          ("AUDUSD=X", "Australian dollar / US dollar"),
                          ("NZDUSD=X", "New Zealand dollar / US dollar"),
                          ("USDCAD=X", "US dollar / Canadian dollar"), ("USDSEK=X", "US dollar / Swedish krona"),
                          ("USDNOK=X", "US dollar / Norwegian krone")], "FX")
    + _rows("FX", "Cross", [("EURGBP=X", "Euro / British pound"), ("EURJPY=X", "Euro / Japanese yen"),
                            ("GBPJPY=X", "British pound / Japanese yen"), ("EURCHF=X", "Euro / Swiss franc")], "FX")
    + _rows("FX", "Emerging", [("USDINR=X", "US dollar / Indian rupee"), ("USDCNY=X", "US dollar / Chinese yuan"),
                               ("USDMXN=X", "US dollar / Mexican peso"), ("USDBRL=X", "US dollar / Brazilian real"),
                               ("USDZAR=X", "US dollar / South African rand"),
                               ("USDTRY=X", "US dollar / Turkish lira"), ("USDKRW=X", "US dollar / Korean won"),
                               ("USDSGD=X", "US dollar / Singapore dollar"),
                               ("USDHKD=X", "US dollar / Hong Kong dollar"),
                               ("USDPLN=X", "US dollar / Polish zloty")], "FX")
    + _rows("FX", "Dollar index", [("DX-Y.NYB", "US Dollar Index")], "FX")
    + _rows("Commodity", "Energy", [("CL=F", "WTI crude oil"), ("BZ=F", "Brent crude oil"),
                                    ("NG=F", "Natural gas"), ("RB=F", "Gasoline"), ("HO=F", "Heating oil")])
    + _rows("Commodity", "Precious metals", [("GC=F", "Gold"), ("SI=F", "Silver"),
                                             ("PL=F", "Platinum"), ("PA=F", "Palladium")])
    + _rows("Commodity", "Industrial metals", [("HG=F", "Copper")])
    + _rows("Commodity", "Grains", [("ZC=F", "Corn"), ("ZW=F", "Wheat"), ("ZS=F", "Soybeans"),
                                    ("ZM=F", "Soybean meal"), ("ZL=F", "Soybean oil")])
    + _rows("Commodity", "Softs", [("KC=F", "Coffee"), ("SB=F", "Sugar"), ("CC=F", "Cocoa"), ("CT=F", "Cotton")])
    + _rows("Commodity", "Livestock", [("LE=F", "Live cattle"), ("HE=F", "Lean hogs"), ("GF=F", "Feeder cattle")])
    + _rows("Commodity", "Commodity ETF", [("DBC", "Broad Commodity ETF"), ("PDBC", "Optimum Yield Commodity ETF"),
                                           ("GLD", "Gold ETF"), ("SLV", "Silver ETF"), ("USO", "Oil ETF")])
    + _rows("Digital Asset", "Cryptocurrency", [
        ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ether"), ("SOL-USD", "Solana"), ("BNB-USD", "BNB"),
        ("XRP-USD", "XRP"), ("ADA-USD", "Cardano"), ("DOGE-USD", "Dogecoin"), ("AVAX-USD", "Avalanche"),
        ("DOT-USD", "Polkadot"), ("LINK-USD", "Chainlink"), ("LTC-USD", "Litecoin"),
        ("BCH-USD", "Bitcoin Cash"), ("TRX-USD", "TRON"), ("XLM-USD", "Stellar"), ("ATOM-USD", "Cosmos"),
        ("ETC-USD", "Ethereum Classic"), ("FIL-USD", "Filecoin"), ("HBAR-USD", "Hedera"),
        ("ALGO-USD", "Algorand"), ("XMR-USD", "Monero")])
    + _rows("Digital Asset", "Stablecoin", [("USDT-USD", "Tether"), ("USDC-USD", "USD Coin")])
    + _rows("Digital Asset", "Crypto ETF", [("IBIT", "iShares Bitcoin Trust"), ("FBTC", "Fidelity Bitcoin Fund"),
                                            ("ETHA", "iShares Ethereum Trust")])
    + _rows("Real Estate", "REIT ETF", [("VNQ", "US REIT ETF"), ("XLRE", "Real Estate Select Sector ETF"),
                                        ("VNQI", "International REIT ETF"), ("SCHH", "US REIT ETF (Schwab)")])
    # Commercial real estate by property type (listed REITs and operators)
    + _rows("Real Estate", "Hotels & lodging", [
        ("HST", "Host Hotels & Resorts (upscale hotels)"), ("PK", "Park Hotels & Resorts"),
        ("APLE", "Apple Hospitality (select-service hotels)"), ("PEB", "Pebblebrook Hotel Trust"),
        ("DRH", "DiamondRock Hospitality"), ("RHP", "Ryman Hospitality (convention hotels)")])
    + _rows("Real Estate", "Motels & economy hotel brands", [
        ("WH", "Wyndham Hotels (Super 8, Days Inn, Microtel)"),
        ("CHH", "Choice Hotels (Econo Lodge, Rodeway Inn, Comfort)")])
    + _rows("Real Estate", "Office", [("BXP", "BXP (Boston Properties)"), ("VNO", "Vornado Realty"),
                                      ("SLG", "SL Green (Manhattan office)"), ("KRC", "Kilroy Realty"),
                                      ("ARE", "Alexandria (life-science offices)")])
    + _rows("Real Estate", "Industrial & logistics", [("PLD", "Prologis"), ("REXR", "Rexford Industrial"),
                                                      ("EGP", "EastGroup Properties")])
    + _rows("Real Estate", "Retail (malls & shopping centers)", [("SPG", "Simon Property (malls)"),
                                                                 ("KIM", "Kimco Realty"), ("REG", "Regency Centers"),
                                                                 ("FRT", "Federal Realty")])
    + _rows("Real Estate", "Net lease", [("O", "Realty Income"), ("NNN", "NNN REIT")])
    + _rows("Real Estate", "Apartments & single-family rental", [("EQR", "Equity Residential"),
                                                                 ("AVB", "AvalonBay"), ("MAA", "Mid-America Apartment"),
                                                                 ("INVH", "Invitation Homes (single-family)")])
    + _rows("Real Estate", "Data centers & towers", [("EQIX", "Equinix (data centers)"),
                                                     ("DLR", "Digital Realty (data centers)"),
                                                     ("AMT", "American Tower"), ("CCI", "Crown Castle")])
    + _rows("Real Estate", "Healthcare & senior housing", [("WELL", "Welltower"), ("VTR", "Ventas"),
                                                           ("OHI", "Omega Healthcare (skilled nursing)")])
    + _rows("Real Estate", "Self-storage", [("PSA", "Public Storage"), ("EXR", "Extra Space Storage"),
                                            ("CUBE", "CubeSmart")])
    + _rows("Real Estate", "CRE debt (mortgage REITs, CMBS)", [
        ("BXMT", "Blackstone Mortgage Trust"), ("STWD", "Starwood Property Trust"),
        ("ARI", "Apollo Commercial RE Finance"), ("CMBS", "iShares CMBS ETF")])
    + _rows("Alternative", "Private equity (listed)", [("BX", "Blackstone"), ("KKR", "KKR"), ("APO", "Apollo"),
                                                       ("CG", "Carlyle"), ("ARES", "Ares Management"),
                                                       ("PSP", "Listed Private Equity ETF")])
    + _rows("Alternative", "Private credit (BDCs)", [("ARCC", "Ares Capital"), ("MAIN", "Main Street Capital"),
                                                     ("OBDC", "Blue Owl Capital Corp"), ("FSK", "FS KKR Capital"),
                                                     ("BIZD", "BDC Income ETF")])
    + _rows("Alternative", "Infrastructure & MLPs", [("IGF", "Global Infrastructure ETF"),
                                                     ("PAVE", "US Infrastructure ETF"), ("AMLP", "MLP ETF")])
    + _rows("Alternative", "Hedge-fund style", [("QAI", "Hedge Multi-Strategy Tracker ETF"),
                                                ("DBMF", "Managed Futures ETF"), ("KMLM", "Managed Futures ETF (KFA)")])
    + _rows("Alternative", "Volatility", [("^VIX", "CBOE Volatility Index"), ("VIXY", "VIX Short-Term Futures ETF")])
    + _rows("Alternative", "Real assets", [("LAND", "Gladstone Land (farmland)"),
                                           ("FPI", "Farmland Partners"), ("WOOD", "Global Timber ETF"),
                                           ("GDX", "Gold Miners ETF")])
)

TREASURY_CURVE = {
    "DGS1MO": 1 / 12, "DGS3MO": 0.25, "DGS6MO": 0.5, "DGS1": 1, "DGS2": 2, "DGS3": 3,
    "DGS5": 5, "DGS7": 7, "DGS10": 10, "DGS20": 20, "DGS30": 30,
}
REAL_YIELDS = {"DFII5": 5, "DFII10": 10, "DFII30": 30}
BREAKEVENS = {"T5YIE": 5, "T10YIE": 10}
CREDIT_SPREADS = {
    "BAMLC0A1CAAA": "AAA", "BAMLC0A2CAA": "AA", "BAMLC0A3CA": "A", "BAMLC0A4CBBB": "BBB",
    "BAMLH0A1HYBB": "BB", "BAMLH0A2HYB": "B", "BAMLH0A3HYC": "CCC & below",
    "BAMLC0A0CM": "US investment grade", "BAMLH0A0HYM2": "US high yield",
    "BAMLEMCBPIOAS": "Emerging-market corporates",
}
# OECD 3-month interbank rates (monthly, % per year) for FX carry.
SHORT_RATES = {
    "USD": "IR3TIB01USM156N", "EUR": "IR3TIB01EZM156N", "GBP": "IR3TIB01GBM156N",
    "JPY": "IR3TIB01JPM156N", "CHF": "IR3TIB01CHM156N", "AUD": "IR3TIB01AUM156N",
    "NZD": "IR3TIB01NZM156N", "CAD": "IR3TIB01CAM156N", "SEK": "IR3TIB01SEM156N",
    "NOK": "IR3TIB01NOM156N", "INR": "IR3TIB01INM156N", "MXN": "IR3TIB01MXM156N",
    "ZAR": "IR3TIB01ZAM156N", "KRW": "IR3TIB01KRM156N", "PLN": "IR3TIB01PLM156N",
    "CNY": "IR3TIB01CNM156N", "BRL": "IR3TIB01BRM156N", "TRY": "IR3TIB01TRM156N",
}

# Regular economic releases professionals track (id, name, category, transform).
# Transforms: yoy = % change vs. a year earlier; diff = change vs. previous
# release; saar = quarterly growth annualized; level = latest value.
ECONOMIC_SERIES = [
    ("CPIAUCSL", "CPI inflation (headline, y/y %)", "Inflation", "yoy"),
    ("CPILFESL", "Core CPI inflation (y/y %)", "Inflation", "yoy"),
    ("PCEPILFE", "Core PCE inflation — the Fed's target measure (y/y %)", "Inflation", "yoy"),
    ("UNRATE", "Unemployment rate (%)", "Labor market", "level"),
    ("PAYEMS", "Nonfarm payrolls (monthly change, thousands)", "Labor market", "diff"),
    ("ICSA", "Initial jobless claims (weekly)", "Labor market", "level"),
    ("GDPC1", "Real GDP growth (q/q annualized %)", "Growth", "saar"),
    ("INDPRO", "Industrial production (y/y %)", "Growth", "yoy"),
    ("RSAFS", "Retail sales (y/y %)", "Consumer", "yoy"),
    ("UMCSENT", "Consumer sentiment (University of Michigan)", "Consumer", "level"),
    ("FEDFUNDS", "Effective fed funds rate (%)", "Monetary policy", "level"),
    ("MORTGAGE30US", "30-year fixed mortgage rate (%)", "Housing", "level"),
    ("HOUST", "Housing starts (thousands, annualized)", "Housing", "level"),
    ("CUSR0000SEHB", "Hotel & lodging prices — CPI lodging away from home (y/y %)", "Commercial real estate", "yoy"),
    ("DRCRELEXFACBS", "Delinquency rate on commercial real estate loans at banks (%)", "Commercial real estate", "level"),
    ("TLCOMCONS", "Commercial construction spending (y/y %)", "Commercial real estate", "yoy"),
    ("VIXCLS", "VIX equity volatility index", "Markets", "level"),
]

# Daily FRED series saved as history for the macro-drivers report.
DAILY_FACTOR_SERIES = ["DGS10", "DGS2", "DGS3MO", "T10YIE", "BAMLH0A0HYM2", "BAMLC0A0CM", "VIXCLS"]
PRICE_HISTORY_DAYS = 430

FRED_SERIES = {**{s: "Treasury" for s in TREASURY_CURVE}, **{s: "Real yield" for s in REAL_YIELDS},
               **{s: "Breakeven" for s in BREAKEVENS}, **{s: "Credit spread" for s in CREDIT_SPREADS},
               **{s: "Short rate" for s in SHORT_RATES.values()},
               **{s[0]: "Economic" for s in ECONOMIC_SERIES}}


def instrument_master() -> pd.DataFrame:
    market = pd.DataFrame(MARKET_INSTRUMENTS,
                          columns=["symbol", "name", "asset_class", "sub_class", "currency"])
    market["source"] = "Yahoo Finance"
    rates = []
    for series, maturity in TREASURY_CURVE.items():
        rates.append((series, f"US Treasury {_maturity_label(maturity)}", "Fixed Income", "Treasury yield"))
    for series, maturity in REAL_YIELDS.items():
        rates.append((series, f"TIPS real yield {maturity}Y", "Fixed Income", "Real yield"))
    for series, maturity in BREAKEVENS.items():
        rates.append((series, f"Breakeven inflation {maturity}Y", "Fixed Income", "Breakeven inflation"))
    for series, rating in CREDIT_SPREADS.items():
        rates.append((series, f"Credit spread: {rating}", "Fixed Income", "Credit spread"))
    fred = pd.DataFrame(rates, columns=["symbol", "name", "asset_class", "sub_class"])
    fred["currency"] = "% / bp"
    fred["source"] = "FRED"
    return pd.concat([market, fred], ignore_index=True)


def _maturity_label(years: float) -> str:
    return f"{round(years * 12)}M" if years < 1 else f"{int(years)}Y"


# ==============================================================
# DATA ACCESS (replaceable in tests)
# ==============================================================

def fetch_market_history(tickers: List[str], start: str) -> pd.DataFrame:
    """Wide adjusted-close prices (dates × tickers) from Yahoo Finance."""
    from vittantra_data_hub import fetch_price_history_yfinance

    frames = []
    for i in range(0, len(tickers), 100):
        long = fetch_price_history_yfinance(tickers[i:i + 100], start)
        if not long.empty:
            frames.append(long)
    if not frames:
        return pd.DataFrame()
    long = pd.concat(frames)
    long["price"] = long["adj_close"].fillna(long["close"])
    return long.pivot_table(index="date", columns="ticker", values="price").sort_index()


def fetch_fred(series_id: str) -> pd.Series:
    from vittantra_data_hub import fetch_fred_series

    df = fetch_fred_series(series_id)
    return df.set_index("date")["value"].sort_index()


@dataclass
class MarketSource:
    history: Callable[[List[str], str], pd.DataFrame] = fetch_market_history
    fred: Callable[[str], pd.Series] = fetch_fred


# ==============================================================
# ANALYTICS
# ==============================================================

ANALYTIC_COLUMNS = [
    "price", "as_of", "return_1d", "return_1m", "return_3m", "return_12m", "momentum_12_1",
    "volatility_1y", "max_drawdown_1y", "trend_vs_200d", "observations_per_year",
    "beta_to_spx", "correlation_to_spx",
]

def _price_on_or_before(series: pd.Series, date: pd.Timestamp) -> Optional[float]:
    before = series[series.index <= date]
    return float(before.iloc[-1]) if len(before) else None


def _ret(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> Optional[float]:
    a, b = _price_on_or_before(series, start), _price_on_or_before(series, end)
    if a is None or b is None or a <= 0:
        return None
    return b / a - 1


def instrument_analytics(series: pd.Series, benchmark: Optional[pd.Series],
                         as_of: pd.Timestamp) -> dict:
    """Price-based analytics comparable across asset classes."""
    out = {"price": None, "as_of": None}
    series = series.dropna()
    if len(series) < 2:
        return out
    series = series[(series > 0) & (pd.DatetimeIndex(series.index) <= as_of)]
    if len(series) < 2:
        return out
    last_date = series.index[-1]
    returns = series.pct_change().dropna()
    last_year = returns[returns.index > last_date - pd.Timedelta(days=365)]
    periods_per_year = max(len(last_year), 1)
    year_prices = series[series.index > last_date - pd.Timedelta(days=365)]
    out.update({
        "price": float(series.iloc[-1]),
        "as_of": last_date.date(),
        "return_1d": float(returns.iloc[-1]),
        "return_1m": _ret(series, last_date - pd.DateOffset(months=1), last_date),
        "return_3m": _ret(series, last_date - pd.DateOffset(months=3), last_date),
        "return_12m": _ret(series, last_date - pd.DateOffset(months=12), last_date),
        # 12-1 momentum: last year excluding the most recent month (short-term reversal)
        "momentum_12_1": _ret(series, last_date - pd.DateOffset(months=12),
                              last_date - pd.DateOffset(months=1)),
        "volatility_1y": (float(last_year.std(ddof=1) * math.sqrt(periods_per_year))
                          if len(last_year) > 20 else None),
        "max_drawdown_1y": float((year_prices / year_prices.cummax() - 1).min()) if len(year_prices) > 1 else None,
        "trend_vs_200d": (float(series.iloc[-1] / series.tail(200).mean() - 1) if len(series) >= 200 else None),
        "observations_per_year": periods_per_year,
    })
    if benchmark is not None:
        aligned = pd.concat([returns, benchmark.pct_change()], axis=1, join="inner").dropna()
        aligned = aligned[aligned.index > last_date - pd.Timedelta(days=365)]
        if len(aligned) > 20 and aligned.iloc[:, 1].var() > 0:
            out["beta_to_spx"] = float(aligned.cov().iloc[0, 1] / aligned.iloc[:, 1].var())
            out["correlation_to_spx"] = float(aligned.corr().iloc[0, 1])
    return out


def yield_curve_table(fred: Dict[str, pd.Series], as_of: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for series_id, maturity in TREASURY_CURVE.items():
        values = fred.get(series_id, pd.Series(dtype=float)).dropna()
        if values.empty:
            continue
        values = values[pd.DatetimeIndex(values.index) <= as_of]
        if values.empty:
            continue
        last_date = values.index[-1]
        latest = float(values.iloc[-1])
        month_ago = _price_on_or_before(values, last_date - pd.DateOffset(months=1))
        year_ago = _price_on_or_before(values, last_date - pd.DateOffset(years=1))
        rows.append({
            "series_id": series_id, "maturity": _maturity_label(maturity), "years": maturity,
            "yield_pct": latest, "date": last_date.date(),
            "yield_1y_ago_pct": year_ago,
            "change_1m_bp": (latest - month_ago) * 100 if month_ago is not None else None,
            "change_1y_bp": (latest - year_ago) * 100 if year_ago is not None else None,
        })
    return pd.DataFrame(rows)


def curve_summary(curve: pd.DataFrame, fred: Dict[str, pd.Series]) -> dict:
    by = curve.set_index("series_id")["yield_pct"] if len(curve) else pd.Series(dtype=float)

    def latest(series_id):
        values = fred.get(series_id, pd.Series(dtype=float)).dropna()
        return float(values.iloc[-1]) if len(values) else None

    out = {
        "slope_2s10s_bp": (by["DGS10"] - by["DGS2"]) * 100 if {"DGS10", "DGS2"} <= set(by.index) else None,
        "slope_3m10y_bp": (by["DGS10"] - by["DGS3MO"]) * 100 if {"DGS10", "DGS3MO"} <= set(by.index) else None,
        "real_yield_10y_pct": latest("DFII10"),
        "breakeven_10y_pct": latest("T10YIE"),
        "breakeven_5y_pct": latest("T5YIE"),
    }
    out["curve_inverted_3m10y"] = out["slope_3m10y_bp"] is not None and out["slope_3m10y_bp"] < 0
    return out


def credit_table(fred: Dict[str, pd.Series], as_of: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for series_id, rating in CREDIT_SPREADS.items():
        values = fred.get(series_id, pd.Series(dtype=float)).dropna()
        if values.empty:
            continue
        values = values[pd.DatetimeIndex(values.index) <= as_of]
        if values.empty:
            continue
        latest = float(values.iloc[-1])
        year_ago = _price_on_or_before(values, values.index[-1] - pd.DateOffset(years=1))
        rows.append({
            "series_id": series_id, "segment": rating,
            "spread_bp": latest * 100, "date": values.index[-1].date(),
            "change_1y_bp": (latest - year_ago) * 100 if year_ago is not None else None,
            # Where today's spread sits in the history FRED provides (0 = tightest)
            "percentile_in_history": float((values <= latest).mean() * 100),
            "history_start": values.index[0].date(),
        })
    return pd.DataFrame(rows)


MAX_RATE_AGE_DAYS = 400


def fx_carry_table(analytics: pd.DataFrame, fred: Dict[str, pd.Series],
                   as_of: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """
    Carry of holding each FX pair long (base currency vs quote currency):
        carry ≈ short rate of base currency − short rate of quote currency
    e.g. long USDJPY earns the US rate and pays the yen rate.
    """
    as_of = as_of or pd.Timestamp.now()

    def latest_rate(ccy):
        values = fred.get(SHORT_RATES.get(ccy, ""), pd.Series(dtype=float)).dropna()
        if values.empty:
            return None, None
        # Ignore discontinued series (e.g. a rate last published years ago).
        newest = pd.Timestamp(values.index[-1])
        if (pd.Timestamp(as_of) - newest).days > MAX_RATE_AGE_DAYS:
            return None, None
        return float(values.iloc[-1]), newest.date()

    rows = []
    fx = analytics[(analytics["asset_class"] == "FX") & analytics["symbol"].str.endswith("=X")]
    for row in fx.itertuples(index=False):
        pair = row.symbol.replace("=X", "")
        base, quote = pair[:3], pair[3:]
        base_rate, base_date = latest_rate(base)
        quote_rate, quote_date = latest_rate(quote)
        carry = base_rate - quote_rate if base_rate is not None and quote_rate is not None else None
        rows.append({
            "symbol": row.symbol, "pair": f"{base}/{quote}", "base_rate_pct": base_rate,
            "quote_rate_pct": quote_rate, "carry_long_pair_pct": carry,
            "rates_as_of": min(d for d in (base_date, quote_date) if d) if (base_date or quote_date) else None,
            "return_12m": row.return_12m, "volatility_1y": row.volatility_1y,
            "carry_to_vol": (carry / 100 / row.volatility_1y
                             if carry is not None and row.volatility_1y else None),
        })
    return pd.DataFrame(rows)


def economic_dashboard(fred: Dict[str, pd.Series]) -> pd.DataFrame:
    """Latest reading of each regular economic release, transformed as professionals quote it."""
    def transform(values: pd.Series, how: str) -> pd.Series:
        if how == "yoy":
            # % change vs. the observation closest to one year earlier
            shifted = values.reindex(values.index - pd.DateOffset(years=1), method="nearest", tolerance=pd.Timedelta(days=20))
            return pd.Series((values.to_numpy() / shifted.to_numpy() - 1) * 100, index=values.index)
        if how == "diff":
            return values.diff()
        if how == "saar":
            return ((values / values.shift(1)) ** 4 - 1) * 100
        return values

    rows = []
    for series_id, name, category, how in ECONOMIC_SERIES:
        values = fred.get(series_id, pd.Series(dtype=float)).dropna()
        if len(values) < 3:
            rows.append({"series_id": series_id, "indicator": name, "category": category})
            continue
        values.index = pd.DatetimeIndex(values.index)
        shown = transform(values, how).dropna()
        if shown.empty:
            continue
        latest, previous = float(shown.iloc[-1]), float(shown.iloc[-2]) if len(shown) > 1 else None
        year_ago = shown[shown.index <= shown.index[-1] - pd.DateOffset(years=1)]
        rows.append({
            "series_id": series_id, "indicator": name, "category": category,
            "latest": latest, "previous": previous,
            "change": latest - previous if previous is not None else None,
            "year_ago": float(year_ago.iloc[-1]) if len(year_ago) else None,
            "release_period": shown.index[-1].date(),
        })
    return pd.DataFrame(rows)


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day76c(master, analytics, curve, credit, fx_carry, as_of) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    market = analytics[analytics["source"] == "Yahoo Finance"]
    priced = market["price"].notna()
    add("Market instruments priced", priced.mean() >= 0.9,
        f"{int(priced.sum())} of {len(market)} instruments")
    add("No non-positive prices", (market.loc[priced, "price"] > 0).all(), "All prices positive")
    classes = set(master["asset_class"])
    covered = set(market.loc[priced, "asset_class"]) | ({"Fixed Income"} if len(curve) else set())
    add("Every asset class covered", classes <= covered, f"Missing: {', '.join(sorted(classes - covered)) or 'none'}")
    vols = pd.to_numeric(market["volatility_1y"], errors="coerce").dropna()
    add("Volatilities positive and plausible", len(vols) and vols.between(0, 5).all(),
        f"range {vols.min():.1%} to {vols.max():.1%}" if len(vols) else "none")
    dates = pd.to_datetime(market["as_of"], errors="coerce")
    fresh = ((as_of - dates).dt.days <= 7).mean() if len(dates) else 0
    add("Prices fresh (within 7 days)", fresh >= 0.9, f"{fresh:.0%} of instruments")
    add("Treasury curve complete", len(curve) == len(TREASURY_CURVE),
        f"{len(curve)} of {len(TREASURY_CURVE)} maturities")
    add("Credit spreads loaded", len(credit) >= 0.8 * len(CREDIT_SPREADS),
        f"{len(credit)} of {len(CREDIT_SPREADS)} segments")
    carry_ok = fx_carry["carry_long_pair_pct"].notna().mean() if len(fx_carry) else 0
    add("FX carry coverage", carry_ok >= 0.5, f"{carry_ok:.0%} of pairs have both short rates")
    stable = analytics[analytics["sub_class"] == "Stablecoin"]["price"].dropna()
    add("Stablecoins near $1 (data sanity)", stable.between(0.97, 1.03).all() if len(stable) else True,
        ", ".join(f"{p:.4f}" for p in stable))
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_multi_asset(as_of: Optional[pd.Timestamp] = None, source: Optional[MarketSource] = None,
                    out_dir: Path = BASE_DIR, verbose: bool = True):
    as_of = (as_of or pd.Timestamp.now()).normalize()
    source = source or MarketSource()
    master = instrument_master()
    market = master[master["source"] == "Yahoo Finance"]
    start = (as_of - pd.DateOffset(years=HISTORY_START_YEARS)).strftime("%Y-%m-%d")

    if verbose:
        print(f"Downloading {len(market)} market instruments and {len(FRED_SERIES)} FRED series...")
    try:
        prices = source.history(market["symbol"].tolist(), start)
    except Exception:
        prices = pd.DataFrame()
    fred: Dict[str, pd.Series] = {}
    for series_id in FRED_SERIES:
        try:
            fred[series_id] = source.fred(series_id)
        except Exception:
            continue

    benchmark = prices[BENCHMARK] if BENCHMARK in prices.columns else None
    rows = []
    for row in market.itertuples(index=False):
        series = prices[row.symbol] if row.symbol in prices.columns else pd.Series(dtype=float)
        rows.append({**row._asdict(), **instrument_analytics(series, benchmark, as_of)})
    for row in master[master["source"] == "FRED"].itertuples(index=False):
        values = fred.get(row.symbol, pd.Series(dtype=float)).dropna()
        rows.append({**row._asdict(), "price": float(values.iloc[-1]) if len(values) else None,
                     "as_of": values.index[-1].date() if len(values) else None})
    analytics = pd.DataFrame(rows)
    for column in ANALYTIC_COLUMNS:
        if column not in analytics.columns:
            analytics[column] = np.nan

    curve = yield_curve_table(fred, as_of)
    curve_stats = curve_summary(curve, fred)
    curve = curve.assign(**curve_stats) if len(curve) else curve
    credit = credit_table(fred, as_of)
    fx_carry = fx_carry_table(analytics, fred, as_of)
    summary = (analytics[analytics["source"] == "Yahoo Finance"]
               .groupby(["asset_class", "sub_class"])
               .agg(instruments=("symbol", "count"), median_return_1m=("return_1m", "median"),
                    median_return_12m=("return_12m", "median"), median_volatility=("volatility_1y", "median"),
                    median_beta_to_spx=("beta_to_spx", "median"))
               .reset_index())
    validation = validate_day76c(master, analytics, curve, credit, fx_carry, as_of)
    economy = economic_dashboard(fred)
    recent = prices[prices.index > as_of - pd.Timedelta(days=PRICE_HISTORY_DAYS)] if len(prices) else prices
    daily_fred = pd.DataFrame({s: fred[s] for s in DAILY_FACTOR_SERIES if s in fred})
    if len(daily_fred):
        daily_fred.index = pd.DatetimeIndex(daily_fred.index)
        daily_fred = daily_fred[daily_fred.index > as_of - pd.Timedelta(days=PRICE_HISTORY_DAYS)]

    out_dir = Path(out_dir)
    if analytics["price"].notna().any():
        master.to_csv(out_dir / OUTPUT_UNIVERSE, index=False)
        analytics.to_csv(out_dir / OUTPUT_ANALYTICS, index=False)
        curve.to_csv(out_dir / OUTPUT_CURVE, index=False)
        credit.to_csv(out_dir / OUTPUT_CREDIT, index=False)
        fx_carry.to_csv(out_dir / OUTPUT_FX_CARRY, index=False)
        summary.to_csv(out_dir / OUTPUT_CLASS_SUMMARY, index=False)
        validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
        economy.to_csv(out_dir / OUTPUT_ECONOMY, index=False)
        recent.round(6).to_csv(out_dir / OUTPUT_PRICE_HISTORY, index_label="date")
        if len(daily_fred):
            daily_fred.to_csv(out_dir / OUTPUT_FRED_HISTORY, index_label="date")
    elif verbose:
        print("No market data downloaded; previous files kept unchanged.")

    if verbose:
        print_report(as_of, analytics, curve, curve_stats, credit, fx_carry, summary, validation)
    return analytics, curve, credit, fx_carry, summary, validation


def print_report(as_of, analytics, curve, curve_stats, credit, fx_carry, summary, validation) -> None:
    line = "=" * 92
    pd.set_option("display.width", 200)
    print(line)
    print(f"VITTANTRA — DAY 76c MULTI-ASSET UNIVERSE (as of {as_of.date()}, Yahoo Finance + FRED)")
    print(line)
    print(f"Instruments: {len(analytics)}  |  asset classes: {analytics['asset_class'].nunique()}")
    print("\nBy asset class")
    print(summary.round(3).to_string(index=False))
    if len(curve):
        print("\nUS Treasury curve")
        print(curve[["maturity", "yield_pct", "change_1m_bp", "change_1y_bp"]].round(2).to_string(index=False))
        print(f"2s10s: {curve_stats['slope_2s10s_bp']:.0f} bp | 3m10y: {curve_stats['slope_3m10y_bp']:.0f} bp"
              if curve_stats["slope_2s10s_bp"] is not None and curve_stats["slope_3m10y_bp"] is not None else "")
    if len(credit):
        print("\nCredit spreads")
        print(credit[["segment", "spread_bp", "change_1y_bp", "percentile_in_history"]].round(0).to_string(index=False))
    if len(fx_carry):
        print("\nFX carry (long the pair)")
        print(fx_carry[["pair", "carry_long_pair_pct", "return_12m", "volatility_1y"]].round(3).to_string(index=False))
    missing = analytics[(analytics["source"] == "Yahoo Finance") & analytics["price"].isna()]["symbol"].tolist()
    if missing:
        print(f"\nNo price downloaded for: {', '.join(missing)}")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 76c multi-asset universe complete. No trades were submitted or executed.")
    print(line)


def main() -> None:
    argparse.ArgumentParser(description="Vittantra multi-asset universe (free data)").parse_args()
    run_multi_asset()


if __name__ == "__main__":
    main()
