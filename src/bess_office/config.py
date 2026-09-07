from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BatteryConfig:
    # BOLT-241 (Boltainer, NL) -- corrigeert DATA-4, zie ASSUMPTIONS.md DATA-9.
    # 241 kWh capaciteit; vermogensopties 49/60/99/120 kW, 99 kW gekozen
    # o.b.v. de berekende piek (99,4 kW, zie derive_peak_kwh_per_quarter).
    # LET OP: bruikbare capaciteit (na min/max SoC) en exacte round-trip
    # efficiency van dit product zijn niet apart geverifieerd -- de
    # onderstaande min/max_soc_fraction en round_trip_efficiency zijn nog
    # de oude SigenStor-aannames, niet productspecifiek voor de BOLT-241.
    capacity_kwh: float = 241.0
    power_kw: float = 99.0
    round_trip_efficiency: float = 0.90  # TODO: BOLT-241-specifiek getal opzoeken
    min_soc_fraction: float = 0.10       # TODO: idem
    max_soc_fraction: float = 0.95       # TODO: idem
    initial_soc_fraction: float = 0.50


@dataclass
class PVConfig:
    latitude: float = 52.01
    longitude: float = 4.36
    # Exportbewuste dimensionering (~33% jaardekking) -- corrigeert de
    # oude 25 kWp, zie ASSUMPTIONS.md DATA-10. Bewust niet op volledige
    # jaarverbruik-dekking gemikt (dat zou ~673 kWp zijn): bij grootverbruik
    # is export structureel lager gewaardeerd dan zelfconsumptie (zie
    # ARCH-5), dus een installatie die vooral exporteert is economisch
    # minder efficiënt dan zijn kWp-getal doet vermoeden.
    peak_power_kw: float = 190.0
    tilt: float = 12.0
    azimuth: float = 180.0
    # 180 = zuid, geverifieerd tegen pvlib's noord-nul-conventie
    # (noord=0, oost=90, zuid=180, west=270) sinds pvlib 0.10.0.
    # pyproject.toml vereist pvlib>=0.15.2, dus deze waarde is correct
    # zonder handmatige omrekening naar PVGIS' eigen (verschillende) conventie.
    mounting_place: str = "free"
    system_loss_pct: float = 14.0
    year: int = 2023
    save_raw: bool = True


@dataclass
class BuildingConfig:
    # Grootverbruik-schaal (>3x80A / 55 kVA), bewust gekozen -- corrigeert
    # DATA-3, zie ASSUMPTIONS.md DATA-8.
    #
    # annual_kwh_per_m2 blijft de NL-gemiddelde kantoor/onderwijs-referentie
    # (Energy Shift, bandbreedte 100-150) -- die verandert niet met schaal.
    # area_m2 is opgehoogd zodat de resulterende piek (via
    # derive_peak_kwh_per_quarter() in fetch_load.py) ruim boven de 55 kVA-
    # grens uitkomt:
    #
    #   som(relative_profile) op KO_KANTOOR_ONDERWIJS, geverifieerd via
    #   get_relative_profile().sum(): 20.824,42
    #   4.500 m2 x 115 kWh/m2/jaar = 517.500 kWh/jaar
    #   -> peak_kwh_per_quarter = 517.500 / 20.824,42 = 24,85 kWh/kwartier
    #   -> piek = 99,4 kW  (geverifieerd, zie notebook-run)
    area_m2: float = 4500.0
    annual_kwh_per_m2: float = 115.0    # NL-gemiddelde, bandbreedte 100-150 (Energy Shift)
    # peak_kwh_per_quarter staat hier bewust niet -- het is geen zuivere
    # gebouwseigenschap (hangt ook af van de gekozen profielvorm), en wordt
    # afgeleid in main.py via derive_peak_kwh_per_quarter().


@dataclass
class SimConfig:
    """Settings shared by both dispatch_sim and optimize."""
    timestep_hours: float = 0.25  # 15-minuten voor capaciteitstarief


@dataclass
class DispatchConfig:
    """Rule-based dispatch (dispatch_sim.py) specific settings."""
    peak_threshold_kw: float = 2.5
    # TODO: hoort bij de oude kleinverbruik-schaal (piek was 13 kW). Op
    # grootverbruik-schaal (piek ~99,4 kW) is 2,5 kW een zinloos lage
    # drempel -- opnieuw bepalen.


@dataclass
class GridTariffConfig:
    """
    Netbeheerder-transportkosten, opgesplitst per component.
    Structuur bevestigd (grootverbruik >3x80A): 3 aparte componenten.
    TODO: alle waarden zijn nog placeholders (None) -- opzoeken bij een
    echte netbeheerder-tarieventabel (Liander/Stedin/Enexis) voordat
    optimize.py hiermee gaat rekenen. Tarieven verschillen per netbeheerder.
    Let op: bij ~99,4 kW piek/aansluiting is de relevante deelmarkt
    waarschijnlijk niet meer "LS t/m 50kW" (eerder opgezocht) maar een
    hogere deelmarkt (MS/LS 50-136kW oid) -- opnieuw opzoeken.
    """
    # 1. Transporttarief: over het totale jaarvolume, kWh -- geen piek-relatie, deze word wel gebruikt in de optimalisatie
    transport_tariff_eur_per_kwh: float | None = None

    # 2. Gecontracteerd transportvermogen (GTV): vaste, gekozen grens (kW) deze word niet gebruikt in de optimalisatie
    #    en de vaste prijs die je daarvoor betaalt, ongeacht werkelijk gebruik
    contracted_capacity_kw: float | None = None
    contracted_capacity_tariff_eur_per_kw: float | None = None

    # 3. Boetetarief bij overschrijding van de gecontracteerde piek -- deze word wel gebruikt in de optimalisatie
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