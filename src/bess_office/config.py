from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BatteryConfig:
    # Boltainer BOLT-241 (LFP), see ASSUMPTIONS.md DATA-9. 241 kWh; power
    # options 49/60/99/120 kW, 99 kW chosen to match the 99.4 kW peak.
    capacity_kwh: float = 241.0
    power_kw: float = 99.0
    round_trip_efficiency: float = 0.90  # not in datasheet, typical LFP value (DATA-9)
    min_soc_fraction: float = 0.10       # not in datasheet, typical LFP value (DATA-9)
    max_soc_fraction: float = 0.95       # not in datasheet, typical LFP value (DATA-9)
    initial_soc_fraction: float = 0.50
    # Degradation cost per kWh DISCHARGED (BAT-10), in the LP objective and in
    # main.compute_financial_metrics. 0.0 = wear is free (BAT-3). Central value
    # 0.04 = replaceable hardware ~200 EUR/kWh x 241 kWh (~48,200 EUR) /
    # (6,000 cycles x 204.85 usable kWh per cycle) = ~0.039 EUR/kWh.
    degradation_cost_eur_per_kwh: float = 0.0
    # Values main.py runs the degradation-cost sensitivity for (BAT-10):
    # 0 = wear is free (calendar ageing dominates), 0.04 = central value,
    # 0.06 = stress case, e.g. 4,000 instead of 6,000 cycles:
    # 48,200 / (4,000 x 204.85) = ~0.059 EUR/kWh.
    degradation_cost_sensitivity_eur_per_kwh: tuple[float, ...] = (0.0, 0.02, 0.04, 0.06)


@dataclass
class PVConfig:
    # Delft (hypothetical site, DATA-8).
    latitude: float = 52.01
    longitude: float = 4.36
    # 190 kWp, ~36% of annual consumption (DATA-10): fits on the roof and keeps
    # most PV consumed on site, since export is valued lower than
    # self-consumption for large consumers (NET-9).
    peak_power_kw: float = 190.0
    tilt: float = 12.0
    # 180 = south in pvlib's north-zero convention (north=0, east=90,
    # south=180, west=270, since pvlib 0.10.0). pyproject.toml requires
    # pvlib>=0.15.2, so no manual conversion to PVGIS' own convention is needed.
    azimuth: float = 180.0
    mounting_place: str = "free"
    system_loss_pct: float = 14.0
    year: int = 2023
    save_raw: bool = True

@dataclass
class BuildingConfig:
    # Hypothetical large-consumer office (DATA-8): 4,500 m2 x 115 kWh/m2/year
    # = 517.5 MWh/year, chosen so the peak lands well above the
    # large-consumer threshold (3x80A, ~55 kVA). The peak (99.4 kW) is not set
    # here: it also depends on the profile shape, and is derived in main.py
    # via derive_peak_kwh_per_quarter().
    area_m2: float = 4500.0
    annual_kwh_per_m2: float = 115.0  # Dutch office average, range 100-150 (Energy Shift)


@dataclass
class SimConfig:
    """Settings shared by both dispatch_sim and optimize."""
    timestep_hours: float = 0.25  # 15 minutes for the capacity tariff


@dataclass
class DispatchConfig:
    """Rule-based dispatch (dispatch_sim.py) specific settings."""
    # The RBC uses one fixed threshold for the whole year. It is not set by
    # hand: main.py scans min..max (inclusive) in steps of step_kw and picks
    # the threshold with the lowest annual net cost (NET-4).
    threshold_scan_min_kw: float = 50.0
    threshold_scan_max_kw: float = 98.0
    threshold_scan_step_kw: float = 2.0


@dataclass
class GridTariffConfig:
    """
    Grid tariffs for Liander sub-market MS/LS > 50 up to and including 136 kW
    (applies to the ~99.4 kW peak), 2026 tariff sheet:
    https://www.liander.nl/-/media/files/tarieven/grootzakelijk/tarieven-2026/tarieven-voor-aansluiting-en-transport-elektriciteit-2026_2.pdf

    Liander charges two capacity components: an annual tariff on the
    contracted capacity (GTV, "kW contract") and a monthly tariff on the
    highest measured peak ("kW max. mnd"). Only the monthly peak is modeled;
    the GTV is treated as a fixed cost (NET-8). Fixed charges (standing charge,
    connection charge) are not modeled: they are paid in every scenario.

    Figures verified against the 2026 tariff sheet (NET-8).
    """
    # EUR per kWh imported, independent of the peak.
    transport_tariff_eur_per_kwh: float | None = 0.0226

    # EUR per kW of the highest quarter-hour import, per calendar month.
    monthly_peak_tariff_eur_per_kw: float | None = 3.57

    # Energy tax, marginal bracket 50,000-10 million kWh, 2026, excl. VAT;
    # import only, no net metering for large consumers (NET-5).
    energy_tax_eur_per_kwh: float = 0.03735

    # GTV component, not used yet (NET-8): EUR per kW contracted, per month.
    contracted_capacity_kw: float | None = None
    contracted_capacity_tariff_eur_per_kw: float | None = 3.74


@dataclass
class ProjectConfig:
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    pv: PVConfig = field(default_factory=PVConfig)
    building: BuildingConfig = field(default_factory=BuildingConfig)
    sim: SimConfig = field(default_factory=SimConfig)
    dispatch: DispatchConfig = field(default_factory=DispatchConfig)
    grid_tariff: GridTariffConfig = field(default_factory=GridTariffConfig)

    data_dir: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "data"
    )


CONFIG = ProjectConfig()