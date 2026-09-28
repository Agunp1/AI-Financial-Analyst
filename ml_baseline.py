
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DB_PATH = Path(__file__).resolve().parent / "hedge_fund.db"
TICKER = "AAPL"


def load_prices(ticker):
    """Load historical prices from the existing project database."""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT date, ticker, close_price
            FROM daily_prices
            WHERE ticker = ?
            ORDER BY date
            """,
            conn,
            params=(ticker,),
        )

    if df.empty:
        raise ValueError(f"No historical prices found for {ticker}")

    df["date"] = pd.to_datetime(df["date"])
    df["close_price"] = pd.to_numeric(df["close_price"])
    return df


def create_features(df):
    """Create features using only information known at each date."""
    df = df.copy()

    df["return_1d"] = df["close_price"].pct_change()
    df["return_5d"] = df["close_price"].pct_change(5)
    df["volatility_5d"] = df["return_1d"].rolling(5).std()
    df["ma_5_ratio"] = (
        df["close_price"] / df["close_price"].rolling(5).mean() - 1
    )
    df["ma_20_ratio"] = (
        df["close_price"] / df["close_price"].rolling(20).mean() - 1
    )

    # Predict the direction of the NEXT trading day's return.
    next_return = df["close_price"].shift(-1) / df["close_price"] - 1
    df["target"] = np.where(
        next_return.notna(),
        (next_return > 0).astype(int),
        np.nan,
    )

    feature_cols = [
        "return_1d",
        "return_5d",
        "volatility_5d",
        "ma_5_ratio",
        "ma_20_ratio",
    ]

    df = df.dropna(subset=feature_cols + ["target"]).copy()
    df["target"] = df["target"].astype(int)

    return df, feature_cols


def main():
    prices = load_prices(TICKER)
    data, features = create_features(prices)

    if len(data) < 50:
        raise ValueError("Not enough historical observations for this model.")

    # Chronological split: earlier observations train the model;
    # later observations evaluate it.
    split = int(len(data) * 0.8)

    train = data.iloc[:split]
    test = data.iloc[split:]

    X_train = train[features]
    y_train = train["target"]
    X_test = test[features]
    y_test = test["target"]

    if y_train.nunique() < 2:
        raise ValueError("Training data must contain both target classes.")

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000)),
        ]
    )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    # A simple benchmark: always predict the majority
    # class observed in the training period.
    majority_class = int(y_train.mode().iloc[0])
    baseline_predictions = np.full(len(y_test), majority_class)

    print("\nDAY 46 — MACHINE LEARNING BASELINE")
    print("=" * 45)
    print(f"Ticker: {TICKER}")
    print(f"Training observations: {len(train)}")
    print(f"Testing observations: {len(test)}")
    print(f"Training period: {train['date'].min().date()} "
          f"to {train['date'].max().date()}")
    print(f"Testing period: {test['date'].min().date()} "
          f"to {test['date'].max().date()}")

    print(f"\nLogistic regression accuracy: "
          f"{accuracy_score(y_test, predictions):.2%}")
    print(f"Majority-class benchmark: "
          f"{accuracy_score(y_test, baseline_predictions):.2%}")

    print("\nClassification report:")
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
    print(confusion_matrix(y_test, predictions, labels=[0, 1]))

    print(
        "\nResearch only. Historical test results do not establish "
        "future predictive performance."
    )


if __name__ == "__main__":
    main()
