"""Rule-based battery dispatch (RBC): the baseline for the LP optimization.

A deterministic, non-optimizing set of priority rules decides charge and
discharge each timestep. It answers the question: how much better does real
optimization (optimize.py) do than a sensible rule-based controller?

Three rules, applied each timestep:
1. PV charging: charge with PV surplus, limited by power and remaining
   capacity.
2. Peak shaving: discharge only when grid import would exceed the threshold,
   and only down to that threshold (the monthly peak is billed on the highest
   quarter-hour, NET-4). Below the threshold the battery does not discharge:
   a small deficit is covered from the grid.
3. Grid charging (ARCH-3): when import stays below the threshold, top up from
   the grid with at most the remaining headroom, so the battery is full before
   the next peak.

The rules never look at prices (ARCH-1) or ahead in time (TIME-1). Battery
model as in ASSUMPTIONS.md: one power limit for both directions (BAT-1),
losses on charging only (BAT-2), SoC between min and max.
"""

import pandas as pd

from bess_office.config import BatteryConfig


def run_baseline_dispatch(
    pv_kwh: pd.Series,
    load_kwh: pd.Series,
    battery: BatteryConfig,
    peak_threshold_kw: float,
    timestep_hours: float,
) -> pd.DataFrame:
    """
    Simulate battery dispatch with the three priority rules.

    Parameters
    ----------
    pv_kwh : pd.Series
        PV generation in kWh per timestep, indexed by timestamp.
    load_kwh : pd.Series
        Building consumption in kWh per timestep, same index as pv_kwh.
    battery : BatteryConfig
        Battery capacity, power, efficiency and SoC bounds.
    peak_threshold_kw : float
        Grid import above this level (kW) triggers discharge.
    timestep_hours : float
        Length of each timestep in hours, e.g. 0.25 for quarter-hours.
        Converts the kW limits into kWh per timestep. Deliberately has no
        default: with 1.0, kWh equals kW and unit errors stay invisible.

    Returns
    -------
    pd.DataFrame
        One row per timestep: pv_kwh, load_kwh, soc_kwh, charge_kwh,
        discharge_kwh, grid_import_kwh, grid_export_kwh (same columns as
        run_lp_dispatch).
    """
    if not pv_kwh.index.equals(load_kwh.index):
        raise ValueError(
            "pv_kwh and load_kwh must share the same index. "
            "Resample/align both series before calling this function."
        )

    min_soc = battery.min_soc_fraction * battery.capacity_kwh
    max_soc = battery.max_soc_fraction * battery.capacity_kwh
    soc = battery.initial_soc_fraction * battery.capacity_kwh
    charge_efficiency = battery.round_trip_efficiency  # applied on charging only (BAT-2)
    max_energy_per_step = battery.power_kw * timestep_hours

    records = []

    for timestamp, pv in pv_kwh.items():
        load = load_kwh.loc[timestamp]
        surplus = pv - load  # > 0: PV surplus, < 0: deficit

        charge = 0.0
        discharge = 0.0

        if surplus > 0:
            # Rule 1: charge with PV surplus.
            room_in_battery = (max_soc - soc) / charge_efficiency
            charge = min(surplus, max_energy_per_step, room_in_battery)
            soc += charge * charge_efficiency

        else:
            deficit = -surplus
            # Rule 2: deficit is kWh per timestep, the threshold is kW.
            if deficit / timestep_hours > peak_threshold_kw:
                shave_target = deficit - peak_threshold_kw * timestep_hours
                available_energy = soc - min_soc
                discharge = min(shave_target, max_energy_per_step, available_energy)
                soc -= discharge

        if discharge == 0:
            # Rule 3: top up from the grid up to the threshold, limited by the
            # power left after PV charging and by max SoC.
            current_import = max(0.0, load + charge - pv)
            headroom = peak_threshold_kw * timestep_hours - current_import
            room_in_battery = (max_soc - soc) / charge_efficiency
            grid_charge = max(0.0, min(headroom, max_energy_per_step - charge, room_in_battery))
            charge += grid_charge
            soc += grid_charge * charge_efficiency

        # Energy balance: load + charge is covered by pv + discharge + import;
        # any remainder is exported.
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


