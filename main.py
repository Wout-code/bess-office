"""End-to-end run: no battery, rule-based control (RBC) and LP optimization.

Unlike the __main__ blocks of dispatch_sim.py and optimize.py, which test the
rules and the LP on small synthetic data, this script runs the full pipeline:
load PV (PVGIS), consumption (Liander standard profile, scaled to the
reference building) and day-ahead prices (ENTSO-E), align them to quarter-
hours, run both dispatch methods and translate the results to EUR.

Output: a comparison of no battery, RBC (dispatch_sim.py) and LP (optimize.py)
on peak reduction and euros, for scenario A (base) and B (double energy tax on
storage, NET-6), plus a cost breakdown plot. Run with `uv run main.py`.
"""

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from bess_office.config import CONFIG, BatteryConfig
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch
from bess_office.fetch_load import derive_peak_kwh_per_quarter, get_relative_profile
from bess_office.fetch_prices import get_day_ahead_prices
from bess_office.fetch_pv import get_pv_profile
from bess_office.optimize import run_lp_dispatch
from bess_office.plotting import plot_cost_breakdown

RESULTS_DIR = Path(__file__).parent / "results"


def compute_financial_metrics(
    result: pd.DataFrame, prices_eur_mwh: pd.Series, grid_tariff, timestep_hours: float
) -> dict:
    """Translate a dispatch result (kWh) into EUR.

    dispatch_sim.py has no prices (ARCH-1); optimize.py has its costs inside
    the objective (ARCH-4). This function recomputes the cost of both results
    with one identical formula, so the comparison is fair. Same components as
    the LP objective:

    - import cost and export revenue at the day-ahead price (NET-7, ARCH-5),
    - transport tariff per kWh imported,
    - energy tax per kWh imported, no netting (NET-5),
    - storage tax per kWh charged into the battery (NET-6, 0 in scenario A),
    - monthly peak tariff per kW of the highest quarter-hour import per
      calendar month (NET-4).

    The GTV/contracted-capacity component is not modeled (NET-8). Works for
    the output of run_baseline_dispatch and run_lp_dispatch alike: both return
    the same columns.
    """
    prices_eur_kwh = prices_eur_mwh / 1000  # ENTSO-E supplies EUR/MWh

    import_cost = (result["grid_import_kwh"] * prices_eur_kwh).sum()
    export_revenue = (result["grid_export_kwh"] * prices_eur_kwh).sum()
    transport_cost = result["grid_import_kwh"].sum() * grid_tariff.transport_tariff_eur_per_kwh
    energy_tax_cost = result["grid_import_kwh"].sum() * grid_tariff.energy_tax_eur_per_kwh
    storage_tax_cost = result["charge_kwh"].sum() * grid_tariff.storage_charge_tax_eur_per_kwh

    # Monthly peak: kWh per timestep -> kW, highest per calendar month.
    peak_import_kw_per_step = result["grid_import_kwh"] / timestep_hours
    monthly_peak_kw = peak_import_kw_per_step.groupby(result.index.to_period("M")).max()
    peak_cost = monthly_peak_kw.sum() * grid_tariff.monthly_peak_tariff_eur_per_kw

    return {
        "import_cost_eur": import_cost,
        "export_revenue_eur": export_revenue,
        "transport_cost_eur": transport_cost,
        "energy_tax_cost_eur": energy_tax_cost,
        "storage_tax_cost_eur": storage_tax_cost,
        "peak_cost_eur": peak_cost,
        "net_cost_eur": (
            import_cost + transport_cost + energy_tax_cost + storage_tax_cost + peak_cost - export_revenue
        ),
        "monthly_peak_kw": monthly_peak_kw,
    }


def equivalent_full_cycles(result: pd.DataFrame, battery: BatteryConfig) -> float:
    """Equivalent full cycles over the horizon: total discharged energy divided
    by the usable capacity (max - min SoC)."""
    usable_kwh = (battery.max_soc_fraction - battery.min_soc_fraction) * battery.capacity_kwh
    return result["discharge_kwh"].sum() / usable_kwh


