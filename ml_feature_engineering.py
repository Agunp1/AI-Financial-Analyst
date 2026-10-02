"""
Day 49 — Enhanced Machine Learning Feature Engineering

Expand Vittantra's market feature set while preserving the original
next-day direction target.

The purpose of this stage is research:
1. Build richer price, momentum, volatility, trend and drawdown features.
2. Avoid future-data leakage.
3. Compare the original feature set with the enhanced feature set.
4. Use chronological walk-forward validation.

Research only. No live trading or investment recommendations.
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


# ---------------------------------------------------------
# PROJECT CONFIGURATION
# ---------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent / "hedge_fund.db"

TICKER = "AAPL"

INITIAL_TRAIN_FRACTION = 0.60
TEST_WINDOW = 10


# ---------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------

def load_prices(ticker):
    """
    Load historical closing prices from Vittantra's database.
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

    df = df.dropna(
        subset=["date", "close_price"]
    ).copy()

    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    return df


# ---------------------------------------------------------
# ORIGINAL DAY 46 FEATURES
# ---------------------------------------------------------

def create_baseline_features(df):
    """
    Reproduce the original Day 46 feature set.

    This gives us a fair comparison against the enhanced features.
    """

    data = df.copy()

    data["return_1d"] = (
        data["close_price"].pct_change()
    )

    data["return_5d"] = (
        data["close_price"].pct_change(5)
    )

    data["volatility_5d"] = (
        data["return_1d"]
        .rolling(5)
        .std()
    )

    data["ma_5_ratio"] = (
        data["close_price"]
        / data["close_price"].rolling(5).mean()
        - 1
    )

    data["ma_20_ratio"] = (
        data["close_price"]
        / data["close_price"].rolling(20).mean()
        - 1
    )

    # Predict next trading day's direction.
    next_return = (
        data["close_price"].shift(-1)
        / data["close_price"]
        - 1
    )

    data["target"] = np.where(
        next_return.notna(),
        (next_return > 0).astype(int),
        np.nan,
    )

    features = [
        "return_1d",
        "return_5d",
        "volatility_5d",
        "ma_5_ratio",
        "ma_20_ratio",
    ]

    data = data.dropna(
        subset=features + ["target"]
    ).copy()

    data["target"] = (
        data["target"].astype(int)
    )

    return data, features


# ---------------------------------------------------------
# ENHANCED FEATURE ENGINEERING
# ---------------------------------------------------------