def compute_dispatch_metrics(
    result: pd.DataFrame, peak_threshold_kw: float, timestep_hours: float
) -> dict:
    """
    Summarize a dispatch result: peak import with and without battery, and
    PV self-consumption.

    Parameters
    ----------
    result : pd.DataFrame
        Output of run_baseline_dispatch or run_lp_dispatch (kWh per timestep).
    peak_threshold_kw : float
        Threshold used for the run; only echoed back.
    timestep_hours : float
        Length of each timestep in hours, to convert kWh per timestep to kW.

    Returns
    -------
    dict
        Peaks in kW (``*_kw``), self-consumption in percent (``*_pct``).
    """
    naive_import = (result["load_kwh"] - result["pv_kwh"]).clip(lower=0)
    peak_no_battery = naive_import.max() / timestep_hours  # kW
    peak_with_battery = result["grid_import_kwh"].max() / timestep_hours  # kW
    peak_shaved = peak_no_battery - peak_with_battery
    peak_shaved_pct = 100 * peak_shaved / peak_no_battery if peak_no_battery > 0 else 0.0

    # Self-consumption = share of PV not exported. Assumes all export is PV;
    # if the battery itself exports (possible in the LP), this understates it.
    pv_total = result["pv_kwh"].sum()
    pv_used_onsite = pv_total - result["grid_export_kwh"].sum()
    self_consumption_pct = 100 * pv_used_onsite / pv_total if pv_total > 0 else 0.0

    # Without a battery, PV used on site is min(pv, load) per timestep.
    naive_pv_used_onsite = pd.concat([result["pv_kwh"], result["load_kwh"]], axis=1).min(axis=1).sum()
    self_consumption_no_battery_pct = 100 * naive_pv_used_onsite / pv_total if pv_total > 0 else 0.0

    return {
        "peak_threshold_kw": peak_threshold_kw,
        "peak_import_no_battery_kw": peak_no_battery,
        "peak_import_with_battery_kw": peak_with_battery,
        "peak_shaved_kw": peak_shaved,
        "peak_shaved_pct": peak_shaved_pct,
        "self_consumption_pct": self_consumption_pct,
        "self_consumption_no_battery_pct": self_consumption_no_battery_pct,
        "self_consumption_gain_pct": self_consumption_pct - self_consumption_no_battery_pct,
    }


if __name__ == "__main__":
    # Quick logic check on small synthetic hourly data. With timestep 1.0,
    # kWh equals kW, so unit errors are not visible here: the pytest tests
    # use 0.25 for that.
    import numpy as np

    hours = pd.date_range("2023-06-01", periods=24, freq="1h")
    pv = pd.Series(np.clip(5 * np.sin((hours.hour - 6) / 12 * np.pi), 0, None), index=hours)
    load = pd.Series(
        [2, 2, 2, 2, 2, 3, 5, 6, 4, 3, 3, 3, 3, 3, 3, 4, 6, 7, 6, 4, 3, 2, 2, 2],
        index=hours,
    )

    battery = BatteryConfig(capacity_kwh=10, power_kw=5)
    peak_threshold_kw = 4
    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=peak_threshold_kw, timestep_hours=1.0)
    print(result)

    metrics = compute_dispatch_metrics(result, peak_threshold_kw=peak_threshold_kw, timestep_hours=1.0)
    print(f"\nPeak without battery: {metrics['peak_import_no_battery_kw']:.2f} kW")
    print(f"Peak with battery:    {metrics['peak_import_with_battery_kw']:.2f} kW")
    print(f"Peak shaved:          {metrics['peak_shaved_kw']:.2f} kW ({metrics['peak_shaved_pct']:.0f}%)")
    print(f"Self-consumption:     {metrics['self_consumption_pct']:.0f}%")
    print(f"\nTotal grid import: {result['grid_import_kwh'].sum():.2f} kWh")
    print(f"Total grid export: {result['grid_export_kwh'].sum():.2f} kWh")