def select_rbc_threshold(
    pv_kwh: pd.Series,
    load_kwh: pd.Series,
    prices_eur_mwh: pd.Series,
    battery: BatteryConfig,
    grid_tariff,
    timestep_hours: float,
) -> tuple[float, pd.Series]:
    """Scan RBC thresholds and return the one with the lowest annual net cost,
    plus the net cost per scanned threshold (NET-4).

    Prices stay out of dispatch_sim.py (ARCH-1): the rule itself never looks at
    prices, only the choice of threshold does. The choice is made on the same
    year it is tested on (in-sample), which favours the RBC.
    """
    cfg = CONFIG.dispatch
    thresholds_kw = np.arange(
        cfg.threshold_scan_min_kw, cfg.threshold_scan_max_kw + 1e-9, cfg.threshold_scan_step_kw
    )
    net_cost_eur = {}
    for threshold_kw in thresholds_kw:
        result = run_baseline_dispatch(
            pv_kwh, load_kwh, battery, peak_threshold_kw=float(threshold_kw), timestep_hours=timestep_hours
        )
        financials = compute_financial_metrics(result, prices_eur_mwh, grid_tariff, timestep_hours)
        net_cost_eur[float(threshold_kw)] = financials["net_cost_eur"]
    scan = pd.Series(net_cost_eur, name="net_cost_eur")
    return float(scan.idxmin()), scan


def print_dispatch_report(label: str, result: pd.DataFrame, metrics: dict, financials: dict) -> None:
    """Print one dispatch method's results, with its name in every line so the
    RBC and LP numbers cannot be mixed up."""
    print(f"=== {label} ===")
    print(f"Peak without battery: {metrics['peak_import_no_battery_kw']:.2f} kW")
    print(f"Peak with battery ({label}): {metrics['peak_import_with_battery_kw']:.2f} kW")
    print(f"Peak shaved ({label}):       {metrics['peak_shaved_kw']:.2f} kW ({metrics['peak_shaved_pct']:.0f}%)")
    print()
    print(f"Self-consumption (no battery):        {metrics['self_consumption_no_battery_pct']:.0f}%")
    print(f"Self-consumption ({label}): {metrics['self_consumption_pct']:.0f}%")
    print(f"Self-consumption gain ({label}):       +{metrics['self_consumption_gain_pct']:.0f} pp")
    print()
    print(f"Total grid import ({label}): {result['grid_import_kwh'].sum():.2f} kWh")
    print(f"Total grid export ({label}): {result['grid_export_kwh'].sum():.2f} kWh")
    print()
    print(f"Import cost ({label}):     €{financials['import_cost_eur']:.2f}")
    print(f"Export revenue ({label}):  €{financials['export_revenue_eur']:.2f}")
    print(f"Transport cost ({label}):  €{financials['transport_cost_eur']:.2f}")
    print(f"Energy tax ({label}):      €{financials['energy_tax_cost_eur']:.2f}")
    print(f"Storage tax ({label}):     €{financials['storage_tax_cost_eur']:.2f}")
    print(f"Peak/capacity cost ({label}): €{financials['peak_cost_eur']:.2f}")
    print(f"Net cost ({label}):        €{financials['net_cost_eur']:.2f}")
    print()


