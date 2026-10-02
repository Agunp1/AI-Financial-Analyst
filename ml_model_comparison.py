
"""
Day 47 — Machine Learning Model Comparison

Compare logistic regression, decision tree and random forest
against the training-period majority-class benchmark.

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
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

# Reuse the exact data preparation from Day 46.
from ml_baseline import TICKER, create_features, load_prices


def main():
    print("\nDAY 47 — MACHINE LEARNING MODEL COMPARISON")
    print("=" * 55)

    # STEP 1: Load the same data and features as Day 46.
    prices = load_prices(TICKER)
    data, features = create_features(prices)

    if len(data) < 50:
        raise ValueError("Insufficient historical observations.")

    # STEP 2: Use the same chronological 80/20 split.
    split = int(len(data) * 0.8)

    train = data.iloc[:split].copy()
    test = data.iloc[split:].copy()

    X_train = train[features]
    y_train = train["target"]

    X_test = test[features]
    y_test = test["target"]

    if y_train.nunique() < 2:
        raise ValueError(
            "Training data must contain both target classes."
        )

    print(f"Ticker: {TICKER}")
    print(f"Features: {features}")
    print(f"Training observations: {len(train)}")
    print(f"Testing observations: {len(test)}")

    print(
        f"Training period: "
        f"{train['date'].min().date()} to "
        f"{train['date'].max().date()}"
    )

    print(
        f"Testing period: "
        f"{test['date'].min().date()} to "
        f"{test['date'].max().date()}"
    )

    # STEP 3: Define the models.
    # All models receive identical training and testing data.
    models = {
        "Majority-Class Benchmark": DummyClassifier(
            strategy="most_frequent"
        ),

        "Logistic Regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(max_iter=1000),
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

    # STEP 4: Fit and evaluate every model.
    results = []

    for name, model in models.items():
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)

        results.append(
            {
                "Model": name,
                "Accuracy": accuracy_score(
                    y_test, predictions
                ),
                "Balanced Accuracy": balanced_accuracy_score(
                    y_test, predictions
                ),
                "Precision (Up)": precision_score(
                    y_test, predictions,
                    zero_division=0,
                ),
                "Recall (Up)": recall_score(
                    y_test, predictions,
                    zero_division=0,
                ),
                "F1 (Up)": f1_score(
                    y_test, predictions,
                    zero_division=0,
                ),
                "Predicted Up (%)": (
                    np.mean(predictions == 1) * 100
                ),
            }
        )

        print(f"\n{name.upper()}")
        print("-" * 55)

        print(
            classification_report(
                y_test,
                predictions,
                labels=[0, 1],
                target_names=["Down / Flat", "Up"],
                zero_division=0,
            )
        )

        print("Confusion matrix:")
        print(
            confusion_matrix(
                y_test,
                predictions,
                labels=[0, 1],
            )
        )

    # STEP 5: Display the comparison table.
    comparison = pd.DataFrame(results).set_index("Model")

    print("\nMODEL COMPARISON")
    print("=" * 55)

    print(
        comparison.round(4).to_string()
    )

    # STEP 6: Examine random forest feature importance.
    forest = models["Random Forest"]

    importance = pd.Series(
        forest.feature_importances_,
        index=features,
    ).sort_values(ascending=False)

    print("\nRANDOM FOREST FEATURE IMPORTANCE")
    print("=" * 55)
    print(importance.round(4).to_string())

    print(
        "\nInterpretation notes:"
        "\n- The benchmark uses the majority class in training."
        "\n- Balanced accuracy accounts for both target classes."
        "\n- Feature importance is descriptive, not causal."
        "\n- The test period is short and is used only for evaluation."
        "\n- These results do not establish future predictive performance."
    )


if __name__ == "__main__":
    main()
