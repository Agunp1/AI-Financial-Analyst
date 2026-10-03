"""
Day 76 — Vittantra Fundamental Engine

Builds point-in-time fundamental metrics and scores for the 33-stock
research universe from SEC EDGAR company filings (10-K and 10-Q XBRL
data). Free and official; no API key.

Framework
---------
1. Point in time: only facts FILED on or before the as-of date are used,
   so a backtest never sees numbers before they were public.
2. Restatements: when a period is reported more than once, the latest
   filing available at the as-of date wins.
3. Flow items (revenue, earnings, cash flow) use trailing twelve months:
       TTM = last fiscal year + current year-to-date − prior year-to-date
4. Stock items (assets, equity, debt) use the latest balance sheet;
   returns on capital use the average of now and one year earlier.
5. Valuation uses yields (E/P, FCF/P, B/P, S/P, EBIT/EV) rather than
   multiples, so negative earnings rank correctly.
6. Scores are cross-sectional percentiles (0-100) within the universe.
   Metrics that are not meaningful for banks and asset managers (gross
   margin, current ratio, leverage, EV-based ratios) are excluded for
   the Financials sector.

SEC fair-access rules require a User-Agent with a contact email. Add to
your .env file:
    SEC_USER_AGENT=Your Name your.email@example.com

Usage
-----
python fundamental_engine.py                    # as of today
python fundamental_engine.py --as-of 2025-06-30 # point-in-time snapshot

Research only. Scores are not investment recommendations.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "sec_cache"
CACHE_MAX_AGE_HOURS = 24
SEC_REQUEST_PAUSE_SECONDS = 0.15      # SEC allows at most 10 requests/second

OUTPUT_METRICS = "day76_fundamental_metrics.csv"
OUTPUT_SCORES = "day76_fundamental_scores.csv"
OUTPUT_COVERAGE = "day76_data_coverage.csv"
OUTPUT_VALIDATION = "day76_validation_summary.csv"

FILING_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
FINANCIALS_SECTOR = "Financials"


# ==============================================================
# XBRL CONCEPTS (first available, most recently reported wins)
# ==============================================================

CONCEPTS: Dict[str, List[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "RevenuesNetOfInterestExpense",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "long_term_debt_total": ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"],
    "long_term_debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermNotesPayable",
        "SeniorNotes",
    ],
    "long_term_debt_current": [
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "DebtCurrent",
    ],
    "short_term_debt": ["ShortTermBorrowings", "CommercialPaper"],
}

PEER_GROUP_METRICS = {"equity_to_assets"}

FLOW_ITEMS = {
    "revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income",
    "eps_diluted", "operating_cash_flow", "capex", "depreciation", "interest_expense",
}

# Score pillars: (metric, higher_is_better, applies_to_financials)
PILLARS: Dict[str, List[tuple]] = {
    "value": [
        ("earnings_yield", True, True),
        ("fcf_yield", True, False),
        ("book_to_price", True, True),
        ("sales_to_price", True, True),
        ("ebit_to_ev", True, False),
    ],
    "growth": [
        ("revenue_growth", True, True),
        ("eps_growth", True, True),
        ("operating_income_growth", True, True),
    ],
    "quality": [
        ("roe", True, True),
        ("roa", True, True),
        ("gross_margin", True, False),
        ("operating_margin", True, True),
        ("accruals_ratio", False, False),
    ],
    "financial_health": [
        ("debt_to_equity", False, False),
        ("current_ratio", True, False),
        ("interest_coverage", True, False),
        ("net_debt_to_ebitda", False, False),
        ("equity_to_assets", True, True),
    ],
}


# ==============================================================
# SEC DATA ACCESS (replaceable in tests)
# ==============================================================

def sec_user_agent() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass
    agent = os.getenv("SEC_USER_AGENT", "").strip()
    if "@" not in agent:
        raise RuntimeError(
            "SEC requires a contact email. Add this line to your .env file:\n"
            "    SEC_USER_AGENT=Your Name your.email@example.com"
        )
    return agent


def _sec_get_json(url: str) -> dict:
    import requests

    response = requests.get(url, headers={"User-Agent": sec_user_agent()}, timeout=30)
    response.raise_for_status()
    time.sleep(SEC_REQUEST_PAUSE_SECONDS)
    return response.json()


def _cached_json(path: Path, fetch: Callable[[], dict]) -> dict:
    """Use the cached copy if fresh; otherwise download, falling back to stale cache."""
    if path.exists():
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            return json.loads(path.read_text())
    try:
        data = fetch()
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))
        return data
    except Exception:
        if path.exists():
            return json.loads(path.read_text())
        raise


def fetch_ticker_map() -> Dict[str, int]:
    data = _cached_json(
        CACHE_DIR / "company_tickers.json",
        lambda: _sec_get_json("https://www.sec.gov/files/company_tickers.json"),
    )
    return {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}


def fetch_company_facts(cik: int) -> dict:
    return _cached_json(
        CACHE_DIR / f"CIK{cik:010d}.json",
        lambda: _sec_get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"),
    )


@dataclass
class SecSource:
    ticker_map: Callable[[], Dict[str, int]] = fetch_ticker_map
    company_facts: Callable[[int], dict] = fetch_company_facts


# ==============================================================
# POINT-IN-TIME FACT EXTRACTION
# ==============================================================

def facts_frame(company_facts: dict, taxonomy: str, concept: str, as_of: pd.Timestamp) -> pd.DataFrame:
    """
    All values of one concept known at as_of: one row per reporting period,
    keeping the latest filing (restatement) filed on or before as_of.
    """
    node = company_facts.get("facts", {}).get(taxonomy, {}).get(concept)
    if not node:
        return pd.DataFrame()
    rows = [row for values in node.get("units", {}).values() for row in values]
    df = pd.DataFrame(rows)
    if df.empty or "filed" not in df.columns:
        return pd.DataFrame()
    df["filed"] = pd.to_datetime(df["filed"])
    df["end"] = pd.to_datetime(df["end"])
    df["start"] = pd.to_datetime(df["start"]) if "start" in df.columns else pd.NaT
    df = df[(df["filed"] <= as_of) & df.get("form", pd.Series("10-K", index=df.index)).isin(FILING_FORMS)]
    if df.empty:
        return df
    df = df.sort_values("filed").drop_duplicates(subset=["start", "end"], keep="last")
    df["days"] = (df["end"] - df["start"]).dt.days
    return df.sort_values("end").reset_index(drop=True)


# Items where several tags can describe nested amounts (for example REIT
# lease income sits outside "contract revenue"): the largest is the total.
TAKE_LARGEST = {"revenue"}


def concept_frame(company_facts: dict, item: str, as_of: pd.Timestamp) -> pd.DataFrame:
    """
    Pick the candidate concept with the most recent period (companies change
    tags over time). For revenue, among tags reporting that latest period,
    take the one with the largest annual-scale value, since narrower tags
    (contract revenue, product revenue) are components of the total.
    """
    candidates = []
    for concept in CONCEPTS[item]:
        df = facts_frame(company_facts, "us-gaap", concept, as_of)
        if not df.empty:
            candidates.append(df)
    if not candidates:
        return pd.DataFrame()
    latest = max(df["end"].max() for df in candidates)
    current = [df for df in candidates if _near(df["end"], latest, 7).any()]
    if item in TAKE_LARGEST and len(current) > 1:
        def size(df):
            at_latest = df[_near(df["end"], latest, 7)]
            longest = at_latest.sort_values("days").iloc[-1] if at_latest["days"].notna().any() else at_latest.iloc[-1]
            return abs(float(longest["val"]))
        return max(current, key=size)
    return current[0]


def _near(series: pd.Series, target: pd.Timestamp, tolerance_days: int) -> pd.Series:
    return (series - target).abs() <= pd.Timedelta(days=tolerance_days)


def ttm_value(df: pd.DataFrame, end: Optional[pd.Timestamp] = None) -> Optional[float]:
    """
    Trailing-twelve-month value of a flow item ending at `end` (default:
    the latest reported period end):

        annual report ending at `end`              → that value
        otherwise: last fiscal year + current YTD − prior-year YTD
        otherwise: sum of four consecutive quarters
    """
    if df.empty or df["days"].isna().all():
        return None
    durations = df.dropna(subset=["days"])
    if end is None:
        end = durations["end"].max()
    at_end = durations[_near(durations["end"], end, 7)]
    if at_end.empty:
        return None

    annual = at_end[at_end["days"].between(350, 380)]
    if not annual.empty:
        return float(annual.iloc[-1]["val"])

    ytd = at_end.sort_values("days").iloc[-1]
    prior = durations[
        _near(durations["end"], ytd["end"] - pd.Timedelta(days=365), 20)
        & (durations["days"] - ytd["days"]).abs().le(20)
    ]
    fiscal_years = durations[
        durations["days"].between(350, 380)
        & (durations["end"] < ytd["end"])
        & (durations["end"] > ytd["end"] - pd.Timedelta(days=380))
    ]
    if not prior.empty and not fiscal_years.empty:
        fiscal_year = fiscal_years.iloc[-1]
        # Valid only if the YTD period starts right after that fiscal year
        # ends (a lone quarter reported without YTD is not a YTD figure).
        starts_new_year = abs((ytd["start"] - fiscal_year["end"]).days) <= 7
        if starts_new_year:
            return float(fiscal_year["val"] + ytd["val"] - prior.iloc[-1]["val"])

    quarters = quarterly_series(durations)
    if quarters.empty:
        return None
    window = quarters[(quarters.index > end - pd.Timedelta(days=330))
                      & (quarters.index <= end + pd.Timedelta(days=7))]
    if len(window) >= 4:
        return float(window.tail(4).sum())
    return None


def quarterly_series(durations: pd.DataFrame) -> pd.Series:
    """
    Three-month values by quarter end, using reported quarters and deriving
    the missing ones from cumulative figures:
        quarter = YTD − shorter YTD with the same start
        Q4      = fiscal year − 9-month YTD, or fiscal year − (Q1+Q2+Q3)
    """
    quarters = {
        row["end"]: float(row["val"])
        for _, row in durations[durations["days"].between(80, 100)].iterrows()
    }
    cumulative = durations[durations["days"] > 100].sort_values("days")
    for _, longer in cumulative.iterrows():
        if any(abs((longer["end"] - q).days) <= 7 for q in quarters):
            continue
        same_start = durations[
            (durations["start"] == longer["start"])
            & (durations["end"] < longer["end"])
            & ((longer["days"] - durations["days"]) - 91).abs().le(15)
        ]
        if not same_start.empty:
            quarters[longer["end"]] = float(longer["val"] - same_start.iloc[-1]["val"])
            continue
        if 350 <= longer["days"] <= 380:
            inside = [v for q, v in quarters.items()
                      if longer["start"] < q < longer["end"] - pd.Timedelta(days=60)]
            if len(inside) == 3:
                quarters[longer["end"]] = float(longer["val"] - sum(inside))
    if not quarters:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return pd.Series(quarters, dtype=float).sort_index()


def latest_instant(df: pd.DataFrame, near: Optional[pd.Timestamp] = None, tolerance_days: int = 45):
    """(value, period end) of a balance-sheet item: latest, or the one nearest a date."""
    if df.empty:
        return None, None
    if near is not None:
        df = df[_near(df["end"], near, tolerance_days)]
        if df.empty:
            return None, None
        row = df.iloc[(df["end"] - near).abs().argsort().iloc[0]]
    else:
        row = df.iloc[-1]
    return float(row["val"]), row["end"]


def shares_outstanding(company_facts: dict, as_of: pd.Timestamp) -> Optional[float]:
    """
    Shares outstanding, in order of preference:
      1. Cover-page shares (dei), summed across share classes.
      2. Balance-sheet common shares outstanding.
      3. Diluted weighted-average shares of the latest quarter.
    Companies with several share classes (GOOGL, META) often tag shares per
    class with XBRL dimensions, which the free companyfacts API omits, so
    the fallbacks matter.
    """
    node = company_facts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding")
    if node:
        rows = pd.DataFrame([r for v in node.get("units", {}).values() for r in v])
        if not rows.empty:
            rows["filed"] = pd.to_datetime(rows["filed"])
            rows = rows[rows["filed"] <= as_of]
            if not rows.empty:
                latest_filing = rows[rows["filed"] == rows["filed"].max()]
                latest_end = latest_filing["end"].max()
                if (as_of - rows["filed"].max()).days <= 200:
                    return float(latest_filing[latest_filing["end"] == latest_end]["val"].sum())
    balance = facts_frame(company_facts, "us-gaap", "CommonStockSharesOutstanding", as_of)
    if not balance.empty and (as_of - balance["end"].max()).days <= 200:
        return float(balance.iloc[-1]["val"])
    diluted = facts_frame(company_facts, "us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding", as_of)
    if not diluted.empty:
        recent = diluted[diluted["days"].between(80, 100)]
        row = (recent if not recent.empty else diluted).iloc[-1]
        if (as_of - row["end"]).days <= 200:
            return float(row["val"])
    return None


# ==============================================================
# METRICS
# ==============================================================

def ratio(numerator, denominator, require_positive_denominator=False) -> Optional[float]:
    if numerator is None or denominator is None:
        return None
    if not (math.isfinite(numerator) and math.isfinite(denominator)) or denominator == 0:
        return None
    if require_positive_denominator and denominator <= 0:
        return None
    return float(numerator / denominator)


def average(a, b) -> Optional[float]:
    if a is None:
        return None
    return a if b is None else (a + b) / 2


def growth(current, previous) -> Optional[float]:
    """Growth relative to the absolute base, so a loss shrinking reads as growth."""
    if current is None or previous is None or previous == 0:
        return None
    return float((current - previous) / abs(previous))


def safe_ttm(df: pd.DataFrame, end) -> Optional[float]:
    """TTM that returns None instead of failing on an unusual filing pattern."""
    try:
        return ttm_value(df, end)
    except Exception:
        return None


def compute_company_metrics(company_facts: dict, as_of: pd.Timestamp,
                            price: Optional[float], sector: str) -> dict:
    frames = {item: concept_frame(company_facts, item, as_of) for item in CONCEPTS}
    out: dict = {}

    # Flow items: TTM now and one year earlier.
    # Latest reporting period: the most common latest period end among core
    # flow items, so one oddly tagged item cannot shift the whole company.
    core_ends = [frames[item]["end"].max() for item in
                 ("revenue", "net_income", "operating_income", "operating_cash_flow")
                 if not frames[item].empty]
    latest_end = (pd.Series(core_ends).mode().max() if core_ends else None)
    year_ago_end = None if latest_end is None else latest_end - pd.Timedelta(days=365)
    ttm, ttm_prior = {}, {}
    for item in FLOW_ITEMS:
        ttm[item] = safe_ttm(frames[item], latest_end) if latest_end is not None else None
        if ttm[item] is None and not frames[item].empty and latest_end is not None:
            own_end = frames[item]["end"].max()
            if abs((own_end - latest_end).days) <= 100:
                ttm[item] = safe_ttm(frames[item], own_end)
        prior_end = None
        if year_ago_end is not None and not frames[item].empty:
            ends = frames[item]["end"]
            close = ends[_near(ends, year_ago_end, 20)]
            prior_end = close.iloc[-1] if len(close) else None
        ttm_prior[item] = safe_ttm(frames[item], prior_end) if prior_end is not None else None

    if ttm["gross_profit"] is None and ttm["revenue"] is not None and ttm["cost_of_revenue"] is not None:
        ttm["gross_profit"] = ttm["revenue"] - ttm["cost_of_revenue"]

    # Stock items: latest and one year earlier.
    stock, stock_prior = {}, {}
    for item in CONCEPTS:
        if item in FLOW_ITEMS:
            continue
        value, end = latest_instant(frames[item])
        # Ignore balance-sheet tags that stopped being reported (stale).
        reference = latest_end if latest_end is not None else as_of
        if end is not None and end < reference - pd.Timedelta(days=120):
            value, end = None, None
        stock[item] = value
        stock_prior[item] = latest_instant(frames[item], end - pd.Timedelta(days=365))[0] if end is not None else None

    # Total long-term debt: the larger of the combined tag and the sum of its
    # current and non-current parts (companies use either presentation).
    split = None
    if stock["long_term_debt_noncurrent"] is not None:
        split = stock["long_term_debt_noncurrent"] + (stock["long_term_debt_current"] or 0.0)
    debt_options = [d for d in (stock["long_term_debt_total"], split) if d is not None]
    debt = max(debt_options) if debt_options else None
    if debt is not None or stock["short_term_debt"] is not None:
        debt = (debt or 0.0) + (stock["short_term_debt"] or 0.0)

    shares = shares_outstanding(company_facts, as_of)
    market_cap = price * shares if price and shares else None
    revenue, net_income = ttm["revenue"], ttm["net_income"]
    ebit = ttm["operating_income"]
    fcf = (ttm["operating_cash_flow"] - abs(ttm["capex"])
           if ttm["operating_cash_flow"] is not None and ttm["capex"] is not None else None)
    ebitda = ebit + ttm["depreciation"] if ebit is not None and ttm["depreciation"] is not None else None
    equity = stock["equity"]
    avg_equity = average(equity, stock_prior["equity"])
    avg_assets = average(stock["assets"], stock_prior["assets"])
    enterprise_value = (market_cap + (debt or 0.0) - (stock["cash"] or 0.0)
                        if market_cap is not None and debt is not None else None)
    net_debt = debt - (stock["cash"] or 0.0) if debt is not None else None
    filed_dates = [f["filed"].max() for f in frames.values() if not f.empty]

    out.update({
        "latest_period_end": latest_end,
        "latest_filing_date": max(filed_dates) if filed_dates else None,
        "price": price,
        "shares_outstanding": shares,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "revenue_ttm": revenue,
        "gross_profit_ttm": ttm["gross_profit"],
        "operating_income_ttm": ebit,
        "net_income_ttm": net_income,
        "eps_diluted_ttm": ttm["eps_diluted"],
        "free_cash_flow_ttm": fcf,
        "ebitda_ttm": ebitda,
        "total_debt": debt,
        "cash": stock["cash"],
        "equity": equity,
        "negative_equity": equity is not None and equity <= 0,
        # Value (yields: higher = cheaper)
        "earnings_yield": ratio(net_income, market_cap, True),
        "fcf_yield": ratio(fcf, market_cap, True),
        "book_to_price": ratio(equity, market_cap, True) if equity and equity > 0 else None,
        "sales_to_price": ratio(revenue, market_cap, True),
        "ebit_to_ev": ratio(ebit, enterprise_value, True),
        "pe_ratio": ratio(market_cap, net_income, True),
        # Growth (year over year, TTM vs TTM)
        "revenue_growth": growth(revenue, ttm_prior["revenue"]),
        "eps_growth": growth(ttm["eps_diluted"], ttm_prior["eps_diluted"]),
        "operating_income_growth": growth(ebit, ttm_prior["operating_income"]),
        # Quality / profitability
        "roe": ratio(net_income, avg_equity, True),
        "roa": ratio(net_income, avg_assets, True),
        "gross_margin": ratio(ttm["gross_profit"], revenue, True),
        "operating_margin": ratio(ebit, revenue, True),
        "net_margin": ratio(net_income, revenue, True),
        "accruals_ratio": (ratio(net_income - ttm["operating_cash_flow"], avg_assets, True)
                           if net_income is not None and ttm["operating_cash_flow"] is not None else None),
        # Financial health
        "debt_to_equity": ratio(debt, equity, True),
        "current_ratio": ratio(stock["current_assets"], stock["current_liabilities"], True),
        "interest_coverage": ratio(ebit, abs(ttm["interest_expense"]) if ttm["interest_expense"] else None, True),
        "net_debt_to_ebitda": ratio(net_debt, ebitda, True),
        # Capital strength: the leverage measure that also works for banks
        "equity_to_assets": ratio(equity, stock["assets"], True),
    })

    if sector == FINANCIALS_SECTOR:
        for pillar in PILLARS.values():
            for metric, _, applies in pillar:
                if not applies:
                    out[metric] = None
    return out


# ==============================================================
# SCORING
# ==============================================================

def percentile_scores(metrics: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional percentile (0-100) per metric, pillar averages, composite."""
    scores = pd.DataFrame(index=metrics.index)
    for pillar, items in PILLARS.items():
        columns = []
        for metric, higher_is_better, _ in items:
            values = pd.to_numeric(metrics[metric], errors="coerce")
            if values.notna().sum() < 3:
                continue
            if metric in PEER_GROUP_METRICS:
                # Banks run at ~8-10% equity/assets by design; compare them
                # with other financials, not with industrial companies.
                groups = metrics["sector"].eq(FINANCIALS_SECTOR)
                ranked = values.groupby(groups).rank(pct=True, ascending=higher_is_better) * 100
            else:
                ranked = values.rank(pct=True, ascending=higher_is_better) * 100
            scores[f"{metric}_score"] = ranked
            columns.append(f"{metric}_score")
        available = scores[columns].notna().sum(axis=1) if columns else pd.Series(0, index=scores.index)
        pillar_score = scores[columns].mean(axis=1) if columns else pd.Series(np.nan, index=scores.index)
        # Require at least half of the pillar's applicable metrics.
        needed = max(1, math.ceil(len(items) / 2))
        financial_needed = max(1, math.ceil(sum(1 for i in items if i[2]) / 2))
        is_financial = metrics["sector"].eq(FINANCIALS_SECTOR)
        threshold = np.where(is_financial, financial_needed, needed)
        scores[f"{pillar}_score"] = pillar_score.where(available >= threshold)
    pillar_columns = [f"{p}_score" for p in PILLARS]
    composite = scores[pillar_columns].mean(axis=1)
    scores["fundamental_score"] = composite.where(scores[pillar_columns].notna().sum(axis=1) >= 3)
    scores["fundamental_rank"] = scores["fundamental_score"].rank(ascending=False, method="min")
    return scores


