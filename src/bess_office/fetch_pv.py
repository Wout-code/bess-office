"""Fetch PV generation profile from PVGIS, via pvlib."""

import pandas as pd
from pvlib.iotools import get_pvgis_hourly

from bess_office.config import CONFIG, PVConfig


def get_pv_profile(pv_config: PVConfig | None = None) -> pd.Series:
    """
    Fetch an hourly PV generation profile from PVGIS via pvlib.

    Parameters
    ----------
    pv_config : PVConfig, optional
        PV installation settings. Defaults to CONFIG.pv if not given
        -- read at call time, so it always reflects the current CONFIG,
        not a stale snapshot from when this module was imported.

    Returns
    -------
    pd.Series
        Hourly PV power output in W, indexed by timestamp (tz-naive,
        rounded to the hour to align cleanly with other hourly series).
    """
    if pv_config is None:
        pv_config = CONFIG.pv

    raw_dir = CONFIG.data_dir / "raw"
    raw_path = (
        raw_dir
        / f"pvgis_{pv_config.latitude}_{pv_config.longitude}_{pv_config.year}.csv"
    )

    if raw_path.exists():
        print(f"Al lokaal aanwezig, laad van schijf: {raw_path}")
        data = pd.read_csv(raw_path, index_col=0, parse_dates=True)
    else:
        data, meta = get_pvgis_hourly(
            latitude=pv_config.latitude,
            longitude=pv_config.longitude,
            pvcalculation=True,
            peakpower=pv_config.peak_power_kw,
            loss=pv_config.system_loss_pct,
            start=pv_config.year,
            end=pv_config.year,
            surface_tilt=pv_config.tilt,
            surface_azimuth=pv_config.azimuth,
            mountingplace=pv_config.mounting_place,
        )

        if pv_config.save_raw:
            raw_dir.mkdir(parents=True, exist_ok=True)
            data.to_csv(raw_path)
            print(f"Saved raw PVGIS response to {raw_path}")

    series = data["P"]
    idx = pd.to_datetime(series.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    series.index = idx.round("h")
    return series


if __name__ == "__main__":
    pv = get_pv_profile()  # gebruikt gewoon CONFIG.pv
    print(pv.head())
    print(f"\nTotal rows: {len(pv)}")
    print(f"Total annual yield: {pv.sum() / 1000:.0f} kWh")