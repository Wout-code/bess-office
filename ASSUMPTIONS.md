# Aannames — bess-office

ID-schema: elke aanname heeft een uniek ID (`DATA-n`, `BAT-n`, `TIME-n`,
`NET-n`, `ARCH-n`), doorlopend genummerd ongeacht V1/V2. Als V2 een
V1-aanname corrigeert, krijgt de correctie een nieuw ID en verwijst
terug naar het oude (bv. "corrigeert BAT-1"). Zo blijft zichtbaar wat
vervangen is versus wat ongewijzigd overeind blijft. Code-comments
verwijzen naar deze ID's — bij wijziging hier, ook de bijbehorende
code-comment nalopen.

## Data & referentiecasus (geldt voor V1 én V2 — gaat over de invoer, niet de berekening)

Dit zijn geen aannames over hoe er gerekend wordt (dat staat bij V1/V2
hieronder) — dit gaat over wat de data zelf voorstelt en waar de
beperkingen daarin zitten. Identiek van toepassing ongeacht welk
rekenmodel je gebruikt.

**DATA-1 — Tijdzone**
- Alle drie databronnen (load, PV, prijzen) worden expliciet omgezet naar
  Europe/Amsterdam, niet UTC. Reden: het capaciteitstarief en
  dispatch-beslissingen zijn gebonden aan lokale kloktijd (bv.
  "avondpiek om 18:00"), niet aan UTC. Prijs die daarvoor betaald wordt:
  de klokwissels in maart/oktober moeten expliciet afgehandeld worden
  (zie DATA-5/DATA-6 hieronder) — UTC had die complexiteit vermeden,
  maar zou resultaten minder direct herkenbaar maken t.o.v. de
  werkelijke lokale gebruikssituatie.

**DATA-2 — Resolutie**
- Kwartier, voor beide bestanden identiek — geen V1/V2-verschil. Dit was
  altijd een `main.py`-keuze (welke data je aanlevert), nooit iets in
  `dispatch_sim.py`/`optimize.py` zelf: beide nemen gewoon
  `timestep_hours` als parameter en rekenen met wat ze krijgen. `main.py`
  upsamplet PV naar kwartier (i.p.v. load downsamplen naar uur), zodat de
  factuurbepalende kwartier-piek niet wegmiddelt.

**DATA-3 — Referentiepand**
- Representatief, geen echt gemeten pand — 590 m² en NL-gemiddelde
  verbruiksintensiteit (115 kWh/m²/jaar). Zie `config.py` voor bronnen.

**DATA-4 — Batterijmodel (productkeuze)**
- Sigenergy SigenStor gekozen: 36,16 kWh (35,04 kWh bruikbaar), ~20 kW
  3-fase omvormer (EC20K). Geen willekeurige keuze — het berekende
  piekvermogen van het referentiepand (13 kW) en de
  capaciteit-t.o.v.-dagverbruik-verhouding (~19%) wezen beide naar deze
  schaal, in plaats van de grotere Deye GE-F60-lijn (60 kWh/100 kW) die
  specifiek voor zwaardere kantoorpanden wordt gemarket. Zie `config.py`
  voor het productblad.

**DATA-5 — PV-data (PVGIS)**
- PVGIS gebruikt standaard (`usehorizon=True`, geen `userhorizon`) een
  terreinschaduw-model op basis van een hoogtekaart — dat ziet natuurlijke
  verhogingen (heuvels), maar geen gebouwen. Staat het referentiepand op
  een bedrijventerrein/binnenstedelijk met hogere buurpanden die
  vroeg/laat schaduw werpen, dan onderschat PVGIS die verliezen
  structureel, zonder waarschuwing in de output — de PV-opbrengst is dan
  te hoog ingeschat.

**DATA-6 — Load-data (Liander K&O-profiel)**
- Genormaliseerd profiel, geen echte meting — daardoor ook geen echte
  klokwissel-onregelmatigheid (365×96 kwartieren, geen gaps). Bij
  tz-aware maken is daarom een bewuste, pragmatische keuze nodig
  (`nonexistent="shift_forward"`, `ambiguous=True`) in plaats van een
  echte DST-correctie zoals bij prijzen/PV, die wél op echte metingen
  draaien.

**DATA-7 — Load-profiel afvlakking (Gelijktijdigheid)**

- Omdat het Liander K&O-profiel een wiskundig gemiddelde is van honderden panden, is de curve afgevlakt (gelijktijdigheidsfactor). De vlijmscherpe, kortstondige vermogenspieken en de diepe nul-verbruik dalen van een individueel fysiek gebouw ontbreken. Voor het LP-optimalisatiemodel betekent dit dat peak shaving waarschijnlijk efficiënter en goedkoper wordt ingeschat dan in werkelijkheid: een brede, lagere piek is voor de batterij eenvoudiger weg te werken dan een grillige naaldpiek. Het berekende financiële rendement voor de geoptimaliseerde piek-drempel is hierdoor een robuuste benadering, maar valt in de fysieke realiteit mogelijk iets conservatiever uit.

