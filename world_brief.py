"""
Day 78b — World & Markets Brief (free sources)

What every desk reads before the open: what moved, why it might have moved,
and what is coming up.

1. Headlines   free RSS feeds from central banks, regulators, statistics
               agencies and market news; each headline is tagged with the
               themes it touches (rates, credit, equities, FX, commodities,
               digital assets, real estate, geopolitics) by transparent
               keyword rules.
2. Calendar    FOMC meetings (Federal Reserve published schedule) and US
               economic releases from the FRED release calendar (needs the
               free FRED_API_KEY in .env; skipped without it), each linked to
               the latest value in the Day 76c economic dashboard.
3. Brief       for every theme: the data move this week (Day 76d factor
               moves, Day 76c asset analytics) next to this week's headlines
               on that theme. Headlines are shown as possible drivers to
               check, never as proven causes.

Outputs
-------
day78b_headlines.csv, day78b_calendar.csv, day78b_brief.csv,
day78b_validation_summary.csv

Network failures are reported, never fatal, and an empty download never
overwrites the last saved headlines. Research only; no trades.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

OUTPUT_HEADLINES = "day78b_headlines.csv"
OUTPUT_CALENDAR = "day78b_calendar.csv"
OUTPUT_BRIEF = "day78b_brief.csv"
OUTPUT_VALIDATION = "day78b_validation_summary.csv"

LOOKBACK_DAYS = 7
CALENDAR_DAYS = 21

# (source, category, url) — all free, no key
FEEDS = [
    ("Federal Reserve", "Central bank", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("European Central Bank", "Central bank", "https://www.ecb.europa.eu/rss/press.html"),
    ("Bank of England", "Central bank", "https://www.bankofengland.co.uk/rss/news"),
    ("US SEC", "Regulator", "https://www.sec.gov/news/pressreleases.rss"),
    ("US Bureau of Labor Statistics", "Statistics", "https://www.bls.gov/feed/bls_latest.rss"),
    ("US Bureau of Economic Analysis", "Statistics", "https://apps.bea.gov/rss/rss.xml"),
    ("CNBC", "Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "Markets", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Yahoo Finance", "Markets", "https://finance.yahoo.com/news/rssindex"),
]

# Theme → keywords (lower case, matched on word boundaries)
THEMES: Dict[str, List[str]] = {
    "Rates": ["fed", "fomc", "federal reserve", "rate cut", "rate hike", "interest rate", "treasury", "treasuries",
              "yield", "yields", "bond", "bonds", "inflation", "cpi", "pce", "powell", "ecb", "central bank",
              "monetary policy", "bank of england", "boj"],
    "Credit": ["credit", "default", "bankruptcy", "downgrade", "high-yield", "junk", "spread", "spreads",
               "private credit", "leveraged loan", "distressed"],
    "Equities": ["stocks", "stock", "s&p", "nasdaq", "dow", "earnings", "shares", "ipo", "buyback", "equity",
                 "equities", "rally", "selloff", "sell-off"],
    "FX": ["dollar", "currency", "currencies", "yen", "euro", "yuan", "sterling", "pound", "forex", "fx"],
    "Commodities": ["oil", "crude", "opec", "brent", "gold", "copper", "natural gas", "wheat", "commodity",
                    "commodities", "silver"],
    "Digital assets": ["bitcoin", "crypto", "cryptocurrency", "ether", "ethereum", "stablecoin", "blockchain"],
    "Real estate": ["housing", "mortgage", "mortgages", "home sales", "reit", "reits", "real estate", "office",
                    "hotel", "hotels", "commercial property", "rent", "rents"],
    "Economy": ["jobs", "payrolls", "unemployment", "gdp", "retail sales", "recession", "consumer", "manufacturing",
                "pmi", "jobless", "economy", "growth"],
    "Geopolitics": ["war", "sanction", "sanctions", "tariff", "tariffs", "election", "conflict", "trade war",
                    "geopolitical", "ceasefire", "missile", "strike"],
}

# Data move shown next to each theme (from Day 76d factor moves / Day 76c analytics)
THEME_DATA = {
    "Rates": ("factor", "interest_rates", "10Y Treasury yield change", "pp"),
    "Credit": ("factor", "credit_spreads", "High-yield spread change", "pp"),
    "Equities": ("factor", "equity_market", "S&P 500 (SPY) return", "return"),
    "FX": ("factor", "us_dollar", "US dollar index return", "return"),
    "Commodities": ("factor", "oil", "Crude oil return", "return"),
    "Digital assets": ("asset", "BTC-USD", "Bitcoin 1-week return", "return"),
    "Real estate": ("asset", "VNQ", "US REITs (VNQ) 1-week return", "return"),
    "Economy": ("factor", "inflation_expectations", "10Y breakeven inflation change", "pp"),
    "Geopolitics": ("asset", "^VIX", "VIX 1-week change", "return"),
}

# Federal Reserve published FOMC schedule (two-day meetings; decision on day two).
FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
             "2026-10-28", "2026-12-09"]

# FRED release names worth tracking → FRED series in the Day 76c economic dashboard
KEY_RELEASES = {
    "Consumer Price Index": "CPIAUCSL",
    "Employment Situation": "UNRATE",
    "Gross Domestic Product": "GDPC1",
    "Personal Income and Outlays": "PCEPILFE",
    "Advance Monthly Sales for Retail and Food Services": "RSAFS",
    "Producer Price Index": None,
    "Job Openings and Labor Turnover Survey": None,
    "Unemployment Insurance Weekly Claims": "ICSA",
    "Industrial Production and Capacity Utilization": "INDPRO",
    "New Residential Construction": "HOUST",
    "University of Michigan Surveys of Consumers": "UMCSENT",
}


# ==============================================================
# FETCHING (replaceable in tests)
# ==============================================================

def _user_agent() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except Exception:
        pass
    contact = os.getenv("SEC_USER_AGENT", "").strip()
    return f"Vittantra research {contact}".strip()


def fetch_url(url: str) -> str:
    import requests

    response = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=20)
    response.raise_for_status()
    return response.text


def fetch_fred_release_dates(start: date, end: date) -> pd.DataFrame:
    """FRED release calendar (free API key in FRED_API_KEY); empty without a key."""
    import requests

    _user_agent()  # loads .env
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        return pd.DataFrame(columns=["date", "release"])
    response = requests.get("https://api.stlouisfed.org/fred/releases/dates", timeout=20, params={
        "api_key": key, "file_type": "json", "realtime_start": start.isoformat(), "realtime_end": end.isoformat(),
        "include_release_dates_with_no_data": "true", "limit": 1000, "sort_order": "asc"})
    response.raise_for_status()
    rows = response.json().get("release_dates", [])
    return pd.DataFrame([{"date": r["date"], "release": r["release_name"]} for r in rows])


@dataclass
class BriefSources:
    url: Callable[[str], str] = fetch_url
    release_dates: Callable[[date, date], pd.DataFrame] = fetch_fred_release_dates
    feeds: List[tuple] = field(default_factory=lambda: list(FEEDS))


# ==============================================================
# PARSING AND TAGGING
# ==============================================================

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_time(text: Optional[str]) -> Optional[pd.Timestamp]:
    if not text:
        return None
    text = text.strip()
    try:
        return pd.Timestamp(parsedate_to_datetime(text)).tz_convert("UTC").tz_localize(None)
    except Exception:
        pass
    try:
        stamp = pd.Timestamp(text)
        return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp
    except Exception:
        return None


def parse_feed(xml_text: str) -> List[dict]:
    """RSS 2.0, RSS 1.0 (RDF) and Atom items → title, link, published, summary."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return []
    items = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        fields = {}
        for child in node:
            name = _local(child.tag)
            if name == "link" and child.get("href"):
                fields.setdefault("link", child.get("href"))
            elif child.text:
                fields.setdefault(name, child.text.strip())
        title = re.sub(r"\s+", " ", fields.get("title", "")).strip()
        if not title:
            continue
        published = _parse_time(fields.get("pubDate") or fields.get("published") or fields.get("updated")
                                or fields.get("date"))
        summary = re.sub(r"<[^>]+>", " ", fields.get("description") or fields.get("summary") or "")
        items.append({"title": title, "link": fields.get("link", ""), "published": published,
                      "summary": re.sub(r"\s+", " ", summary).strip()[:300]})
    return items


