import sqlite3
import pandas as pd


DATABASE = "hedge_fund.db"


def load_economic_vintages(database=DATABASE):
    """Load economic vintage records from SQLite."""

    with sqlite3.connect(database) as conn:
        data = pd.read_sql_query(
            "SELECT * FROM economic_vintages",
            conn
        )

    for column in [
        "observation_date",
        "available_date",
        "vintage_end_date"
    ]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column])

    return data


def get_economic_snapshot(as_of_date, database=DATABASE):
    """
    Return the latest available observation of each
    economic indicator before the selected date.
    """

    data = load_economic_vintages(database)
    cutoff = pd.Timestamp(as_of_date)

    eligible = data[
        (data["available_date"] < cutoff)
        & (data["observation_date"] < cutoff)
    ].copy()

    if eligible.empty:
        return pd.DataFrame()

    latest = (
        eligible.sort_values(
            ["indicator", "observation_date", "available_date"]
        )
        .drop_duplicates("indicator", keep="last")
        [
            [
                "indicator",
                "observation_date",
                "available_date",
                "value"
            ]
        ]
        .reset_index(drop=True)
    )

    return latest