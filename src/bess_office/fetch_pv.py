"""Fetch PV generation profile from PVGIS, via pvlib."""

from pathlib import Path

import pandas as pd
from pvlib.iotools import get_pvgis_hourly

RAW_DATA_DIR = Path("data/raw")


def get_pv_profile(
    latitude: float,
    longitude: float,
    peak_power_kw: float,
    tilt: float = 35,
    azimuth: float = 0,
    save_raw: bool = True,
) -> pd.Series:
    """
    Fetch an hourly PV generation profile from PVGIS via pvlib.

    Parameters
    ----------
    latitude, longitude : float
        Location of the installation.
    peak_power_kw : float
        Installed peak power in kWp.
    tilt : float
        Panel tilt angle in degrees (0 = flat, 90 = vertical).
    azimuth : float
        Panel orientation in degrees, PVGIS convention:
        0 = south, negative = east, positive = west.
        (Internally converted to pvlib's own convention.)
    save_raw : bool
        If True, saves the raw response to data/raw/.

    Returns
    -------
    pd.Series
        Hourly PV power output in W, indexed by timestamp.
    """
    # pvlib gebruikt een andere azimuth-conventie dan PVGIS zelf:
    # pvlib: noord=0, zuid=180 (kloksgewijs). PVGIS: zuid=0.
    azimuth_pvlib = azimuth + 180

    data, meta = get_pvgis_hourly(
        latitude=latitude,
        longitude=longitude,
        pvcalculation=True,
        peakpower=peak_power_kw,
        loss=14,
        surface_tilt=tilt,
        surface_azimuth=azimuth_pvlib,
    )

    if save_raw:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DATA_DIR / f"pvgis_{latitude}_{longitude}.csv"
        data.to_csv(raw_path)
        print(f"Saved raw PVGIS response to {raw_path}")

    return data["P"]


if __name__ == "__main__":
    pv = get_pv_profile(latitude=52.01, longitude=4.36, peak_power_kw=10)
    print(pv.head())
    print(f"\nAvailable columns: {list(pv.to_frame().columns) if hasattr(pv, 'to_frame') else 'N/A'}")
    print(f"Total rows: {len(pv)}")
    print(f"Total annual yield: {pv.sum() / 1000:.0f} kWh")