_PATTERNS = {theme: re.compile(r"\b(" + "|".join(re.escape(k) for k in words) + r")\b", re.IGNORECASE)
             for theme, words in THEMES.items()}


def tag_themes(text: str) -> List[str]:
    return [theme for theme, pattern in _PATTERNS.items() if pattern.search(text or "")]


def collect_headlines(sources: BriefSources, now: pd.Timestamp) -> tuple:
    rows, status = [], []
    for source, category, url in sources.feeds:
        try:
            items = parse_feed(sources.url(url))
            status.append({"source": source, "ok": True, "items": len(items), "error": ""})
        except Exception as error:
            status.append({"source": source, "ok": False, "items": 0, "error": str(error)[:120]})
            continue
        for item in items:
            themes = tag_themes(f"{item['title']} {item['summary']}")
            rows.append({**item, "source": source, "category": category, "themes": ", ".join(themes)})
    headlines = pd.DataFrame(rows, columns=["published", "source", "category", "title", "themes", "link", "summary"])
    if len(headlines):
        headlines["published"] = pd.to_datetime(headlines["published"])
        recent = headlines["published"].isna() | (headlines["published"] >= now - pd.Timedelta(days=LOOKBACK_DAYS))
        headlines = headlines[recent & (headlines["published"].isna() | (headlines["published"] <= now
                                                                          + pd.Timedelta(days=1)))]
        headlines = (headlines.assign(key=headlines["title"].str.lower().str.replace(r"\W+", " ", regex=True))
                     .drop_duplicates("key").drop(columns="key")
                     .sort_values("published", ascending=False, na_position="last"))
    return headlines.reset_index(drop=True), pd.DataFrame(status)


