"""
Day 52 — Cross-Security Validation

Test the Day 51 20-trading-day robustness framework across every
security currently available in hedge_fund.db.

Current universe:
AAPL, BLK, GS, JPM, MSFT

Purpose:
Determine whether the 20-day signal observed for AAPL is specific
to one security or shows evidence of surviving across multiple
securities.

Methodology preserved from Day 51:
1. 20-trading-day forward target
2. Expanding-window training
3. 20-observation purge between train and test
4. Non-overlapping test observations
5. Majority-class benchmark
6. Simple 20-day momentum benchmark
7. Logistic regression
8. Decision tree
9. Random forest
10. Security-by-security and pooled diagnostics

Research only.
No live trading or investment recommendations.
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)

from ml_feature_engineering import (
    create_enhanced_features,
)

# Reuse the Day 51 methodology directly.
from ml_robustness import (
    HORIZON,
    TEST_STEP,
    INITIAL_TRAIN_FRACTION,
    build_models,
    create_20_day_dataset,
    momentum_prediction,
)


DB_PATH = Path(__file__).resolve().parent / "hedge_fund.db"

MIN_PRICE_OBSERVATIONS = 100
MIN_MODEL_OBSERVATIONS = 80


def load_available_tickers():
    """
    Find every ticker currently available in daily_prices.

    The universe is discovered from the database rather than
    manually selected after observing model performance.
    """

    with sqlite3.connect(DB_PATH) as conn:
        tickers = pd.read_sql_query(
            """
            SELECT
                ticker,
                COUNT(*) AS observations,
                MIN(date) AS first_date,
                MAX(date) AS last_date
            FROM daily_prices
            GROUP BY ticker
            ORDER BY ticker
            """,
            conn,
        )

    return tickers


def load_security_prices(ticker):
    """
    Load historical prices for one security.
    """

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT
                date,
                ticker,
                close_price
            FROM daily_prices
            WHERE ticker = ?
            ORDER BY date
            """,
            conn,
            params=(ticker,),
        )

    if df.empty:
        raise ValueError(
            f"No historical prices found for {ticker}"
        )

    df["date"] = pd.to_datetime(df["date"])

    df["close_price"] = pd.to_numeric(
        df["close_price"],
        errors="coerce",
    )

    df = (
        df.dropna(
            subset=[
                "date",
                "close_price",
            ]
        )
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return df


def classification_metrics(
    y_true,
    predictions,
):
    """
    Calculate classification diagnostics.
    """

    return {
        "Accuracy": accuracy_score(
            y_true,
            predictions,
        ),

        "Balanced Accuracy": balanced_accuracy_score(
            y_true,
            predictions,
        ),

        "Precision (Up)": precision_score(
            y_true,
            predictions,
            zero_division=0,
        ),

        "Recall (Up)": recall_score(
            y_true,
            predictions,
            zero_division=0,
        ),

        "F1 (Up)": f1_score(
            y_true,
            predictions,
            zero_division=0,
        ),
    }


def run_security_test(
    ticker,
    data,
    features,
):
    """
    Apply the Day 51 robustness methodology to one security.

    For every test observation:

    - training uses only earlier information;
    - training ends HORIZON observations before test;
    - test observations occur every HORIZON observations;
    - models are rebuilt independently for each fold.
    """

    initial_test_index = int(
        len(data)
        * INITIAL_TRAIN_FRACTION
    )

    initial_test_index = max(
        initial_test_index,
        HORIZON + 30,
    )

    prediction_rows = []
    fold_number = 1

    for test_index in range(
        initial_test_index,
        len(data),
        TEST_STEP,
    ):

        train_end = (
            test_index
            - HORIZON
        )

        if train_end <= 0:
            continue

        train = (
            data.iloc[:train_end]
            .copy()
        )

        test = (
            data.iloc[[test_index]]
            .copy()
        )

        if len(train) < 50:
            continue

        X_train = train[features]
        y_train = train["target_20d"]

        X_test = test[features]
        y_test = test["target_20d"]

        if y_train.nunique() < 2:
            continue

        actual = int(
            y_test.iloc[0]
        )

        test_date = (
            test["date"]
            .iloc[0]
            .date()
        )

        forward_return = float(
            test["forward_return_20d"]
            .iloc[0]
        )

        models = build_models()

        for model_name, model in models.items():

            model.fit(
                X_train,
                y_train,
            )

            prediction = int(
                model.predict(
                    X_test
                )[0]
            )

            prediction_rows.append(
                {
                    "Ticker": ticker,
                    "Fold": fold_number,
                    "Date": test_date,
                    "Model": model_name,
                    "Actual": actual,
                    "Prediction": prediction,
                    "Forward Return": forward_return,
                    "Train Size": len(train),
                }
            )

        momentum_pred = momentum_prediction(
            test.iloc[0]
        )

        prediction_rows.append(
            {
                "Ticker": ticker,
                "Fold": fold_number,
                "Date": test_date,
                "Model": "20-Day Momentum Rule",
                "Actual": actual,
                "Prediction": momentum_pred,
                "Forward Return": forward_return,
                "Train Size": len(train),
            }
        )

        fold_number += 1

    return pd.DataFrame(
        prediction_rows
    )


def summarize_security(
    ticker,
    predictions,
):
    """
    Calculate model performance for one security.
    """

    rows = []

    for model_name, group in predictions.groupby(
        "Model"
    ):

        metrics = classification_metrics(
            group["Actual"],
            group["Prediction"],
        )

        rows.append(
            {
                "Ticker": ticker,
                "Model": model_name,
                "Observations": len(group),
                **metrics,
                "Predicted Up (%)": (
                    group["Prediction"].mean()
                    * 100
                ),
            }
        )

    return pd.DataFrame(rows)


def create_balanced_accuracy_matrix(
    summary,
):
    """
    Security x model matrix of balanced accuracy.
    """

    matrix = summary.pivot(
        index="Ticker",
        columns="Model",
        values="Balanced Accuracy",
    )

    preferred_order = [
        "Majority Benchmark",
        "20-Day Momentum Rule",
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]

    available_columns = [
        column
        for column in preferred_order
        if column in matrix.columns
    ]

    return matrix[
        available_columns
    ]


def pooled_model_performance(
    predictions,
):
    """
    Pool all out-of-sample predictions across securities.

    This is supplementary evidence only because observations
    from different securities can occur on the same dates and
    therefore are not necessarily statistically independent.
    """

    rows = []

    for model_name, group in predictions.groupby(
        "Model"
    ):

        metrics = classification_metrics(
            group["Actual"],
            group["Prediction"],
        )

        rows.append(
            {
                "Model": model_name,
                "Observations": len(group),
                **metrics,
                "Predicted Up (%)": (
                    group["Prediction"].mean()
                    * 100
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .set_index("Model")
        .sort_values(
            "Balanced Accuracy",
            ascending=False,
        )
    )


def model_cross_security_stability(
    summary,
):
    """
    Examine how stable each model is across securities.
    """

    stability = (
        summary
        .groupby("Model")[
            "Balanced Accuracy"
        ]
        .agg(
            [
                "mean",
                "std",
                "min",
                "max",
                "median",
            ]
        )
    )

    stability.columns = [
        "Mean",
        "Std Dev",
        "Minimum",
        "Maximum",
        "Median",
    ]

    return stability.sort_values(
        "Mean",
        ascending=False,
    )


def benchmark_comparison(
    matrix,
):
    """
    Compare each ML model with the majority benchmark
    security by security.
    """

    if "Majority Benchmark" not in matrix.columns:
        return pd.DataFrame()

    benchmark = matrix[
        "Majority Benchmark"
    ]

    rows = []

    for model_name in [
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]:

        if model_name not in matrix.columns:
            continue

        difference = (
            matrix[model_name]
            - benchmark
        )

        rows.append(
            {
                "Model": model_name,
                "Mean Advantage": difference.mean(),
                "Median Advantage": difference.median(),
                "Securities Above Benchmark": int(
                    (difference > 0).sum()
                ),
                "Securities Equal Benchmark": int(
                    (difference == 0).sum()
                ),
                "Securities Below Benchmark": int(
                    (difference < 0).sum()
                ),
                "Total Securities": int(
                    difference.notna().sum()
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .set_index("Model")
    )


def main():

    print(
        "\nDAY 52 — CROSS-SECURITY VALIDATION"
    )
    print("=" * 78)

    print(
        f"Forecast horizon: {HORIZON} trading days"
    )

    print(
        f"Test spacing: {TEST_STEP} observations"
    )

    print(
        "Initial training fraction: "
        f"{INITIAL_TRAIN_FRACTION:.0%}"
    )

    universe = load_available_tickers()

    print(
        "\nDATABASE UNIVERSE"
    )
    print("=" * 78)

    print(
        universe.to_string(
            index=False
        )
    )

    eligible = universe[
        universe["observations"]
        >= MIN_PRICE_OBSERVATIONS
    ].copy()

    if eligible.empty:
        raise ValueError(
            "No securities have enough historical data."
        )

    print(
        "\nELIGIBLE SECURITIES"
    )
    print("=" * 78)

    print(
        ", ".join(
            eligible["ticker"].tolist()
        )
    )

    all_predictions = []
    all_summaries = []
    security_diagnostics = []

    for ticker in eligible["ticker"]:

        print(
            f"\n{'=' * 78}"
        )

        print(
            f"TESTING {ticker}"
        )

        print(
            f"{'=' * 78}"
        )

        try:

            prices = load_security_prices(
                ticker
            )

            feature_data, features = (
                create_enhanced_features(
                    prices
                )
            )

            data = create_20_day_dataset(
                feature_data,
                features,
            )

            print(
                f"Raw price observations: "
                f"{len(prices)}"
            )

            print(
                f"Usable model observations: "
                f"{len(data)}"
            )

            print(
                f"Enhanced features: "
                f"{len(features)}"
            )

            if len(data) < MIN_MODEL_OBSERVATIONS:

                print(
                    "SKIPPED: insufficient usable "
                    "model observations."
                )

                continue

            up_pct = (
                data["target_20d"]
                .mean()
                * 100
            )

            print(
                "Target balance: "
                f"{up_pct:.2f}% UP / "
                f"{100 - up_pct:.2f}% DOWN-FLAT"
            )

            predictions = run_security_test(
                ticker,
                data,
                features,
            )

            if predictions.empty:

                print(
                    "SKIPPED: no valid robustness "
                    "folds produced."
                )

                continue

            summary = summarize_security(
                ticker,
                predictions,
            )

            evaluated_periods = (
                predictions[
                    [
                        "Ticker",
                        "Fold",
                        "Date",
                        "Actual",
                        "Forward Return",
                    ]
                ]
                .drop_duplicates()
            )

            security_diagnostics.append(
                {
                    "Ticker": ticker,
                    "Price Observations": len(prices),
                    "Model Observations": len(data),
                    "Test Periods": len(
                        evaluated_periods
                    ),
                    "Target Up (%)": up_pct,
                    "Test Up (%)": (
                        evaluated_periods[
                            "Actual"
                        ].mean()
                        * 100
                    ),
                    "Mean Test Return": (
                        evaluated_periods[
                            "Forward Return"
                        ].mean()
                    ),
                    "Median Test Return": (
                        evaluated_periods[
                            "Forward Return"
                        ].median()
                    ),
                }
            )

            all_predictions.append(
                predictions
            )

            all_summaries.append(
                summary
            )

            print(
                "\nSECURITY MODEL PERFORMANCE"
            )
            print("-" * 78)

            print(
                summary[
                    [
                        "Model",
                        "Observations",
                        "Accuracy",
                        "Balanced Accuracy",
                        "Precision (Up)",
                        "Recall (Up)",
                        "F1 (Up)",
                    ]
                ]
                .round(4)
                .to_string(
                    index=False
                )
            )

        except Exception as exc:

            print(
                f"ERROR testing {ticker}: {exc}"
            )

    if not all_predictions:
        raise ValueError(
            "No securities produced valid predictions."
        )

    predictions = pd.concat(
        all_predictions,
        ignore_index=True,
    )

    summary = pd.concat(
        all_summaries,
        ignore_index=True,
    )

    diagnostics = pd.DataFrame(
        security_diagnostics
    )

    matrix = create_balanced_accuracy_matrix(
        summary
    )

    print(
        "\n\nCROSS-SECURITY BALANCED ACCURACY"
    )
    print("=" * 78)

    print(
        matrix
        .round(4)
        .to_string()
    )

    print(
        "\nSECURITY DIAGNOSTICS"
    )
    print("=" * 78)

    display_diagnostics = (
        diagnostics.copy()
    )

    display_diagnostics[
        "Mean Test Return"
    ] = (
        display_diagnostics[
            "Mean Test Return"
        ]
        * 100
    )

    display_diagnostics[
        "Median Test Return"
    ] = (
        display_diagnostics[
            "Median Test Return"
        ]
        * 100
    )

    print(
        display_diagnostics
        .round(2)
        .to_string(
            index=False
        )
    )

    stability = (
        model_cross_security_stability(
            summary
        )
    )

    print(
        "\nCROSS-SECURITY MODEL STABILITY"
    )
    print("=" * 78)

    print(
        stability
        .round(4)
        .to_string()
    )

    comparison = benchmark_comparison(
        matrix
    )

    print(
        "\nML MODELS VS MAJORITY BENCHMARK"
    )
    print("=" * 78)

    if comparison.empty:

        print(
            "Benchmark comparison unavailable."
        )

    else:

        print(
            comparison
            .round(4)
            .to_string()
        )

    pooled = pooled_model_performance(
        predictions
    )

    print(
        "\nPOOLED OUT-OF-SAMPLE PERFORMANCE"
    )
    print("=" * 78)

    print(
        pooled
        .round(4)
        .to_string()
    )

    print(
        "\nRANDOM FOREST SECURITY RESULTS"
    )
    print("=" * 78)

    if "Random Forest" in matrix.columns:

        rf = (
            matrix[
                ["Random Forest"]
            ]
            .copy()
        )

        print(
            rf
            .round(4)
            .to_string()
        )

        print(
            "\nRandom Forest mean "
            "cross-security balanced accuracy: "
            f"{rf['Random Forest'].mean():.4f}"
        )

        print(
            "Random Forest median "
            "cross-security balanced accuracy: "
            f"{rf['Random Forest'].median():.4f}"
        )

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 78)

    print(
        "- Every eligible ticker is discovered from the database "
        "before model results are evaluated."
        "\n- The same 20-day methodology is applied to every security."
        "\n- Training remains chronological and uses only earlier observations."
        "\n- A 20-observation purge separates training from each test date."
        "\n- Test observations are spaced 20 observations apart."
        "\n- Models are rebuilt independently for every fold."
        "\n- Cross-security consistency matters more than one unusually strong ticker."
        "\n- The current database contains only a small U.S. equity universe."
        "\n- Several securities are financially related, so the tests are not fully independent."
        "\n- Pooled observations across securities may share the same market dates."
        "\n- Small non-overlapping test samples can produce unstable balanced accuracy."
        "\n- A strong result here would require substantially more securities, "
        "history, regimes and truly unseen data before stronger conclusions."
        "\n- Cross-security validation is not yet cross-asset validation."
        "\n- No result here establishes future investment performance."
    )


if __name__ == "__main__":
    main()