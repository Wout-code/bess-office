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


@dataclass
class PVConfig:
    # Delft (hypothetical site, DATA-8).
    latitude: float = 52.01
    longitude: float = 4.36
    # 190 kWp, ~36% of annual consumption (DATA-10): fits on the roof and keeps
    # most PV consumed on site, since export is valued lower than
    # self-consumption for large consumers (ARCH-5).
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
    # The RBC threshold is no longer fixed, but scanned in main.py for the
    # lowest annual net cost (NET-4): range(min, max + 1, step).
    threshold_scan_min_kw: float = 50.0
    threshold_scan_max_kw: float = 99.0
    threshold_scan_step_kw: float = 2.0


@dataclass
class GridTariffConfig:
    """
    Grid operator transport costs -- DELIBERATELY SIMPLIFIED, see below.

    The tariff STRUCTURE comes from the Liander PDF "tarieven voor aansluiting
    en transport elektriciteit 2026" (sub-market MS/LS > 50 up to and including
    136 kW, applicable to ~99.4 kW); the NUMBERS below have not been verified
    (see TODO). According to that PDF there are TWO separate capacity components:
      1. "kW contract" -- annual tariff for contracted transport capacity (GTV)
         over your contracted power; exceeding it automatically raises your GTV
         for the entire calendar year (no separate penalty tariff).
      2. "kW max. mnd" -- a SEPARATE tariff, recalculated every month over
         the highest measured peak that month, independent of your GTV.

    SIMPLIFICATION (deliberate, to get the model working now): this
    file models only component 2 (the monthly peak). Component
    1 (GTV/annual exceedance) is NOT included -- treated as
    a fixed, dispatch-independent cost, out of scope for now.
    optimize.py therefore only minimizes the sum of the 12 monthly peaks × the
    monthly tariff, not the full Liander cost structure.

    TODO, in order:
    - The numbers below are ESTIMATES from an AI summary of
      the Liander PDF, NOT manually verified -- two attempts gave
      mutually inconsistent figures for the same sub-market. Check
      the exact table yourself in:
      https://www.liander.nl/-/media/files/tarieven/grootzakelijk/tarieven-2026/tarieven-voor-aansluiting-en-transport-elektriciteit-2026_2.pdf
    - Once verified: add component 1 (GTV) to the model after all,
      e.g. as a peak_floor constraint on an annual peak.
    """
    # Component: transport tariff over the total annual volume, kWh -- no
    # relation to the peak. ESTIMATE, not verified: €0.0226/kWh (sub-market
    # MS/LS > 50 up to and including 136 kW).
    transport_tariff_eur_per_kwh: float | None = 0.0226

    # Component: "kW max. mnd" -- tariff per kW of the highest measured
    # peak in a calendar month. This is the only capacity tariff that
    # optimize.py currently uses. ESTIMATE, not verified:
    # €3.57/kW/month (sub-market MS/LS > 50 up to and including 136 kW).
    monthly_peak_tariff_eur_per_kw: float | None = 3.57

    # Energy tax (energiebelasting, NET-5): fixed rate per imported kWh, marginal
    # bracket 50,000-10 million kWh, 2026, excl. VAT. Only on import, no
    # net metering (saldering) for large consumers. The higher rates of the first
    # 50,000 kWh are a fixed cost and not decision-relevant.
    energy_tax_eur_per_kwh: float = 0.03735

    # Hypothetical double energy tax on storage (NET-6), per kWh that goes into
    # the battery (charge_kwh, so PV charging too: upper bound).
    # 0.0 = scenario A (base); equal to energy_tax_eur_per_kwh = scenario B.
    storage_charge_tax_eur_per_kwh: float = 0.0

    # Not used in the current simplified model -- kept for when
    # component 1 (GTV/annual exceedance) is added.
    # ESTIMATE, not verified: €3.74/kW/month for the GTV tariff.
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