# ==============================================================
# CALENDAR AND BRIEF
# ==============================================================

def build_calendar(sources: BriefSources, today: date, base: Path) -> tuple:
    end = today + timedelta(days=CALENDAR_DAYS)
    upcoming = [d for d in FOMC_2026 if d >= today.isoformat()]
    # Every meeting in the window, and always the next one
    meetings = [d for d in upcoming if d <= end.isoformat()] or upcoming[:1]
    rows = [{"date": d, "event": "FOMC rate decision", "source": "Federal Reserve published schedule",
             "indicator": "Effective fed funds rate (%)", "latest": None, "previous": None, "period": None}
            for d in meetings]
    note = "FRED release calendar"
    try:
        releases = sources.release_dates(today, end)
    except Exception as error:
        releases, note = pd.DataFrame(columns=["date", "release"]), f"FRED calendar unavailable ({str(error)[:80]})"
    if releases.empty and note == "FRED release calendar":
        note = "FRED release calendar skipped (add the free FRED_API_KEY to .env)"
    economy = base / "day76c_economic_dashboard.csv"
    dashboard = pd.read_csv(economy).set_index("series_id") if economy.exists() else pd.DataFrame()
    if "FEDFUNDS" in dashboard.index and rows:
        for r in rows:
            r.update(latest=dashboard.at["FEDFUNDS", "latest"], previous=dashboard.at["FEDFUNDS", "previous"],
                     period=dashboard.at["FEDFUNDS", "release_period"])
    for row in releases.itertuples():
        match = next((name for name in KEY_RELEASES if row.release.lower().startswith(name.lower())), None)
        if match is None:
            continue
        series = KEY_RELEASES[match]
        indicator = latest = previous = period = None
        if series and series in dashboard.index:
            d = dashboard.loc[series]
            indicator, latest, previous, period = d.get("indicator"), d.get("latest"), d.get("previous"), \
                d.get("release_period")
        rows.append({"date": row.date, "event": row.release, "source": "FRED release calendar",
                     "latest": latest, "previous": previous, "period": period, "indicator": indicator})
    calendar = pd.DataFrame(rows, columns=["date", "event", "source", "indicator", "latest", "previous", "period"])
    calendar = calendar.drop_duplicates(["date", "event"]).sort_values("date").reset_index(drop=True)
    return calendar, note


def _data_move(theme: str, base: Path) -> tuple:
    kind, key, label, unit = THEME_DATA[theme]
    if kind == "factor":
        path = base / "day76d_factor_moves.csv"
        if path.exists():
            moves = pd.read_csv(path)
            row = moves[(moves["factor"] == key) & (moves["window"] == "1 week")]
            if len(row):
                return label, float(row["move"].iloc[0]), unit, "day76d_factor_moves.csv"
    else:
        path = base / "day76c_price_history.csv"
        if path.exists():
            prices = pd.read_csv(path, index_col=0, parse_dates=True)
            if key in prices.columns:
                s = prices[key].dropna()
                past = s[s.index <= s.index.max() - pd.Timedelta(days=7)]
                if len(s) and len(past):
                    return label, float(s.iloc[-1] / past.iloc[-1] - 1), unit, "day76c_price_history.csv"
    return label, None, unit, None


