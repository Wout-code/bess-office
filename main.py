"""End-to-end baseline dispatch run, using real PV and load data.

Unlike dispatch_sim.py's own __main__ block (which tests the dispatch
RULES against small, synthetic, hand-verifiable data), this script
runs the REAL pipeline: fetch actual PV generation and actual building
consumption, align them, and simulate dispatch -- the same thing the
exploration notebook (notebooks/1.0-dispatch-baseline-test.ipynb) does
interactively, but runnable directly from the terminal with `uv run
main.py`, without needing to open a notebook.
"""

from bess_office.config import CONFIG
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch
from bess_office.fetch_load import get_load_profile
from bess_office.fetch_pv import get_pv_profile


def main() -> None:
    pv = get_pv_profile()  # uses CONFIG.pv
    load = get_load_profile(peak_kwh_per_quarter=CONFIG.building.peak_kwh_per_quarter)
    load_hourly = load.resample("1h").sum()  # match PV's hourly resolution

    result = run_baseline_dispatch(
        pv,
        load_hourly,
        CONFIG.battery,
        peak_threshold_kw=CONFIG.dispatch.peak_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )

    metrics = compute_dispatch_metrics(result, peak_threshold_kw=CONFIG.dispatch.peak_threshold_kw)

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