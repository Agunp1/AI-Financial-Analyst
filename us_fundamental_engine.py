"""
Day 76b — Vittantra US Market Fundamental Engine (all US-listed stocks)

Extends the Day 76 fundamental engine from the 33-stock research universe to
every operating company listed on NYSE, Nasdaq and NYSE American (about
6,000 companies, including REITs and foreign companies that file with the
SEC). Free, official SEC data; no API key.

How it scales
-------------
- Universe: SEC company_tickers_exchange.json (ticker, CIK, exchange).
- Industry: SIC code from each company's SEC submissions record (cached for
  90 days), mapped to GICS-style sectors. Blank-check companies (SPACs) and
  funds are excluded.
- Fundamentals: SEC XBRL "frames". One request returns one line item for
  one period for every company, so about 500 requests cover the market
  instead of 6,000 company downloads.
- The same metric engine as Day 76 is reused (TTM, fallbacks, bank rules),
  by rebuilding each company's facts from the frames.
- Scores are percentiles within each sector when the sector has enough
  companies, otherwise within the whole universe.

Limitation (stated): frames return each company's latest reported value for
a period, including later restatements, and do not carry filing dates. That
is right for today's snapshot but not for historical backtests, which keep
using the point-in-time Day 76 engine.

Usage
-----
python us_fundamental_engine.py               # full US market
python us_fundamental_engine.py --limit 300   # quick test on 300 companies

Research only. Scores are not investment recommendations.
"""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

import fundamental_engine as fe


BASE_DIR = Path(__file__).resolve().parent
FRAMES_CACHE = fe.CACHE_DIR / "frames"
SUBMISSIONS_CACHE = fe.CACHE_DIR / "submissions"

LISTED_EXCHANGES = {"NYSE", "Nasdaq", "NYSE American", "NYSE MKT", "NYSE Arca", "CBOE"}
EXCLUDED_SIC = {6770}            # blank checks (SPACs)
MIN_SECTOR_SIZE = 15             # below this, rank against the whole universe
QUARTERS_BACK = 11
ANNUALS_BACK = 3
INSTANTS_BACK = 8

OUTPUT_UNIVERSE = "day76_us_universe.csv"
OUTPUT_METRICS = "day76_us_fundamental_metrics.csv"
OUTPUT_SCORES = "day76_us_fundamental_scores.csv"
OUTPUT_VALIDATION = "day76_us_validation_summary.csv"

UNITS = {"eps_diluted": "USD-per-shares"}
SHARE_CONCEPTS = {
    "CommonStockSharesOutstanding": ("shares", "instant"),
    "WeightedAverageNumberOfDilutedSharesOutstanding": ("shares", "duration"),
}


# ==============================================================
# SIC → SECTOR (approximate GICS-style mapping)
# ==============================================================

SIC_RANGES = [
    (100, 999, "Consumer Staples"),
    (1000, 1099, "Materials"), (1200, 1399, "Energy"), (1400, 1499, "Materials"),
    (1500, 1799, "Industrials"),
    (2000, 2199, "Consumer Staples"), (2200, 2399, "Consumer Discretionary"),
    (2400, 2499, "Materials"), (2500, 2599, "Consumer Discretionary"),
    (2600, 2699, "Materials"), (2700, 2799, "Communication Services"),
    (2800, 2829, "Materials"), (2830, 2836, "Health Care"),
    (2840, 2844, "Consumer Staples"), (2845, 2899, "Materials"),
    (2900, 2999, "Energy"), (3000, 3099, "Materials"),
    (3100, 3199, "Consumer Discretionary"), (3200, 3399, "Materials"),
    (3400, 3499, "Industrials"), (3500, 3569, "Industrials"),
    (3570, 3579, "Information Technology"), (3580, 3599, "Industrials"),
    (3600, 3629, "Industrials"), (3630, 3639, "Consumer Discretionary"),
    (3640, 3659, "Industrials"), (3660, 3699, "Information Technology"),
    (3700, 3716, "Consumer Discretionary"), (3717, 3799, "Industrials"),
    (3800, 3839, "Information Technology"), (3840, 3851, "Health Care"),
    (3852, 3899, "Information Technology"), (3900, 3999, "Consumer Discretionary"),
    (4000, 4799, "Industrials"), (4800, 4899, "Communication Services"),
    (4900, 4999, "Utilities"),
    (5000, 5119, "Industrials"), (5120, 5129, "Health Care"), (5130, 5199, "Industrials"),
    (5200, 5399, "Consumer Discretionary"), (5400, 5499, "Consumer Staples"),
    (5500, 5911, "Consumer Discretionary"), (5912, 5912, "Consumer Staples"),
    (5913, 5999, "Consumer Discretionary"),
    (6000, 6499, "Financials"), (6500, 6553, "Real Estate"),
    (6700, 6797, "Financials"), (6798, 6798, "Real Estate"), (6799, 6799, "Financials"),
    (7000, 7299, "Consumer Discretionary"), (7300, 7369, "Industrials"),
    (7370, 7379, "Information Technology"), (7380, 7799, "Industrials"),
    (7800, 7899, "Communication Services"), (7900, 7999, "Consumer Discretionary"),
    (8000, 8099, "Health Care"), (8100, 8999, "Industrials"),
]