def create_enhanced_features(df):
    """
    Create a richer market feature set using only information
    available on or before each observation date.

    No future information is used in the feature calculations.
    """

    data = df.copy()

    price = data["close_price"]

    # -----------------------------------------------------
    # 1. RETURN / MOMENTUM FEATURES
    # -----------------------------------------------------

    data["return_1d"] = price.pct_change(1)
    data["return_2d"] = price.pct_change(2)
    data["return_5d"] = price.pct_change(5)
    data["return_10d"] = price.pct_change(10)
    data["return_20d"] = price.pct_change(20)

    # Short-term acceleration:
    # recent momentum minus medium-term momentum.
    data["momentum_acceleration"] = (
        data["return_5d"]
        - data["return_20d"]
    )

    # -----------------------------------------------------
    # 2. MOVING-AVERAGE / TREND FEATURES
    # -----------------------------------------------------

    ma_5 = price.rolling(5).mean()
    ma_10 = price.rolling(10).mean()
    ma_20 = price.rolling(20).mean()

    data["ma_5_ratio"] = (
        price / ma_5 - 1
    )

    data["ma_10_ratio"] = (
        price / ma_10 - 1
    )

    data["ma_20_ratio"] = (
        price / ma_20 - 1
    )

    # Relationship between fast and slow moving averages.
    data["ma_5_vs_20"] = (
        ma_5 / ma_20 - 1
    )

    data["ma_10_vs_20"] = (
        ma_10 / ma_20 - 1
    )

    # -----------------------------------------------------
    # 3. VOLATILITY FEATURES
    # -----------------------------------------------------

    daily_return = price.pct_change()

    data["volatility_5d"] = (
        daily_return
        .rolling(5)
        .std()
    )

    data["volatility_10d"] = (
        daily_return
        .rolling(10)
        .std()
    )

    data["volatility_20d"] = (
        daily_return
        .rolling(20)
        .std()
    )

    # Volatility regime:
    # is short-term volatility high relative to longer-term volatility?
    data["volatility_ratio"] = (
        data["volatility_5d"]
        / data["volatility_20d"]
    )

    # -----------------------------------------------------
    # 4. DOWNSIDE-RISK FEATURES
    # -----------------------------------------------------

    downside_return = daily_return.where(
        daily_return < 0,
        0,
    )

    data["downside_vol_10d"] = (
        downside_return
        .rolling(10)
        .std()
    )

    data["downside_vol_20d"] = (
        downside_return
        .rolling(20)
        .std()
    )

    # -----------------------------------------------------
    # 5. DRAWDOWN FEATURES
    # -----------------------------------------------------

    rolling_peak_20 = (
        price
        .rolling(20)
        .max()
    )

    data["drawdown_20d"] = (
        price / rolling_peak_20 - 1
    )

    rolling_peak_60 = (
        price
        .rolling(60)
        .max()
    )

    data["drawdown_60d"] = (
        price / rolling_peak_60 - 1
    )

    # -----------------------------------------------------
    # 6. PRICE Z-SCORE
    # -----------------------------------------------------

    rolling_mean_20 = (
        price
        .rolling(20)
        .mean()
    )

    rolling_std_20 = (
        price
        .rolling(20)
        .std()
    )

    data["price_zscore_20d"] = (
        (price - rolling_mean_20)
        / rolling_std_20
    )

    # -----------------------------------------------------
    # 7. RETURN Z-SCORE
    # -----------------------------------------------------

    return_mean_20 = (
        daily_return
        .rolling(20)
        .mean()
    )

    return_std_20 = (
        daily_return
        .rolling(20)
        .std()
    )

    data["return_zscore_20d"] = (
        (daily_return - return_mean_20)
        / return_std_20
    )

    # -----------------------------------------------------
    # 8. POSITIVE-DAY FREQUENCY
    # -----------------------------------------------------

    positive_day = (
        daily_return > 0
    ).astype(float)

    data["positive_days_5d"] = (
        positive_day
        .rolling(5)
        .mean()
    )

    data["positive_days_20d"] = (
        positive_day
        .rolling(20)
        .mean()
    )

    # -----------------------------------------------------
    # TARGET
    # -----------------------------------------------------

    # Preserve Day 46's target:
    # next trading day's direction.

    next_return = (
        price.shift(-1)
        / price
        - 1
    )

    data["next_return"] = next_return

    data["target"] = np.where(
        next_return.notna(),
        (next_return > 0).astype(int),
        np.nan,
    )

    # -----------------------------------------------------
    # FEATURE LIST
    # -----------------------------------------------------

    features = [
        "return_1d",
        "return_2d",
        "return_5d",
        "return_10d",
        "return_20d",

        "momentum_acceleration",

        "ma_5_ratio",
        "ma_10_ratio",
        "ma_20_ratio",
        "ma_5_vs_20",
        "ma_10_vs_20",

        "volatility_5d",
        "volatility_10d",
        "volatility_20d",
        "volatility_ratio",

        "downside_vol_10d",
        "downside_vol_20d",

        "drawdown_20d",
        "drawdown_60d",

        "price_zscore_20d",
        "return_zscore_20d",

        "positive_days_5d",
        "positive_days_20d",
    ]

    # Replace infinite values before dropping missing rows.
    data = data.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    data = data.dropna(
        subset=features + ["target"]
    ).copy()

    data["target"] = (
        data["target"].astype(int)
    )

    return data, features


# ---------------------------------------------------------
# MODEL DEFINITIONS
# ---------------------------------------------------------

def build_models():
    """
    Build fresh models for each walk-forward fold.
    """

    return {
        "Majority Benchmark": DummyClassifier(
            strategy="most_frequent"
        ),

        "Logistic Regression": Pipeline(
            [
                (
                    "scaler",
                    StandardScaler(),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2000,
                        random_state=42,
                    ),
                ),
            ]
        ),

        "Decision Tree": DecisionTreeClassifier(
            max_depth=3,
            min_samples_leaf=10,
            random_state=42,
        ),

        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=4,
            min_samples_leaf=8,
            random_state=42,
            n_jobs=-1,
        ),
    }


# ---------------------------------------------------------
# METRICS
# ---------------------------------------------------------

