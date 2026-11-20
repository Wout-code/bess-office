"""Load the office consumption profile from Liander's K&O dataset.

Unlike fetch_pv.py and fetch_prices.py, this is NOT a live API call.
Liander's K&O profiles are static, manually downloaded CSV files.
Download from https://www.liander.nl/over-ons/open-data -> "K&O profielen",
and place the file in data/raw/ before running this.

Verified file structure:
- Separator: semicolon (;), decimal: period
- Two columns: DATUM_TIJDSTIP (real datetime), WAARDE (single relative value)
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
    Load the raw, normalized K&O consumption profile shape (0-1 range),
    not yet scaled to any specific building's peak.

    This is the "shape" half of the profile -- see derive_peak_kwh_per_quarter
    for the "scale" half. Split out so the profile shape can be reused for
    both scaling a load (get_load_profile) and for deriving
    peak_kwh_per_quarter from a target annual consumption (main.py).

    Returns
    -------
    pd.Series
        Quarter-hourly relative consumption (0-1), indexed by timestamp
        (tz-aware, Europe/Amsterdam -- matches fetch_pv.py and
        fetch_prices.py's convention).
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

    # Normalized profile (365x96, no gaps -- see docstring), so
    # no real clock-change irregularity in the source data. tz_localize
    # still trips over it: nonexistent (March) we shift forward,
    # ambiguous (October) we deliberately pick as summer time -- pragmatically
    # correct for a normalized pattern, not for a real measurement.
    df.index = df.index.tz_localize(
        "Europe/Amsterdam", nonexistent="shift_forward", ambiguous=True
    )
    # shift_forward (March) can collide with already existing rows in this
    # uniform 96-per-day profile -- for synthetic data there is no
    # "correct" one of the two, so deduplicate explicitly instead of guessing
    df = df[~df.index.duplicated(keep="first")]

    # Re-normalize to the profile's own max, so peak_kwh_per_quarter is
    # reached exactly at the profile's peak moment (observed max was
    # 0.9, not a clean 1.0).
    relative_profile = df["WAARDE"] / df["WAARDE"].max()

    return relative_profile


def derive_peak_kwh_per_quarter(
    area_m2: float, annual_kwh_per_m2: float, relative_profile: pd.Series
) -> float:
    """
    Derive peak_kwh_per_quarter from a building's target annual
    consumption and this specific profile's shape (how peaky vs. flat
    it is).

    peak_kwh_per_quarter is NOT a pure building property -- it depends
    on both the building's annual consumption (area_m2 x
    annual_kwh_per_m2, externally verifiable against benchmarks) AND
    the shape of whichever profile you scale it with (a flatter profile
    needs a higher peak_kwh_per_quarter to reach the same annual total
    than a peakier one does). Keeping the derivation here, next to the
    profile, keeps that dependency visible instead of hiding it inside
    a building-only config.

    Parameters
    ----------
    area_m2 : float
        Building floor area in square metres.
    annual_kwh_per_m2 : float
        Target annual consumption intensity, kWh per m2 per year.
    relative_profile : pd.Series
        The 0-1 profile shape, e.g. from get_relative_profile(). Its sum
        over the year is the conversion factor between an annual total
        and a single peak quarter-hour.

    Returns
    -------
    float
        peak_kwh_per_quarter: expected consumption in kWh within the
        single most-loaded 15-minute interval of the year.
    """
    annual_total_kwh = area_m2 * annual_kwh_per_m2
    return annual_total_kwh / relative_profile.sum()


def get_load_profile(peak_kwh_per_quarter: float) -> pd.Series:
    """
    Load and scale the office (K&O Kantoor/Onderwijs) consumption profile
    directly to a known peak_kwh_per_quarter.

    Convenience wrapper around get_relative_profile() for callers that
    already have a peak_kwh_per_quarter value in hand (e.g.
    dispatch_sim.py's own __main__ block) and don't need the
    area_m2/annual_kwh_per_m2 derivation. For the real pipeline
    (main.py), prefer get_relative_profile() + derive_peak_kwh_per_quarter()
    so the area_m2/annual_kwh_per_m2 -> peak_kwh_per_quarter link stays
    visible.

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
        timestamp (tz-aware, Europe/Amsterdam -- matches fetch_pv.py
        and fetch_prices.py's convention).
    """
    return get_relative_profile() * peak_kwh_per_quarter


if __name__ == "__main__":
    load = get_load_profile(peak_kwh_per_quarter=15)
    print(load.head())
    print(f"\nTotal rows: {len(load)}")
    print(f"Total annual consumption: {load.sum():.0f} kWh")
    print(f"Peak quarter: {load.max():.2f} kWh")

    # Sanity check for derive_peak_kwh_per_quarter: round-tripping a
    # chosen area/intensity should reproduce a consistent annual total.
    relative_profile = get_relative_profile()
    print(f"\nsum(relative_profile) = {relative_profile.sum():.2f}")
    derived_peak = derive_peak_kwh_per_quarter(
        area_m2=590.0, annual_kwh_per_m2=115.0, relative_profile=relative_profile
    )
    print(f"derive_peak_kwh_per_quarter(590 m2, 115 kWh/m2/year) = {derived_peak:.2f} kWh/quarter-hour")