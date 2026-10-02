"""
Day 53 — Market Universe Expansion & Scalable Price Ingestion

Expand Vittantra's equity research universe beyond the original
five securities.

Goals:
1. Maintain a diversified equity universe across major sectors.
2. Download historical daily prices.
3. Validate incoming data.
4. Update hedge_fund.db without creating duplicate observations.
5. Maintain a security master.
6. Maintain an ingestion audit log.
7. Preserve the existing daily_prices schema used by Vittantra.

Research infrastructure only.
No investment recommendations.
"""

from pathlib import Path
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------
# PROJECT CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hedge_fund.db"

START_DATE = "2022-01-01"

# yfinance treats the end date as exclusive, so use tomorrow.
END_DATE = (
    pd.Timestamp.now().normalize()
    + pd.Timedelta(days=1)
).strftime("%Y-%m-%d")


# ---------------------------------------------------------
# RESEARCH UNIVERSE
# ---------------------------------------------------------

UNIVERSE = {
    # Information Technology
    "AAPL": {
        "name": "Apple",
        "sector": "Information Technology",
    },
    "MSFT": {
        "name": "Microsoft",
        "sector": "Information Technology",
    },
    "NVDA": {
        "name": "NVIDIA",
        "sector": "Information Technology",
    },

    # Financials
    "JPM": {
        "name": "JPMorgan Chase",
        "sector": "Financials",
    },
    "GS": {
        "name": "Goldman Sachs",
        "sector": "Financials",
    },
    "BLK": {
        "name": "BlackRock",
        "sector": "Financials",
    },

    # Health Care
    "JNJ": {
        "name": "Johnson & Johnson",
        "sector": "Health Care",
    },
    "LLY": {
        "name": "Eli Lilly",
        "sector": "Health Care",
    },
    "UNH": {
        "name": "UnitedHealth Group",
        "sector": "Health Care",
    },

    # Energy
    "XOM": {
        "name": "Exxon Mobil",
        "sector": "Energy",
    },
    "CVX": {
        "name": "Chevron",
        "sector": "Energy",
    },
    "COP": {
        "name": "ConocoPhillips",
        "sector": "Energy",
    },

    # Industrials
    "CAT": {
        "name": "Caterpillar",
        "sector": "Industrials",
    },
    "HON": {
        "name": "Honeywell",
        "sector": "Industrials",
    },
    "UNP": {
        "name": "Union Pacific",
        "sector": "Industrials",
    },

    # Consumer Discretionary
    "AMZN": {
        "name": "Amazon",
        "sector": "Consumer Discretionary",
    },
    "HD": {
        "name": "Home Depot",
        "sector": "Consumer Discretionary",
    },
    "MCD": {
        "name": "McDonald's",
        "sector": "Consumer Discretionary",
    },

    # Consumer Staples
    "PG": {
        "name": "Procter & Gamble",
        "sector": "Consumer Staples",
    },
    "KO": {
        "name": "Coca-Cola",
        "sector": "Consumer Staples",
    },
    "WMT": {
        "name": "Walmart",
        "sector": "Consumer Staples",
    },

    # Communication Services
    "GOOGL": {
        "name": "Alphabet",
        "sector": "Communication Services",
    },
    "META": {
        "name": "Meta Platforms",
        "sector": "Communication Services",
    },
    "DIS": {
        "name": "Walt Disney",
        "sector": "Communication Services",
    },

    # Utilities
    "NEE": {
        "name": "NextEra Energy",
        "sector": "Utilities",
    },
    "DUK": {
        "name": "Duke Energy",
        "sector": "Utilities",
    },
    "SO": {
        "name": "Southern Company",
        "sector": "Utilities",
    },

    # Real Estate
    "PLD": {
        "name": "Prologis",
        "sector": "Real Estate",
    },
    "AMT": {
        "name": "American Tower",
        "sector": "Real Estate",
    },
    "O": {
        "name": "Realty Income",
        "sector": "Real Estate",
    },

    # Materials
    "LIN": {
        "name": "Linde",
        "sector": "Materials",
    },
    "APD": {
        "name": "Air Products and Chemicals",
        "sector": "Materials",
    },
    "NEM": {
        "name": "Newmont",
        "sector": "Materials",
    },
}


# ---------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------

def create_supporting_tables(conn):
    """
    Create Day 53 metadata tables.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS security_master (
            ticker TEXT PRIMARY KEY,
            security_name TEXT,
            asset_class TEXT,
            sector TEXT,
            data_source TEXT,
            active INTEGER,
            updated_at TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_data_ingestion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            run_timestamp TEXT,
            requested_start TEXT,
            requested_end TEXT,
            rows_downloaded INTEGER,
            first_date TEXT,
            last_date TEXT,
            status TEXT,
            message TEXT
        )
        """
    )

    conn.commit()