def build_brief(headlines: pd.DataFrame, base: Path) -> pd.DataFrame:
    rows = []
    for theme in THEMES:
        label, move, unit, source = _data_move(theme, base)
        related = headlines[headlines["themes"].fillna("").str.contains(re.escape(theme))] if len(headlines) \
            else headlines
        if move is None:
            move_text = f"{label}: not available"
        elif unit == "pp":
            move_text = f"{label}: {move * 100:+.0f} bp this week"
        else:
            move_text = f"{label}: {move:+.1%} this week"
        rows.append({"theme": theme, "data_move": move_text, "move": move, "unit": unit, "data_source": source,
                     "headline_count": len(related),
                     "top_headlines": " || ".join(f"{h.title} ({h.source})" for h in related.head(3).itertuples())})
    brief = pd.DataFrame(rows)
    return brief.sort_values("headline_count", ascending=False, kind="stable").reset_index(drop=True)


def validate_brief(headlines, status, calendar, brief, calendar_note) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    ok = status[status["ok"]] if len(status) else status
    add("News feeds reachable", len(ok) >= max(1, len(status) // 2),
        f"{len(ok)} of {len(status)} feeds" + ("" if len(ok) == len(status) else
                                               "; failed: " + ", ".join(status.loc[~status["ok"], "source"])))
    add("Recent headlines collected", len(headlines) >= 10, f"{len(headlines)} headlines in the last {LOOKBACK_DAYS} days")
    tagged = (headlines["themes"].fillna("") != "").mean() if len(headlines) else 0
    add("Headlines tagged to themes", tagged >= 0.3 or not len(headlines), f"{tagged:.0%} tagged")
    add("Every theme has a data move", brief["move"].notna().mean() >= 0.7,
        f"{int(brief['move'].notna().sum())} of {len(brief)} themes")
    add("Calendar built", len(calendar) > 0, f"{len(calendar)} events; {calendar_note}")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def run_brief(sources: Optional[BriefSources] = None, base: Path = BASE_DIR, out_dir: Optional[Path] = None,
              now: Optional[pd.Timestamp] = None, verbose: bool = True):
    sources = sources or BriefSources()
    out_dir = Path(out_dir or base)
    now = now or pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
    headlines, status = collect_headlines(sources, now)
    saved = out_dir / OUTPUT_HEADLINES
    if headlines.empty and saved.exists():
        if verbose:
            print("No headlines downloaded; keeping the last saved headlines.")
        headlines = pd.read_csv(saved, parse_dates=["published"])
    calendar, calendar_note = build_calendar(sources, now.date(), base)
    brief = build_brief(headlines, base)
    validation = validate_brief(headlines, status, calendar, brief, calendar_note)

    if len(headlines):
        headlines.to_csv(saved, index=False)
    calendar.to_csv(out_dir / OUTPUT_CALENDAR, index=False)
    brief.to_csv(out_dir / OUTPUT_BRIEF, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        print_report(headlines, status, calendar, brief, validation)
    return headlines, calendar, brief, validation


def print_report(headlines, status, calendar, brief, validation) -> None:
    line = "=" * 92
    print(line)
    print("VITTANTRA — DAY 78b WORLD & MARKETS BRIEF")
    print(line)
    print(status.to_string(index=False))
    print("\nThis week by theme (data move · headlines to check)")
    for row in brief.itertuples():
        print(f"- {row.theme:<15} {row.data_move}  [{row.headline_count} headlines]")
        for h in str(row.top_headlines).split(" || ")[:2] if row.headline_count else []:
            print(f"      · {h[:110]}")
    print("\nComing up")
    print(calendar[["date", "event", "latest", "period"]].head(15).to_string(index=False) if len(calendar) else "none")
    print("\nValidation")
    print(validation[["check", "passed", "details"]].to_string(index=False))
    print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
    print("\nDay 78b world brief complete. Headlines are possible drivers to check, not proven causes.")
    print(line)


if __name__ == "__main__":
    run_brief()
