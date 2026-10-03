"""
Vittantra
Day 54 — Expanded-Universe ML Validation

Purpose
-------
Test whether the ML research framework developed in Days 49–53
generalizes across the expanded equity universe stored in hedge_fund.db.

Research principles
-------------------
1. Discover securities dynamically from the database.
2. Keep training chronological.
3. Use a 20-trading-day forward return target.
4. Purge observations near each test date.
5. Space test observations to reduce forward-return overlap.
6. Compare ML models against simple benchmarks.
7. Evaluate results by security and sector.
8. Measure breadth and stability rather than relying on one strong ticker.

This is a research experiment, not an investment recommendation.
"""

import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier


warnings.filterwarnings("ignore", category=ConvergenceWarning)


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("hedge_fund.db")

FORWARD_DAYS = 20
PURGE_OBSERVATIONS = 20
TEST_STEP = 20

MIN_HISTORY = 250
MIN_TRAINING_ROWS = 120
MAX_TESTS_PER_SECURITY = 40

RANDOM_STATE = 42


# ============================================================
# FEATURE CONFIGURATION
# ============================================================

FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "momentum_20d",
    "distance_ma20",
    "distance_ma50",
    "volume_change_5d",
]


# ============================================================
# DATABASE HELPERS
# ============================================================

def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} was not found. Run this script from the "
            "AI-Financial-Analyst project directory."
        )

    return sqlite3.connect(DB_PATH)


def get_table_columns(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [row[1] for row in rows]


def discover_price_schema(conn):
    columns = get_table_columns(conn, "daily_prices")

    if not columns:
        raise RuntimeError(
            "daily_prices table was not found in hedge_fund.db."
        )

    ticker_col = None
    date_col = None
    close_col = None
    volume_col = None

    ticker_candidates = ["ticker", "symbol"]
    date_candidates = ["date", "price_date", "trade_date"]
    close_candidates = [
        "close_price",
        "close",
        "adj_close",
        "adjusted_close",
    ]
    volume_candidates = ["volume", "trade_volume"]

    for candidate in ticker_candidates:
        if candidate in columns:
            ticker_col = candidate
            break

    for candidate in date_candidates:
        if candidate in columns:
            date_col = candidate
            break

    for candidate in close_candidates:
        if candidate in columns:
            close_col = candidate
            break

    for candidate in volume_candidates:
        if candidate in columns:
            volume_col = candidate
            break

    if ticker_col is None:
        raise RuntimeError(
            f"Could not identify ticker column. Columns: {columns}"
        )

    if date_col is None:
        raise RuntimeError(
            f"Could not identify date column. Columns: {columns}"
        )

    if close_col is None:
        raise RuntimeError(
            f"Could not identify close-price column. Columns: {columns}"
        )

    return {
        "ticker": ticker_col,
        "date": date_col,
        "close": close_col,
        "volume": volume_col,
    }


def discover_security_master_schema(conn):
    columns = get_table_columns(conn, "security_master")

    if not columns:
        return None

    ticker_col = None
    sector_col = None

    for candidate in ["ticker", "symbol"]:
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
# LOAD DATA
# ============================================================

def load_market_data():
    conn = connect_db()

    try:
        price_schema = discover_price_schema(conn)

        ticker_col = price_schema["ticker"]
        date_col = price_schema["date"]
        close_col = price_schema["close"]
        volume_col = price_schema["volume"]

        if volume_col:
            volume_expression = f"{volume_col} AS volume"
        else:
            volume_expression = "NULL AS volume"

        query = f"""
        SELECT
            {ticker_col} AS ticker,
            {date_col} AS date,
            {close_col} AS close,
            {volume_expression}
        FROM daily_prices
        WHERE {close_col} IS NOT NULL
        ORDER BY ticker, date
        """

        prices = pd.read_sql_query(query, conn)

        master_schema = discover_security_master_schema(conn)

        sector_map = {}

        if master_schema is not None:
            master_ticker = master_schema["ticker"]
            master_sector = master_schema["sector"]

            if master_sector:
                master_query = f"""
                SELECT
                    {master_ticker} AS ticker,
                    {master_sector} AS sector
                FROM security_master
                """

                master = pd.read_sql_query(master_query, conn)

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
                    zip(master["ticker"], master["sector"])
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
        errors="coerce"
    )

    prices["close"] = pd.to_numeric(
        prices["close"],
        errors="coerce"
    )

    prices["volume"] = pd.to_numeric(
        prices["volume"],
        errors="coerce"
    )

    prices = prices.dropna(
        subset=["ticker", "date", "close"]
    )

    prices = prices.sort_values(
        ["ticker", "date"]
    )

    prices = prices.drop_duplicates(
        subset=["ticker", "date"],
        keep="last"
    )

    return prices, sector_map


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def engineer_features(stock):
    df = stock.copy()

    df = df.sort_values("date").reset_index(drop=True)

    df["return_1d"] = df["close"].pct_change(1)
    df["return_5d"] = df["close"].pct_change(5)
    df["return_20d"] = df["close"].pct_change(20)

    df["volatility_20d"] = (
        df["return_1d"]
        .rolling(20)
        .std()
    )

    df["momentum_20d"] = (
        df["close"] /
        df["close"].shift(20)
        - 1
    )

    ma20 = df["close"].rolling(20).mean()
    ma50 = df["close"].rolling(50).mean()

    df["distance_ma20"] = (
        df["close"] / ma20 - 1
    )

    df["distance_ma50"] = (
        df["close"] / ma50 - 1
    )

    if df["volume"].notna().any():
        volume_ma5 = (
            df["volume"]
            .rolling(5)
            .mean()
        )

        df["volume_change_5d"] = (
            df["volume"] /
            volume_ma5
            - 1
        )
    else:
        df["volume_change_5d"] = 0.0

    df["forward_return_20d"] = (
        df["close"]
        .shift(-FORWARD_DAYS) /
        df["close"]
        - 1
    )

    df["target"] = np.where(
        df["forward_return_20d"].notna(),
        (
            df["forward_return_20d"] > 0
        ).astype(int),
        np.nan
    )

    return df


