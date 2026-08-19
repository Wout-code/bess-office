"""End-to-end baseline dispatch run, using real PV and load data.

Unlike dispatch_sim.py's own __main__ block (which tests the dispatch
RULES against small, synthetic, hand-verifiable data), this script
runs the REAL pipeline: fetch actual PV generation and actual building
consumption, align them, and simulate dispatch -- the same thing the
exploration notebook (notebooks/0.4-dispatch-exploration.ipynb) does
interactively, but runnable directly from the terminal with `uv run
main.py`, without needing to open a notebook.
"""

from bess_office.dispatch_sim import (
    BatterySpec,
    compute_dispatch_metrics,
    run_baseline_dispatch,
)
from bess_office.fetch_load import get_load_profile
from bess_office.fetch_pv import get_pv_profile

# --- Scenario configuration -------------------------------------------
# TODO: replace with the actual building/battery specs once known.
LATITUDE = 52.01
LONGITUDE = 4.36
PEAK_POWER_KW = 10  # installed PV peak power

PEAK_KWH_PER_QUARTER = 15  # office building's peak quarter-hour consumption

BATTERY = BatterySpec(capacity_kwh=10, power_kw=10)  # fake specs, TODO: replace
PEAK_THRESHOLD_KW = 8
TIMESTEP_HOURS = 1.0


def main() -> None:
    pv = get_pv_profile(latitude=LATITUDE, longitude=LONGITUDE, peak_power_kw=PEAK_POWER_KW)

    load = get_load_profile(peak_kwh_per_quarter=PEAK_KWH_PER_QUARTER)
    load_hourly = load.resample("1h").sum()  # match PV's hourly resolution

    result = run_baseline_dispatch(
        pv,
        load_hourly,
        BATTERY,
        peak_threshold_kw=PEAK_THRESHOLD_KW,
        timestep_hours=TIMESTEP_HOURS,
    )

    metrics = compute_dispatch_metrics(result, peak_threshold_kw=PEAK_THRESHOLD_KW)

    print(result.head())
    print()
    print(f"Peak without battery: {metrics['peak_import_no_battery_kw']:.2f} kW")
    print(f"Peak with battery:    {metrics['peak_import_with_battery_kw']:.2f} kW")
    print(f"Peak shaved:          {metrics['peak_shaved_kw']:.2f} kW ({metrics['peak_shaved_pct']:.0f}%)")
    print()
    print(f"Self-consumption (no battery):   {metrics['self_consumption_no_battery_pct']:.0f}%")
    print(f"Self-consumption (with battery): {metrics['self_consumption_pct']:.0f}%")
    print(f"Self-consumption gain:           +{metrics['self_consumption_gain_pct']:.0f} pp")
    print()
    print(f"Total grid import: {result['grid_import_kwh'].sum():.2f} kWh")
    print(f"Total grid export: {result['grid_export_kwh'].sum():.2f} kWh")


if __name__ == "__main__":
    main()