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
class BatterySpec:  # fake battery specs, need to replace with real ones
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
    Simulate battery dispatch using simple priority rules.

    Parameters
    ----------
    pv_kwh : pd.Series
        PV generation in kWh per timestep, indexed by timestamp.
    load_kwh : pd.Series
        Building consumption in kWh per timestep, same index as pv_kwh.
        Resample/align both series to the same index before calling
        this (e.g. load_kwh.resample("1h").sum()).
    battery : BatterySpec
        Battery capacity, power, efficiency and SoC bounds.
    peak_threshold_kw : float
        Grid import above this level triggers battery discharge for
        peak shaving, if the battery has capacity/power available.
    timestep_hours : float
        Length of each timestep in hours (e.g. 1.0 for hourly data,
        0.25 for 15-minute data). Needed to convert the battery's
        power rating (kW) into an energy limit (kWh) per timestep --
        without this, power and energy units get silently mixed up.

    Returns
    -------
    pd.DataFrame
        One row per timestep: pv_kwh, load_kwh, soc_kwh, charge_kwh,
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
    max_energy_per_step = battery.power_kw * timestep_hours

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
            charge = min(surplus, max_energy_per_step, room_in_battery)
            soc += charge * charge_efficiency

        else:
            deficit = -surplus
            if deficit > peak_threshold_kw:
                # Peak shaving: discharge to bring import down to the
                # threshold, limited by power rating and available SoC.
                shave_target = deficit - peak_threshold_kw
                available_energy = soc - min_soc
                discharge = min(shave_target, max_energy_per_step, available_energy)
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


def compute_dispatch_metrics(result: pd.DataFrame, peak_threshold_kw: float) -> dict:
    """
    Compute summary metrics for a dispatch result: peak shaving and
    self-consumption. Works on the output of run_baseline_dispatch()
    or any other dispatch strategy with the same column layout, so it
    can be reused to compare the LP optimization against this baseline.

    Parameters
    ----------
    result : pd.DataFrame
        Output of run_baseline_dispatch() (or equivalent), with at
        least pv_kwh, load_kwh, grid_import_kwh, grid_export_kwh
        columns.
    peak_threshold_kw : float
        The threshold used during dispatch, only reported here for
        context alongside the metrics.

    Returns
    -------
    dict
        peak_import_no_battery_kw, peak_import_with_battery_kw,
        peak_shaved_kw, peak_shaved_pct, self_consumption_pct.
    """
    # Peak shaving: compare against the "naive" import that would have
    # happened with no battery at all (grid covering the full deficit).
    naive_import = (result["load_kwh"] - result["pv_kwh"]).clip(lower=0)
    peak_no_battery = naive_import.max()
    peak_with_battery = result["grid_import_kwh"].max()
    peak_shaved = peak_no_battery - peak_with_battery
    peak_shaved_pct = 100 * peak_shaved / peak_no_battery if peak_no_battery > 0 else 0.0

    # Self-consumption: share of PV generation that did NOT leave the
    # building as grid export (used directly, or via the battery).
    pv_total = result["pv_kwh"].sum()
    pv_exported = result["grid_export_kwh"].sum()
    pv_used_onsite = pv_total - pv_exported
    self_consumption_pct = 100 * pv_used_onsite / pv_total if pv_total > 0 else 0.0

    return {
        "peak_threshold_kw": peak_threshold_kw,
        "peak_import_no_battery_kw": peak_no_battery,
        "peak_import_with_battery_kw": peak_with_battery,
        "peak_shaved_kw": peak_shaved,
        "peak_shaved_pct": peak_shaved_pct,
        "self_consumption_pct": self_consumption_pct,
    }


if __name__ == "__main__":
    # Isolated logic test with synthetic, perfectly-aligned data.
    # This checks the dispatch RULES, not real-world data integration
    # (timezones, resampling, index alignment) -- that's covered in
    # notebooks/0.4-dispatch-exploration.ipynb.
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
    peak_threshold_kw = 4
    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=peak_threshold_kw)

    print(result)

    metrics = compute_dispatch_metrics(result, peak_threshold_kw=peak_threshold_kw)
    print(f"\nPeak without battery: {metrics['peak_import_no_battery_kw']:.2f} kW")
    print(f"Peak with battery:    {metrics['peak_import_with_battery_kw']:.2f} kW")
    print(f"Peak shaved:          {metrics['peak_shaved_kw']:.2f} kW ({metrics['peak_shaved_pct']:.0f}%)")
    print(f"Self-consumption:     {metrics['self_consumption_pct']:.0f}%")
    print(f"\nTotal grid import: {result['grid_import_kwh'].sum():.2f} kWh")
    print(f"Total grid export: {result['grid_export_kwh'].sum():.2f} kWh")