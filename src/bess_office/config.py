from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BatteryConfig:
    capacity_kwh: float = 36.16  # Sigenergy SigenStor, 4x9.04 kWh module
    power_kw: float = 20.0       # 3-fase omvormer (EC20K), o.b.v. berekende piek 13 kW
    round_trip_efficiency: float = 0.90
    min_soc_fraction: float = 0.10
    max_soc_fraction: float = 0.95
    initial_soc_fraction: float = 0.50


@dataclass
class PVConfig:
    latitude: float = 52.01
    longitude: float = 4.36
    peak_power_kw: float = 25.0  # o.b.v. jaarverbruik-vuistregel, zie BuildingConfig
    tilt: float = 12.0
    azimuth: float = 180.0
    mounting_place: str = "building"
    system_loss_pct: float = 14.0
    year: int = 2023
    save_raw: bool = True


@dataclass
class BuildingConfig:
    area_m2: float = 590.0              # "gemiddeld kantoor", Minder.nl-referentie
    annual_kwh_per_m2: float = 115.0    # NL-gemiddelde, bandbreedte 100-150 (Energy Shift)
    peak_kwh_per_quarter: float = 3.26  # afgeleid: (area_m2 * annual_kwh_per_m2) / profile_sum


@dataclass
class SimConfig:
    """Settings shared by both dispatch_sim and optimize."""
    timestep_hours: float = 0.25  # 15-minuten voor capaciteitstarief


@dataclass
class DispatchConfig:
    """Rule-based dispatch (dispatch_sim.py) specific settings."""
    peak_threshold_kw: float = 20.0


@dataclass
class GridTariffConfig:
    """
    Netbeheerder-transportkosten, opgesplitst per component.
    Structuur bevestigd (grootverbruik >3x80A): 3 aparte componenten.
    TODO: alle waarden zijn nog placeholders (None) -- opzoeken bij een
    echte netbeheerder-tarieventabel (Liander/Stedin/Enexis) voordat
    optimize.py hiermee gaat rekenen. Tarieven verschillen per netbeheerder.
    """
    # 1. Transporttarief: over het totale jaarvolume, kWh -- geen piek-relatie
    transport_tariff_eur_per_kwh: float | None = None

    # 2. Gecontracteerd transportvermogen (GTV): vaste, gekozen grens (kW)
    #    en de vaste prijs die je daarvoor betaalt, ongeacht werkelijk gebruik
    contracted_capacity_kw: float | None = None
    contracted_capacity_tariff_eur_per_kw: float | None = None

    # 3. Boetetarief bij overschrijding van de gecontracteerde piek --
    #    dit is de term die optimize.py's doelfunctie zal gebruiken
    overshoot_penalty_eur_per_kw: float | None = None


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