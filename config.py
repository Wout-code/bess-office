from dataclasses import dataclass
from pathlib import Path

@dataclass
class BatteryConfig:
    capacity_kwh: float = 150.0
    power_kw: float = 50.0
    round_trip_efficiency: float = 0.90
    min_soc_fraction: float = 0.10
    max_soc_fraction: float = 0.95
    initial_soc_fraction: float = 0.50

@dataclass
class PVConfig:
    latitude: float = 52.01
    longitude: float = 4.36
    peak_power_kw: float = 50.0
    tilt: float = 35.0
    azimuth: float = 180.0
    mounting_place: str = "building"
    year: int = 2023
    save_raw: bool = True

@dataclass
class BuildingConfig:
    peak_kwh_per_quarter: float = 15.0 # Schaal van het kantoorverbruik

@dataclass
class SimConfig:
    timestep_hours: float = 0.25     # 15-minuten voor capaciteitstarief!
    peak_threshold_kw: float = 20.0  #only relevant for dispatch
    #peak_tariff: float = 5.0     Hier moet je nog naar kijken want dit is te versimpeld.

@dataclass
class ProjectConfig:
    battery: BatteryConfig = BatteryConfig()
    pv: PVConfig = PVConfig()
    building: BuildingConfig = BuildingConfig()
    sim: SimConfig = SimConfig()
    
    data_dir: Path = Path(__file__).parent.parent.parent / "data"

CONFIG = ProjectConfig()