def main() -> None:
    # PV: hourly from PVGIS, interpolated to quarter-hours rather than
    # averaging the load to hours, so the quarter-hour peak is kept (DATA-2).
    pv = get_pv_profile()  # power in W
    pv_quarter_w = pv.resample("15min").interpolate("linear")  # still W
    # Convert to energy only now: interpolating power is physically correct,
    # and kWh needs the final timestep length.
    pv_quarter = pv_quarter_w * CONFIG.sim.timestep_hours / 1000  # kWh per quarter-hour

    # Load: profile shape (Liander, already quarter-hourly) times the scale
    # derived from area and intensity (DATA-8). The scale depends on both the
    # building and this profile's shape, so it is derived here, not stored.
    relative_profile = get_relative_profile()
    peak_kwh_per_quarter = derive_peak_kwh_per_quarter(
        area_m2=CONFIG.building.area_m2,
        annual_kwh_per_m2=CONFIG.building.annual_kwh_per_m2,
        relative_profile=relative_profile,
    )
    load = relative_profile * peak_kwh_per_quarter

    # Prices: hourly in 2023 (before the 15-minute market of October 2025), so
    # each hour's price is held constant over its quarter-hours, not
    # interpolated (DATA-2).
    prices = get_day_ahead_prices(
        pd.Timestamp(f"{CONFIG.pv.year}-01-01", tz="Europe/Amsterdam"),
        pd.Timestamp(f"{CONFIG.pv.year + 1}-01-01", tz="Europe/Amsterdam"),
    )
    prices_quarter = prices.resample("15min").ffill()

    # Align: keep only the quarter-hours present in both PV and load (they can
    # differ at the year's edges and around the clock changes), then match the
    # prices to that index.
    pv_quarter, load = pv_quarter.align(load, join="inner")
    prices_quarter = prices_quarter.reindex(load.index, method="ffill")

    surplus = pv_quarter - load

    print(f"Using peak_kwh_per_quarter: {peak_kwh_per_quarter:.2f} kWh "
          f"(from {CONFIG.building.area_m2:.0f} m2 x {CONFIG.building.annual_kwh_per_m2:.0f} kWh/m2/year)")
    print(f"Timesteps with PV surplus: {(surplus > 0).sum()} of {len(surplus)}")
    print()

    # --- RBC: choose the threshold with the lowest annual net cost (NET-4) ---
    rbc_threshold_kw, threshold_scan = select_rbc_threshold(
        pv_quarter, load, prices_quarter, CONFIG.battery, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print(
        f"RBC threshold scan {threshold_scan.index.min():.0f}-{threshold_scan.index.max():.0f} kW: "
        f"net cost €{threshold_scan.min():.2f} - €{threshold_scan.max():.2f}"
    )
    print(f"Selected RBC threshold: {rbc_threshold_kw:.0f} kW")
    print()

    # --- Reference: no battery. The RBC function with a 0 kWh / 0 kW battery,
    # so columns and energy balance are identical by construction.
    no_battery_result = run_baseline_dispatch(
        pv_quarter,
        load,
        BatteryConfig(capacity_kwh=0.0, power_kw=0.0),
        peak_threshold_kw=rbc_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    no_battery_metrics = compute_dispatch_metrics(
        no_battery_result, peak_threshold_kw=rbc_threshold_kw, timestep_hours=CONFIG.sim.timestep_hours
    )
    no_battery_financials = compute_financial_metrics(
        no_battery_result, prices_quarter, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print_dispatch_report("No battery", no_battery_result, no_battery_metrics, no_battery_financials)

    # --- RBC ---
    rbc_result = run_baseline_dispatch(
        pv_quarter,
        load,
        CONFIG.battery,
        peak_threshold_kw=rbc_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    rbc_metrics = compute_dispatch_metrics(
        rbc_result,
        peak_threshold_kw=rbc_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    rbc_financials = compute_financial_metrics(
        rbc_result, prices_quarter, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print_dispatch_report("RBC (baseline)", rbc_result, rbc_metrics, rbc_financials)

    # --- LP: one LP over the full year at quarter-hour resolution (~35,000
    # timesteps); the slowest step of the pipeline.
    lp_result = run_lp_dispatch(
        pv_quarter,
        load,
        prices_quarter,
        CONFIG.battery,
        CONFIG.grid_tariff,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    # compute_dispatch_metrics only uses the shared columns, so it works for the
    # LP too. The threshold is only echoed back; the LP does not use it.
    lp_metrics = compute_dispatch_metrics(
        lp_result,
        peak_threshold_kw=rbc_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    lp_financials = compute_financial_metrics(
        lp_result, prices_quarter, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print_dispatch_report("LP optimization", lp_result, lp_metrics, lp_financials)

    # --- Comparison RBC vs. LP ---
    print("=== Comparison RBC vs. LP ===")
    cost_savings = rbc_financials["net_cost_eur"] - lp_financials["net_cost_eur"]
    cost_savings_pct = (
        100 * cost_savings / rbc_financials["net_cost_eur"] if rbc_financials["net_cost_eur"] else 0.0
    )
    print(
        f"Peak reduction LP vs. RBC: "
        f"{rbc_metrics['peak_import_with_battery_kw'] - lp_metrics['peak_import_with_battery_kw']:.2f} kW"
    )
    print(f"Cost savings LP vs. RBC: €{cost_savings:.2f} ({cost_savings_pct:.1f}%)")
    print(
        f"Equivalent full cycles/year: RBC {equivalent_full_cycles(rbc_result, CONFIG.battery):.0f}, "
        f"LP {equivalent_full_cycles(lp_result, CONFIG.battery):.0f}"
    )
    print()

    # --- Scenario B: hypothetical double energy tax on storage (NET-6) ---
    # The RBC never looks at prices (ARCH-1), so its dispatch stays the same and
    # only its costs are recalculated. The LP is re-solved.
    tariff_b = dataclasses.replace(
        CONFIG.grid_tariff, storage_charge_tax_eur_per_kwh=CONFIG.grid_tariff.energy_tax_eur_per_kwh
    )
    rbc_financials_b = compute_financial_metrics(rbc_result, prices_quarter, tariff_b, CONFIG.sim.timestep_hours)
    lp_result_b = run_lp_dispatch(
        pv_quarter, load, prices_quarter, CONFIG.battery, tariff_b, timestep_hours=CONFIG.sim.timestep_hours
    )
    lp_financials_b = compute_financial_metrics(lp_result_b, prices_quarter, tariff_b, CONFIG.sim.timestep_hours)

    # Without a battery nothing is charged, so B equals A here.
    no_battery_financials_b = compute_financial_metrics(
        no_battery_result, prices_quarter, tariff_b, CONFIG.sim.timestep_hours
    )

    print("=== Scenario A (base) vs. B (double tax on storage) ===")
    print(f"{'':36}{'A':>12}{'B':>12}")
    for label, fin_a, fin_b in [
        ("Net cost no battery", no_battery_financials, no_battery_financials_b),
        ("Net cost RBC", rbc_financials, rbc_financials_b),
        ("Net cost LP", lp_financials, lp_financials_b),
    ]:
        print(f"{label:36}{fin_a['net_cost_eur']:>12.2f}{fin_b['net_cost_eur']:>12.2f}")
    for label, fin_a, fin_b in [
        ("Savings RBC vs. no battery", rbc_financials, rbc_financials_b),
        ("Savings LP vs. no battery", lp_financials, lp_financials_b),
    ]:
        saving_a = no_battery_financials["net_cost_eur"] - fin_a["net_cost_eur"]
        saving_b = no_battery_financials_b["net_cost_eur"] - fin_b["net_cost_eur"]
        print(f"{label:36}{saving_a:>12.2f}{saving_b:>12.2f}")
    print(
        f"{'Cycles/year LP':36}{equivalent_full_cycles(lp_result, CONFIG.battery):>12.0f}"
        f"{equivalent_full_cycles(lp_result_b, CONFIG.battery):>12.0f}"
    )
    print()

    # --- Plot: annual cost per component, scenario A ---
    plot_path = plot_cost_breakdown(
        {
            "No battery": no_battery_financials,
            f"RBC ({rbc_threshold_kw:.0f} kW)": rbc_financials,
            "LP": lp_financials,
        },
        RESULTS_DIR / "cost_breakdown.png",
    )
    print(f"Plot saved: {plot_path}")


if __name__ == "__main__":
    main()