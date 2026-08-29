**Wat er gebeurt:** peak shaving en zelfconsumptie zijn in `dispatch_sim.py`
geen onafhankelijke doelen — ze concurreren om dezelfde, gedeelde
hulpbron: batterij-SoC. Ontdekt doordat `peak_threshold_kw` aanpassen (een
parameter die alleen over peak shaving lijkt te gaan) de
zelfconsumptie-uitkomst liet verschuiven, zonder dat er iets aan de
PV/load-data veranderde.
 
**Het mechanisme, stap voor stap:**
- Lage `peak_threshold_kw` → batterij ontlaadt al bij kleine tekorten →
  SoC daalt vaker/dieper → meer `room_in_battery` vrij bij de
  eerstvolgende PV-overschot-periode → hogere zelfconsumptie
- Hoge `peak_threshold_kw` → batterij ontlaadt bijna nooit → SoC blijft
  hoog → geen ruimte vrij bij PV-overschot → lagere zelfconsumptie,
  zelfs bij identieke PV/load-situatie
**Waarom dit meer is dan een parameter-effect:** dit is een structurele
eigenschap van een regelgebaseerde aanpak met twee doelen op één gedeelde
resource, geen instelbare knop die je "goed" kan zetten. Elke
drempelkeuze is een **impliciete, verborgen afweging** tussen de twee
doelen — de regel kan dit nooit bewust, expliciet balanceren; hij doet
het toevallig, als bijeffect van een parameter die eigenlijk voor iets
anders bedoeld was.