def validate_daily_prices_table(conn):
    """
    Confirm Vittantra's existing price table contains
    the required fields.
    """

    columns = conn.execute(
        """
        PRAGMA table_info(daily_prices)
        """
    ).fetchall()

    if not columns:
        raise ValueError(
            "daily_prices table does not exist in hedge_fund.db."
        )

    column_names = {
        row[1]
        for row in columns
    }

    required = {
        "date",
        "ticker",
        "close_price",
    }

    missing = required - column_names

    if missing:
        raise ValueError(
            "daily_prices is missing required columns: "
            f"{sorted(missing)}"
        )


# ---------------------------------------------------------
# SECURITY MASTER
# ---------------------------------------------------------

def update_security_master(conn):
    """
    Store the Day 53 equity universe.
    """

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    for ticker, metadata in UNIVERSE.items():

        conn.execute(
            """
            INSERT INTO security_master (
                ticker,
                security_name,
                asset_class,
                sector,
                data_source,
                active,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(ticker)
            DO UPDATE SET
                security_name = excluded.security_name,
                asset_class = excluded.asset_class,
                sector = excluded.sector,
                data_source = excluded.data_source,
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (
                ticker,
                metadata["name"],
                "Equity",
                metadata["sector"],
                "Yahoo Finance",
                1,
                timestamp,
            ),
        )

    conn.commit()


# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------

def download_prices(
    ticker,
    start_date,
    end_date,
):
    """
    Download one security at a time.
    """

    history = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=False,
        actions=False,
        threads=False,
    )

    if history.empty:
        raise ValueError(
            "No price data returned."
        )

    if isinstance(
        history.columns,
        pd.MultiIndex,
    ):
        history.columns = (
            history.columns
            .get_level_values(0)
        )

    if "Close" not in history.columns:
        raise ValueError(
            "Downloaded data does not contain a Close column."
        )

    prices = (
        history[
            ["Close"]
        ]
        .reset_index()
        .rename(
            columns={
                "Date": "date",
                "Close": "close_price",
            }
        )
    )

    prices["date"] = pd.to_datetime(
        prices["date"]
    )

    try:
        prices["date"] = (
            prices["date"]
            .dt.tz_localize(None)
        )
    except TypeError:
        pass

    prices["date"] = (
        prices["date"]
        .dt.strftime("%Y-%m-%d")
    )

    prices["ticker"] = ticker

    prices["close_price"] = pd.to_numeric(
        prices["close_price"],
        errors="coerce",
    )

    prices = (
        prices[
            [
                "date",
                "ticker",
                "close_price",
            ]
        ]
        .dropna()
        .drop_duplicates(
            subset=[
                "date",
                "ticker",
            ],
            keep="last",
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    return prices


# ---------------------------------------------------------
# DATA VALIDATION
# ---------------------------------------------------------

def validate_prices(
    ticker,
    prices,
):
    """
    Run integrity checks before loading prices.
    """

    problems = []

    if prices.empty:
        problems.append(
            "dataset is empty"
        )

    if (
        prices["close_price"] <= 0
    ).any():
        problems.append(
            "non-positive close price detected"
        )

    if prices.duplicated(
        subset=[
            "date",
            "ticker",
        ]
    ).any():
        problems.append(
            "duplicate date/ticker observations detected"
        )

    if (
        prices["ticker"] != ticker
    ).any():
        problems.append(
            "unexpected ticker found in dataset"
        )

    if len(prices) < 100:
        problems.append(
            "fewer than 100 observations returned"
        )

    return problems


# ---------------------------------------------------------
# DATABASE WRITE
# ---------------------------------------------------------

def replace_ticker_prices(
    conn,
    ticker,
    prices,
):
    """
    Replace the downloaded date range for one ticker.
    """

    first_date = (
        prices["date"]
        .min()
    )

    last_date = (
        prices["date"]
        .max()
    )

    conn.execute(
        """
        DELETE FROM daily_prices
        WHERE ticker = ?
          AND date >= ?
          AND date <= ?
        """,
        (
            ticker,
            first_date,
            last_date,
        ),
    )

    records = list(
        prices[
            [
                "date",
                "ticker",
                "close_price",
            ]
        ]
        .itertuples(
            index=False,
            name=None,
        )
    )

    conn.executemany(
        """
        INSERT INTO daily_prices (
            date,
            ticker,
            close_price
        )
        VALUES (?, ?, ?)
        """,
        records,
    )

    conn.commit()


# ---------------------------------------------------------
# INGESTION AUDIT
# ---------------------------------------------------------

def write_log(
    conn,
    ticker,
    rows_downloaded,
    first_date,
    last_date,
    status,
    message,
):
    """
    Record the result of each ingestion attempt.
    """

    conn.execute(
        """
        INSERT INTO market_data_ingestion_log (
            ticker,
            run_timestamp,
            requested_start,
            requested_end,
            rows_downloaded,
            first_date,
            last_date,
            status,
            message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker,
            datetime.now(
                timezone.utc
            ).isoformat(),
            START_DATE,
            END_DATE,
            rows_downloaded,
            first_date,
            last_date,
            status,
            message,
        ),
    )

    conn.commit()


# ---------------------------------------------------------
# DATABASE SUMMARY
# ---------------------------------------------------------

