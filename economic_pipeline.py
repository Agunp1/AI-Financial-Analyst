
import os
import sqlite3
import requests
import pandas as pd
from dotenv import load_dotenv

SERIES = {
    "CPI": "CPIAUCSL",
    "UNEMPLOYMENT": "UNRATE",
    "REAL_GDP": "GDPC1",
    "FED_RATE": "FEDFUNDS"
}


def fetch_economic_data(indicator, series_id):
    load_dotenv()

    api_key = os.getenv("FRED_API_KEY")

    if not api_key:
        raise ValueError("FRED_API_KEY not found in .env")

    response = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": "2024-01-01"
        },
        timeout=30
    )

    response.raise_for_status()

    data = pd.DataFrame(
        response.json()["observations"]
    )

    data["value"] = pd.to_numeric(
        data["value"], errors="coerce"
    )

    data = data.dropna(subset=["value"])

    data["indicator"] = indicator

    return data


def update_economic_database():
    with sqlite3.connect("hedge_fund.db") as conn:
        for indicator, series_id in SERIES.items():
            data = fetch_economic_data(
                indicator, series_id
            )

            print(
                indicator,
                len(data),
                "observations downloaded"
            )