"""
Day 50 — Forward Horizon & Target Research

Research whether Vittantra's machine-learning evidence becomes more
informative when predicting forward returns over different investment
horizons rather than only next-day direction.

Horizons tested:
    1 trading day
    5 trading days
    10 trading days
    20 trading days

The enhanced Day 49 feature architecture is reused.

Research only.
No live trading or investment recommendations.
"""

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

from ml_feature_engineering import (
    TICKER,
    INITIAL_TRAIN_FRACTION,
    TEST_WINDOW,
    create_enhanced_features,
    load_prices,
)


HORIZONS = [1, 5, 10, 20]


def build_models():
    """
    Build fresh model instances for every walk-forward fold.
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


def calculate_metrics(y_true, predictions):
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


def create_horizon_dataset(
    feature_data,
    features,
    horizon,
):
    """
    Create a binary target for a specified forward horizon.

    Example:
        horizon = 5

    asks whether the closing price five trading observations
    into the future is higher than today's closing price.

    Features remain known at time t.
    Target uses future prices only for research labeling.
    """

    data = feature_data.copy()

    future_price = (
        data["close_price"]
        .shift(-horizon)
    )

    data["forward_return"] = (
        future_price
        / data["close_price"]
        - 1
    )

    data["target_horizon"] = np.where(
        data["forward_return"].notna(),
        (
            data["forward_return"] > 0
        ).astype(int),
        np.nan,
    )

    data = data.dropna(
        subset=features
        + [
            "forward_return",
            "target_horizon",
        ]
    ).copy()

    data["target_horizon"] = (
        data["target_horizon"]
        .astype(int)
    )

    return data


def walk_forward_horizon(
    data,
    features,
    horizon,
):
    """
    Run expanding-window walk-forward validation for one horizon.

    A purge gap equal to the forecast horizon is used between
    training labels and the test block.

    This reduces overlap between the future period used to define
    the final training labels and the beginning of the test period.
    """

    data = (
        data
        .sort_values("date")
        .reset_index(drop=True)
    )

    initial_test_start = int(
        len(data)
        * INITIAL_TRAIN_FRACTION
    )

    if initial_test_start < 30:
        raise ValueError(
            f"Horizon {horizon}: "
            "initial sample too small."
        )

    fold_results = []
    prediction_records = []

    fold_number = 1

    for test_start in range(
        initial_test_start,
        len(data),
        TEST_WINDOW,
    ):
        test_end = min(
            test_start + TEST_WINDOW,
            len(data),
        )

        # Purge the final 'horizon' rows from training.
        train_end = (
            test_start
            - horizon
        )

        if train_end <= 0:
            continue

        train = data.iloc[
            :train_end
        ].copy()

        test = data.iloc[
            test_start:test_end
        ].copy()

        if test.empty:
            continue

        if len(train) < 30:
            continue

        X_train = train[features]
        y_train = train["target_horizon"]

        X_test = test[features]
        y_test = test["target_horizon"]

        if y_train.nunique() < 2:
            fold_number += 1
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

            fold_results.append(
                {
                    "Horizon": horizon,
                    "Fold": fold_number,
                    "Model": model_name,
                    "Train Size": len(train),
                    "Test Size": len(test),
                    **metrics,
                }
            )

            for actual, prediction in zip(
                y_test,
                predictions,
            ):
                prediction_records.append(
                    {
                        "Horizon": horizon,
                        "Fold": fold_number,
                        "Model": model_name,
                        "Actual": int(actual),
                        "Prediction": int(prediction),
                    }
                )

        fold_number += 1

    if not fold_results:
        raise ValueError(
            f"No valid folds produced "
            f"for horizon {horizon}."
        )

    return (
        pd.DataFrame(fold_results),
        pd.DataFrame(prediction_records),
    )


def summarize_target(
    data,
    horizon,
):
    """
    Display target and forward-return characteristics.
    """

    up_percentage = (
        data["target_horizon"]
        .mean()
        * 100
    )

    down_percentage = (
        100
        - up_percentage
    )

    mean_forward_return = (
        data["forward_return"]
        .mean()
    )

    median_forward_return = (
        data["forward_return"]
        .median()
    )

    print(
        f"\nHORIZON: {horizon} TRADING DAY(S)"
    )
    print("-" * 70)

    print(
        f"Observations: {len(data)}"
    )

    print(
        f"Down / Flat: {down_percentage:.2f}%"
    )

    print(
        f"Up:          {up_percentage:.2f}%"
    )

    print(
        "Mean forward return: "
        f"{mean_forward_return:.4%}"
    )

    print(
        "Median forward return: "
        f"{median_forward_return:.4%}"
    )


def main():

    print(
        "\nDAY 50 — FORWARD HORIZON & TARGET RESEARCH"
    )
    print("=" * 70)

    prices = load_prices(
        TICKER
    )

    feature_data, features = (
        create_enhanced_features(
            prices
        )
    )

    print(
        f"Ticker: {TICKER}"
    )

    print(
        f"Enhanced features: {len(features)}"
    )

    print(
        f"Feature observations: "
        f"{len(feature_data)}"
    )

    print(
        "Feature sample: "
        f"{feature_data['date'].min().date()} "
        "to "
        f"{feature_data['date'].max().date()}"
    )

    all_fold_results = []
    all_predictions = []

    for horizon in HORIZONS:

        horizon_data = (
            create_horizon_dataset(
                feature_data,
                features,
                horizon,
            )
        )

        summarize_target(
            horizon_data,
            horizon,
        )

        fold_results, predictions = (
            walk_forward_horizon(
                horizon_data,
                features,
                horizon,
            )
        )

        all_fold_results.append(
            fold_results
        )

        all_predictions.append(
            predictions
        )

    fold_results = pd.concat(
        all_fold_results,
        ignore_index=True,
    )

    predictions = pd.concat(
        all_predictions,
        ignore_index=True,
    )

    # -----------------------------------------------------
    # AVERAGE FOLD PERFORMANCE
    # -----------------------------------------------------

    average_performance = (
        fold_results
        .groupby(
            [
                "Horizon",
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
        average_performance
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # POOLED OUT-OF-SAMPLE PERFORMANCE
    # -----------------------------------------------------

    pooled_rows = []

    for (
        horizon,
        model_name
    ), group in predictions.groupby(
        [
            "Horizon",
            "Model",
        ]
    ):

        metrics = calculate_metrics(
            group["Actual"],
            group["Prediction"],
        )

        pooled_rows.append(
            {
                "Horizon": horizon,
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
                "Horizon",
                "Model",
            ]
        )
        .sort_index()
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
    # BALANCED ACCURACY SUMMARY
    # -----------------------------------------------------

    balanced_table = (
        pooled["Balanced Accuracy"]
        .unstack("Model")
    )

    desired_order = [
        "Majority Benchmark",
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]

    balanced_table = (
        balanced_table
        .reindex(
            columns=desired_order
        )
    )

    print(
        "\nBALANCED ACCURACY BY HORIZON"
    )
    print("=" * 70)

    print(
        balanced_table
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # EXCESS BALANCED ACCURACY VS BENCHMARK
    # -----------------------------------------------------

    print(
        "\nMODEL IMPROVEMENT VS BENCHMARK"
    )
    print("=" * 70)

    for horizon in HORIZONS:

        if horizon not in balanced_table.index:
            continue

        benchmark = balanced_table.loc[
            horizon,
            "Majority Benchmark",
        ]

        print(
            f"\n{horizon}-DAY HORIZON"
        )

        for model_name in [
            "Logistic Regression",
            "Decision Tree",
            "Random Forest",
        ]:

            score = balanced_table.loc[
                horizon,
                model_name,
            ]

            improvement = (
                score
                - benchmark
            )

            print(
                f"{model_name:<22} "
                f"{score:.4f} "
                f"({improvement:+.4f} "
                "vs benchmark)"
            )

    # -----------------------------------------------------
    # STABILITY
    # -----------------------------------------------------

    stability = (
        fold_results
        .groupby(
            [
                "Horizon",
                "Model",
            ]
        )["Balanced Accuracy"]
        .agg(
            Mean="mean",
            Std_Dev="std",
            Minimum="min",
            Maximum="max",
        )
    )

    print(
        "\nBALANCED ACCURACY STABILITY"
    )
    print("=" * 70)

    print(
        stability
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # RESEARCH NOTES
    # -----------------------------------------------------

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 70)

    print(
        "- Day 50 compares multiple forward investment horizons."
        "\n- Features are known at the prediction date."
        "\n- Future prices are used only to construct research labels."
        "\n- A purge gap is used between training and test periods."
        "\n- This reduces horizon overlap between training labels "
        "and test observations."
        "\n- Balanced accuracy helps compare models when target "
        "classes are uneven."
        "\n- Longer horizons can contain more persistent information, "
        "but they also create overlapping forward-return labels."
        "\n- Higher classification accuracy does not automatically "
        "mean higher investment returns."
        "\n- Transaction costs, turnover, probability calibration and "
        "portfolio sizing remain outside this experiment."
        "\n- Results are historical research evidence only."
    )


if __name__ == "__main__":
    main()