def sic_to_sector(sic) -> str:
    try:
        code = int(sic)
    except (TypeError, ValueError):
        return "Unclassified"
    for low, high, sector in SIC_RANGES:
        if low <= code <= high:
            return sector
    return "Unclassified"


# ==============================================================
# SEC ACCESS (replaceable in tests)
# ==============================================================

def _cache_age_ok(path: Path, max_age_hours: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) / 3600 < max_age_hours


def _cached(path: Path, max_age_hours: float, fetch: Callable[[], dict]) -> dict:
    import json

    if _cache_age_ok(path, max_age_hours):
        return json.loads(path.read_text())
    try:
        data = fetch()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return data
    except Exception:
        if path.exists():
            return json.loads(path.read_text())
        raise


def fetch_ticker_exchange() -> pd.DataFrame:
    data = _cached(fe.CACHE_DIR / "company_tickers_exchange.json", 24,
                   lambda: fe._sec_get_json("https://www.sec.gov/files/company_tickers_exchange.json"))
    return pd.DataFrame(data["data"], columns=data["fields"])


def fetch_submission(cik: int) -> dict:
    """Small subset of the SEC submissions record (SIC, entity type)."""
    def download():
        full = fe._sec_get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        return {key: full.get(key) for key in
                ("cik", "name", "sic", "sicDescription", "entityType", "fiscalYearEnd", "exchanges")}
    return _cached(SUBMISSIONS_CACHE / f"CIK{cik:010d}.json", 24 * 90, download)


def fetch_frame(concept: str, unit: str, period: str) -> List[dict]:
    """One XBRL frame: one concept, one period, all companies."""
    path = FRAMES_CACHE / f"{concept}_{unit}_{period}.json"
    max_age = 24 if _period_is_recent(period) else 24 * 30

    def download():
        try:
            return fe._sec_get_json(
                f"https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/{unit}/{period}.json")
        except Exception as exc:
            if "404" in str(exc):
                return {"data": []}           # nobody reported this concept/period
            raise
    return _cached(path, max_age, download).get("data", [])


def fetch_prices(tickers: List[str], chunk_size: int = 200) -> Dict[str, float]:
    """Latest daily close from Yahoo Finance, downloaded in batches."""
    import yfinance as yf

    prices: Dict[str, float] = {}
    for start in range(0, len(tickers), chunk_size):
        chunk = tickers[start:start + chunk_size]
        try:
            raw = yf.download(chunk, period="5d", interval="1d", group_by="ticker",
                              auto_adjust=False, progress=False, threads=True)
        except Exception:
            continue
        for ticker in chunk:
            try:
                series = raw[ticker]["Close"] if len(chunk) > 1 else raw["Close"]
                series = series.dropna()
                if len(series):
                    prices[ticker] = float(series.iloc[-1])
            except Exception:
                continue
        time.sleep(1.0)
    return prices


@dataclass
class UsSource:
    ticker_exchange: Callable[[], pd.DataFrame] = fetch_ticker_exchange
    submission: Callable[[int], dict] = fetch_submission
    frame: Callable[[str, str, str], List[dict]] = fetch_frame
    prices: Callable[[List[str]], Dict[str, float]] = fetch_prices


# ==============================================================
# PERIODS
# ==============================================================

def _period_end(period: str) -> pd.Timestamp:
    year = int(period[2:6])
    if "Q" in period:
        quarter = int(period[7])
        return pd.Timestamp(year=year, month=3 * quarter, day=1) + pd.offsets.MonthEnd(0)
    return pd.Timestamp(year=year, month=12, day=31)


def _period_is_recent(period: str) -> bool:
    return (pd.Timestamp.now() - _period_end(period)).days < 200


