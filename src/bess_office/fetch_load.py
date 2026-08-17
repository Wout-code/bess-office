"""Load the office consumption profile from Liander's K&O dataset.

Unlike fetch_pv.py and fetch_prices.py, this is NOT a live API call.
Liander's K&O profiles are static, manually downloaded CSV files.
Download from https://www.liander.nl/over-ons/open-data -> "K&O profielen",
and place the file in data/raw/ before running this.

Verified file structure (see notebooks/0.2-load-exploration.ipynb):
- Separator: semicolon (;), decimal: period
- Two columns: DATUM_TIJDSTIP (real datetime), WAARDE (single relative value)
- 35,040 rows = 365 days x 96 quarter-hours (complete year, no gaps)
- WAARDE is relative/normalized, observed range ~0.31-0.90 (not absolute kWh)
"""

from pathlib import Path

import pandas as pd

RAW_DATA_DIR = Path("data/raw")
LOAD_PROFILE_FILE = RAW_DATA_DIR / "KO_KANTOOR_ONDERWIJS_clean_2023_semicolon.csv"


def get_load_profile(peak_kwh_per_quarter: float) -> pd.Series:
    """
    Load and scale the office (K&O Kantoor/Onderwijs) consumption profile.

    Parameters
    ----------
    peak_kwh_per_quarter : float
        Expected peak consumption in kWh within a single 15-minute
        interval for the office building being modelled. The profile
        is re-normalized to its own max (=1.0) before scaling, so this
        value always corresponds to the profile's actual peak moment.

    Returns
    -------
    pd.Series
        Quarter-hourly electricity consumption in kWh, indexed by
        timestamp.
    """
    if not LOAD_PROFILE_FILE.exists():
        raise FileNotFoundError(
            f"{LOAD_PROFILE_FILE} not found. Download it manually from "
            "liander.nl/over-ons/open-data -> 'K&O profielen', and place "
            "it in data/raw/."
        )

    df = pd.read_csv(LOAD_PROFILE_FILE, sep=";")
    df["DATUM_TIJDSTIP"] = pd.to_datetime(df["DATUM_TIJDSTIP"])
    df = df.set_index("DATUM_TIJDSTIP")

    # Re-normalize to the profile's own max, so peak_kwh_per_quarter is
    # reached exactly at the profile's peak moment (observed max was
    # 0.9, not a clean 1.0 -- see exploration notebook).
    relative_profile = df["WAARDE"] / df["WAARDE"].max()

    load_kwh = relative_profile * peak_kwh_per_quarter

    return load_kwh


if __name__ == "__main__":
    load = get_load_profile(peak_kwh_per_quarter=15)
    print(load.head())
    print(f"\nTotal rows: {len(load)}")
    print(f"Total annual consumption: {load.sum():.0f} kWh")
    print(f"Peak quarter: {load.max():.2f} kWh")