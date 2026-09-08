## inzicht moet nog een titel krijgen
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

## DOD data muur
1. De pragmatische handelaren: Traden op het contract, niet de fysica
Heel veel energiemarkt-traders bouwen helemaal geen elektrochemisch model. Zij kijken puur naar de garantievoorwaarden. Als de fabrikant in het contract zet: "De garantie dekt maximaal 1.5 cycli per dag en maximaal 300.000 kWh doorstroom per jaar", dan zet de trader dat simpelweg als harde restrictie (een constraint) in de LP-solver. De "kosten" van een trade zijn in dat geval geen euro's per slijtage, maar de opportunity cost: "als ik nu een cyclus draai voor weinig geld, mag ik er morgen misschien één minder draaien als de prijzen torenhoog zijn."

2. De data-kopers: Software als TWAICE en ACCURE
De partijen die de batterij bezitten (asset owners/investeerders) weten dat garanties extreem conservatief zijn (fabrikanten dekken zich in). Om te weten wat de batterij echt aankan zonder direct kapot te gaan, nemen zij peperdure licenties bij TWAICE of ACCURE. Deze bedrijven verkopen de digital twins die precies doen wat jij zoekt: zij sturen via een API elke dag de actuele degradatiekosten naar de trading optimizer.

3. De Tech-Giganten: Eigen testlaboratoria
Grote spelers als Tesla (met Autobidder), Fluence, of energiereuzen (zoals RWE of Vattenfall) accepteren geen black-box van fabrikanten of externe software. Zij kopen zeecontainers vol batterijcellen, zetten die in hun eigen R&D-centra in klimaatkasten, en cyclen ze zelf maandenlang helemaal kapot op verschillende DoD's en temperaturen. Zij creëren de data zelf.