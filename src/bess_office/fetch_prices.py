"""Fetch day-ahead electricity prices from the ENTSO-E Transparency Platform."""

import os
from pathlib import Path

import pandas as pd
from entsoe import EntsoePandasClient

# Paths relative to the project root (assumes this runs from main.py at the root)
RAW_DATA_DIR = Path("data/raw")


def get_day_ahead_prices(
    start: pd.Timestamp,
    end: pd.Timestamp,
    country_code: str = "NL",
    save_raw: bool = True,
) -> pd.Series:
    """
    Fetch day-ahead electricity prices for a given period and country.

    Parameters
    ----------
    start : pd.Timestamp
        Start of the period (timezone-aware, e.g. "Europe/Amsterdam").
    end : pd.Timestamp
        End of the period (timezone-aware).
    country_code : str
        ENTSO-E bidding zone code, "NL" for the Netherlands.
    save_raw : bool
        If True, saves the unmodified API response to data/raw/.

    Returns
    -------
    pd.Series
        Hourly day-ahead prices in EUR/MWh, indexed by timestamp.
    """
    api_key = os.getenv("ENTSOE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ENTSOE_API_KEY not found. Set it as an environment variable "
            "(see README for instructions)."
        )

    client = EntsoePandasClient(api_key=api_key)

    prices = client.query_day_ahead_prices(country_code, start=start, end=end)

    if save_raw:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DATA_DIR / f"entsoe_prices_{country_code}_{start.date()}_{end.date()}.csv"
        prices.to_csv(raw_path, header=["price_eur_mwh"])
        print(f"Saved raw prices to {raw_path}")

    return prices


if __name__ == "__main__":
    # Quick manual test: fetch the last 7 days
    tz = "Europe/Amsterdam"
    end = pd.Timestamp.now(tz=tz).normalize()
    start = end - pd.Timedelta(days=7)

    prices = get_day_ahead_prices(start, end)
    print(prices.head())
    print(f"\nFetched {len(prices)} hourly prices.")