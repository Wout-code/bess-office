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
    # De RBC-drempel wordt niet meer vast gekozen, maar in main.py gescand op
    # laagste jaarlijkse netto kosten (NET-4): range(min, max + 1, step).
    threshold_scan_min_kw: float = 50.0
    threshold_scan_max_kw: float = 99.0
    threshold_scan_step_kw: float = 2.0


@dataclass
class GridTariffConfig:
    """
    Netbeheerder-transportkosten -- BEWUST VEREENVOUDIGD, zie onder.

    Liander's werkelijke tariefstructuur voor grootverbruik (geverifieerd
    tegen "tarieven voor aansluiting en transport elektriciteit 2026",
    deelmarkt MS/LS > 50 t/m 136 kW, van toepassing op ~99,4 kW) bevat TWEE
    aparte capaciteitscomponenten:
      1. "kW contract" -- jaarlijks GTV-tarief over je gecontracteerde
         vermogen; overschrijding verhoogt je GTV automatisch voor het hele
         kalenderjaar (geen apart boetetarief).
      2. "kW max. mnd" -- een LOS tarief, elke maand opnieuw berekend over
         de hoogste gemeten piek die maand, onafhankelijk van je GTV.

    VEREENVOUDIGING (bewust, om het model nu werkend te krijgen): dit
    bestand modelleert alleen component 2 (de maandelijkse piek). Component
    1 (GTV/jaarlijkse overschrijding) wordt NIET meegenomen -- behandeld als
    een vaste, niet-dispatch-afhankelijke kost, voorlopig buiten scope.
    optimize.py minimaliseert dus alleen de som van de 12 maandpieken × het
    maandtarief, niet de volledige Liander-kostenstructuur.

    TODO, in volgorde:
    - De onderstaande getallen zijn SCHATTINGEN uit een AI-samenvatting van
      de Liander-PDF, NIET handmatig geverifieerd -- twee pogingen gaven
      onderling inconsistente cijfers voor dezelfde deelmarkt. Controleer
      zelf de exacte tabel in:
      https://www.liander.nl/-/media/files/tarieven/grootzakelijk/tarieven-2026/tarieven-voor-aansluiting-en-transport-elektriciteit-2026_2.pdf
    - Zodra geverifieerd: component 1 (GTV) alsnog toevoegen aan het model
      (zie de oudere versie van dit bestand / het overzicht-document voor
      hoe dat eruitzag: een peak_floor-constraint op een jaarlijkse piek).
    """
    # Component: transporttarief over het totale jaarvolume, kWh -- geen
    # piek-relatie. SCHATTING, niet geverifieerd: €0,0226/kWh (deelmarkt
    # MS/LS > 50 t/m 136 kW).
    transport_tariff_eur_per_kwh: float | None = 0.0226

    # Component: "kW max. mnd" -- tarief per kW van de hoogste gemeten
    # piek in een kalendermaand. Dit is het enige capaciteitstarief dat
    # optimize.py momenteel gebruikt. SCHATTING, niet geverifieerd:
    # €3,57/kW/maand (deelmarkt MS/LS > 50 t/m 136 kW).
    monthly_peak_tariff_eur_per_kw: float | None = 3.57

    # Energiebelasting (NET-5): vast tarief per geïmporteerde kWh, marginale
    # schijf 50.000-10 mln kWh, 2026, excl. btw. Alleen op import, geen
    # saldering bij grootverbruik. De hogere tarieven van de eerste
    # 50.000 kWh zijn een vaste kost en niet beslissingsrelevant.
    energy_tax_eur_per_kwh: float = 0.03735

    # Hypothetische dubbele energiebelasting op opslag (NET-6), per kWh die de
    # batterij in gaat (charge_kwh, dus ook PV-laden: bovengrens).
    # 0.0 = scenario A (basis); gelijk aan energy_tax_eur_per_kwh = scenario B.
    storage_charge_tax_eur_per_kwh: float = 0.0

    # Niet gebruikt in het huidige vereenvoudigde model -- bewaard voor
    # wanneer component 1 (GTV/jaarlijkse overschrijding) wordt toegevoegd.
    # SCHATTING, niet geverifieerd: €3,74/kW/maand voor het GTV-tarief.
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