# ==============================================================
# VALIDATION
# ==============================================================

def validate_day76(metrics: pd.DataFrame, scores: pd.DataFrame, universe_size: int,
                   as_of: pd.Timestamp) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    loaded = metrics["facts_loaded"]
    add("SEC filings loaded", loaded.mean() >= 0.9,
        f"{int(loaded.sum())} of {universe_size} companies")
    filed = pd.to_datetime(metrics["latest_filing_date"], errors="coerce")
    add("Point in time: no filing after as-of date", (filed.dropna() <= as_of).all(),
        f"Latest filing used: {filed.max()}; as of {as_of.date()}")
    recent = (as_of - filed).dt.days.le(135)
    add("Filings are recent (within 135 days)", recent[loaded].mean() >= 0.8 if loaded.any() else False,
        f"{int(recent.sum())} of {int(loaded.sum())} companies")
    revenue_ok = metrics.loc[loaded, "revenue_ttm"].notna().mean() if loaded.any() else 0
    add("TTM revenue available", revenue_ok >= 0.9, f"{revenue_ok:.0%} of loaded companies")
    caps = pd.to_numeric(metrics["market_cap"], errors="coerce")
    add("Market caps positive", (caps.dropna() > 0).all() and caps.notna().mean() >= 0.9,
        f"{int(caps.notna().sum())} market caps")
    margins = pd.to_numeric(metrics["gross_margin"], errors="coerce").dropna()
    add("Gross margins between 0% and 100%", margins.between(0, 1).all(),
        f"range {margins.min():.1%} to {margins.max():.1%}" if len(margins) else "none")
    score_values = pd.to_numeric(scores.filter(like="_score").stack(), errors="coerce").dropna()
    add("Scores between 0 and 100", score_values.between(0, 100).all(), "All percentile scores")
    loaded_index = metrics.index[loaded]
    for pillar in PILLARS:
        coverage = scores.loc[loaded_index, f"{pillar}_score"].notna().mean() if len(loaded_index) else 0.0
        add(f"{pillar.replace('_', ' ').title()} score coverage", coverage >= 0.8,
            f"{coverage:.0%} of loaded companies")
    composite = scores.loc[loaded_index, "fundamental_score"].notna().mean() if len(loaded_index) else 0.0
    add("Composite score coverage", composite >= 0.9, f"{composite:.0%}")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


