"""End-to-end baseline dispatch run, using real PV, load, and price data.

Unlike dispatch_sim.py's own __main__ block (which tests the dispatch
RULES against small, synthetic, hand-verifiable data), this script
runs the REAL pipeline: fetch actual PV generation, actual building
consumption, and actual day-ahead prices, align them to a common
quarter-hour resolution, simulate dispatch, and translate the result
to EUR -- runnable directly from the terminal with `uv run main.py`.
"""

import pandas as pd

from bess_office.config import CONFIG
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch
from bess_office.fetch_load import derive_peak_kwh_per_quarter, get_relative_profile
from bess_office.fetch_prices import get_day_ahead_prices
from bess_office.fetch_pv import get_pv_profile


def compute_financial_metrics(result: pd.DataFrame, prices_eur_mwh: pd.Series) -> dict:
    """Translate the dispatch result (kWh) into EUR, as a separate step
    AFTER the dispatch itself -- dispatch_sim.py stays kWh-only by
    design (see ASSUMPTIONS.md, Architectuur)."""
    prices_eur_kwh = prices_eur_mwh / 1000  # ENTSO-E levert EUR/MWh

    import_cost = (result["grid_import_kwh"] * prices_eur_kwh).sum()    # ARCH-5
    export_revenue = (result["grid_export_kwh"] * prices_eur_kwh).sum()

    return {
        "import_cost_eur": import_cost,   
        "export_revenue_eur": export_revenue,
        "net_cost_eur": import_cost - export_revenue,
    }


def main() -> None:
    # PV: PVGIS levert uur-resolutie -- upsamplen naar kwartier
    # (interpoleren, niet downsamplen -- anders middel je de
    # kwartier-piek van load juist weg, precies andersom van wat je wil).
    pv = get_pv_profile()  # vermogen in W, geen energie
    pv_quarter_w = pv.resample("15min").interpolate("linear")  # nog steeds W

    # W -> kWh per kwartier: vermogen x tijdsduur, pas hier doen (niet
    # eerder), want interpoleren van vermogen over tijd is fysisch
    # correct, maar de omrekening naar energie heeft de uiteindelijke
    # tijdstapgrootte nodig.
    pv_quarter = pv_quarter_w * CONFIG.sim.timestep_hours / 1000

    # Load: profielvorm (Liander K&O, al kwartier-resolutie) apart ophalen
    # van de schaal. peak_kwh_per_quarter is GEEN vast gebouwskenmerk --
    # hij hangt zowel af van het gewenste jaarverbruik (area_m2 x
    # annual_kwh_per_m2, extern verifieerbaar) als van hoe piekig dít
    # specifieke profiel is (relative_profile.sum() -- verandert als je
    # ooit van profielbestand wisselt). Die afhankelijkheid hier expliciet
    # houden i.p.v. verstopt in een losse config-constante (zie
    # ASSUMPTIONS.md voor de discussie).
    relative_profile = get_relative_profile()
    peak_kwh_per_quarter = derive_peak_kwh_per_quarter(
        area_m2=CONFIG.building.area_m2,
        annual_kwh_per_m2=CONFIG.building.annual_kwh_per_m2,
        relative_profile=relative_profile,
    )
    load = relative_profile * peak_kwh_per_quarter

    # Prijzen: 2023 was nog uur-resolutie (voor de SDAC 15-min-overstap
    # van okt 2025) -- ffill naar kwartier, niet interpoleren, want de
    # prijs was toen echt 1 waarde per uur, geen geleidelijke overgang.
    prices = get_day_ahead_prices(
        pd.Timestamp(f"{CONFIG.pv.year}-01-01", tz="Europe/Amsterdam"),
        pd.Timestamp(f"{CONFIG.pv.year + 1}-01-01", tz="Europe/Amsterdam"),
    )
    prices_quarter = prices.resample("15min").ffill()

    # Uitlijnen: alle drie tz-aware/kwartier, maar PV (geinterpoleerd)
    # en prijzen (ge-ffilled) kunnen aan de randen net iets anders lopen
    # dan load (origineel) -- inner join op wat daadwerkelijk overlapt.
    pv_quarter, load = pv_quarter.align(load, join="inner")
    prices_quarter = prices_quarter.reindex(load.index, method="ffill")

    surplus = pv_quarter - load

    result = run_baseline_dispatch(
        pv_quarter,
        load,
        CONFIG.battery,
        peak_threshold_kw=CONFIG.dispatch.peak_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )

    metrics = compute_dispatch_metrics(result, peak_threshold_kw=CONFIG.dispatch.peak_threshold_kw)
    financials = compute_financial_metrics(result, prices_quarter)

    print(f"Gebruikt peak_kwh_per_quarter: {peak_kwh_per_quarter:.2f} kWh "
          f"(uit {CONFIG.building.area_m2:.0f} m2 x {CONFIG.building.annual_kwh_per_m2:.0f} kWh/m2/jaar)")
    print()
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
    print()
    print(f"Import cost:    €{financials['import_cost_eur']:.2f}")
    print(f"Export revenue: €{financials['export_revenue_eur']:.2f}")
    print(f"Net cost:       €{financials['net_cost_eur']:.2f}")
    print(f"Momenten met PV-overschot: {(surplus > 0).sum()} van {len(surplus)}")


if __name__ == "__main__":
    main()