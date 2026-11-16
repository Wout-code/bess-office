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
        Hourly PV power output in W, indexed by timestamp (tz-aware,
        Europe/Amsterdam, rounded to the hour -- matches fetch_load.py
        and fetch_prices.py's convention).
    """
    if pv_config is None:
        pv_config = CONFIG.pv

    raw_dir = CONFIG.data_dir / "raw"
    # All parameters that determine the PVGIS response belong in the file name.
    # Otherwise, after a config change (e.g. peak_power_kw), an old cache that
    # no longer matches the config is silently loaded.
    raw_path = raw_dir / (
        f"pvgis_{pv_config.latitude}_{pv_config.longitude}_{pv_config.year}"
        f"_{pv_config.peak_power_kw}kWp_tilt{pv_config.tilt}_az{pv_config.azimuth}"
        f"_loss{pv_config.system_loss_pct}_{pv_config.mounting_place}.csv"
    )

    if raw_path.exists():
        print(f"Already available locally, loading from disk: {raw_path}")
        data = pd.read_csv(raw_path, index_col=0)
        data.index = pd.to_datetime(data.index, utc=True)  # stays UTC; conversion happens below, shared by both paths
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
    if idx.tz is None:
        idx = idx.tz_localize("UTC")  # PVGIS supplies UTC-based timestamps
    idx = idx.round("h")  # round while still in UTC -- no DST ambiguity
    series.index = idx.tz_convert("Europe/Amsterdam")  # only convert after that
    return series


if __name__ == "__main__":
    pv = get_pv_profile()  # simply uses CONFIG.pv
    print(pv.head())
    print(f"\nTotal rows: {len(pv)}")
    print(f"Total annual yield: {pv.sum() / 1000:.0f} kWh")