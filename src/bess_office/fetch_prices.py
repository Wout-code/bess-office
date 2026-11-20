"""Fetch day-ahead electricity prices from the ENTSO-E Transparency Platform."""

import os
from pathlib import Path

import pandas as pd
from entsoe import EntsoePandasClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def get_day_ahead_prices(
    start: pd.Timestamp,
    end: pd.Timestamp,
    country_code: str = "NL",
    save_raw: bool = True,
) -> pd.Series:
    """
    Fetch day-ahead electricity prices for a given period and bidding zone.

    Loads from the CSV in data/raw/ if available; the 2023 prices for NL are
    included in the repository, so the reference case runs without an API key.
    For other periods or zones it queries ENTSO-E, which requires the
    ENTSOE_API_KEY environment variable (see the README for how to get a key),
    and caches the result.

    Parameters
    ----------
    start : pd.Timestamp
        Start of the period (tz-aware, e.g. "Europe/Amsterdam").
    end : pd.Timestamp
        End of the period (tz-aware).
    country_code : str
        ENTSO-E bidding zone code, "NL" for the Netherlands.
    save_raw : bool
        If True, caches the fetched prices to data/raw/ as CSV.

    Returns
    -------
    pd.Series
        Day-ahead prices in EUR/MWh, indexed by timestamp (tz-aware,
        Europe/Amsterdam, like fetch_load.py and fetch_pv.py). Resolution is
        hourly before the SDAC 15-minute transition (1 October 2025) and
        quarter-hourly after.
    """
    raw_path = RAW_DATA_DIR / f"entsoe_prices_{country_code}_{start.date()}_{end.date()}.csv"

    if raw_path.exists():
        print(f"Loading prices from disk: {raw_path}")
        df = pd.read_csv(raw_path, index_col=0)
        # The CSV stores timestamps with their UTC offset; parse via UTC so the
        # clock changes are handled correctly.
        df.index = pd.to_datetime(df.index, utc=True)
        prices = df["price_eur_mwh"]
    else:
        api_key = os.getenv("ENTSOE_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"No cached prices at {raw_path} and ENTSOE_API_KEY not found. "
                "Set it as an environment variable to fetch this period "
                "(see README for how to get a key)."
            )

        client = EntsoePandasClient(api_key=api_key)
        prices = client.query_day_ahead_prices(country_code, start=start, end=end)

        if save_raw:
            RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
            prices.to_csv(raw_path, header=["price_eur_mwh"])
            print(f"Saved prices to {raw_path}")

    # Both routes (cache and fresh fetch) end up tz-aware in Europe/Amsterdam,
    # like fetch_load.py and fetch_pv.py (DATA-1).
    prices.index = prices.index.tz_convert("Europe/Amsterdam")

    return prices


if __name__ == "__main__":
    tz = "Europe/Amsterdam"
    start = pd.Timestamp("2023-01-01", tz=tz)
    end = pd.Timestamp("2024-01-01", tz=tz)

    prices = get_day_ahead_prices(start, end)
    print(prices.head())
    resolution = prices.index[1] - prices.index[0] if len(prices) > 1 else "unknown"
    print(f"\nFetched {len(prices)} prices at {resolution} resolution.")