# ==============================================================
# ORCHESTRATION
# ==============================================================

def load_universe() -> Dict[str, dict]:
    from market_universe_ingestion import UNIVERSE
    return UNIVERSE


def load_prices(path: Path = BASE_DIR / "day75_market_snapshot.csv") -> Dict[str, float]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["ticker"], pd.to_numeric(df["price"], errors="coerce")))


def run_fundamentals(as_of: Optional[pd.Timestamp] = None, source: Optional[SecSource] = None,
                     universe: Optional[Dict[str, dict]] = None, prices: Optional[Dict[str, float]] = None,
                     out_dir: Path = BASE_DIR, verbose: bool = True):
    as_of = (as_of or pd.Timestamp.now()).normalize()
    source = source or SecSource()
    universe = universe or load_universe()
    prices = load_prices() if prices is None else prices
    ticker_map = source.ticker_map()

    rows = []
    for ticker, info in universe.items():
        row = {"ticker": ticker, "name": info.get("name"), "sector": info.get("sector"),
               "cik": ticker_map.get(ticker.replace(".", "-").upper()), "facts_loaded": False,
               "error": ""}
        if row["cik"] is None:
            row["error"] = "CIK not found"
            rows.append(row)
            continue
        try:
            facts = source.company_facts(row["cik"])
            price = prices.get(ticker)
            price = float(price) if price is not None and pd.notna(price) else None
            row.update(compute_company_metrics(facts, as_of, price, row["sector"]))
            row["facts_loaded"] = True
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"[:200]
        rows.append(row)

    metrics = pd.DataFrame(rows).set_index("ticker")
    metrics["as_of"] = as_of.date()
    required = ["latest_filing_date", "latest_period_end", "market_cap", "revenue_ttm",
                "negative_equity"] + [m for p in PILLARS.values() for m, _, _ in p]
    for column in required:
        if column not in metrics.columns:
            metrics[column] = np.nan
    scores = percentile_scores(metrics)
    scores.insert(0, "sector", metrics["sector"])
    scores.insert(0, "name", metrics["name"])
    scores = scores.sort_values("fundamental_rank")
    coverage = metrics[[m for p in PILLARS.values() for m, _, _ in p]].notna()
    validation = validate_day76(metrics, scores, len(universe), as_of)

    out_dir = Path(out_dir)
    metrics.to_csv(out_dir / OUTPUT_METRICS)
    scores.to_csv(out_dir / OUTPUT_SCORES)
    coverage.to_csv(out_dir / OUTPUT_COVERAGE)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)

    if verbose:
        print_report(as_of, metrics, scores, validation)
    return metrics, scores, validation


