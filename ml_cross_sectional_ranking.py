"""
Vittantra
Day 55 — Cross-Sectional Ranking Engine

Purpose
-------
Move from binary security-by-security classification toward
cross-sectional ranking across the expanded equity universe.

Research questions
------------------
1. Can Vittantra rank securities by predicted 20-day upside probability?
2. Are the rankings broad across sectors?
3. Do top-ranked securities outperform bottom-ranked securities
   in subsequent 20-day returns?
4. Is there a monotonic relationship between model score and realized return?

Research safeguards
-------------------
- Uses only historical information available before each ranking date.
- Fits models separately at each ranking date.
- Uses a 20-trading-day purge between training and ranking date.
- Uses 20-day spaced ranking dates to reduce target overlap.
- Produces research rankings only.
- Does not send or execute trades.

Research only.
No investment recommendations.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("hedge_fund.db")

FORWARD_DAYS = 20
PURGE_OBSERVATIONS = 20
REBALANCE_STEP = 20

MIN_SECURITY_HISTORY = 250
MIN_CROSS_SECTION = 20
MIN_TRAIN_ROWS_PER_SECURITY = 120

RANDOM_STATE = 42

OUTPUT_RANKINGS = "day55_cross_sectional_rankings.csv"
OUTPUT_DECILES = "day55_score_bucket_summary.csv"
OUTPUT_DATES = "day55_ranking_date_summary.csv"
OUTPUT_SECTORS = "day55_sector_rank_summary.csv"


FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "momentum_20d",
    "distance_ma20",
    "distance_ma50",
]


# ============================================================
# DATABASE HELPERS
# ============================================================

def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found. Run this script from the "
            "AI-Financial-Analyst project directory."
        )

    return sqlite3.connect(DB_PATH)


def get_table_columns(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [
        row[1]
        for row in rows
    ]


def discover_price_schema(conn):
    columns = get_table_columns(
        conn,
        "daily_prices",
    )

    if not columns:
        raise RuntimeError(
            "daily_prices table was not found."
        )

    ticker_col = None
    date_col = None
    close_col = None

    for candidate in [
        "ticker",
        "symbol",
    ]:
        if candidate in columns:
            ticker_col = candidate
            break

    for candidate in [
        "date",
        "price_date",
        "trade_date",
    ]:
        if candidate in columns:
            date_col = candidate
            break

    for candidate in [
        "close_price",
        "close",
        "adj_close",
        "adjusted_close",
    ]:
        if candidate in columns:
            close_col = candidate
            break

    if ticker_col is None:
        raise RuntimeError(
            f"Ticker column not found. Columns: {columns}"
        )

    if date_col is None:
        raise RuntimeError(
            f"Date column not found. Columns: {columns}"
        )

    if close_col is None:
        raise RuntimeError(
            f"Close column not found. Columns: {columns}"
        )

    return {
        "ticker": ticker_col,
        "date": date_col,
        "close": close_col,
    }


def discover_master_schema(conn):
    columns = get_table_columns(
        conn,
        "security_master",
    )

    if not columns:
        return None

    ticker_col = None
    sector_col = None

    for candidate in [
        "ticker",
        "symbol",
    ]:
        if candidate in columns:
            ticker_col = candidate
            break

    for candidate in [
        "sector",
        "gics_sector",
        "industry_sector",
    ]:
        if candidate in columns:
            sector_col = candidate
            break

    if ticker_col is None:
        return None

    return {
        "ticker": ticker_col,
        "sector": sector_col,
    }


# ============================================================
# LOAD MARKET DATA
# ============================================================

def load_data():
    conn = connect_db()

    try:
        price_schema = discover_price_schema(
            conn
        )

        ticker_col = price_schema[
            "ticker"
        ]

        date_col = price_schema[
            "date"
        ]

        close_col = price_schema[
            "close"
        ]

        query = f"""
        SELECT
            {ticker_col} AS ticker,
            {date_col} AS date,
            {close_col} AS close
        FROM daily_prices
        WHERE {close_col} IS NOT NULL
        ORDER BY ticker, date
        """

        prices = pd.read_sql_query(
            query,
            conn,
        )

        master_schema = (
            discover_master_schema(
                conn
            )
        )

        sector_map = {}

        if (
            master_schema is not None
            and master_schema["sector"] is not None
        ):
            master_ticker = (
                master_schema["ticker"]
            )

            master_sector = (
                master_schema["sector"]
            )

            master_query = f"""
            SELECT
                {master_ticker} AS ticker,
                {master_sector} AS sector
            FROM security_master
            """

            master = pd.read_sql_query(
                master_query,
                conn,
            )

            master["ticker"] = (
                master["ticker"]
                .astype(str)
                .str.upper()
                .str.strip()
            )

            master["sector"] = (
                master["sector"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
            )

            sector_map = dict(
                zip(
                    master["ticker"],
                    master["sector"],
                )
            )

    finally:
        conn.close()

    prices["ticker"] = (
        prices["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce",
    )

    prices["close"] = pd.to_numeric(
        prices["close"],
        errors="coerce",
    )

    prices = (
        prices.dropna(
            subset=[
                "ticker",
                "date",
                "close",
            ]
        )
        .sort_values(
            [
                "ticker",
                "date",
            ]
        )
        .drop_duplicates(
            subset=[
                "ticker",
                "date",
            ],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return prices, sector_map


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def engineer_security_features(stock):
    df = (
        stock
        .sort_values("date")
        .reset_index(drop=True)
        .copy()
    )

    df["return_1d"] = (
        df["close"]
        .pct_change(1)
    )

    df["return_5d"] = (
        df["close"]
        .pct_change(5)
    )

    df["return_20d"] = (
        df["close"]
        .pct_change(20)
    )

    df["volatility_20d"] = (
        df["return_1d"]
        .rolling(20)
        .std()
    )

    df["momentum_20d"] = (
        df["close"]
        / df["close"].shift(20)
        - 1
    )

    ma20 = (
        df["close"]
        .rolling(20)
        .mean()
    )

    ma50 = (
        df["close"]
        .rolling(50)
        .mean()
    )

    df["distance_ma20"] = (
        df["close"]
        / ma20
        - 1
    )

    df["distance_ma50"] = (
        df["close"]
        / ma50
        - 1
    )

    df["future_close"] = (
        df["close"]
        .shift(-FORWARD_DAYS)
    )

    df["forward_return_20d"] = (
        df["future_close"]
        / df["close"]
        - 1
    )

    df["target"] = np.where(
        df["forward_return_20d"].notna(),
        (
            df["forward_return_20d"]
            > 0
        ).astype(int),
        np.nan,
    )

    return df


def build_feature_panel(
    prices,
    sector_map,
):
    panels = []

    counts = (
        prices.groupby("ticker")
        .size()
    )

    eligible_tickers = (
        counts[
            counts >= MIN_SECURITY_HISTORY
        ]
        .index
        .tolist()
    )

    for ticker in eligible_tickers:

        stock = (
            prices[
                prices["ticker"] == ticker
            ]
            .copy()
        )

        featured = (
            engineer_security_features(
                stock
            )
        )

        featured["sector"] = (
            sector_map.get(
                ticker,
                "Unknown",
            )
        )

        panels.append(
            featured
        )

    if not panels:
        raise RuntimeError(
            "No securities have enough history."
        )

    panel = pd.concat(
        panels,
        ignore_index=True,
    )

    return panel


# ============================================================
# MODEL
# ============================================================

def build_model():
    return Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=5,
                    min_samples_leaf=8,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


# ============================================================
# RANKING DATE CREATION
# ============================================================

def get_common_ranking_dates(panel):
    date_counts = (
        panel[
            panel[FEATURE_COLUMNS]
            .notna()
            .all(axis=1)
        ]
        .groupby("date")[
            "ticker"
        ]
        .nunique()
    )

    valid_dates = (
        date_counts[
            date_counts
            >= MIN_CROSS_SECTION
        ]
        .index
        .sort_values()
        .tolist()
    )

    if not valid_dates:
        raise RuntimeError(
            "No ranking dates have a sufficiently "
            "large cross-section."
        )

    start_index = max(
        0,
        len(valid_dates)
        - 40 * REBALANCE_STEP,
    )

    selected = valid_dates[
        start_index::REBALANCE_STEP
    ]

    return selected


# ============================================================
# POINT-IN-TIME TRAINING SET
# ============================================================

def build_training_set(
    panel,
    ranking_date,
):
    eligible = (
        panel[
            panel["date"]
            < ranking_date
        ]
        .copy()
    )

    training_blocks = []

    for ticker, group in eligible.groupby(
        "ticker"
    ):
        group = (
            group
            .sort_values("date")
            .reset_index(drop=True)
        )

        if len(group) <= PURGE_OBSERVATIONS:
            continue

        group = group.iloc[
            :-PURGE_OBSERVATIONS
        ].copy()

        group = group.dropna(
            subset=
            FEATURE_COLUMNS
            + ["target"]
        )

        if (
            len(group)
            < MIN_TRAIN_ROWS_PER_SECURITY
        ):
            continue

        training_blocks.append(
            group
        )

    if not training_blocks:
        return None

    training = pd.concat(
        training_blocks,
        ignore_index=True,
    )

    return training


def build_ranking_cross_section(
    panel,
    ranking_date,
):
    cross_section = (
        panel[
            panel["date"]
            == ranking_date
        ]
        .copy()
    )

    cross_section = cross_section.dropna(
        subset=FEATURE_COLUMNS
    )

    if (
        len(cross_section)
        < MIN_CROSS_SECTION
    ):
        return None

    return cross_section


# ============================================================
# RANK ONE DATE
# ============================================================

def rank_one_date(
    panel,
    ranking_date,
):
    training = build_training_set(
        panel,
        ranking_date,
    )

    cross_section = (
        build_ranking_cross_section(
            panel,
            ranking_date,
        )
    )

    if (
        training is None
        or cross_section is None
    ):
        return None

    if (
        training["target"]
        .nunique()
        < 2
    ):
        return None

    X_train = training[
        FEATURE_COLUMNS
    ]

    y_train = (
        training["target"]
        .astype(int)
    )

    X_rank = cross_section[
        FEATURE_COLUMNS
    ]

    model = build_model()

    model.fit(
        X_train,
        y_train,
    )

    probabilities = (
        model.predict_proba(
            X_rank
        )[:, 1]
    )

    result = cross_section[
        [
            "date",
            "ticker",
            "sector",
            "close",
            "forward_return_20d",
            "target",
        ]
    ].copy()

    result["up_probability"] = (
        probabilities
    )

    result["universe_rank"] = (
        result[
            "up_probability"
        ]
        .rank(
            ascending=False,
            method="first",
        )
        .astype(int)
    )

    result["universe_percentile"] = (
        result[
            "up_probability"
        ]
        .rank(
            pct=True,
            ascending=True,
        )
    )

    result["sector_rank"] = (
        result.groupby(
            "sector"
        )[
            "up_probability"
        ]
        .rank(
            ascending=False,
            method="first",
        )
        .astype(int)
    )

    result[
        "sector_percentile"
    ] = (
        result.groupby(
            "sector"
        )[
            "up_probability"
        ]
        .rank(
            pct=True,
            ascending=True,
        )
    )

    result["cross_section_size"] = (
        len(result)
    )

    result[
        "training_observations"
    ] = (
        len(training)
    )

    return result


# ============================================================
# SCORE BUCKET ANALYSIS
# ============================================================

def assign_score_bucket(group):
    group = group.copy()

    unique_scores = (
        group[
            "up_probability"
        ]
        .nunique()
    )

    bucket_count = min(
        5,
        len(group),
        unique_scores,
    )

    if bucket_count < 2:
        group["score_bucket"] = np.nan
        return group

    ranked = (
        group[
            "up_probability"
        ]
        .rank(
            method="first"
        )
    )

    group["score_bucket"] = (
        pd.qcut(
            ranked,
            q=bucket_count,
            labels=False,
            duplicates="drop",
        )
        + 1
    )

    return group


def build_bucket_summary(rankings):
    bucketed = (
        rankings.groupby(
            "date",
            group_keys=False,
        )
        .apply(
            assign_score_bucket,
            include_groups=False,
        )
        .reset_index(drop=True)
    )

    bucketed = bucketed.dropna(
        subset=[
            "score_bucket",
            "forward_return_20d",
        ]
    )

    if bucketed.empty:
        return pd.DataFrame()

    bucketed[
        "score_bucket"
    ] = (
        bucketed[
            "score_bucket"
        ]
        .astype(int)
    )

    summary = (
        bucketed.groupby(
            "score_bucket"
        )
        .agg(
            observations=(
                "ticker",
                "size",
            ),
            mean_probability=(
                "up_probability",
                "mean",
            ),
            mean_forward_return=(
                "forward_return_20d",
                "mean",
            ),
            median_forward_return=(
                "forward_return_20d",
                "median",
            ),
            positive_rate=(
                "target",
                "mean",
            ),
        )
        .reset_index()
    )

    return summary


# ============================================================
# DATE SUMMARY
# ============================================================

def build_date_summary(rankings):
    rows = []

    for date, group in rankings.groupby(
        "date"
    ):
        group = (
            group
            .dropna(
                subset=[
                    "forward_return_20d",
                ]
            )
            .copy()
        )

        if len(group) < 10:
            continue

        group = group.sort_values(
            "up_probability",
            ascending=False,
        )

        group_size = len(group)

        basket_size = max(
            3,
            int(
                np.ceil(
                    group_size
                    * 0.20
                )
            ),
        )

        top = group.head(
            basket_size
        )

        bottom = group.tail(
            basket_size
        )

        rows.append(
            {
                "date": date,
                "cross_section_size":
                    group_size,
                "basket_size":
                    basket_size,
                "top_mean_probability":
                    top[
                        "up_probability"
                    ].mean(),
                "bottom_mean_probability":
                    bottom[
                        "up_probability"
                    ].mean(),
                "probability_spread":
                    (
                        top[
                            "up_probability"
                        ].mean()
                        -
                        bottom[
                            "up_probability"
                        ].mean()
                    ),
                "top_mean_forward_return":
                    top[
                        "forward_return_20d"
                    ].mean(),
                "bottom_mean_forward_return":
                    bottom[
                        "forward_return_20d"
                    ].mean(),
                "return_spread":
                    (
                        top[
                            "forward_return_20d"
                        ].mean()
                        -
                        bottom[
                            "forward_return_20d"
                        ].mean()
                    ),
                "top_positive_rate":
                    top[
                        "target"
                    ].mean(),
                "bottom_positive_rate":
                    bottom[
                        "target"
                    ].mean(),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# SECTOR SUMMARY
# ============================================================

def build_sector_summary(rankings):
    valid = rankings.dropna(
        subset=[
            "forward_return_20d",
            "up_probability",
        ]
    )

    if valid.empty:
        return pd.DataFrame()

    return (
        valid.groupby(
            "sector"
        )
        .agg(
            observations=(
                "ticker",
                "size",
            ),
            securities=(
                "ticker",
                "nunique",
            ),
            mean_probability=(
                "up_probability",
                "mean",
            ),
            mean_forward_return=(
                "forward_return_20d",
                "mean",
            ),
            positive_rate=(
                "target",
                "mean",
            ),
        )
        .reset_index()
        .sort_values(
            "sector"
        )
    )


# ============================================================
# PRINT HELPERS
# ============================================================

def print_header(title):
    print()
    print(title)
    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main():
    print_header(
        "VITTANTRA — DAY 55 CROSS-SECTIONAL RANKING ENGINE"
    )

    prices, sector_map = load_data()

    print(
        f"Securities discovered: "
        f"{prices['ticker'].nunique()}"
    )

    print(
        f"Daily-price observations: "
        f"{len(prices):,}"
    )

    print(
        "Database range: "
        f"{prices['date'].min().date()} "
        "to "
        f"{prices['date'].max().date()}"
    )

    panel = build_feature_panel(
        prices,
        sector_map,
    )

    ranking_dates = (
        get_common_ranking_dates(
            panel
        )
    )

    print(
        f"Ranking dates selected: "
        f"{len(ranking_dates)}"
    )

    all_rankings = []

    print_header(
        "RUNNING POINT-IN-TIME CROSS-SECTIONAL RANKINGS"
    )

    for number, ranking_date in enumerate(
        ranking_dates,
        start=1,
    ):
        result = rank_one_date(
            panel,
            ranking_date,
        )

        if result is None:
            print(
                f"[{number:02d}/"
                f"{len(ranking_dates):02d}] "
                f"{ranking_date.date()} "
                "-> SKIPPED"
            )
            continue

        all_rankings.append(
            result
        )

        print(
            f"[{number:02d}/"
            f"{len(ranking_dates):02d}] "
            f"{ranking_date.date()} "
            f"-> {len(result)} securities"
        )

    if not all_rankings:
        raise RuntimeError(
            "No valid ranking dates were produced."
        )

    rankings = pd.concat(
        all_rankings,
        ignore_index=True,
    )

    rankings = rankings.sort_values(
        [
            "date",
            "universe_rank",
        ]
    )

    bucket_summary = (
        build_bucket_summary(
            rankings
        )
    )

    date_summary = (
        build_date_summary(
            rankings
        )
    )

    sector_summary = (
        build_sector_summary(
            rankings
        )
    )

    # --------------------------------------------------------
    # Latest ranking
    # --------------------------------------------------------

    latest_date = (
        rankings["date"]
        .max()
    )

    latest = (
        rankings[
            rankings["date"]
            == latest_date
        ]
        .sort_values(
            "universe_rank"
        )
        .copy()
    )

    print_header(
        "LATEST RESEARCH RANKING"
    )

    print(
        f"Ranking date: "
        f"{latest_date.date()}"
    )

    latest_display = latest[
        [
            "universe_rank",
            "ticker",
            "sector",
            "up_probability",
            "sector_rank",
            "universe_percentile",
        ]
    ].copy()

    latest_display[
        "up_probability"
    ] = (
        latest_display[
            "up_probability"
        ]
        .map(
            lambda x:
            f"{x:.4f}"
        )
    )

    latest_display[
        "universe_percentile"
    ] = (
        latest_display[
            "universe_percentile"
        ]
        .map(
            lambda x:
            f"{x:.1%}"
        )
    )

    print(
        latest_display
        .to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Bucket summary
    # --------------------------------------------------------

    print_header(
        "MODEL SCORE BUCKET PERFORMANCE"
    )

    if bucket_summary.empty:
        print(
            "Bucket summary unavailable."
        )
    else:
        display = (
            bucket_summary.copy()
        )

        display[
            "mean_probability"
        ] = (
            display[
                "mean_probability"
            ]
            .map(
                lambda x:
                f"{x:.4f}"
            )
        )

        display[
            "mean_forward_return"
        ] = (
            display[
                "mean_forward_return"
            ]
            .map(
                lambda x:
                f"{x:.2%}"
            )
        )

        display[
            "median_forward_return"
        ] = (
            display[
                "median_forward_return"
            ]
            .map(
                lambda x:
                f"{x:.2%}"
            )
        )

        display[
            "positive_rate"
        ] = (
            display[
                "positive_rate"
            ]
            .map(
                lambda x:
                f"{x:.1%}"
            )
        )

        print(
            display.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Date-level top/bottom analysis
    # --------------------------------------------------------

    print_header(
        "TOP-VS-BOTTOM CROSS-SECTIONAL SPREAD"
    )

    if date_summary.empty:
        print(
            "Date summary unavailable."
        )
    else:
        print(
            "Ranking dates evaluated: "
            f"{len(date_summary)}"
        )

        print(
            "Mean model probability spread: "
            f"{date_summary['probability_spread'].mean():.4f}"
        )

        print(
            "Mean top-basket 20-day return: "
            f"{date_summary['top_mean_forward_return'].mean():.2%}"
        )

        print(
            "Mean bottom-basket 20-day return: "
            f"{date_summary['bottom_mean_forward_return'].mean():.2%}"
        )

        print(
            "Mean top-minus-bottom return spread: "
            f"{date_summary['return_spread'].mean():.2%}"
        )

        print(
            "Median top-minus-bottom return spread: "
            f"{date_summary['return_spread'].median():.2%}"
        )

        print(
            "Ranking dates with positive return spread: "
            f"{(date_summary['return_spread'] > 0).sum()} "
            f"/ {len(date_summary)} "
            f"("
            f"{(date_summary['return_spread'] > 0).mean():.1%}"
            f")"
        )

    # --------------------------------------------------------
    # Sector research summary
    # --------------------------------------------------------

    print_header(
        "SECTOR RESEARCH SUMMARY"
    )

    if sector_summary.empty:
        print(
            "Sector summary unavailable."
        )
    else:
        sector_display = (
            sector_summary.copy()
        )

        sector_display[
            "mean_probability"
        ] = (
            sector_display[
                "mean_probability"
            ]
            .map(
                lambda x:
                f"{x:.4f}"
            )
        )

        sector_display[
            "mean_forward_return"
        ] = (
            sector_display[
                "mean_forward_return"
            ]
            .map(
                lambda x:
                f"{x:.2%}"
            )
        )

        sector_display[
            "positive_rate"
        ] = (
            sector_display[
                "positive_rate"
            ]
            .map(
                lambda x:
                f"{x:.1%}"
            )
        )

        print(
            sector_display.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------

    rankings.to_csv(
        OUTPUT_RANKINGS,
        index=False,
    )

    bucket_summary.to_csv(
        OUTPUT_DECILES,
        index=False,
    )

    date_summary.to_csv(
        OUTPUT_DATES,
        index=False,
    )

    sector_summary.to_csv(
        OUTPUT_SECTORS,
        index=False,
    )

    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    print_header(
        "DAY 55 INTERPRETATION NOTES"
    )

    print(
        "- Day 55 converts the classification model into "
        "a cross-sectional research ranking."
    )

    print(
        "- Ranking scores are model probabilities, not "
        "expected returns."
    )

    print(
        "- Each ranking date uses only training observations "
        "available before that date."
    )

    print(
        f"- A {PURGE_OBSERVATIONS}-observation purge is applied "
        "before every ranking date."
    )

    print(
        f"- Ranking dates are spaced {REBALANCE_STEP} trading "
        "observations apart."
    )

    print(
        "- Top-vs-bottom forward-return spread helps test whether "
        "model scores contain cross-sectional information."
    )

    print(
        "- A positive average spread is not sufficient evidence "
        "of a tradable strategy."
    )

    print(
        "- Transaction costs, portfolio constraints, turnover, "
        "slippage and capacity are not modeled here."
    )

    print(
        "- Sector ranks are descriptive research outputs and "
        "not recommendations."
    )

    print(
        "- This remains historical research using a small "
        "33-security U.S. equity universe."
    )

    print(
        "- Day 55 rankings should not be used for live trading."
    )

    print_header(
        "OUTPUT FILES CREATED"
    )

    print(
        OUTPUT_RANKINGS
    )

    print(
        OUTPUT_DECILES
    )

    print(
        OUTPUT_DATES
    )

    print(
        OUTPUT_SECTORS
    )

    print()
    print(
        "Day 55 cross-sectional ranking complete."
    )


if __name__ == "__main__":
    main()