# ============================================================
# MODELS
# ============================================================

def build_models():
    logistic = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    decision_tree = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "model",
                DecisionTreeClassifier(
                    max_depth=4,
                    min_samples_leaf=10,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    random_forest = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=5,
                    min_samples_leaf=8,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    return {
        "Logistic Regression": logistic,
        "Decision Tree": decision_tree,
        "Random Forest": random_forest,
    }


# ============================================================
# BENCHMARKS
# ============================================================

def majority_prediction(y_train):
    counts = pd.Series(y_train).value_counts()

    if counts.empty:
        return 0

    return int(counts.idxmax())


def momentum_prediction(row):
    value = row["momentum_20d"]

    if pd.isna(value):
        return 0

    return int(value > 0)


# ============================================================
# SINGLE-SECURITY WALK-FORWARD TEST
# ============================================================

def evaluate_security(ticker, stock, sector):
    df = engineer_features(stock)

    usable = df.dropna(
        subset=[
            "target",
            "forward_return_20d",
        ]
    ).copy()

    if len(usable) < MIN_HISTORY:
        return None

    usable["target"] = usable["target"].astype(int)

    models = build_models()

    predictions = []

    first_test_index = max(
        MIN_TRAINING_ROWS + PURGE_OBSERVATIONS,
        150,
    )

    candidate_indices = list(
        range(
            first_test_index,
            len(usable),
            TEST_STEP,
        )
    )

    if len(candidate_indices) > MAX_TESTS_PER_SECURITY:
        candidate_indices = candidate_indices[
            -MAX_TESTS_PER_SECURITY:
        ]

    for test_index in candidate_indices:

        training_end = (
            test_index - PURGE_OBSERVATIONS
        )

        if training_end < MIN_TRAINING_ROWS:
            continue

        train = usable.iloc[:training_end].copy()
        test = usable.iloc[[test_index]].copy()

        if train["target"].nunique() < 2:
            continue

        X_train = train[FEATURE_COLUMNS]
        y_train = train["target"]

        X_test = test[FEATURE_COLUMNS]
        y_test = int(test["target"].iloc[0])

        majority_pred = majority_prediction(y_train)
        momentum_pred = momentum_prediction(
            test.iloc[0]
        )

        row_result = {
            "ticker": ticker,
            "sector": sector,
            "date": test["date"].iloc[0],
            "actual": y_test,
            "forward_return_20d":
                test["forward_return_20d"].iloc[0],
            "Majority Benchmark": majority_pred,
            "20-Day Momentum Rule": momentum_pred,
        }

        for model_name, model in models.items():
            fitted_model = clone(model)

            try:
                fitted_model.fit(
                    X_train,
                    y_train,
                )

                prediction = int(
                    fitted_model.predict(X_test)[0]
                )

            except Exception:
                prediction = np.nan

            row_result[model_name] = prediction

        predictions.append(row_result)

    if not predictions:
        return None

    return pd.DataFrame(predictions)


# ============================================================
# METRICS
# ============================================================

MODEL_COLUMNS = [
    "Majority Benchmark",
    "20-Day Momentum Rule",
    "Logistic Regression",
    "Decision Tree",
    "Random Forest",
]


def safe_balanced_accuracy(actual, predicted):
    valid = (
        pd.Series(actual).notna()
        & pd.Series(predicted).notna()
    )

    y_true = pd.Series(actual)[valid]
    y_pred = pd.Series(predicted)[valid]

    if len(y_true) == 0:
        return np.nan

    if y_true.nunique() < 2:
        return np.nan

    return balanced_accuracy_score(
        y_true.astype(int),
        y_pred.astype(int),
    )


def build_security_summary(predictions):
    rows = []

    for ticker, group in predictions.groupby("ticker"):

        row = {
            "ticker": ticker,
            "sector": group["sector"].iloc[0],
            "tests": len(group),
            "positive_rate":
                group["actual"].mean(),
            "mean_forward_return":
                group["forward_return_20d"].mean(),
        }

        for model in MODEL_COLUMNS:
            row[model] = safe_balanced_accuracy(
                group["actual"],
                group[model],
            )

        rows.append(row)

    return pd.DataFrame(rows)


def build_sector_summary(predictions):
    rows = []

    for sector, group in predictions.groupby("sector"):

        row = {
            "sector": sector,
            "securities":
                group["ticker"].nunique(),
            "tests": len(group),
        }

        for model in MODEL_COLUMNS:
            row[model] = safe_balanced_accuracy(
                group["actual"],
                group[model],
            )

        rows.append(row)

    return pd.DataFrame(rows)


def build_model_stability(security_summary):
    rows = []

    for model in MODEL_COLUMNS:

        values = pd.to_numeric(
            security_summary[model],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        rows.append(
            {
                "model": model,
                "mean": values.mean(),
                "median": values.median(),
                "std_dev": values.std(),
                "minimum": values.min(),
                "maximum": values.max(),
                "securities": len(values),
                "above_0_50":
                    (values > 0.50).mean(),
                "at_or_above_0_50":
                    (values >= 0.50).mean(),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# PRINT HELPERS
# ============================================================

def print_header(title):
    print()
    print(title)
    print("=" * 100)


def format_accuracy_table(df, index_column):
    display = df.copy()

    for column in MODEL_COLUMNS:
        if column in display.columns:
            display[column] = display[column].map(
                lambda x:
                f"{x:.4f}"
                if pd.notna(x)
                else "N/A"
            )

    print(
        display.to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print_header(
        "VITTANTRA — DAY 54 EXPANDED-UNIVERSE ML VALIDATION"
    )

    print(
        "Loading expanded market universe from hedge_fund.db..."
    )

    prices, sector_map = load_market_data()

    counts = (
        prices.groupby("ticker")
        .size()
        .sort_values(ascending=False)
    )

    tickers = counts.index.tolist()

    print()
    print(f"Securities discovered: {len(tickers)}")
    print(
        f"Daily-price observations: {len(prices):,}"
    )
    print(
        f"Database range: "
        f"{prices['date'].min().date()} "
        f"to {prices['date'].max().date()}"
    )

    all_predictions = []
    skipped = []

    print_header(
        "RUNNING SECURITY-LEVEL WALK-FORWARD TESTS"
    )

    for number, ticker in enumerate(
        tickers,
        start=1,
    ):

        stock = prices[
            prices["ticker"] == ticker
        ].copy()

        sector = sector_map.get(
            ticker,
            "Unknown",
        )

        print(
            f"[{number:02d}/{len(tickers):02d}] "
            f"{ticker:<7} "
            f"{sector:<30} "
            f"{len(stock):>5} rows",
            end="",
        )

        result = evaluate_security(
            ticker,
            stock,
            sector,
        )

        if result is None:
            skipped.append(ticker)
            print("  -> SKIPPED")
            continue

        all_predictions.append(result)

        print(
            f"  -> {len(result):>2} tests"
        )

    if not all_predictions:
        raise RuntimeError(
            "No securities produced valid ML tests."
        )

    predictions = pd.concat(
        all_predictions,
        ignore_index=True,
    )

    security_summary = build_security_summary(
        predictions
    )

    sector_summary = build_sector_summary(
        predictions
    )

    stability = build_model_stability(
        security_summary
    )

    # --------------------------------------------------------
    # Overall pooled results
    # --------------------------------------------------------

    print_header(
        "OVERALL EXPANDED-UNIVERSE BALANCED ACCURACY"
    )

    overall_rows = []

    for model in MODEL_COLUMNS:

        score = safe_balanced_accuracy(
            predictions["actual"],
            predictions[model],
        )

        overall_rows.append(
            {
                "model": model,
                "balanced_accuracy": score,
            }
        )

    overall = pd.DataFrame(overall_rows)

    overall["balanced_accuracy"] = (
        overall["balanced_accuracy"]
        .map(
            lambda x:
            f"{x:.4f}"
            if pd.notna(x)
            else "N/A"
        )
    )

    print(
        overall.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Security-level results
    # --------------------------------------------------------

    print_header(
        "SECURITY-LEVEL BALANCED ACCURACY"
    )

    security_display = (
        security_summary
        .sort_values("ticker")
        .copy()
    )

    security_display["positive_rate"] = (
        security_display["positive_rate"]
        .map(lambda x: f"{x:.2%}")
    )

    security_display["mean_forward_return"] = (
        security_display["mean_forward_return"]
        .map(lambda x: f"{x:.2%}")
    )

    format_accuracy_table(
        security_display,
        "ticker",
    )

    # --------------------------------------------------------
    # Sector-level results
    # --------------------------------------------------------

    print_header(
        "SECTOR-LEVEL BALANCED ACCURACY"
    )

    sector_display = (
        sector_summary
        .sort_values("sector")
        .copy()
    )

    format_accuracy_table(
        sector_display,
        "sector",
    )

    # --------------------------------------------------------
    # Model stability
    # --------------------------------------------------------

    print_header(
        "MODEL STABILITY ACROSS SECURITIES"
    )

    stability_display = stability.copy()

    for column in [
        "mean",
        "median",
        "std_dev",
        "minimum",
        "maximum",
    ]:
        stability_display[column] = (
            stability_display[column]
            .map(lambda x: f"{x:.4f}")
        )

    stability_display["above_0_50"] = (
        stability_display["above_0_50"]
        .map(lambda x: f"{x:.1%}")
    )

    stability_display[
        "at_or_above_0_50"
    ] = (
        stability_display[
            "at_or_above_0_50"
        ]
        .map(lambda x: f"{x:.1%}")
    )

    print(
        stability_display.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Random Forest breadth
    # --------------------------------------------------------

    print_header(
        "RANDOM FOREST CROSS-SECURITY BREADTH"
    )

    rf_values = pd.to_numeric(
        security_summary["Random Forest"],
        errors="coerce",
    ).dropna()

    print(
        f"Securities evaluated: {len(rf_values)}"
    )

    print(
        "Mean security-level balanced accuracy: "
        f"{rf_values.mean():.4f}"
    )

    print(
        "Median security-level balanced accuracy: "
        f"{rf_values.median():.4f}"
    )

    print(
        "Securities above 0.50 balanced accuracy: "
        f"{(rf_values > 0.50).sum()} / "
        f"{len(rf_values)} "
        f"({(rf_values > 0.50).mean():.1%})"
    )

    print(
        "Securities at or above 0.50: "
        f"{(rf_values >= 0.50).sum()} / "
        f"{len(rf_values)} "
        f"({(rf_values >= 0.50).mean():.1%})"
    )

    # --------------------------------------------------------
    # Best / weakest security results
    # Descriptive only — not investment recommendations.
    # --------------------------------------------------------

    print_header(
        "RANDOM FOREST SECURITY DISPERSION"
    )

    rf_security = security_summary[
        [
            "ticker",
            "sector",
            "tests",
            "Random Forest",
        ]
    ].dropna().sort_values(
        "Random Forest",
        ascending=False,
    )

    print(
        rf_security.to_string(
            index=False,
            formatters={
                "Random Forest":
                    lambda x: f"{x:.4f}"
            },
        )
    )

    # --------------------------------------------------------
    # Save research outputs
    # --------------------------------------------------------

    predictions.to_csv(
        "day54_expanded_predictions.csv",
        index=False,
    )

    security_summary.to_csv(
        "day54_security_ml_summary.csv",
        index=False,
    )

    sector_summary.to_csv(
        "day54_sector_ml_summary.csv",
        index=False,
    )

    stability.to_csv(
        "day54_model_stability.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Final notes
    # --------------------------------------------------------

    print_header(
        "DAY 54 INTERPRETATION NOTES"
    )

    print(
        "- Securities are discovered dynamically from hedge_fund.db."
    )

    print(
        "- Each security is modeled separately rather than "
        "mixing all observations into one training set."
    )

    print(
        "- Training is chronological and uses only observations "
        "before each test observation."
    )

    print(
        f"- A {PURGE_OBSERVATIONS}-observation purge separates "
        "training from each test observation."
    )

    print(
        f"- Test observations are spaced {TEST_STEP} observations "
        "apart to reduce overlap in 20-day targets."
    )

    print(
        "- Balanced accuracy is used because positive and negative "
        "forward-return classes may be uneven."
    )

    print(
        "- Sector results help determine whether apparent model "
        "performance is concentrated in particular industries."
    )

    print(
        "- Security-level breadth matters more than an unusually "
        "strong result for one ticker."
    )

    print(
        "- Securities share market dates and macroeconomic conditions, "
        "so results are not fully independent."
    )

    print(
        "- This remains equity cross-sectional validation, not "
        "cross-asset validation."
    )

    print(
        "- Historical classification accuracy does not establish "
        "future investment performance."
    )

    if skipped:
        print()
        print(
            "Skipped securities due to insufficient usable history:"
        )
        print(", ".join(skipped))

    print_header(
        "OUTPUT FILES CREATED"
    )

    print("day54_expanded_predictions.csv")
    print("day54_security_ml_summary.csv")
    print("day54_sector_ml_summary.csv")
    print("day54_model_stability.csv")

    print()
    print("Day 54 expanded-universe validation complete.")


if __name__ == "__main__":
    main()