def print_report(as_of, metrics, scores, validation) -> None:
    line = "=" * 90
    print(line)
    print(f"VITTANTRA — DAY 76 FUNDAMENTAL ENGINE (as of {as_of.date()}, source: SEC EDGAR)")
    print(line)
    pd.set_option("display.width", 200)
    columns = ["name", "sector", "value_score", "growth_score", "quality_score",
               "financial_health_score", "fundamental_score"]
    print(scores[columns].round(1).to_string())
    failed = metrics[metrics["error"].astype(str).str.len() > 0]
    if len(failed):
        print("\nCompanies not loaded:")
        print(failed[["error"]].to_string())
    filed = pd.to_datetime(metrics["latest_filing_date"], errors="coerce")
    stale = metrics.index[(as_of - filed).dt.days > 135].tolist()
    if stale:
        print(f"\nNo filing in the last 135 days (check SEC data; scores use older figures): "
              f"{', '.join(stale)}")
    incomplete = scores.index[scores["fundamental_score"].isna()].tolist()
    if incomplete:
        print(f"Not enough data for a composite score: {', '.join(incomplete)}")
    negative = metrics.index[metrics["negative_equity"].fillna(False).astype(bool)].tolist()
    if negative:
        print(f"\nNegative shareholders' equity (ROE, book/price and leverage not meaningful): "
              f"{', '.join(negative)}")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 76 fundamental analysis complete. Scores are research inputs, not recommendations.")
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vittantra fundamental engine (SEC EDGAR)")
    parser.add_argument("--as-of", help="point-in-time date, e.g. 2025-06-30")
    args = parser.parse_args()
    run_fundamentals(pd.Timestamp(args.as_of) if args.as_of else None)


if __name__ == "__main__":
    main()
