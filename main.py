"""End-to-end baseline + LP dispatch run, using real PV, load, and price data.

Unlike dispatch_sim.py's and optimize.py's own __main__ blocks (which test
the dispatch RULES/LP against small, synthetic, hand-verifiable data), this
script runs the REAL pipeline: fetch actual PV generation, actual building
consumption, and actual day-ahead prices, align them to a common
quarter-hour resolution, run BOTH dispatch methods, and translate the
results to EUR -- runnable directly from the terminal with `uv run main.py`.

The result is a quantitative comparison between no battery, the
rule-based baseline (RBC, dispatch_sim.py) and the LP optimization
(optimize.py), on both peak reduction and euros, for scenario A (base)
and B (double energy tax on storage, NET-6).
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
    """Translate a dispatch result (kWh) into EUR, as a separate step
    after the dispatch itself.

    dispatch_sim.py is kWh-only by design (ARCH-1); optimize.py has its
    costs inside the objective (ARCH-4). This function recomputes the cost
    of BOTH results with one identical formula, so the comparison is fair.
    It uses the same components as optimize.py's objective:

    - import cost and export revenue at the day-ahead price (ARCH-5),
    - transport tariff per kWh imported,
    - energy tax per kWh imported, no netting (NET-5),
    - storage tax per kWh charged into the battery (NET-6, 0 in scenario A),
    - monthly peak tariff per kW of the highest quarter-hour import per
      calendar month.

    The annual GTV/contract-capacity component is deliberately not
    modeled (see config.py GridTariffConfig). Works for the output of
    run_baseline_dispatch and run_lp_dispatch alike -- both return the
    same columns.
    """
    prices_eur_kwh = prices_eur_mwh / 1000  # ENTSO-E supplies EUR/MWh

    import_cost = (result["grid_import_kwh"] * prices_eur_kwh).sum()  # ARCH-5
    export_revenue = (result["grid_export_kwh"] * prices_eur_kwh).sum()
    transport_cost = result["grid_import_kwh"].sum() * grid_tariff.transport_tariff_eur_per_kwh
    energy_tax_cost = result["grid_import_kwh"].sum() * grid_tariff.energy_tax_eur_per_kwh  # NET-5
    storage_tax_cost = result["charge_kwh"].sum() * grid_tariff.storage_charge_tax_eur_per_kwh  # NET-6

    # Monthly peak cost: same formula as optimize.py's objective (Liander's
    # "kW max. mnd" component, see config.py GridTariffConfig docstring).
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
    """Equivalent full cycles over the result's horizon: total discharged
    energy divided by the usable capacity (max - min SoC)."""
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
    """Scan RBC peak thresholds and return the one with the lowest annual
    net cost, plus the net cost per scanned threshold (NET-4).

    This keeps prices out of dispatch_sim.py (ARCH-1): the rule itself is
    price-agnostic, only the choice of threshold happens here, ex post on the
    full year (in-sample, and thus favourable to the RBC).
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
    """Print one dispatch method's results, with the method's name in
    every header -- without that label it is impossible to tell whether a
    number belongs to the RBC baseline or the LP optimization once two
    results are shown side by side."""
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
    # PV: PVGIS supplies hourly resolution -- upsample to quarter-hours
    # (interpolate, don't downsample -- otherwise you average away the
    # quarter-hour peak of the load, exactly the opposite of what you want).
    pv = get_pv_profile()  # power in W, not energy
    pv_quarter_w = pv.resample("15min").interpolate("linear")  # still W

    # W -> kWh per quarter-hour: power x duration, only do this here (not
    # earlier), because interpolating power over time is physically
    # correct, but the conversion to energy needs the final
    # timestep size.
    pv_quarter = pv_quarter_w * CONFIG.sim.timestep_hours / 1000

    # Load: fetch the profile shape (Liander K&O, already quarter-hour
    # resolution) separately from the scale. peak_kwh_per_quarter is NOT a
    # fixed building property -- it depends both on the target annual
    # consumption (area_m2 x annual_kwh_per_m2, externally verifiable) and
    # on how peaky THIS specific profile is (relative_profile.sum() --
    # changes if you ever switch profile files). Keep that dependency
    # explicit here instead of hidden in a separate config constant (see
    # ASSUMPTIONS.md for the discussion).
    relative_profile = get_relative_profile()
    peak_kwh_per_quarter = derive_peak_kwh_per_quarter(
        area_m2=CONFIG.building.area_m2,
        annual_kwh_per_m2=CONFIG.building.annual_kwh_per_m2,
        relative_profile=relative_profile,
    )
    load = relative_profile * peak_kwh_per_quarter

    # Prices: 2023 was still hourly resolution (before the SDAC 15-min
    # transition of Oct 2025) -- ffill to quarter-hours, don't interpolate,
    # because the price really was 1 value per hour, not a gradual transition.
    prices = get_day_ahead_prices(
        pd.Timestamp(f"{CONFIG.pv.year}-01-01", tz="Europe/Amsterdam"),
        pd.Timestamp(f"{CONFIG.pv.year + 1}-01-01", tz="Europe/Amsterdam"),
    )
    prices_quarter = prices.resample("15min").ffill()

    # Align: all three are tz-aware/quarter-hour, but PV (interpolated)
    # and prices (ffilled) can run slightly differently at the edges
    # than load (original) -- inner join on what actually overlaps.
    pv_quarter, load = pv_quarter.align(load, join="inner")
    prices_quarter = prices_quarter.reindex(load.index, method="ffill")

    surplus = pv_quarter - load

    print(f"Using peak_kwh_per_quarter: {peak_kwh_per_quarter:.2f} kWh "
          f"(from {CONFIG.building.area_m2:.0f} m2 x {CONFIG.building.annual_kwh_per_m2:.0f} kWh/m2/year)")
    print(f"Timesteps with PV surplus: {(surplus > 0).sum()} of {len(surplus)}")
    print()

    # --- RBC (Rule-Based Control): rule-based baseline, dispatch_sim.py ---
    # Choose the threshold fairly: scan for the lowest annual net cost (NET-4).
    rbc_threshold_kw, threshold_scan = select_rbc_threshold(
        pv_quarter, load, prices_quarter, CONFIG.battery, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print(
        f"RBC threshold scan {threshold_scan.index.min():.0f}-{threshold_scan.index.max():.0f} kW: "
        f"net cost €{threshold_scan.min():.2f} - €{threshold_scan.max():.2f}"
    )
    print(f"Selected RBC threshold: {rbc_threshold_kw:.0f} kW")
    print()

    # --- Reference: no battery. Same RBC function with a battery of
    # 0 kWh / 0 kW, so columns and energy balance are guaranteed identical.
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

    # --- LP optimization: optimize.py. NOTE: this solves an LP over the
    # full annual horizon at quarter-hour resolution (~35,000 timesteps) --
    # this can take a few minutes, depending on your CBC installation.
    lp_result = run_lp_dispatch(
        pv_quarter,
        load,
        prices_quarter,
        CONFIG.battery,
        CONFIG.grid_tariff,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    # compute_dispatch_metrics is dispatch-method-agnostic (it only looks
    # at the columns pv_kwh/load_kwh/grid_import_kwh/grid_export_kwh),
    # so it is reusable for the LP result. peak_threshold_kw here is
    # purely a descriptive metric (how much reduction relative to that
    # threshold), not something the LP itself optimizes against.
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
    # The RBC is price-agnostic (ARCH-1): its dispatch stays the same, only the
    # costs are recalculated. The LP is re-solved.
    tariff_b = dataclasses.replace(
        CONFIG.grid_tariff, storage_charge_tax_eur_per_kwh=CONFIG.grid_tariff.energy_tax_eur_per_kwh
    )
    rbc_financials_b = compute_financial_metrics(rbc_result, prices_quarter, tariff_b, CONFIG.sim.timestep_hours)
    lp_result_b = run_lp_dispatch(
        pv_quarter, load, prices_quarter, CONFIG.battery, tariff_b, timestep_hours=CONFIG.sim.timestep_hours
    )
    lp_financials_b = compute_financial_metrics(lp_result_b, prices_quarter, tariff_b, CONFIG.sim.timestep_hours)

    # Without a battery charge_kwh is 0 everywhere, so B == A for this scenario.
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