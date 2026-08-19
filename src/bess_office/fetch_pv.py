"""Fetch PV generation profile from PVGIS, via pvlib."""

from functools import lru_cache
from pathlib import Path

import pandas as pd
from pvlib.iotools import get_pvgis_hourly

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # src/bess_office/ -> src/ -> project root
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


@lru_cache(maxsize=32)
def get_pv_profile(  # the variables defined here can change
    latitude: float,
    longitude: float,
    peak_power_kw: float,
    tilt: float = 35,
    azimuth: float = 180,  # pvlib convention: north=0, south=180
    mounting_place: str = "building",  # "building" = dakpanelen, no aircirculation
    year: int = 2023,
    save_raw: bool = True,
) -> pd.Series:
    """
    Fetch an hourly PV generation profile from PVGIS via pvlib.

    Cached with lru_cache: repeated calls with the exact same
    arguments return the stored result instantly instead of hitting
    the PVGIS API again. This is safe because PV yield for a fixed
    location/orientation/year is deterministic -- the same inputs
    always produce the same output, unlike e.g. live price data.

    Parameters
    ----------
    latitude, longitude : float
        Location of the installation.
    peak_power_kw : float
        Installed peak power in kWp.
    tilt : float
        Panel tilt angle in degrees (0 = flat, 90 = vertical).
    azimuth : float
        Panel orientation in degrees, pvlib convention:
        north=0, south=180 (clockwise).
    mounting_place : str
        "building" (default) = panels mounted flush on a roof, no
        airflow behind them → higher module temperature, lower yield.
        "free" = panels on a rack with airflow behind them → cooler,
        higher yield. Use "building" for a typical office rooftop
        installation; use "free" for a ground-mount system.
    save_raw : bool
        If True, saves the raw response to data/raw/.

    Returns
    -------
    pd.Series
        Hourly PV power output in W, indexed by timestamp.
    """
    data, meta = get_pvgis_hourly(
        latitude=latitude,
        longitude=longitude,
        pvcalculation=True,
        peakpower=peak_power_kw,
        loss=14,
        start=year,
        end=year,
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        mountingplace=mounting_place,
    )

    if save_raw:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DATA_DIR / f"pvgis_{latitude}_{longitude}.csv"
        data.to_csv(raw_path)
        print(f"Saved raw PVGIS response to {raw_path}")

    series = data["P"]
    series.index = series.index.tz_localize(None).round("h")
    return series


if __name__ == "__main__":  # the variables defined here are permanent
    pv = get_pv_profile(latitude=52.01, longitude=4.36, peak_power_kw=10)
    print(pv.head())
    print(f"\nAvailable columns: {list(pv.to_frame().columns) if hasattr(pv, 'to_frame') else 'N/A'}")
    print(f"Total rows: {len(pv)}")
    print(f"Total annual yield: {pv.sum() / 1000:.0f} kWh")