def calculate_metrics(
    y_true,
    predictions,
):
    """
    Calculate classification metrics.
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

        "Predicted Up (%)": (
            np.mean(predictions == 1)
            * 100
        ),
    }


# ---------------------------------------------------------
# WALK-FORWARD VALIDATION
# ---------------------------------------------------------

def walk_forward_evaluate(
    data,
    features,
    feature_set_name,
):
    """
    Run expanding-window walk-forward validation.
    """

    data = (
        data
        .sort_values("date")
        .reset_index(drop=True)
    )

    initial_train_size = int(
        len(data)
        * INITIAL_TRAIN_FRACTION
    )

    if initial_train_size < 30:
        raise ValueError(
            f"{feature_set_name}: "
            "initial training sample too small."
        )

    results = []
    predictions_all = []

    fold = 1

    for test_start in range(
        initial_train_size,
        len(data),
        TEST_WINDOW,
    ):
        test_end = min(
            test_start + TEST_WINDOW,
            len(data),
        )

        train = data.iloc[
            :test_start
        ].copy()

        test = data.iloc[
            test_start:test_end
        ].copy()

        if test.empty:
            continue

        X_train = train[features]
        y_train = train["target"]

        X_test = test[features]
        y_test = test["target"]

        if y_train.nunique() < 2:
            fold += 1
            continue

        models = build_models()

        for model_name, model in models.items():

            model.fit(
                X_train,
                y_train,
            )

            predictions = model.predict(
                X_test
            )

            metrics = calculate_metrics(
                y_test,
                predictions,
            )

            results.append(
                {
                    "Feature Set": feature_set_name,
                    "Fold": fold,
                    "Model": model_name,
                    "Train Size": len(train),
                    "Test Size": len(test),
                    **metrics,
                }
            )

            for actual, predicted in zip(
                y_test,
                predictions,
            ):
                predictions_all.append(
                    {
                        "Feature Set": feature_set_name,
                        "Model": model_name,
                        "Actual": int(actual),
                        "Prediction": int(predicted),
                    }
                )

        fold += 1

    if not results:
        raise ValueError(
            f"No valid folds produced for "
            f"{feature_set_name}"
        )

    return (
        pd.DataFrame(results),
        pd.DataFrame(predictions_all),
    )


# ---------------------------------------------------------
# FEATURE IMPORTANCE
# ---------------------------------------------------------

def show_feature_importance(
    data,
    features,
):
    """
    Fit a research random forest on the full historical sample
    only to inspect descriptive feature importance.

    This is NOT an out-of-sample performance test.
    """

    X = data[features]
    y = data["target"]

    forest = RandomForestClassifier(
        n_estimators=500,
        max_depth=4,
        min_samples_leaf=8,
        random_state=42,
        n_jobs=-1,
    )

    forest.fit(
        X,
        y,
    )

    importance = pd.Series(
        forest.feature_importances_,
        index=features,
    ).sort_values(
        ascending=False
    )

    print(
        "\nTOP ENHANCED FEATURE IMPORTANCE"
    )
    print("=" * 70)

    print(
        importance
        .head(15)
        .round(4)
        .to_string()
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print(
        "\nDAY 49 — ENHANCED ML FEATURE ENGINEERING"
    )
    print("=" * 70)

    prices = load_prices(
        TICKER
    )

    print(
        f"Ticker: {TICKER}"
    )

    print(
        f"Raw price observations: {len(prices)}"
    )

    print(
        "Raw sample: "
        f"{prices['date'].min().date()} "
        "to "
        f"{prices['date'].max().date()}"
    )

    # -----------------------------------------------------
    # BASELINE FEATURES
    # -----------------------------------------------------

    baseline_data, baseline_features = (
        create_baseline_features(
            prices
        )
    )

    print(
        "\nBASELINE FEATURE SET"
    )
    print("-" * 70)

    print(
        f"Features: {len(baseline_features)}"
    )

    print(
        baseline_features
    )

    print(
        f"Usable observations: "
        f"{len(baseline_data)}"
    )

    # -----------------------------------------------------
    # ENHANCED FEATURES
    # -----------------------------------------------------

    enhanced_data, enhanced_features = (
        create_enhanced_features(
            prices
        )
    )

    print(
        "\nENHANCED FEATURE SET"
    )
    print("-" * 70)

    print(
        f"Features: {len(enhanced_features)}"
    )

    print(
        f"Usable observations: "
        f"{len(enhanced_data)}"
    )

    for feature in enhanced_features:
        print(
            f"  - {feature}"
        )

    # -----------------------------------------------------
    # WALK-FORWARD BASELINE
    # -----------------------------------------------------

    baseline_results, baseline_predictions = (
        walk_forward_evaluate(
            baseline_data,
            baseline_features,
            "Baseline",
        )
    )

    # -----------------------------------------------------
    # WALK-FORWARD ENHANCED
    # -----------------------------------------------------

    enhanced_results, enhanced_predictions = (
        walk_forward_evaluate(
            enhanced_data,
            enhanced_features,
            "Enhanced",
        )
    )

    all_results = pd.concat(
        [
            baseline_results,
            enhanced_results,
        ],
        ignore_index=True,
    )

    all_predictions = pd.concat(
        [
            baseline_predictions,
            enhanced_predictions,
        ],
        ignore_index=True,
    )

    # -----------------------------------------------------
    # AVERAGE FOLD PERFORMANCE
    # -----------------------------------------------------

    average_results = (
        all_results
        .groupby(
            [
                "Feature Set",
                "Model",
            ]
        )[
            [
                "Accuracy",
                "Balanced Accuracy",
                "Precision (Up)",
                "Recall (Up)",
                "F1 (Up)",
            ]
        ]
        .mean()
    )

    print(
        "\nAVERAGE WALK-FORWARD PERFORMANCE"
    )
    print("=" * 70)

    print(
        average_results
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # POOLED PERFORMANCE
    # -----------------------------------------------------

    pooled_rows = []

    for (
        feature_set,
        model_name
    ), group in all_predictions.groupby(
        [
            "Feature Set",
            "Model",
        ]
    ):

        metrics = calculate_metrics(
            group["Actual"],
            group["Prediction"],
        )

        pooled_rows.append(
            {
                "Feature Set": feature_set,
                "Model": model_name,
                "Observations": len(group),
                **metrics,
            }
        )

    pooled = (
        pd.DataFrame(
            pooled_rows
        )
        .set_index(
            [
                "Feature Set",
                "Model",
            ]
        )
    )

    print(
        "\nPOOLED OUT-OF-SAMPLE PERFORMANCE"
    )
    print("=" * 70)

    print(
        pooled
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # DIRECT FEATURE-SET COMPARISON
    # -----------------------------------------------------

    print(
        "\nENHANCED FEATURES VS BASELINE"
    )
    print("=" * 70)

    models_to_compare = [
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]

    for model_name in models_to_compare:

        try:
            baseline_balanced = pooled.loc[
                (
                    "Baseline",
                    model_name,
                ),
                "Balanced Accuracy",
            ]

            enhanced_balanced = pooled.loc[
                (
                    "Enhanced",
                    model_name,
                ),
                "Balanced Accuracy",
            ]

            difference = (
                enhanced_balanced
                - baseline_balanced
            )

            print(
                f"{model_name:<22} "
                f"Baseline={baseline_balanced:.4f} | "
                f"Enhanced={enhanced_balanced:.4f} | "
                f"Change={difference:+.4f}"
            )

        except KeyError:
            continue

    # -----------------------------------------------------
    # FEATURE IMPORTANCE
    # -----------------------------------------------------

    show_feature_importance(
        enhanced_data,
        enhanced_features,
    )

    # -----------------------------------------------------
    # TARGET BALANCE
    # -----------------------------------------------------

    target_balance = (
        enhanced_data["target"]
        .value_counts(
            normalize=True
        )
        .sort_index()
    )

    print(
        "\nTARGET DISTRIBUTION"
    )
    print("=" * 70)

    print(
        f"Down / Flat: "
        f"{target_balance.get(0, 0):.2%}"
    )

    print(
        f"Up:          "
        f"{target_balance.get(1, 0):.2%}"
    )

    # -----------------------------------------------------
    # INTERPRETATION
    # -----------------------------------------------------

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 70)

    print(
        "- Day 49 expands the feature set without changing "
        "the original next-day target."
        "\n- This helps isolate whether additional market "
        "information improves prediction."
        "\n- All features are calculated using current or "
        "historical observations only."
        "\n- Walk-forward validation preserves chronological order."
        "\n- More features do not automatically produce a better model."
        "\n- Feature importance is descriptive and does not establish "
        "causality."
        "\n- Next-day direction is inherently noisy and may remain "
        "difficult to predict."
        "\n- If enhanced features remain weak, Vittantra should next "
        "research alternative target definitions."
        "\n- Future stages can incorporate point-in-time macroeconomic, "
        "cross-asset and fundamental information."
        "\n- No result here establishes future investment performance."
    )


if __name__ == "__main__":
    main()