def calendar_quarters(as_of: pd.Timestamp, count: int) -> List[str]:
    """Most recent `count` calendar quarters that have ended by as_of."""
    quarter_end = (as_of + pd.offsets.QuarterEnd(0)).normalize()
    if quarter_end > as_of:
        quarter_end = (quarter_end - pd.offsets.QuarterEnd(1)).normalize()
    periods = []
    for _ in range(count):
        periods.append(f"CY{quarter_end.year}Q{(quarter_end.month - 1) // 3 + 1}")
        quarter_end = (quarter_end - pd.offsets.QuarterEnd(1)).normalize()
    return periods


def frame_periods(as_of: pd.Timestamp, item_kind: str) -> List[str]:
    quarters = calendar_quarters(as_of, QUARTERS_BACK)
    if item_kind == "instant":
        return [f"{q}I" for q in quarters[:INSTANTS_BACK]]
    last_year = as_of.year if as_of.month == 12 and as_of.day == 31 else as_of.year - 1
    annuals = [f"CY{last_year - i}" for i in range(ANNUALS_BACK)]
    return quarters + annuals


# ==============================================================
# UNIVERSE
# ==============================================================

def build_universe(source: UsSource, limit: Optional[int] = None, verbose: bool = True) -> pd.DataFrame:
    tickers = source.ticker_exchange()
    tickers = tickers[tickers["exchange"].isin(LISTED_EXCHANGES)].copy()
    tickers["ticker"] = tickers["ticker"].str.upper().str.replace(".", "-", regex=False)
    # One row per company: keep the first listed ticker for each CIK.
    tickers = tickers.drop_duplicates(subset="cik", keep="first").reset_index(drop=True)
    if limit:
        tickers = tickers.head(limit)

    rows = []
    for i, row in enumerate(tickers.itertuples(index=False), start=1):
        try:
            info = source.submission(int(row.cik))
        except Exception:
            info = {}
        sic = info.get("sic")
        rows.append({
            "ticker": row.ticker, "cik": int(row.cik), "name": row.name, "exchange": row.exchange,
            "sic": sic, "sic_description": info.get("sicDescription"),
            "entity_type": info.get("entityType"), "sector": sic_to_sector(sic),
        })
        if verbose and i % 500 == 0:
            print(f"  company profiles: {i}/{len(tickers)}")
    universe = pd.DataFrame(rows)
    sic_numeric = pd.to_numeric(universe["sic"], errors="coerce")
    operating = universe["entity_type"].fillna("operating").str.lower().eq("operating")
    universe["included"] = operating & ~sic_numeric.isin(EXCLUDED_SIC)
    universe["exclusion_reason"] = np.where(
        sic_numeric.isin(EXCLUDED_SIC), "blank check (SPAC)",
        np.where(~operating, "not an operating company", ""))
    return universe


# ==============================================================
# FRAMES → COMPANY FACTS
# ==============================================================

def collect_frames(source: UsSource, as_of: pd.Timestamp, ciks: Iterable[int],
                   verbose: bool = True) -> Dict[int, dict]:
    """
    Rebuild a companyfacts-style dictionary per company from frames, so the
    Day 76 metric engine can be reused unchanged. Filing dates are not in
    frames; they are approximated as period end + 45 days (capped at as_of)
    and are used only for display.
    """
    wanted = set(int(c) for c in ciks)
    company_facts: Dict[int, dict] = defaultdict(lambda: {"facts": {"us-gaap": {}}})
    items = [(concept, UNITS.get(item, "USD"), "duration" if item in fe.FLOW_ITEMS else "instant")
             for item, concepts in fe.CONCEPTS.items() for concept in concepts]
    items += [(concept, unit, kind) for concept, (unit, kind) in SHARE_CONCEPTS.items()]
    total = sum(len(frame_periods(as_of, kind)) for _, _, kind in items)
    done = 0
    for concept, unit, kind in items:
        for period in frame_periods(as_of, kind):
            done += 1
            try:
                rows = source.frame(concept, unit, period)
            except Exception:
                rows = []
            for row in rows:
                cik = int(row.get("cik", -1))
                if cik not in wanted:
                    continue
                end = pd.Timestamp(row["end"])
                filed = min(end + pd.Timedelta(days=45), as_of)
                days = (end - pd.Timestamp(row["start"])).days if row.get("start") else None
                fact = {"end": row["end"], "val": row["val"], "filed": str(filed.date()),
                        "form": "10-K" if days and days > 300 else "10-Q"}
                if row.get("start"):
                    fact["start"] = row["start"]
                node = company_facts[cik]["facts"]["us-gaap"].setdefault(concept, {"units": {unit: []}})
                node["units"][unit].append(fact)
            if verbose and done % 100 == 0:
                print(f"  SEC frames: {done}/{total}")
    return dict(company_facts)


