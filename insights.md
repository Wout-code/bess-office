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

4. een groep die mogelijk naief is


5. Onderzoek van wang et al. (2011) onder een bepaalde c-rate is de dod niet meer de dominante schade veroozaker




## Degradatie lithuim-ion batterijen

"De degradatie van lithium-ion batterijen is sterk afhankelijk van de toepassingscontext. Waar EV-toepassingen door hoge C-rates en snelladen gedreven worden door mechanische slijtage en cyclusdiepte (DoD), opereren stationaire BESS-systemen (zoals de BOLT-241) in een mild C-rate regime ($\le 0.5\text{C}$). Uit literatuur (o.a. Wang et al., 2011) blijkt dat in dit regime kalenderveroudering en tijd dominanter zijn dan de dynamische cyclusstress."


## Waarom LP blijven in plaats van MILP

1. Oplostijd schaalt slecht (het grootste praktische probleem)

LP is polynomiaal oplosbaar (interior point/simplex, ~seconden voor jouw schaal). MILP is NP-hard — de solver moet een branch-and-bound boom doorzoeken. Bij een jaarsimulatie op 15-min resolutie (35.040 timesteps) met bijvoorbeeld een binary voor charge/discharge-exclusiviteit, ga je van "los het hele jaar in één keer op" naar mogelijk uren rekentijd, of je moet rolling-horizon/windowing toepassen. Bij MPC (wat je toch gaat doen in je MSc) is dit direct relevant: als je een MILP elke stap opnieuw moet oplossen binnen een control-interval, kan de oplostijd de haalbaarheid van real-time toepassing breken.

2. Geen garantie op globaal optimum binnen praktische tijd

Bij LP weet je: als de solver terugkomt met een oplossing, is die gegarandeerd globaal optimaal (convex probleem). Bij MILP moet je vaak een optimality gap accepteren (bv. solver stopt bij 1% gap na X minuten) omdat exact oplossen te lang duurt. Dat betekent je resultaten zijn technisch "goed genoeg" maar niet bewijsbaar optimaal, wat lastig is als je je model wilt claimen als transparant/reproduceerbaar — een kernpunt van je project.

3. Combinatorische explosie bij meerdere binaries

Eén binary (bv. charge/discharge exclusiviteit) is meestal nog te doen. Maar zodra je dat combineert met bv. min. aan/uit-tijd (BAT-4), start/stop-kosten, én misschien later meerdere batterijen of multi-market participatie, groeit de complexiteit niet lineair maar exponentieel in het aantal binaries × tijdstappen. Dit is precies waarom BAT-4 loslaten praktisch waarde had — niet alleen omdat het fysiek onnodig is, maar omdat het je oplosbaarheid drastisch zou verslechteren voor een fysiek irrelevant effect.

4. Gevoeliger voor numerieke issues en solver-keuze

MILP-solvers (bv. HiGHS, CBC, Gurobi, CPLEX) verschillen veel meer in performance en robuustheid dan LP-solvers. Je transparantie/reproduceerbaarheid-doel wordt lastiger: een open-source MILP-solver (HiGHS/CBC) kan significant trager of minder stabiel zijn dan een commerciële (Gurobi), en dat raakt je "open-source, transparant" ambitie direct — licentiekosten of prestatieverschil wordt een designkeuze die je moet verantwoorden.

5. Moeilijker te debuggen en analyseren

Bij LP kun je duality (shadow prices, reduced costs) gebruiken om te begrijpen waarom de oplossing is wat die is — heel waardevol voor een transparant model. Bij MILP verlies je een schone dual-interpretatie zodra binaries actief zijn; sensitivity-analyse wordt veel minder rechttoe-rechtaan.

