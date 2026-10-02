"""
Day 48 — Machine Learning Walk-Forward Validation

Evaluate Vittantra's machine-learning models across multiple
chronological out-of-sample periods instead of relying on one
train/test split.

Research only. No live trading or investment recommendations.
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

# Reuse the exact data preparation from Days 46 and 47.
from ml_baseline import TICKER, create_features, load_prices


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

INITIAL_TRAIN_FRACTION = 0.60
TEST_WINDOW = 10


def build_models():
    """
    Create fresh model instances for every walk-forward fold.

    Fresh models are important because each fold must be trained
    only on information available before that test period.
    """

    return {
        "Majority-Class Benchmark": DummyClassifier(
            strategy="most_frequent"
        ),

        "Logistic Regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
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
            n_estimators=200,
            max_depth=3,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        ),
    }


def calculate_metrics(y_true, predictions):
    """
    Calculate the same classification metrics used on Day 47.
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
            np.mean(predictions == 1) * 100
        ),
    }


def main():
    print("\nDAY 48 — WALK-FORWARD ML VALIDATION")
    print("=" * 65)

    # -----------------------------------------------------
    # STEP 1: Load exactly the same dataset as Day 47.
    # -----------------------------------------------------

    prices = load_prices(TICKER)
    data, features = create_features(prices)

    if len(data) < 50:
        raise ValueError(
            "Insufficient historical observations."
        )

    data = data.sort_values("date").reset_index(drop=True)

    print(f"Ticker: {TICKER}")
    print(f"Features: {features}")
    print(f"Total observations: {len(data)}")

    print(
        "Full sample: "
        f"{data['date'].min().date()} to "
        f"{data['date'].max().date()}"
    )

    # -----------------------------------------------------
    # STEP 2: Determine initial training window.
    # -----------------------------------------------------

    initial_train_size = int(
        len(data) * INITIAL_TRAIN_FRACTION
    )

    if initial_train_size < 30:
        raise ValueError(
            "Initial training window is too small."
        )

    if initial_train_size >= len(data):
        raise ValueError(
            "Initial training window leaves no test data."
        )

    print(
        f"Initial training observations: "
        f"{initial_train_size}"
    )

    print(
        f"Test window per fold: {TEST_WINDOW}"
    )

    # -----------------------------------------------------
    # STEP 3: Expanding-window walk-forward validation.
    #
    # Fold 1:
    # [ TRAIN TRAIN TRAIN ] [ TEST ]
    #
    # Fold 2:
    # [ TRAIN TRAIN TRAIN TRAIN ] [ TEST ]
    #
    # The model never sees future observations during training.
    # -----------------------------------------------------

    fold_results = []
    prediction_records = []

    fold_number = 1

    for test_start in range(
        initial_train_size,
        len(data),
        TEST_WINDOW,
    ):
        test_end = min(
            test_start + TEST_WINDOW,
            len(data),
        )

        train = data.iloc[:test_start].copy()
        test = data.iloc[test_start:test_end].copy()

        if test.empty:
            continue

        X_train = train[features]
        y_train = train["target"]

        X_test = test[features]
        y_test = test["target"]

        # Classification requires both classes in training.
        if y_train.nunique() < 2:
            print(
                f"\nSkipping fold {fold_number}: "
                "training data contains only one class."
            )
            fold_number += 1
            continue

        print(
            f"\nFOLD {fold_number}"
        )
        print("-" * 65)

        print(
            "Train: "
            f"{train['date'].min().date()} to "
            f"{train['date'].max().date()} "
            f"({len(train)} observations)"
        )

        print(
            "Test:  "
            f"{test['date'].min().date()} to "
            f"{test['date'].max().date()} "
            f"({len(test)} observations)"
        )

        models = build_models()

        for name, model in models.items():
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
                    "Fold": fold_number,
                    "Model": name,
                    "Train Size": len(train),
                    "Test Size": len(test),
                    "Train End": train["date"].max(),
                    "Test Start": test["date"].min(),
                    "Test End": test["date"].max(),
                    **metrics,
                }
            )

            for row_position, prediction in enumerate(
                predictions
            ):
                actual_row = test.iloc[row_position]

                prediction_records.append(
                    {
                        "Fold": fold_number,
                        "Date": actual_row["date"],
                        "Model": name,
                        "Actual": int(
                            actual_row["target"]
                        ),
                        "Prediction": int(
                            prediction
                        ),
                    }
                )

            print(
                f"{name:<28} "
                f"Accuracy={metrics['Accuracy']:.4f} | "
                f"Balanced="
                f"{metrics['Balanced Accuracy']:.4f}"
            )

        fold_number += 1

    # -----------------------------------------------------
    # STEP 4: Validate that folds were produced.
    # -----------------------------------------------------

    if not fold_results:
        raise ValueError(
            "No valid walk-forward folds were produced."
        )

    results = pd.DataFrame(fold_results)
    predictions_df = pd.DataFrame(
        prediction_records
    )

    # -----------------------------------------------------
    # STEP 5: Average fold-level performance.
    # -----------------------------------------------------

    metric_columns = [
        "Accuracy",
        "Balanced Accuracy",
        "Precision (Up)",
        "Recall (Up)",
        "F1 (Up)",
        "Predicted Up (%)",
    ]

    average_results = (
        results
        .groupby("Model")[metric_columns]
        .mean()
    )

    # Preserve the same model order used in Day 47.
    model_order = [
        "Majority-Class Benchmark",
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]

    average_results = average_results.reindex(
        model_order
    )

    print(
        "\nAVERAGE WALK-FORWARD PERFORMANCE"
    )
    print("=" * 65)

    print(
        average_results
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # STEP 6: Calculate pooled out-of-sample performance.
    #
    # This treats every prediction across all folds as one
    # continuous collection of unseen observations.
    # -----------------------------------------------------

    pooled_results = []

    for model_name in model_order:
        model_predictions = predictions_df[
            predictions_df["Model"] == model_name
        ].copy()

        if model_predictions.empty:
            continue

        y_true = model_predictions["Actual"]
        y_pred = model_predictions["Prediction"]

        metrics = calculate_metrics(
            y_true,
            y_pred,
        )

        pooled_results.append(
            {
                "Model": model_name,
                "Out-of-Sample Observations": len(
                    model_predictions
                ),
                **metrics,
            }
        )

    pooled = (
        pd.DataFrame(pooled_results)
        .set_index("Model")
        .reindex(model_order)
    )

    print(
        "\nPOOLED OUT-OF-SAMPLE PERFORMANCE"
    )
    print("=" * 65)

    print(
        pooled
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # STEP 7: Compare each ML model with the benchmark.
    # -----------------------------------------------------

    benchmark_balanced = pooled.loc[
        "Majority-Class Benchmark",
        "Balanced Accuracy",
    ]

    print(
        "\nBALANCED ACCURACY VS BENCHMARK"
    )
    print("=" * 65)

    for model_name in [
        "Logistic Regression",
        "Decision Tree",
        "Random Forest",
    ]:
        model_balanced = pooled.loc[
            model_name,
            "Balanced Accuracy",
        ]

        difference = (
            model_balanced
            - benchmark_balanced
        )

        print(
            f"{model_name:<22}: "
            f"{model_balanced:.4f} "
            f"({difference:+.4f} vs benchmark)"
        )

    # -----------------------------------------------------
    # STEP 8: Stability across folds.
    #
    # A model that performs extremely well once and badly
    # everywhere else is less convincing than a model with
    # more stable out-of-sample behavior.
    # -----------------------------------------------------

    stability = (
        results
        .groupby("Model")["Balanced Accuracy"]
        .agg(
            Mean="mean",
            Std_Dev="std",
            Minimum="min",
            Maximum="max",
        )
        .reindex(model_order)
    )

    print(
        "\nBALANCED ACCURACY STABILITY"
    )
    print("=" * 65)

    print(
        stability
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # STEP 9: Research interpretation.
    # -----------------------------------------------------

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 65)

    print(
        "- Walk-forward validation preserves chronological order."
        "\n- Every test observation occurs after its training data."
        "\n- Training expands as new historical observations become "
        "available."
        "\n- The majority-class benchmark is refitted independently "
        "inside every fold."
        "\n- Balanced accuracy is important when class frequencies "
        "are uneven."
        "\n- Average fold performance and pooled performance answer "
        "slightly different questions."
        "\n- Performance stability matters in addition to average "
        "performance."
        "\n- A model beating the benchmark here still does not prove "
        "economic profitability."
        "\n- Transaction costs, probability calibration, regime "
        "changes and trading rules are not evaluated here."
        "\n- These results are research evidence, not investment "
        "recommendations."
    )


if __name__ == "__main__":
    main()