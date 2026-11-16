from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BatteryConfig:
    # BOLT-241 (Boltainer, NL) -- corrects DATA-4, see ASSUMPTIONS.md DATA-9.
    # 241 kWh capacity; power options 49/60/99/120 kW, 99 kW chosen
    # based on the calculated peak (99.4 kW, see derive_peak_kwh_per_quarter).
    # NOTE: usable capacity (after min/max SoC) and exact round-trip
    # efficiency of this product have not been verified separately -- the
    # min/max_soc_fraction and round_trip_efficiency below are still
    # the old SigenStor assumptions, not product-specific for the BOLT-241.
    capacity_kwh: float = 241.0
    power_kw: float = 99.0
    round_trip_efficiency: float = 0.90  # TODO: look up BOLT-241-specific figure
    min_soc_fraction: float = 0.10       # TODO: same
    max_soc_fraction: float = 0.95       # TODO: same
    initial_soc_fraction: float = 0.50


@dataclass
class PVConfig:
    latitude: float = 52.01
    longitude: float = 4.36
    # Export-aware sizing (~33% annual coverage) -- corrects the
    # old 25 kWp, see ASSUMPTIONS.md DATA-10. Deliberately not aimed at full
    # annual consumption coverage (that would be ~673 kWp): for large consumers
    # export is structurally valued lower than self-consumption (see
    # ARCH-5), so an installation that mainly exports is economically
    # less efficient than its kWp figure suggests.
    peak_power_kw: float = 190.0
    tilt: float = 12.0
    azimuth: float = 180.0
    # 180 = south, verified against pvlib's north-zero convention
    # (north=0, east=90, south=180, west=270) since pvlib 0.10.0.
    # pyproject.toml requires pvlib>=0.15.2, so this value is correct
    # without manual conversion to PVGIS' own (different) convention.
    mounting_place: str = "free"
    system_loss_pct: float = 14.0
    year: int = 2023
    save_raw: bool = True


@dataclass
class BuildingConfig:
    # Large-consumer scale (grootverbruik, >3x80A / 55 kVA), deliberately
    # chosen -- corrects DATA-3, see ASSUMPTIONS.md DATA-8.
    #
    # annual_kwh_per_m2 remains the Dutch average office/education reference
    # (Energy Shift, range 100-150) -- that does not change with scale.
    # area_m2 has been increased so that the resulting peak (via
    # derive_peak_kwh_per_quarter() in fetch_load.py) ends up well above the
    # 55 kVA threshold:
    #
    #   sum(relative_profile) on KO_KANTOOR_ONDERWIJS, verified via
    #   get_relative_profile().sum(): 20,824.42
    #   4,500 m2 x 115 kWh/m2/year = 517,500 kWh/year
    #   -> peak_kwh_per_quarter = 517,500 / 20,824.42 = 24.85 kWh/quarter-hour
    #   -> peak = 99.4 kW  (verified via get_relative_profile().sum())
    area_m2: float = 4500.0
    annual_kwh_per_m2: float = 115.0    # Dutch average, range 100-150 (Energy Shift)
    # peak_kwh_per_quarter is deliberately not here -- it is not a pure
    # building property (it also depends on the chosen profile shape), and is
    # derived in main.py via derive_peak_kwh_per_quarter().


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