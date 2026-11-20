"""Load the office consumption profile from Liander's K&O dataset.

Unlike fetch_pv.py and fetch_prices.py, this is NOT a live API call.
Liander's K&O profiles are static, manually downloaded CSV files.
Download from https://www.liander.nl/over-ons/open-data -> "K&O profielen",
and place the file in data/raw/ before running this.

Verified file structure:
- Separator: semicolon (;), decimal: period
- Two columns: DATUM_TIJDSTIP (timestamp), WAARDE (relative value)
- 35,040 rows = 365 days x 96 quarter-hours (complete year, no gaps)
- WAARDE is relative/normalized, observed range ~0.31-0.90 (not absolute kWh)

NOTE on what this profile actually is (see ASSUMPTIONS.md DATA-6): this is one
of Liander's own "K&O" standard profiles, built from real large-consumer
(grootverbruik) telemetry and used by Liander itself to size new large-consumer
connections without their own history yet. It is a normalized shape: the
absolute level comes from the scale you multiply it by (see
derive_peak_kwh_per_quarter below). That scale is chosen so the modeled
building is also a large consumer, matching the population the profile was
built from (DATA-8).
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
LOAD_PROFILE_FILE = RAW_DATA_DIR / "KO_KANTOOR_ONDERWIJS_clean_2023_semicolon.csv"


def get_relative_profile() -> pd.Series:
    """
    Load the normalized K&O consumption profile shape (0-1 range), not yet
    scaled to any specific building.

    This is the "shape" half of the profile; derive_peak_kwh_per_quarter
    gives the "scale" half.

    Returns
    -------
    pd.Series
        Quarter-hourly relative consumption (0-1), indexed by timestamp
        (tz-aware, Europe/Amsterdam, like fetch_pv.py and fetch_prices.py).
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

    # The profile has 96 quarter-hours every day, also on clock-change days,
    # so it has no real DST irregularity (DATA-6). The missing hour in March
    # is shifted forward; the double hour in October is assigned to summer
    # time. Pragmatic for a normalized pattern, not for a real measurement.
    df.index = df.index.tz_localize(
        "Europe/Amsterdam", nonexistent="shift_forward", ambiguous=True
    )
    # Shifting forward in March creates duplicate timestamps; for a synthetic
    # profile neither one is "correct", so keep the first.
    df = df[~df.index.duplicated(keep="first")]

    # Re-normalize to the profile's own max (observed 0.9, not 1.0), so the
    # scaled peak is reached exactly at the profile's peak moment.
    return df["WAARDE"] / df["WAARDE"].max()


def derive_peak_kwh_per_quarter(
    area_m2: float, annual_kwh_per_m2: float, relative_profile: pd.Series
) -> float:
    """
    Derive peak_kwh_per_quarter from a building's target annual consumption
    and this profile's shape.

    peak_kwh_per_quarter is not a pure building property: it depends on the
    annual consumption (area_m2 x annual_kwh_per_m2, checkable against
    benchmarks) and on the shape of the profile. A peakier profile needs a
    higher peak_kwh_per_quarter to reach the same annual total than a flatter
    one. Keeping the derivation next to the profile keeps that dependency
    visible.

    Parameters
    ----------
    area_m2 : float
        Building floor area in square metres.
    annual_kwh_per_m2 : float
        Annual consumption intensity, kWh per m2 per year.
    relative_profile : pd.Series
        The 0-1 profile shape from get_relative_profile(). Its sum over the
        year converts an annual total into the peak quarter-hour.

    Returns
    -------
    float
        Consumption in kWh in the busiest quarter-hour of the year.
    """
    annual_total_kwh = area_m2 * annual_kwh_per_m2
    return annual_total_kwh / relative_profile.sum()


def get_load_profile(peak_kwh_per_quarter: float) -> pd.Series:
    """
    Load the profile and scale it directly to a known peak_kwh_per_quarter.

    Convenience wrapper around get_relative_profile() for callers that
    already have a peak_kwh_per_quarter value. The real pipeline (main.py)
    uses get_relative_profile() + derive_peak_kwh_per_quarter() instead, so
    the link from area and intensity to the peak stays visible.

    Parameters
    ----------
    peak_kwh_per_quarter : float
        Consumption in kWh in the busiest quarter-hour of the year.

    Returns
    -------
    pd.Series
        Quarter-hourly consumption in kWh, indexed by timestamp (tz-aware,
        Europe/Amsterdam).
    """
    return get_relative_profile() * peak_kwh_per_quarter


if __name__ == "__main__":
    # Sanity check against ASSUMPTIONS.md DATA-8: should give a profile sum of
    # 20,824.42, a peak of 24.85 kWh per quarter-hour and 99.4 kW.
    from bess_office.config import CONFIG

    relative_profile = get_relative_profile()
    print(relative_profile.head())
    print(f"\nTotal rows: {len(relative_profile)}")
    print(f"sum(relative_profile) = {relative_profile.sum():.2f}")

    peak = derive_peak_kwh_per_quarter(
        area_m2=CONFIG.building.area_m2,
        annual_kwh_per_m2=CONFIG.building.annual_kwh_per_m2,
        relative_profile=relative_profile,
    )
    load = relative_profile * peak
    print(f"peak_kwh_per_quarter = {peak:.2f} kWh ({peak / 0.25:.1f} kW)")
    print(f"Annual consumption: {load.sum():.0f} kWh")