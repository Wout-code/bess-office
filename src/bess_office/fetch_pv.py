"""Fetch the PV generation profile from PVGIS, via pvlib."""

import pandas as pd
from pvlib.iotools import get_pvgis_hourly

from bess_office.config import CONFIG, PVConfig


def get_pv_profile(pv_config: PVConfig | None = None) -> pd.Series:
    """
    Fetch an hourly PV generation profile from PVGIS via pvlib.

    Loads from the CSV in data/raw/ if available (the reference case is
    included in the repository); otherwise queries PVGIS and caches the
    result. No API key is needed.

    Parameters
    ----------
    pv_config : PVConfig, optional
        PV installation settings. Defaults to CONFIG.pv, read at call time so
        it always reflects the current CONFIG.

    Returns
    -------
    pd.Series
        Hourly PV power output in W, indexed by timestamp (tz-aware,
        Europe/Amsterdam, rounded to the hour; DATA-1, DATA-5).
    """
    if pv_config is None:
        pv_config = CONFIG.pv

    raw_dir = CONFIG.data_dir / "raw"
    # Every parameter that affects the PVGIS response is in the file name, so a
    # config change (e.g. peak_power_kw) never silently loads an old cache.
    raw_path = raw_dir / (
        f"pvgis_{pv_config.latitude}_{pv_config.longitude}_{pv_config.year}"
        f"_{pv_config.peak_power_kw}kWp_tilt{pv_config.tilt}_az{pv_config.azimuth}"
        f"_loss{pv_config.system_loss_pct}_{pv_config.mounting_place}.csv"
    )

    if raw_path.exists():
        print(f"Loading PV from disk: {raw_path}")
        data = pd.read_csv(raw_path, index_col=0)
        data.index = pd.to_datetime(data.index, utc=True)  # converted below, as for a fresh fetch
    else:
        data, _meta = get_pvgis_hourly(
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
            print(f"Saved PVGIS data to {raw_path}")

    series = data["P"]
    idx = pd.to_datetime(series.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")  # PVGIS timestamps are in UTC
    # PVGIS stamps each hour a few minutes past the hour (e.g. 00:10). Round in
    # UTC, where there are no clock changes, then convert to local time.
    idx = idx.round("h")
    series.index = idx.tz_convert("Europe/Amsterdam")
    return series


if __name__ == "__main__":
    pv = get_pv_profile()
    print(pv.head())
    print(f"\nTotal rows: {len(pv)}")
    # Hourly values in W: their sum is Wh, so / 1000 gives kWh.
    print(f"Total annual yield: {pv.sum() / 1000:.0f} kWh")