def show_database_summary(conn):
    """
    Display post-ingestion database coverage.
    """

    coverage = pd.read_sql_query(
        """
        SELECT
            dp.ticker,
            sm.sector,
            COUNT(*) AS observations,
            MIN(dp.date) AS first_date,
            MAX(dp.date) AS last_date
        FROM daily_prices dp

        LEFT JOIN security_master sm
            ON dp.ticker = sm.ticker

        GROUP BY
            dp.ticker,
            sm.sector

        ORDER BY
            sm.sector,
            dp.ticker
        """,
        conn,
    )

    print(
        "\nDATABASE COVERAGE AFTER INGESTION"
    )
    print("=" * 90)

    print(
        coverage.to_string(
            index=False
        )
    )

    return coverage


def show_sector_summary(conn):
    """
    Display active securities by sector.
    """

    sector_summary = pd.read_sql_query(
        """
        SELECT
            sector,
            COUNT(*) AS securities
        FROM security_master
        WHERE active = 1
        GROUP BY sector
        ORDER BY sector
        """,
        conn,
    )

    print(
        "\nACTIVE EQUITY UNIVERSE BY SECTOR"
    )
    print("=" * 70)

    print(
        sector_summary.to_string(
            index=False
        )
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print(
        "\nDAY 53 — MARKET UNIVERSE EXPANSION"
    )
    print("=" * 90)

    print(
        f"Database: {DB_PATH}"
    )

    print(
        f"Requested history: "
        f"{START_DATE} to {END_DATE}"
    )

    print(
        f"Target universe: "
        f"{len(UNIVERSE)} equities"
    )

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        validate_daily_prices_table(
            conn
        )

        create_supporting_tables(
            conn
        )

        update_security_master(
            conn
        )

        successful = []
        failed = []

        for position, ticker in enumerate(
            UNIVERSE,
            start=1,
        ):

            metadata = (
                UNIVERSE[ticker]
            )

            print(
                f"\n[{position}/{len(UNIVERSE)}] "
                f"{ticker} — "
                f"{metadata['name']} "
                f"({metadata['sector']})"
            )

            try:

                prices = download_prices(
                    ticker,
                    START_DATE,
                    END_DATE,
                )

                problems = validate_prices(
                    ticker,
                    prices,
                )

                if problems:

                    raise ValueError(
                        "; ".join(problems)
                    )

                replace_ticker_prices(
                    conn,
                    ticker,
                    prices,
                )

                first_date = (
                    prices["date"]
                    .min()
                )

                last_date = (
                    prices["date"]
                    .max()
                )

                write_log(
                    conn=conn,
                    ticker=ticker,
                    rows_downloaded=len(
                        prices
                    ),
                    first_date=first_date,
                    last_date=last_date,
                    status="SUCCESS",
                    message="Validated and loaded.",
                )

                successful.append(
                    ticker
                )

                print(
                    f"  SUCCESS — "
                    f"{len(prices)} rows | "
                    f"{first_date} to "
                    f"{last_date}"
                )

            except Exception as exc:

                failed.append(
                    ticker
                )

                write_log(
                    conn=conn,
                    ticker=ticker,
                    rows_downloaded=0,
                    first_date=None,
                    last_date=None,
                    status="FAILED",
                    message=str(exc),
                )

                print(
                    f"  FAILED — {exc}"
                )

        print(
            "\nINGESTION SUMMARY"
        )
        print("=" * 90)

        print(
            f"Successful: "
            f"{len(successful)} / "
            f"{len(UNIVERSE)}"
        )

        print(
            f"Failed: "
            f"{len(failed)}"
        )

        if failed:

            print(
                "Failed tickers: "
                + ", ".join(
                    failed
                )
            )

        show_sector_summary(
            conn
        )

        coverage = show_database_summary(
            conn
        )

        print(
            "\nFINAL DATABASE TOTALS"
        )
        print("=" * 90)

        print(
            "Securities with price data: "
            f"{coverage['ticker'].nunique()}"
        )

        print(
            "Total daily-price observations: "
            f"{coverage['observations'].sum():,}"
        )

        if not coverage.empty:

            print(
                "Earliest database date: "
                f"{coverage['first_date'].min()}"
            )

            print(
                "Latest database date: "
                f"{coverage['last_date'].max()}"
            )

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 90)

    print(
        "- Day 53 expands Vittantra's research dataset rather than "
        "changing ML models."
        "\n- Securities were selected before observing Day 53 ML results."
        "\n- The universe spans major U.S. equity sectors."
        "\n- Each ticker is downloaded and validated independently."
        "\n- Failed downloads do not stop the entire ingestion process."
        "\n- Existing price rows within the downloaded range are replaced "
        "to prevent duplicate date/ticker observations."
        "\n- security_master separates instrument metadata from price history."
        "\n- market_data_ingestion_log creates an audit trail."
        "\n- Yahoo Finance is being used here as a research data source."
        "\n- This remains an equity-only universe; cross-asset expansion "
        "will require asset-specific metadata and models."
        "\n- Larger datasets improve research capacity but do not "
        "guarantee predictive performance."
    )


if __name__ == "__main__":
    main()