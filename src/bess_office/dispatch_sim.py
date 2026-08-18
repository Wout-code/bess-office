"""Rule-based (heuristic) battery dispatch simulation.

This is a deterministic, non-optimizing baseline: a simple set of
priority rules decides charge/discharge behaviour each hour. It exists
to give a reference point to compare the LP optimization (optimize.py)
against -- "how much better does actual optimization do than a
sensible but non-optimal rule-based controller?"

Two value drivers are combined, matching what an office building
(MKB) battery is actually used for:
1. Self-consumption: charge on PV surplus, discharge on PV deficit.
2. Peak shaving: discharge (even beyond self-consumption) whenever
   grid import would otherwise exceed a configured peak threshold,
   since MKB capacity tariffs are billed on the highest measured
   quarter-hour peak in a billing period.

Battery model: single capacity/power pair, round-trip efficiency
applied on charge only (discharge assumed lossless on the way out --
a common simplification), SoC bounded between configurable min/max.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass 
class BatterySpec: #fake battery specs, need to replace with real ones, 
    """Physical specification of the battery."""

    capacity_kwh: float
    power_kw: float
    round_trip_efficiency: float = 0.90
    min_soc_fraction: float = 0.10
    max_soc_fraction: float = 0.95
    initial_soc_fraction: float = 0.50


def run_baseline_dispatch(
    pv_kwh: pd.Series,
    load_kwh: pd.Series,
    battery: BatterySpec,
    peak_threshold_kw: float,
    timestep_hours: float = 1.0,
) -> pd.DataFrame:
    """
    Simulate hourly battery dispatch using simple priority rules.

    Parameters
    ----------
    pv_kwh : pd.Series
        Hourly PV generation in kWh, indexed by timestamp.
    load_kwh : pd.Series
        Hourly building consumption in kWh, same index as pv_kwh.
        Resample/align both series to the same hourly index before
        calling this (e.g. load_kwh.resample("1h").sum()).
    battery : BatterySpec
        Battery capacity, power, efficiency and SoC bounds.
    peak_threshold_kw : float
        Grid import above this level triggers battery discharge for
        peak shaving, if the battery has capacity/power available.

    Returns
    -------
    pd.DataFrame
        One row per hour: pv_kwh, load_kwh, soc_kwh, charge_kwh,
        discharge_kwh, grid_import_kwh, grid_export_kwh.
    """
    if not pv_kwh.index.equals(load_kwh.index):
        raise ValueError(
            "pv_kwh and load_kwh must share the same index. "
            "Resample/align both series before calling this function."
        )

    min_soc = battery.min_soc_fraction * battery.capacity_kwh
    max_soc = battery.max_soc_fraction * battery.capacity_kwh
    soc = battery.initial_soc_fraction * battery.capacity_kwh
    charge_efficiency = battery.round_trip_efficiency

    records = []

    for timestamp, pv in pv_kwh.items():
        load = load_kwh.loc[timestamp]
        surplus = pv - load  # >0: PV excess, <0: deficit

        charge = 0.0
        discharge = 0.0

        if surplus > 0:
            # Self-consumption: charge with PV surplus, limited by
            # power rating, remaining capacity, and charging losses.
            room_in_battery = (max_soc - soc) / charge_efficiency
            charge = min(surplus, battery.power_kw, room_in_battery)
            soc += charge * charge_efficiency

        else:
            deficit = -surplus
            if deficit > peak_threshold_kw:
                # Peak shaving: discharge to bring import down to the
                # threshold, limited by power rating and available SoC.
                shave_target = deficit - peak_threshold_kw
                available_energy = soc - min_soc
                discharge = min(shave_target, battery.power_kw, available_energy)
                soc -= discharge

        # Full energy balance: (load + charge) must be met by
        # (pv + discharge + grid_import), with any leftover exported.
        net_need = (load + charge) - (pv + discharge)
        grid_import = max(0.0, net_need)
        grid_export = max(0.0, -net_need)

        records.append(
            {
                "timestamp": timestamp,
                "pv_kwh": pv,
                "load_kwh": load,
                "soc_kwh": soc,
                "charge_kwh": charge,
                "discharge_kwh": discharge,
                "grid_import_kwh": grid_import,
                "grid_export_kwh": grid_export,
            }
        )

    return pd.DataFrame(records).set_index("timestamp")


if __name__ == "__main__":
    # Quick manual test with a tiny synthetic day: PV peaking at
    # noon, load with morning + evening peaks (typical office shape).
    import numpy as np

    hours = pd.date_range("2023-06-01", periods=24, freq="1h")
    pv = pd.Series(
        np.clip(5 * np.sin((hours.hour - 6) / 12 * np.pi), 0, None),
        index=hours,
    )
    load = pd.Series(
        [2, 2, 2, 2, 2, 3, 5, 6, 4, 3, 3, 3, 3, 3, 3, 4, 6, 7, 6, 4, 3, 2, 2, 2],
        index=hours,
    )

    battery = BatterySpec(capacity_kwh=10, power_kw=5)
    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=4)

    print(result)
    print(f"\nPeak grid import: {result['grid_import_kwh'].max():.2f} kWh")
    print(f"Total grid import: {result['grid_import_kwh'].sum():.2f} kWh")
    print(f"Total grid export: {result['grid_export_kwh'].sum():.2f} kWh")