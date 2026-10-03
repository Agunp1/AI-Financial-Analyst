"""
VITTANTRA
Day 57 — Portfolio Robustness & Stress Testing

Purpose
-------
Pressure-test the Day 55 cross-sectional ranking signal and the
Day 56 portfolio backtest.

Tests
-----
1. Transaction-cost sensitivity
2. Portfolio basket-size sensitivity
3. Subperiod stability
4. Sector-neutral portfolio construction
5. Bootstrap confidence intervals
6. Signal monotonicity across ranking buckets

Input
-----
day55_cross_sectional_rankings.csv

Outputs
-------
day57_cost_sensitivity.csv
day57_basket_sensitivity.csv
day57_subperiod_stability.csv
day57_sector_neutral.csv
day57_bootstrap_summary.csv
day57_bucket_monotonicity.csv
day57_robustness_summary.csv
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("day55_cross_sectional_rankings.csv")

OUTPUT_COST = Path("day57_cost_sensitivity.csv")
OUTPUT_BASKET = Path("day57_basket_sensitivity.csv")
OUTPUT_SUBPERIOD = Path("day57_subperiod_stability.csv")
OUTPUT_SECTOR = Path("day57_sector_neutral.csv")
OUTPUT_BOOTSTRAP = Path("day57_bootstrap_summary.csv")
OUTPUT_BUCKET = Path("day57_bucket_monotonicity.csv")
OUTPUT_SUMMARY = Path("day57_robustness_summary.csv")

HORIZON_DAYS = 20
TRADING_DAYS = 252

# Day 56 used non-overlapping 20-day observations.
PERIODS_PER_YEAR = TRADING_DAYS / HORIZON_DAYS

RANDOM_SEED = 42
BOOTSTRAP_SAMPLES = 10_000

# Round-trip cost assumptions in basis points applied to turnover.
COST_LEVELS_BPS = [
    0,
    5,
    10,
    20,
    30,
    50,
    75,
    100,
]

# Cross-sectional fractions tested.
BASKET_FRACTIONS = [
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
]

MIN_SECURITIES_PER_DATE = 10


# ============================================================
# GENERAL HELPERS
# ============================================================

def banner(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def safe_divide(a: float, b: float) -> float:
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def annualized_return(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) == 0:
        return np.nan

    wealth = float((1.0 + r).prod())

    if wealth <= 0:
        return np.nan

    return wealth ** (PERIODS_PER_YEAR / len(r)) - 1.0


def annualized_volatility(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) < 2:
        return np.nan

    return float(r.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR))


def sharpe_ratio(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) < 2:
        return np.nan

    vol = r.std(ddof=1)

    if vol == 0:
        return np.nan

    return float(
        r.mean()
        / vol
        * np.sqrt(PERIODS_PER_YEAR)
    )


def sortino_ratio(returns: pd.Series) -> float:
    """
    Sortino = mean(R) / downside deviation x sqrt(periods per year),
    downside deviation = sqrt(mean(min(R, 0)^2)) over ALL periods.
    Long-short returns are self-financing excess returns, so no
    risk-free rate is subtracted.
    """
    r = pd.Series(returns).dropna()

    if len(r) < 2:
        return np.nan

    downside_deviation = float(
        np.sqrt((r.clip(upper=0.0) ** 2).mean())
    )

    if downside_deviation == 0:
        return np.nan

    return float(
        r.mean()
        / downside_deviation
        * np.sqrt(PERIODS_PER_YEAR)
    )


def maximum_drawdown(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) == 0:
        return np.nan

    wealth = (1.0 + r).cumprod()
    peak = wealth.cummax()

    drawdown = wealth / peak - 1.0

    return float(drawdown.min())


def cumulative_return(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) == 0:
        return np.nan

    return float((1.0 + r).prod() - 1.0)


def hit_rate(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()

    if len(r) == 0:
        return np.nan

    return float((r > 0).mean())


def performance_metrics(
    returns: pd.Series,
    name: str,
) -> dict:
    r = pd.Series(returns).dropna()

    return {
        "test": name,
        "periods": len(r),
        "cumulative_return": cumulative_return(r),
        "annualized_return": annualized_return(r),
        "annualized_volatility": annualized_volatility(r),
        "sharpe_ratio": sharpe_ratio(r),
        "sortino_ratio": sortino_ratio(r),
        "maximum_drawdown": maximum_drawdown(r),
        "hit_rate": hit_rate(r),
        "mean_period_return": (
            float(r.mean())
            if len(r) > 0
            else np.nan
        ),
    }


# ============================================================
# DATA LOADING
# ============================================================

def load_rankings() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {INPUT_FILE}."
        )

    df = pd.read_csv(INPUT_FILE)

    required = {
        "date",
        "ticker",
        "sector",
        "forward_return_20d",
        "up_probability",
    }

    missing = required.difference(df.columns)

    if missing:
        raise KeyError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    numeric_columns = [
        "forward_return_20d",
        "up_probability",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "date",
            "ticker",
            "forward_return_20d",
            "up_probability",
        ]
    ).copy()

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["sector"] = (
        df["sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    df = df.sort_values(
        ["date", "up_probability", "ticker"],
        ascending=[True, False, True],
    ).reset_index(drop=True)

    counts = df.groupby("date")["ticker"].nunique()

    valid_dates = counts[
        counts >= MIN_SECURITIES_PER_DATE
    ].index

    df = df[
        df["date"].isin(valid_dates)
    ].copy()

    return df


# ============================================================
# NON-OVERLAPPING DATES
# ============================================================

def select_non_overlapping_dates(
    df: pd.DataFrame,
) -> list[pd.Timestamp]:
    dates = sorted(
        pd.to_datetime(df["date"].unique())
    )

    selected = []
    last_date = None

    for date in dates:
        date = pd.Timestamp(date)

        if last_date is None:
            selected.append(date)
            last_date = date
            continue

        if (date - last_date).days >= HORIZON_DAYS:
            selected.append(date)
            last_date = date

    return selected


# ============================================================
# PORTFOLIO CONSTRUCTION
# ============================================================

def choose_basket_size(
    n: int,
    fraction: float,
) -> int:
    k = int(np.floor(n * fraction))

    k = max(1, k)

    # Long and short sides cannot overlap.
    k = min(k, n // 2)

    return k


def build_long_short_periods(
    df: pd.DataFrame,
    basket_fraction: float = 0.20,
    sector_neutral: bool = False,
) -> pd.DataFrame:

    selected_dates = select_non_overlapping_dates(df)

    rows = []

    previous_long = set()
    previous_short = set()

    for date in selected_dates:

        cross = df[
            df["date"] == date
        ].copy()

        if len(cross) < MIN_SECURITIES_PER_DATE:
            continue

        if sector_neutral:
            long_names = []
            short_names = []

            for sector, group in cross.groupby("sector"):

                group = group.sort_values(
                    "up_probability",
                    ascending=False,
                )

                n = len(group)

                if n < 2:
                    continue

                k = choose_basket_size(
                    n,
                    basket_fraction,
                )

                long_names.append(
                    group.head(k)
                )

                short_names.append(
                    group.tail(k)
                )

            if (
                len(long_names) == 0
                or len(short_names) == 0
            ):
                continue

            long_df = pd.concat(
                long_names,
                ignore_index=True,
            )

            short_df = pd.concat(
                short_names,
                ignore_index=True,
            )

        else:

            cross = cross.sort_values(
                "up_probability",
                ascending=False,
            )

            k = choose_basket_size(
                len(cross),
                basket_fraction,
            )

            long_df = cross.head(k).copy()
            short_df = cross.tail(k).copy()

        if len(long_df) == 0 or len(short_df) == 0:
            continue

        long_return = float(
            long_df["forward_return_20d"].mean()
        )

        short_return = float(
            short_df["forward_return_20d"].mean()
        )

        long_short_return = (
            long_return - short_return
        )

        current_long = set(
            long_df["ticker"].tolist()
        )

        current_short = set(
            short_df["ticker"].tolist()
        )

        if len(previous_long) == 0:
            long_turnover = 1.0
        else:
            retained = len(
                current_long.intersection(previous_long)
            )

            long_turnover = (
                1.0
                - safe_divide(
                    retained,
                    len(current_long),
                )
            )

        if len(previous_short) == 0:
            short_turnover = 1.0
        else:
            retained = len(
                current_short.intersection(previous_short)
            )

            short_turnover = (
                1.0
                - safe_divide(
                    retained,
                    len(current_short),
                )
            )

        # Average turnover across long and short books.
        turnover = np.nanmean(
            [
                long_turnover,
                short_turnover,
            ]
        )

        rows.append(
            {
                "date": date,
                "universe_size": len(cross),
                "long_names": len(long_df),
                "short_names": len(short_df),
                "long_return": long_return,
                "short_return": short_return,
                "long_short_gross_return": (
                    long_short_return
                ),
                "turnover": turnover,
                "sector_neutral": sector_neutral,
                "basket_fraction": basket_fraction,
            }
        )

        previous_long = current_long
        previous_short = current_short

    result = pd.DataFrame(rows)

    if not result.empty:
        result = result.sort_values(
            "date"
        ).reset_index(drop=True)

    return result


# ============================================================
# TEST 1 — TRANSACTION COST SENSITIVITY
# ============================================================

def transaction_cost_test(
    periods: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for bps in COST_LEVELS_BPS:

        cost_rate = bps / 10_000.0

        # Each book (100% long, 100% short) replaces a fraction f of
        # its names: f is sold and f is bought, so each book trades 2f.
        # Both books together trade 4f of portfolio value, and every
        # dollar traded pays the cost.
        transaction_cost = (
            periods["turnover"]
            * 4.0
            * cost_rate
        )

        net_returns = (
            periods["long_short_gross_return"]
            - transaction_cost
        )

        metrics = performance_metrics(
            net_returns,
            f"{bps} bps",
        )

        metrics["cost_bps"] = bps

        metrics["average_turnover"] = float(
            periods["turnover"].mean()
        )

        metrics["total_transaction_cost"] = float(
            transaction_cost.sum()
        )

        rows.append(metrics)

    return pd.DataFrame(rows)


# ============================================================
# TEST 2 — BASKET-SIZE SENSITIVITY
# ============================================================

def basket_sensitivity_test(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for fraction in BASKET_FRACTIONS:

        periods = build_long_short_periods(
            df,
            basket_fraction=fraction,
            sector_neutral=False,
        )

        if periods.empty:
            continue

        metrics = performance_metrics(
            periods["long_short_gross_return"],
            f"{fraction:.0%}",
        )

        metrics["basket_fraction"] = fraction

        metrics["average_long_names"] = float(
            periods["long_names"].mean()
        )

        metrics["average_short_names"] = float(
            periods["short_names"].mean()
        )

        metrics["average_turnover"] = float(
            periods["turnover"].mean()
        )

        rows.append(metrics)

    return pd.DataFrame(rows)


# ============================================================
# TEST 3 — SUBPERIOD STABILITY
# ============================================================

def subperiod_test(
    periods: pd.DataFrame,
) -> pd.DataFrame:

    if periods.empty:
        return pd.DataFrame()

    p = periods.sort_values(
        "date"
    ).reset_index(drop=True)

    n = len(p)

    if n < 6:
        return pd.DataFrame()

    midpoint = n // 2

    first_half = p.iloc[:midpoint]
    second_half = p.iloc[midpoint:]

    splits = {
        "Full Sample": p,
        "First Half": first_half,
        "Second Half": second_half,
    }

    # Add calendar-year tests.
    for year, group in p.groupby(
        p["date"].dt.year
    ):
        splits[f"Year {year}"] = group

    rows = []

    for name, sample in splits.items():

        metrics = performance_metrics(
            sample["long_short_gross_return"],
            name,
        )

        metrics["start_date"] = (
            sample["date"].min()
        )

        metrics["end_date"] = (
            sample["date"].max()
        )

        metrics["average_turnover"] = float(
            sample["turnover"].mean()
        )

        rows.append(metrics)

    return pd.DataFrame(rows)


# ============================================================
# TEST 4 — SECTOR-NEUTRAL CONSTRUCTION
# ============================================================

def sector_neutral_test(
    df: pd.DataFrame,
) -> pd.DataFrame:

    standard = build_long_short_periods(
        df,
        basket_fraction=0.20,
        sector_neutral=False,
    )

    neutral = build_long_short_periods(
        df,
        basket_fraction=0.20,
        sector_neutral=True,
    )

    rows = []

    for name, periods in [
        ("Standard Long Short", standard),
        ("Sector Neutral Long Short", neutral),
    ]:

        if periods.empty:
            continue

        metrics = performance_metrics(
            periods["long_short_gross_return"],
            name,
        )

        metrics["average_turnover"] = float(
            periods["turnover"].mean()
        )

        metrics["average_long_names"] = float(
            periods["long_names"].mean()
        )

        metrics["average_short_names"] = float(
            periods["short_names"].mean()
        )

        rows.append(metrics)

    return pd.DataFrame(rows)


# ============================================================
# TEST 5 — BOOTSTRAP CONFIDENCE INTERVALS
# ============================================================

def bootstrap_test(
    returns: pd.Series,
) -> pd.DataFrame:

    r = (
        pd.Series(returns)
        .dropna()
        .astype(float)
        .to_numpy()
    )

    if len(r) < 2:
        return pd.DataFrame()

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    bootstrap_means = np.empty(
        BOOTSTRAP_SAMPLES
    )

    bootstrap_sharpes = np.empty(
        BOOTSTRAP_SAMPLES
    )

    n = len(r)

    for i in range(BOOTSTRAP_SAMPLES):

        sample = rng.choice(
            r,
            size=n,
            replace=True,
        )

        bootstrap_means[i] = sample.mean()

        std = sample.std(ddof=1)

        if std > 0:
            bootstrap_sharpes[i] = (
                sample.mean()
                / std
                * np.sqrt(PERIODS_PER_YEAR)
            )
        else:
            bootstrap_sharpes[i] = np.nan

    mean_ci = np.quantile(
        bootstrap_means,
        [0.025, 0.50, 0.975],
    )

    valid_sharpes = bootstrap_sharpes[
        np.isfinite(bootstrap_sharpes)
    ]

    if len(valid_sharpes) > 0:
        sharpe_ci = np.quantile(
            valid_sharpes,
            [0.025, 0.50, 0.975],
        )
    else:
        sharpe_ci = [
            np.nan,
            np.nan,
            np.nan,
        ]

    probability_positive_mean = float(
        np.mean(
            bootstrap_means > 0
        )
    )

    result = {
        "observations": n,
        "observed_mean_period_return": float(
            r.mean()
        ),
        "observed_sharpe": sharpe_ratio(
            pd.Series(r)
        ),
        "mean_return_ci_2_5": mean_ci[0],
        "mean_return_ci_50": mean_ci[1],
        "mean_return_ci_97_5": mean_ci[2],
        "sharpe_ci_2_5": sharpe_ci[0],
        "sharpe_ci_50": sharpe_ci[1],
        "sharpe_ci_97_5": sharpe_ci[2],
        "bootstrap_probability_mean_positive": (
            probability_positive_mean
        ),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
    }

    return pd.DataFrame([result])


# ============================================================
# TEST 6 — BUCKET MONOTONICITY
# ============================================================

def bucket_monotonicity_test(
    df: pd.DataFrame,
) -> pd.DataFrame:

    selected_dates = select_non_overlapping_dates(
        df
    )

    rows = []

    for date in selected_dates:

        cross = df[
            df["date"] == date
        ].copy()

        if len(cross) < MIN_SECURITIES_PER_DATE:
            continue

        cross = cross.sort_values(
            "up_probability",
            ascending=True,
        ).reset_index(drop=True)

        # Rank method='first' avoids qcut problems
        # when predicted probabilities are tied.
        cross["_rank"] = (
            cross["up_probability"]
            .rank(
                method="first",
                pct=True,
            )
        )

        cross["bucket"] = pd.cut(
            cross["_rank"],
            bins=[
                0.0,
                0.2,
                0.4,
                0.6,
                0.8,
                1.0,
            ],
            labels=[
                1,
                2,
                3,
                4,
                5,
            ],
            include_lowest=True,
        )

        bucket_returns = (
            cross.groupby(
                "bucket",
                observed=True,
            )["forward_return_20d"]
            .mean()
        )

        for bucket, ret in bucket_returns.items():
            rows.append(
                {
                    "date": date,
                    "bucket": int(bucket),
                    "forward_return_20d": float(ret),
                }
            )

    raw = pd.DataFrame(rows)

    if raw.empty:
        return raw

    summary = (
        raw.groupby("bucket")
        .agg(
            periods=(
                "forward_return_20d",
                "count",
            ),
            mean_forward_return=(
                "forward_return_20d",
                "mean",
            ),
            median_forward_return=(
                "forward_return_20d",
                "median",
            ),
            std_forward_return=(
                "forward_return_20d",
                "std",
            ),
            positive_period_rate=(
                "forward_return_20d",
                lambda x: (
                    x > 0
                ).mean(),
            ),
        )
        .reset_index()
    )

    return summary


# ============================================================
# ROBUSTNESS SCORECARD
# ============================================================

def build_robustness_summary(
    cost_df: pd.DataFrame,
    basket_df: pd.DataFrame,
    subperiod_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    bootstrap_df: pd.DataFrame,
    bucket_df: pd.DataFrame,
) -> pd.DataFrame:

    checks = []

    # --------------------------------------------------------
    # Cost robustness
    # --------------------------------------------------------

    cost_50 = cost_df[
        cost_df["cost_bps"] == 50
    ]

    if not cost_50.empty:
        value = float(
            cost_50.iloc[0][
                "annualized_return"
            ]
        )

        checks.append(
            {
                "robustness_check": (
                    "Positive annualized return "
                    "at 50 bps cost"
                ),
                "value": value,
                "passed": bool(value > 0),
            }
        )

    # --------------------------------------------------------
    # Basket robustness
    # --------------------------------------------------------

    if not basket_df.empty:

        positive_baskets = int(
            (
                basket_df[
                    "mean_period_return"
                ] > 0
            ).sum()
        )

        total_baskets = len(
            basket_df
        )

        checks.append(
            {
                "robustness_check": (
                    "Positive mean return "
                    "across basket sizes"
                ),
                "value": (
                    positive_baskets
                    / total_baskets
                ),
                "passed": bool(
                    positive_baskets
                    == total_baskets
                ),
            }
        )

    # --------------------------------------------------------
    # First-half / second-half stability
    # --------------------------------------------------------

    if not subperiod_df.empty:

        halves = subperiod_df[
            subperiod_df["test"].isin(
                [
                    "First Half",
                    "Second Half",
                ]
            )
        ]

        if len(halves) == 2:

            both_positive = bool(
                (
                    halves[
                        "mean_period_return"
                    ] > 0
                ).all()
            )

            checks.append(
                {
                    "robustness_check": (
                        "Positive mean return "
                        "in both sample halves"
                    ),
                    "value": float(
                        halves[
                            "mean_period_return"
                        ].min()
                    ),
                    "passed": both_positive,
                }
            )

    # --------------------------------------------------------
    # Sector-neutral robustness
    # --------------------------------------------------------

    neutral = sector_df[
        sector_df["test"]
        == "Sector Neutral Long Short"
    ]

    if not neutral.empty:

        neutral_mean = float(
            neutral.iloc[0][
                "mean_period_return"
            ]
        )

        checks.append(
            {
                "robustness_check": (
                    "Positive sector-neutral "
                    "mean return"
                ),
                "value": neutral_mean,
                "passed": bool(
                    neutral_mean > 0
                ),
            }
        )

    # --------------------------------------------------------
    # Bootstrap confidence interval
    # --------------------------------------------------------

    if not bootstrap_df.empty:

        lower_ci = float(
            bootstrap_df.iloc[0][
                "mean_return_ci_2_5"
            ]
        )

        checks.append(
            {
                "robustness_check": (
                    "Bootstrap 95% CI lower "
                    "bound above zero"
                ),
                "value": lower_ci,
                "passed": bool(
                    lower_ci > 0
                ),
            }
        )

    # --------------------------------------------------------
    # Bucket monotonicity
    # --------------------------------------------------------

    if len(bucket_df) >= 5:

        bucket_df = bucket_df.sort_values(
            "bucket"
        )

        returns = (
            bucket_df[
                "mean_forward_return"
            ]
            .to_numpy()
        )

        monotonic = bool(
            np.all(
                np.diff(returns) >= 0
            )
        )

        spread = float(
            returns[-1] - returns[0]
        )

        checks.append(
            {
                "robustness_check": (
                    "Average bucket returns "
                    "monotonically increase"
                ),
                "value": spread,
                "passed": monotonic,
            }
        )

    summary = pd.DataFrame(
        checks
    )

    if not summary.empty:

        passed = int(
            summary["passed"].sum()
        )

        total = len(summary)

        summary["tests_passed"] = passed
        summary["tests_total"] = total
        summary["pass_rate"] = (
            passed / total
        )

    return summary


# ============================================================
# PRINT HELPERS
# ============================================================

def print_dataframe(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> None:

    if df.empty:
        print("No results.")
        return

    display = df.copy()

    if columns is not None:
        columns = [
            c
            for c in columns
            if c in display.columns
        ]

        display = display[
            columns
        ]

    numeric = display.select_dtypes(
        include=np.number
    ).columns

    display[numeric] = display[
        numeric
    ].round(4)

    print(
        display.to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    banner(
        "VITTANTRA — DAY 57 PORTFOLIO ROBUSTNESS"
    )

    try:

        # ----------------------------------------------------
        # Load Day 55 signal
        # ----------------------------------------------------

        df = load_rankings()

        print(
            f"Rows loaded: {len(df):,}"
        )

        print(
            f"Securities: "
            f"{df['ticker'].nunique():,}"
        )

        print(
            f"Sectors: "
            f"{df['sector'].nunique():,}"
        )

        print(
            f"Dates: "
            f"{df['date'].nunique():,}"
        )

        print(
            "Sample:",
            df["date"].min().date(),
            "to",
            df["date"].max().date(),
        )

        # ----------------------------------------------------
        # Baseline portfolio
        # ----------------------------------------------------

        baseline = build_long_short_periods(
            df,
            basket_fraction=0.20,
            sector_neutral=False,
        )

        if baseline.empty:
            raise RuntimeError(
                "Baseline long-short portfolio "
                "could not be constructed."
            )

        banner(
            "BASELINE LONG-SHORT PORTFOLIO"
        )

        baseline_metrics = pd.DataFrame(
            [
                performance_metrics(
                    baseline[
                        "long_short_gross_return"
                    ],
                    "Baseline 20% Long Short",
                )
            ]
        )

        print_dataframe(
            baseline_metrics
        )

        # ----------------------------------------------------
        # Transaction costs
        # ----------------------------------------------------

        banner(
            "TEST 1 — TRANSACTION COST SENSITIVITY"
        )

        cost_df = transaction_cost_test(
            baseline
        )

        print_dataframe(
            cost_df,
            [
                "cost_bps",
                "periods",
                "cumulative_return",
                "annualized_return",
                "sharpe_ratio",
                "maximum_drawdown",
                "total_transaction_cost",
            ],
        )

        cost_df.to_csv(
            OUTPUT_COST,
            index=False,
        )

        # ----------------------------------------------------
        # Basket size
        # ----------------------------------------------------

        banner(
            "TEST 2 — BASKET-SIZE SENSITIVITY"
        )

        basket_df = basket_sensitivity_test(
            df
        )

        print_dataframe(
            basket_df,
            [
                "basket_fraction",
                "periods",
                "mean_period_return",
                "annualized_return",
                "sharpe_ratio",
                "maximum_drawdown",
                "average_turnover",
            ],
        )

        basket_df.to_csv(
            OUTPUT_BASKET,
            index=False,
        )

        # ----------------------------------------------------
        # Subperiods
        # ----------------------------------------------------

        banner(
            "TEST 3 — SUBPERIOD STABILITY"
        )

        subperiod_df = subperiod_test(
            baseline
        )

        print_dataframe(
            subperiod_df,
            [
                "test",
                "periods",
                "mean_period_return",
                "annualized_return",
                "sharpe_ratio",
                "maximum_drawdown",
                "hit_rate",
            ],
        )

        subperiod_df.to_csv(
            OUTPUT_SUBPERIOD,
            index=False,
        )

        # ----------------------------------------------------
        # Sector neutrality
        # ----------------------------------------------------

        banner(
            "TEST 4 — SECTOR-NEUTRAL PORTFOLIO"
        )

        sector_df = sector_neutral_test(
            df
        )

        print_dataframe(
            sector_df,
            [
                "test",
                "periods",
                "mean_period_return",
                "annualized_return",
                "annualized_volatility",
                "sharpe_ratio",
                "maximum_drawdown",
                "hit_rate",
            ],
        )

        sector_df.to_csv(
            OUTPUT_SECTOR,
            index=False,
        )

        # ----------------------------------------------------
        # Bootstrap
        # ----------------------------------------------------

        banner(
            "TEST 5 — BOOTSTRAP CONFIDENCE INTERVAL"
        )

        bootstrap_df = bootstrap_test(
            baseline[
                "long_short_gross_return"
            ]
        )

        print_dataframe(
            bootstrap_df
        )

        bootstrap_df.to_csv(
            OUTPUT_BOOTSTRAP,
            index=False,
        )

        # ----------------------------------------------------
        # Bucket monotonicity
        # ----------------------------------------------------

        banner(
            "TEST 6 — SIGNAL MONOTONICITY"
        )

        bucket_df = bucket_monotonicity_test(
            df
        )

        print_dataframe(
            bucket_df
        )

        bucket_df.to_csv(
            OUTPUT_BUCKET,
            index=False,
        )

        # ----------------------------------------------------
        # Final robustness scorecard
        # ----------------------------------------------------

        banner(
            "DAY 57 ROBUSTNESS SCORECARD"
        )

        summary_df = build_robustness_summary(
            cost_df,
            basket_df,
            subperiod_df,
            sector_df,
            bootstrap_df,
            bucket_df,
        )

        print_dataframe(
            summary_df
        )

        summary_df.to_csv(
            OUTPUT_SUMMARY,
            index=False,
        )

        # ----------------------------------------------------
        # Outputs
        # ----------------------------------------------------

        banner(
            "FILES CREATED"
        )

        outputs = [
            OUTPUT_COST,
            OUTPUT_BASKET,
            OUTPUT_SUBPERIOD,
            OUTPUT_SECTOR,
            OUTPUT_BOOTSTRAP,
            OUTPUT_BUCKET,
            OUTPUT_SUMMARY,
        ]

        for output in outputs:
            print(output.name)

        print()
        print(
            "Day 57 portfolio robustness testing complete."
        )

        print()
        print(
            "Important: robustness tests reduce the risk "
            "of mistaking an attractive historical "
            "backtest for a durable investment signal."
        )

    except Exception as exc:

        banner(
            "DAY 57 FAILED"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "Do not interpret the strategy until "
            "the robustness suite completes."
        )

        sys.exit(1)


if __name__ == "__main__":
    main()