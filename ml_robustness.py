"""
Day 51 — 20-Day Signal Robustness & Leakage Audit

Investigate the unusually strong 20-trading-day result from Day 50.

Tests:
1. Expanding-window walk-forward validation
2. 20-day purge between train and test
3. Non-overlapping test observations
4. Majority-class benchmark
5. Simple momentum benchmark
6. Logistic regression
7. Decision tree
8. Random forest
9. Fold-by-fold stability
10. Class-balance diagnostics

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
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from ml_feature_engineering import (
    TICKER,
    create_enhanced_features,
    load_prices,
)


HORIZON = 20

# Use a reasonably large initial training sample.
INITIAL_TRAIN_FRACTION = 0.60

# Test observations are selected every 20 trading observations,
# reducing overlap among evaluated forward-return windows.
TEST_STEP = HORIZON


def build_models():
    """Create fresh ML models for every fold."""

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


def create_20_day_dataset(
    feature_data,
    features,
):
    """
    Construct a 20-trading-day forward target.

    Features are observed at time t.
    The target asks whether price at t+20 is above price at t.
    """

    data = (
        feature_data
        .sort_values("date")
        .reset_index(drop=True)
        .copy()
    )

    future_price = (
        data["close_price"]
        .shift(-HORIZON)
    )

    data["forward_return_20d"] = (
        future_price
        / data["close_price"]
        - 1
    )

    data["target_20d"] = np.where(
        data["forward_return_20d"].notna(),
        (
            data["forward_return_20d"] > 0
        ).astype(int),
        np.nan,
    )

    data = data.dropna(
        subset=(
            features
            + [
                "forward_return_20d",
                "target_20d",
            ]
        )
    ).copy()

    data["target_20d"] = (
        data["target_20d"]
        .astype(int)
    )

    return data


def classification_metrics(
    y_true,
    predictions,
):
    """Return the main classification diagnostics."""

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


def momentum_prediction(row):
    """
    Simple non-ML benchmark.

    Predict UP when the historical 20-day return known at time t
    is positive; otherwise predict DOWN / FLAT.
    """

    return int(
        row["return_20d"] > 0
    )


def run_robustness_test(
    data,
    features,
):
    """
    Evaluate one non-overlapping observation per fold.

    For a test observation at index t, training stops at t-HORIZON.

    This means the last training observation's forward target
    finishes before the test observation begins.
    """

    initial_test_index = int(
        len(data)
        * INITIAL_TRAIN_FRACTION
    )

    # Align the starting point to the next full horizon block.
    initial_test_index = max(
        initial_test_index,
        HORIZON + 30,
    )

    fold_rows = []
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

        test_date = (
            test["date"]
            .iloc[0]
            .date()
        )

        train_end_date = (
            train["date"]
            .max()
            .date()
        )

        actual = int(
            y_test.iloc[0]
        )

        forward_return = float(
            test["forward_return_20d"]
            .iloc[0]
        )

        train_up_pct = (
            y_train.mean()
            * 100
        )

        print(
            f"\nFOLD {fold_number}"
        )
        print("-" * 70)

        print(
            f"Train through: {train_end_date}"
        )

        print(
            f"Test date:     {test_date}"
        )

        print(
            f"Train size:    {len(train)}"
        )

        print(
            f"Training UP:   {train_up_pct:.2f}%"
        )

        print(
            "Actual 20-day return: "
            f"{forward_return:.2%}"
        )

        print(
            "Actual class: "
            f"{'UP' if actual == 1 else 'DOWN / FLAT'}"
        )

        models = build_models()

        # -------------------------------------------------
        # ML + MAJORITY BENCHMARK
        # -------------------------------------------------

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
                    "Fold": fold_number,
                    "Date": test_date,
                    "Model": model_name,
                    "Actual": actual,
                    "Prediction": prediction,
                    "Forward Return": forward_return,
                }
            )

            print(
                f"{model_name:<22} "
                f"{'UP' if prediction == 1 else 'DOWN / FLAT'}"
            )

        # -------------------------------------------------
        # SIMPLE MOMENTUM BENCHMARK
        # -------------------------------------------------

        momentum_pred = momentum_prediction(
            test.iloc[0]
        )

        prediction_rows.append(
            {
                "Fold": fold_number,
                "Date": test_date,
                "Model": "20-Day Momentum Rule",
                "Actual": actual,
                "Prediction": momentum_pred,
                "Forward Return": forward_return,
            }
        )

        print(
            f"{'20-Day Momentum Rule':<22} "
            f"{'UP' if momentum_pred == 1 else 'DOWN / FLAT'}"
        )

        fold_rows.append(
            {
                "Fold": fold_number,
                "Train End": train_end_date,
                "Test Date": test_date,
                "Train Size": len(train),
                "Training Up (%)": train_up_pct,
                "Actual": actual,
                "Forward Return": forward_return,
            }
        )

        fold_number += 1

    if not prediction_rows:
        raise ValueError(
            "No robustness folds were produced."
        )

    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(prediction_rows),
    )


def summarize_predictions(
    predictions,
):
    """Calculate pooled performance for each model."""

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


def main():

    print(
        "\nDAY 51 — 20-DAY SIGNAL ROBUSTNESS & LEAKAGE AUDIT"
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

    data = create_20_day_dataset(
        feature_data,
        features,
    )

    print(
        f"Ticker: {TICKER}"
    )

    print(
        f"Forecast horizon: {HORIZON} trading days"
    )

    print(
        f"Enhanced features: {len(features)}"
    )

    print(
        f"Usable observations: {len(data)}"
    )

    print(
        "Sample: "
        f"{data['date'].min().date()} "
        "to "
        f"{data['date'].max().date()}"
    )

    print(
        "\nTARGET BALANCE"
    )
    print("-" * 70)

    up_pct = (
        data["target_20d"]
        .mean()
        * 100
    )

    print(
        f"UP observations:        {up_pct:.2f}%"
    )

    print(
        f"DOWN / FLAT observations: "
        f"{100 - up_pct:.2f}%"
    )

    folds, predictions = (
        run_robustness_test(
            data,
            features,
        )
    )

    # -----------------------------------------------------
    # POOLED PERFORMANCE
    # -----------------------------------------------------

    summary = summarize_predictions(
        predictions
    )

    print(
        "\nROBUST NON-OVERLAPPING PERFORMANCE"
    )
    print("=" * 70)

    print(
        summary
        .round(4)
        .to_string()
    )

    # -----------------------------------------------------
    # CORRECT / INCORRECT BY FOLD
    # -----------------------------------------------------

    audit = predictions.copy()

    audit["Correct"] = (
        audit["Actual"]
        == audit["Prediction"]
    )

    audit_table = (
        audit.pivot(
            index="Date",
            columns="Model",
            values="Correct",
        )
    )

    print(
        "\nCORRECT PREDICTION BY TEST DATE"
    )
    print("=" * 70)

    print(
        audit_table
        .to_string()
    )

    # -----------------------------------------------------
    # CONFUSION MATRICES
    # -----------------------------------------------------

    print(
        "\nCONFUSION MATRICES"
    )
    print("=" * 70)

    for model_name, group in predictions.groupby(
        "Model"
    ):

        matrix = confusion_matrix(
            group["Actual"],
            group["Prediction"],
            labels=[0, 1],
        )

        print(
            f"\n{model_name}"
        )

        print(
            matrix
        )

    # -----------------------------------------------------
    # RETURN CHARACTERISTICS
    # -----------------------------------------------------

    evaluated_dates = (
        folds[
            [
                "Test Date",
                "Actual",
                "Forward Return",
            ]
        ]
        .drop_duplicates()
    )

    print(
        "\nNON-OVERLAPPING TEST RETURN CHARACTERISTICS"
    )
    print("=" * 70)

    print(
        "Number of evaluated periods: "
        f"{len(evaluated_dates)}"
    )

    print(
        "Mean 20-day return: "
        f"{evaluated_dates['Forward Return'].mean():.2%}"
    )

    print(
        "Median 20-day return: "
        f"{evaluated_dates['Forward Return'].median():.2%}"
    )

    print(
        "Positive periods: "
        f"{evaluated_dates['Actual'].mean():.2%}"
    )

    # -----------------------------------------------------
    # DAY 50 COMPARISON WARNING
    # -----------------------------------------------------

    print(
        "\nDAY 50 COMPARISON"
    )
    print("=" * 70)

    print(
        "Day 50 Random Forest 20-day balanced accuracy "
        "was approximately 0.8802."
    )

    rf_rows = predictions[
        predictions["Model"]
        == "Random Forest"
    ]

    rf_robust = balanced_accuracy_score(
        rf_rows["Actual"],
        rf_rows["Prediction"],
    )

    print(
        "Day 51 non-overlapping Random Forest "
        "balanced accuracy: "
        f"{rf_robust:.4f}"
    )

    print(
        "Difference: "
        f"{rf_robust - 0.8802:+.4f}"
    )

    # -----------------------------------------------------
    # INTERPRETATION
    # -----------------------------------------------------

    print(
        "\nINTERPRETATION NOTES"
    )
    print("=" * 70)

    print(
        "- Day 51 intentionally uses far fewer test observations."
        "\n- Test observations are spaced 20 trading observations apart."
        "\n- A 20-observation purge separates training from each test date."
        "\n- This substantially reduces overlap in evaluated forward-return windows."
        "\n- The simple momentum rule provides a non-ML comparison."
        "\n- Very small test samples can produce unstable accuracy estimates."
        "\n- A large decline from Day 50 would suggest the earlier result "
        "depended heavily on overlapping observations or the particular sample."
        "\n- A strong result that survives still requires testing across more "
        "history, securities, regimes and truly unseen data."
        "\n- No result here establishes future investment performance."
    )


if __name__ == "__main__":
    main()