**ARCH-5 - Symmetrische import-/exportprijzen**
- `compute_financial_metrics` waardeert import en export tegen dezelfde
day-ahead-prijs. In werkelijkheid mist export het vermeden-transporttarief
dat zelfconsumptie wél bespaart, en wordt teruglevering bij grootverbruik
doorgaans lager vergoed dan de volledige importprijs (marktprijs-gekoppeld
leverancierscontract -- bij grootverbruik is er geen saldering, dus geen
vaste 1-op-1-verrekening om op terug te vallen). Richting van de fout:
dit overwaardeert export, en dus een grotere PV-installatie t.o.v. een
kleinere. Kwantitatieve correctie vereist een reëel terugleverings-
contract-getal dat nu niet beschikbaar is -- TODO.

---

## V1 — alleen dispatch_sim.py (regelgebaseerd)

**Batterij**
- **BAT-1** — Symmetrisch laad-/ontlaadvermogen — zelfde vermogen beide
  richtingen (vereenvoudiging, niet fysiek correct — gecorrigeerd in V2,
  zie BAT-7)
- **BAT-2** — Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- **BAT-3** — Geen degradatie over tijd — capaciteit/efficiëntie blijven
  constant (Sigenergy-garantie: 70% na 10 jaar/3.048 cycli, relevant
  zodra dit naar een meerjarige projectie gaat)
- **BAT-4** — Geen minimale aan/uit-tijd — batterij schakelt vrij
- **BAT-5** — Efficiëntie/capaciteit constant, ongeacht SoC, laadsnelheid
  of temperatuur
- **BAT-6** — Geen zelfontlading

**Tijd**
- **TIME-1** — Geen vooruitkijken — puur reactief, elk kwartier op zichzelf

**Markt/Net**
- **NET-1** — Eén vaste, statische peak-drempel voor het hele jaar
  (gecorrigeerd in V2, zie NET-4)
- **NET-2** — Peak shaving reageert alleen op import, niet op exportpieken
- **NET-3** — Onbeperkte teruglevering — geen exportlimiet/curtailment

**Architectuur**
- **ARCH-1** — Geen kosten/prijzen in het model zelf — puur een fysieke
  energiestroom-simulatie, financiële vertaling gebeurt elders
- **ARCH-2** — Batterij kan structureel nooit vanaf het net laden — alleen
  vanaf PV-overschot (gecorrigeerd in V2, zie ARCH-3)

---

# V2 — dispatch_sim.py + optimize.py

`dispatch_sim.py` verdwijnt niet in V2 — het blijft bestaan naast
`optimize.py`, en krijgt de fixes die geen kwestie van algoritme zijn maar
van correcte fysica of betere parameters.

## Gedeeld tussen beide bestanden in V2

**Batterij**
- **BAT-7** — Asymmetrisch laad-/ontlaadvermogen — corrigeert BAT-1;
  fysiek feit, geen V1-vereenvoudiging meer, dus geldt voor beide bestanden
- BAT-2 t/m BAT-6 blijven ongewijzigd van kracht

**Markt/Net**
- **NET-4** — Geoptimaliseerde peak-drempel i.p.v. vaste jaardrempel —
  corrigeert NET-1; in `optimize.py` intern berekend, in
  `dispatch_sim.py` als vooraf berekende parameter ingevoerd, de regel
  zelf blijft reactief
- **NET-5** Export prijzen zijn gelijk aan de importprijzen
- NET-2, NET-3 blijven ongewijzigd van kracht


**Architectuur**
- **ARCH-3** — Grid-charging wordt mogelijk — corrigeert ARCH-2

## dispatch_sim.py specifiek (blijft regelgebaseerd)

**Tijd**
- TIME-1 blijft ongewijzigd van kracht — nog steeds geen vooruitkijken,
  inherent aan een reactieve regel, niet iets wat "gefixed" wordt

**Architectuur**
- ARCH-1 blijft ongewijzigd van kracht voor dit bestand — nog steeds geen
  kosten in het model zelf, financiële vertaling gebeurt elders

## optimize.py

**Tijd**
- **TIME-2** — Perfecte forecast binnen de horizon — vervangt TIME-1
  voor dit bestand ("geen vooruitkijken" vervalt)

**Architectuur**
- **ARCH-4** — Kosten zitten direct in de objective, geen aparte
  financiële laag — vervangt ARCH-1 voor dit bestand

**Batterij**
- **BAT-8** — Aangenomen dat laden en ontladen nooit tegelijk gebeuren
  omdat de solver altijd de efficiëntste oplossing kiest — **nog niet
  gecontroleerd of dit ook klopt bij negatieve prijzen** (NL day-ahead
  gaat af en toe negatief). Check: `df[df["price"] < 0]` op je prijsdata.