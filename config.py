from dataclasses import dataclass
from pathlib import Path

@dataclass
class BatteryConfig:
    capacity_kwh: float = 150.0      # Batterijcapaciteit in kWh
    max_power_kw: float = 50.0       # Maximaal (symmetrisch) vermogen in kW
    efficiency: float = 0.90         # Round-trip efficiëntie (90%)

#@dataclass
#class SimConfig:
    #timestep_hours: float = 0.25     # 15-minuten resolutie voor de kwartierpiek
    #peak_tariff: float = 5.0         # Capaciteitstarief: €5 per kW per maand

#@dataclass
#class ProjectConfig:
    # Groepeer de instellingen
    #battery: BatteryConfig = BatteryConfig()
    #sim: SimConfig = SimConfig()
    
    # Zoek automatisch het juiste pad naar je data-map
    # Vanaf src/bess_office/config.py gaat dit omhoog naar de root, dan naar /data
    #data_dir: Path = Path(__file__).parent.parent.parent / "data"

# Dit is de 'Single Source of Truth' variabele die we overal gaan inladen
#CONFIG = ProjectConfig()