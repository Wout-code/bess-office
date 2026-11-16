"""End-to-end baseline + LP dispatch run, using real PV, load, and price data.

Unlike dispatch_sim.py's and optimize.py's own __main__ blocks (which test
the dispatch RULES/LP against small, synthetic, hand-verifiable data), this
script runs the REAL pipeline: fetch actual PV generation, actual building
consumption, and actual day-ahead prices, align them to a common
quarter-hour resolution, run BOTH dispatch methods, and translate the
results to EUR -- runnable directly from the terminal with `uv run main.py`.

This is Fase 1's deliverable (zie ROADMAP.md): een kwantitatieve
vergelijking tussen de regelgebaseerde baseline (RBC, dispatch_sim.py) en
de LP-optimalisatie (optimize.py), op zowel piekreductie als euro's.
"""

import numpy as np
import pandas as pd

from bess_office.config import CONFIG, BatteryConfig
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch
from bess_office.fetch_load import derive_peak_kwh_per_quarter, get_relative_profile
from bess_office.fetch_prices import get_day_ahead_prices
from bess_office.fetch_pv import get_pv_profile
from bess_office.optimize import run_lp_dispatch


def compute_financial_metrics(
    result: pd.DataFrame, prices_eur_mwh: pd.Series, grid_tariff, timestep_hours: float
) -> dict:
    """Translate a dispatch result (kWh) into EUR -- as a separate step
    AFTER the dispatch itself (dispatch_sim.py and optimize.py both stay
    kWh-only by design, see ASSUMPTIONS.md Architectuur).

    Rekent dezelfde drie kostencomponenten als optimize.py's objective
    (energie, transport, maandpiek -- zie config.py GridTariffConfig voor
    waarom het bij twee componenten + maandpiek is gebleven, GTV
    bewust buiten scope), zodat de baseline en de LP op een EERLIJKE,
    identieke kostenformule vergeleken worden. Werkt voor het resultaat
    van ZOWEL run_baseline_dispatch als run_lp_dispatch -- beide geven
    dezelfde kolommen terug.
    """
    prices_eur_kwh = prices_eur_mwh / 1000  # ENTSO-E levert EUR/MWh

    import_cost = (result["grid_import_kwh"] * prices_eur_kwh).sum()  # ARCH-5
    export_revenue = (result["grid_export_kwh"] * prices_eur_kwh).sum()
    transport_cost = result["grid_import_kwh"].sum() * grid_tariff.transport_tariff_eur_per_kwh

    # Maandpiek-kost: zelfde formule als optimize.py's objective (Liander's
    # "kW max. mnd"-component, zie config.py GridTariffConfig-docstring).
    peak_import_kw_per_step = result["grid_import_kwh"] / timestep_hours
    monthly_peak_kw = peak_import_kw_per_step.groupby(result.index.to_period("M")).max()
    peak_cost = monthly_peak_kw.sum() * grid_tariff.monthly_peak_tariff_eur_per_kw

    return {
        "import_cost_eur": import_cost,
        "export_revenue_eur": export_revenue,
        "transport_cost_eur": transport_cost,
        "peak_cost_eur": peak_cost,
        "net_cost_eur": import_cost + transport_cost + peak_cost - export_revenue,
        "monthly_peak_kw": monthly_peak_kw,
    }


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

    De prijzen blijven zo buiten dispatch_sim.py (ARCH-1): de regel zelf is
    prijsloos, alleen de keuze van de drempel gebeurt hier, achteraf op het
    hele jaar (in-sample, dus gunstig voor de RBC).
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
    every header -- zonder dat label is niet te zien of een getal bij de
    RBC-baseline of de LP-optimalisatie hoort zodra er twee resultaten
    naast elkaar staan."""
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
    print(f"Peak/capacity cost ({label}): €{financials['peak_cost_eur']:.2f}")
    print(f"Net cost ({label}):        €{financials['net_cost_eur']:.2f}")
    print()


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

    print(f"Gebruikt peak_kwh_per_quarter: {peak_kwh_per_quarter:.2f} kWh "
          f"(uit {CONFIG.building.area_m2:.0f} m2 x {CONFIG.building.annual_kwh_per_m2:.0f} kWh/m2/jaar)")
    print(f"Momenten met PV-overschot: {(surplus > 0).sum()} van {len(surplus)}")
    print()

    # --- RBC (Rule-Based Control): regelgebaseerde baseline, dispatch_sim.py ---
    # Drempel eerlijk kiezen: scan op laagste jaarlijkse netto kosten (NET-4).
    rbc_threshold_kw, threshold_scan = select_rbc_threshold(
        pv_quarter, load, prices_quarter, CONFIG.battery, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print(
        f"RBC-drempelscan {threshold_scan.index.min():.0f}-{threshold_scan.index.max():.0f} kW: "
        f"netto kosten €{threshold_scan.min():.2f} - €{threshold_scan.max():.2f}"
    )
    print(f"Gekozen RBC-drempel: {rbc_threshold_kw:.0f} kW")
    print()

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

    # --- LP-optimalisatie: optimize.py. LET OP: dit lost een LP op over de
    # volledige jaarhorizon op kwartier-resolutie (~35.000 tijdstappen) --
    # dit kan een paar minuten duren, afhankelijk van je CBC-installatie.
    lp_result = run_lp_dispatch(
        pv_quarter,
        load,
        prices_quarter,
        CONFIG.battery,
        CONFIG.grid_tariff,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    # compute_dispatch_metrics is dispatch-methode-agnostisch (kijkt alleen
    # naar de kolommen pv_kwh/load_kwh/grid_import_kwh/grid_export_kwh),
    # dus herbruikbaar voor het LP-resultaat. peak_threshold_kw hier is
    # puur een beschrijvende metriek (hoeveel reductie t.o.v. die drempel),
    # niet iets waar de LP zelf tegen optimaliseert.
    lp_metrics = compute_dispatch_metrics(
        lp_result,
        peak_threshold_kw=rbc_threshold_kw,
        timestep_hours=CONFIG.sim.timestep_hours,
    )
    lp_financials = compute_financial_metrics(
        lp_result, prices_quarter, CONFIG.grid_tariff, CONFIG.sim.timestep_hours
    )
    print_dispatch_report("LP-optimalisatie", lp_result, lp_metrics, lp_financials)

    # --- Vergelijking: dit is het eigenlijke Fase 1-deliverable ---
    print("=== Vergelijking RBC vs. LP ===")
    cost_savings = rbc_financials["net_cost_eur"] - lp_financials["net_cost_eur"]
    cost_savings_pct = (
        100 * cost_savings / rbc_financials["net_cost_eur"] if rbc_financials["net_cost_eur"] else 0.0
    )
    print(
        f"Piekreductie LP t.o.v. RBC: "
        f"{rbc_metrics['peak_import_with_battery_kw'] - lp_metrics['peak_import_with_battery_kw']:.2f} kW"
    )
    print(f"Kostenbesparing LP t.o.v. RBC: €{cost_savings:.2f} ({cost_savings_pct:.1f}%)")


if __name__ == "__main__":
    main()