PARALLEL_THRESHOLD = 300


def company_metrics_task(task) -> dict:
    """Metrics for one company (module-level so worker processes can run it)."""
    info, facts, as_of, price = task
    record = {**info, "error": ""}
    if facts is None:
        record["error"] = "no XBRL financial data in frames"
    else:
        try:
            record.update(fe.compute_company_metrics(facts, as_of, price, info["sector"]))
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"[:200]
    record.setdefault("price", price)
    return record


# ==============================================================
# SCORING (sector-relative)
# ==============================================================

def sector_relative_scores(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Percentile scores within each sector that has at least MIN_SECTOR_SIZE
    scored companies; smaller sectors are ranked against the whole universe.
    """
    sector_sizes = metrics["sector"].map(metrics["sector"].value_counts())
    groups = np.where(sector_sizes >= MIN_SECTOR_SIZE, metrics["sector"], "__universe__")
    scores = pd.DataFrame(index=metrics.index)
    for pillar, items in fe.PILLARS.items():
        columns = []
        for metric, higher_is_better, _ in items:
            values = pd.to_numeric(metrics[metric], errors="coerce")
            if values.notna().sum() < 3:
                continue
            ranked = values.groupby(groups).rank(pct=True, ascending=higher_is_better) * 100
            scores[f"{metric}_score"] = ranked
            columns.append(f"{metric}_score")
        is_financial = metrics["sector"].eq(fe.FINANCIALS_SECTOR)
        needed = np.where(is_financial,
                          max(1, -(-sum(1 for i in items if i[2]) // 2)),
                          max(1, -(-len(items) // 2)))
        available = scores[columns].notna().sum(axis=1) if columns else 0
        pillar_score = scores[columns].mean(axis=1) if columns else np.nan
        scores[f"{pillar}_score"] = pd.Series(pillar_score, index=scores.index).where(available >= needed)
    pillar_columns = [f"{p}_score" for p in fe.PILLARS]
    scores["fundamental_score"] = scores[pillar_columns].mean(axis=1).where(
        scores[pillar_columns].notna().sum(axis=1) >= 3)
    scores["sector_rank"] = scores["fundamental_score"].groupby(metrics["sector"]).rank(
        ascending=False, method="min")
    scores["market_rank"] = scores["fundamental_score"].rank(ascending=False, method="min")
    scores["ranking_group"] = np.where(groups == "__universe__", "universe", "sector")
    return scores


# ==============================================================
# VALIDATION
# ==============================================================

def validate_us(universe: pd.DataFrame, metrics: pd.DataFrame, scores: pd.DataFrame,
                expected_size: int = 3000) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    included = universe[universe["included"]]
    add("Universe size", len(included) >= expected_size,
        f"{len(included)} listed operating companies (expected at least {expected_size})")
    classified = included["sector"].ne("Unclassified").mean() if len(included) else 0
    add("Sector classification", classified >= 0.95, f"{classified:.1%} mapped from SIC codes")
    revenue = metrics["revenue_ttm"].notna().mean() if len(metrics) else 0
    add("TTM revenue coverage", revenue >= 0.8, f"{revenue:.1%} of companies")
    priced = metrics["price"].notna().mean() if len(metrics) else 0
    add("Price coverage", priced >= 0.85, f"{priced:.1%} of companies")
    caps = pd.to_numeric(metrics["market_cap"], errors="coerce")
    add("Market cap coverage", caps.notna().mean() >= 0.8 and (caps.dropna() > 0).all(),
        f"{caps.notna().mean():.1%} of companies")
    margins = pd.to_numeric(metrics["gross_margin"], errors="coerce").dropna()
    implausible = (margins.abs() > 1).mean() if len(margins) else 0
    add("Gross margins plausible", implausible < 0.01, f"{implausible:.2%} outside ±100%")
    values = pd.to_numeric(scores.filter(like="_score").stack(), errors="coerce").dropna()
    add("Scores between 0 and 100", values.between(0, 100).all(), "All percentile scores")
    composite = scores["fundamental_score"].notna().mean() if len(scores) else 0
    add("Composite score coverage", composite >= 0.7, f"{composite:.1%} of companies")
    sector_ranked = scores["ranking_group"].eq("sector").mean() if len(scores) else 0
    add("Sector-relative ranking", sector_ranked >= 0.9, f"{sector_ranked:.1%} ranked within their sector")
    research = set(fe.load_universe()) if expected_size >= 3000 else set()
    missing = sorted(research - set(metrics.index))
    add("Research universe included", not missing, f"Missing: {', '.join(missing) or 'none'}")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def run_us_fundamentals(as_of: Optional[pd.Timestamp] = None, source: Optional[UsSource] = None,
                        limit: Optional[int] = None, out_dir: Path = BASE_DIR,
                        expected_size: int = 3000, verbose: bool = True):
    as_of = (as_of or pd.Timestamp.now()).normalize()
    source = source or UsSource()
    started = time.time()

    if verbose:
        print("Step 1/4: US-listed universe and SEC industry codes")
    universe = build_universe(source, limit, verbose)
    included = universe[universe["included"]].copy()

    if verbose:
        print("Step 2/4: SEC XBRL frames (all companies per request)")
    company_facts = collect_frames(source, as_of, included["cik"], verbose)

    if verbose:
        print("Step 3/4: prices (Yahoo Finance)")
    prices = source.prices(included["ticker"].tolist())

    if verbose:
        print("Step 4/4: metrics and scores")
    tasks = [
        ({"ticker": row.ticker, "cik": row.cik, "name": row.name, "exchange": row.exchange,
          "sector": row.sector, "sic": row.sic},
         company_facts.get(int(row.cik)), as_of, prices.get(row.ticker))
        for row in included.itertuples(index=False)
    ]
    workers = min(8, os.cpu_count() or 1)
    if workers > 1 and len(tasks) >= PARALLEL_THRESHOLD:
        # Companies are independent, so they are computed in parallel.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(company_metrics_task, tasks, chunksize=50))
    else:
        rows = [company_metrics_task(task) for task in tasks]

    metrics = pd.DataFrame(rows).set_index("ticker")
    metrics["as_of"] = as_of.date()
    for column in ["market_cap", "revenue_ttm", "gross_margin", "price"] + \
            [m for p in fe.PILLARS.values() for m, _, _ in p]:
        if column not in metrics.columns:
            metrics[column] = np.nan
    has_data = metrics["error"].eq("")
    scores = sector_relative_scores(metrics[has_data])
    scores.insert(0, "market_cap", metrics.loc[has_data, "market_cap"])
    scores.insert(0, "sector", metrics.loc[has_data, "sector"])
    scores.insert(0, "name", metrics.loc[has_data, "name"])
    scores = scores.sort_values("market_rank")
    validation = validate_us(universe, metrics[has_data], scores, expected_size)

    out_dir = Path(out_dir)
    universe.to_csv(out_dir / OUTPUT_UNIVERSE, index=False)
    metrics.to_csv(out_dir / OUTPUT_METRICS)
    scores.to_csv(out_dir / OUTPUT_SCORES)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)

    if verbose:
        print_report(as_of, universe, metrics, scores, validation, time.time() - started)
    return universe, metrics, scores, validation


def print_report(as_of, universe, metrics, scores, validation, seconds) -> None:
    line = "=" * 92
    print(line)
    print(f"VITTANTRA — DAY 76b US MARKET FUNDAMENTALS (as of {as_of.date()}, SEC EDGAR frames)")
    print(line)
    included = universe["included"].sum()
    print(f"Listed companies: {len(universe)}  |  operating companies analysed: {included}  "
          f"|  scored: {int(scores['fundamental_score'].notna().sum())}  |  {seconds / 60:.1f} min")
    print("\nCompanies by sector")
    print(scores.groupby("sector")["fundamental_score"].agg(["count", "median"]).round(1).to_string())
    print("\nTop 15 by fundamental score (market cap ≥ $1B)")
    large = scores[pd.to_numeric(scores["market_cap"], errors="coerce") >= 1e9]
    columns = ["name", "sector", "value_score", "growth_score", "quality_score",
               "financial_health_score", "fundamental_score"]
    print(large.head(15)[columns].round(0).to_string())
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 76b US market fundamentals complete. Scores are research inputs, not recommendations.")
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fundamentals for all US-listed stocks (SEC frames)")
    parser.add_argument("--limit", type=int, help="analyse only the first N companies (testing)")
    args = parser.parse_args()
    run_us_fundamentals(limit=args.limit, expected_size=3000 if not args.limit else 1)


if __name__ == "__main__":
    main()
