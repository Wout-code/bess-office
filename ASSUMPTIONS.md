# Aannames — bess-office

ID-schema: elke aanname heeft een uniek ID (`DATA-n`, `BAT-n`, `TIME-n`,
`NET-n`, `ARCH-n`), doorlopend genummerd ongeacht V1/V2. Als V2 een
V1-aanname corrigeert, krijgt de correctie een nieuw ID en verwijst
terug naar het oude (bv. "corrigeert BAT-1"). Zo blijft zichtbaar wat
vervangen is versus wat ongewijzigd overeind blijft. Code-comments
verwijzen naar deze ID's — bij wijziging hier, ook de bijbehorende
code-comment nalopen.

Vervangen/verouderde aannames staan niet meer in dit document — die
geschiedenis leeft in git (`git log -p ASSUMPTIONS.md`). Dit bestand
toont alleen wat nu geldt.

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
  Let op wat dit profiel wél is: Liander's eigen K&O-standaardprofiel,
  opgebouwd uit telemetrie van grootverbruikers en door Liander zelf
  gebruikt om nieuwe grootverbruik-klanten in te schatten (zie externe
  documentatie MOOI EIGEN SBI-profielen). De profielvorm bepaalt dus
  niets over klein- of grootverbruik van het gemodelleerde pand — dat is
  puur een functie van de schaal (area_m2/annual_kwh_per_m2, zie DATA-8),
  niet van dit bestand.

**DATA-7 — Load-profiel afvlakking (Gelijktijdigheid)**
- Omdat het Liander K&O-profiel een wiskundig gemiddelde is van honderden
  panden, is de curve afgevlakt (gelijktijdigheidsfactor). De pieken van
  een echt pand zijn hoger, dus de waarde van piekverlaging wordt in dit
  model waarschijnlijk onderschat. Die echte pieken zijn wel kort en
  grillig, en daardoor in de praktijk lastiger te voorspellen en weg te
  werken dan hier met een perfecte voorspelling (TIME-2).

**DATA-8 — Referentiepand, grootverbruik-schaal**
- 4.500 m² i.p.v. 590 m², annual_kwh_per_m2 ongewijzigd (115 kWh/m²/jaar,
  NL-gemiddelde, verandert niet met schaal). Bewust gekozen zodat de
  berekende piek ruim boven de grootverbruik-grens (55 kVA / 3x80A)
  uitkomt, i.p.v. er net tegenaan te zitten. Berekening:
  som(relative_profile) op KO_KANTOOR_ONDERWIJS, geverifieerd via
  `get_relative_profile().sum()`: 20.824,42. 4.500 x 115 = 517.500
  kWh/jaar -> peak_kwh_per_quarter = 517.500 / 20.824,42 = 24,85
  kWh/kwartier -> piek = 99,4 kW (geverifieerd via notebook-run).
  peak_kwh_per_quarter is geen los BuildingConfig-veld meer, maar wordt
  afgeleid in main.py via derive_peak_kwh_per_quarter() (fetch_load.py)
  — voorkomt dat area_m2 en peak_kwh_per_quarter stilzwijgend uit elkaar
  lopen.

**DATA-9 — Batterijmodel, BOLT-241**
- Boltainer BOLT-241 (NL fabrikant): 241 kWh capaciteit, vermogensopties
  49/60/99/120 kW. 99 kW gekozen o.b.v. de berekende piek (99,4 kW,
  DATA-8) — zelfde "vermogen ≈ piek"-logica als bij de oorspronkelijke
  SigenStor-keuze. Capaciteit gecontroleerd tegen dezelfde
  capaciteit-t.o.v.-dagverbruik-ratio als eerder (~19%): nieuw
  daggemiddelde 517.500/365 ≈ 1.418 kWh/dag, 19% daarvan ≈ 270 kWh — 241
  kWh ligt iets onder die ratio (iets vaker/dieper cyclen dan bij de oude
  verhouding).
  LET OP: gevonden via één zoekopdracht, niet grondig geverifieerd op
  prijs/beschikbaarheid/leveringstermijn. Bruikbare capaciteit (na
  min/max SoC) en round-trip efficiency van dit specifieke product zijn
  niet apart opgezocht — BatteryConfig gebruikt hiervoor nog de oude,
  generieke SigenStor-aannames (90%/10%/95%) als placeholder. TODO:
  verifiëren.

**DATA-10 — PV-dimensionering, exportbewust**
- 190 kWp i.p.v. 25 kWp, zelfde onderliggende verhouding als het
  oorspronkelijke (niet-gedocumenteerde) "jaarverbruik-vuistregel"-
  commentaar bij PVConfig: 25 kWp / 67.850 kWh (oud jaarverbruik) ≈ 0,368
  kWp per MWh/jaar, toegepast op het nieuwe jaarverbruik (517.500 kWh) ->
  ~190,6 kWp.
  Bewuste keuze tussen twee strategieën: (a) exportbewust, ~33%
  jaardekking (190 kWp, gekozen) vs. (b) volledige jaarverbruik-dekking
  (~673 kWp, gangbare residentiële vuistregel: 1,3 kWp per 1.000 kWh
  jaarverbruik). Voor (b) is ~2.605 m² dakoppervlak nodig (1.447 panelen
  à 465 Wp x 1,8 m²/paneel), voor (a) ~736 m² — laatstgenoemde past
  comfortabel binnen een 4.500 m² pand, eerstgenoemde is aan de krappe
  kant.
  Reden voor (a): bij grootverbruik is export structureel lager
  gewaardeerd dan zelfconsumptie (zie ARCH-5) — een installatie die
  vooral op export mikt, benut een groot deel van zijn kWp op het minst
  waardevolle deel van de opbrengst.
  LET OP: dit is een verhouding-behoudende extrapolatie van een
  oorspronkelijk niet-onderbouwd getal (geen notebook/berekening
  teruggevonden voor de originele 25 kWp), geen onafhankelijk
  geverifieerde vuistregel. TODO indien tijd: eigen onderbouwing (bv.
  dakoppervlak-beschikbaarheid) i.p.v. verhouding-behoud.

---

## V1 — alleen dispatch_sim.py (regelgebaseerd)

**Batterij**
- **BAT-1** — Symmetrisch laad-/ontlaadvermogen — zelfde vermogen beide
  richtingen (vereenvoudiging, niet fysiek correct — gecorrigeerd in V2,
  zie BAT-7)
- **BAT-2** — Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- **BAT-3** — Geen degradatie over tijd — capaciteit/efficiëntie blijven
  constant.
  Degradatie zit daarom ook bewust **niet** in de LP-objective (geen
  cycluskost). Onderbouwing: gemeten equivalente volle cycli/jaar
  (`main.py`, 2023-data) zijn RBC 102, LP scenario A 487 (1,33/dag), LP
  scenario B 264. Dat staat tegenover ≥ 6000 cycli voor de BOLT-241 (opgave,
  niet geverifieerd, zie DATA-9): zelfs bij 487/jaar ~12 jaar. Bij lage
  C-rates bepalen vooral tijd, temperatuur en doorgezette lading de
  veroudering, en nauwelijks de cyclusdiepte (DoD) (Wang et al., 2011);
  hun tests begonnen bij C/2, dit systeem draait op 99 kW / 241 kWh ≈ 0,41C.
  Een DoD-afhankelijke kost is daarom niet nodig; een kost per doorgezette
  kWh wel, maar die is niet geïmplementeerd.
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
- **ARCH-5 — Symmetrische import-/exportprijzen** — `compute_financial_metrics`
  waardeert import en export tegen dezelfde day-ahead-prijs. In
  werkelijkheid mist export het vermeden-transporttarief dat
  zelfconsumptie wél bespaart, en wordt teruglevering bij grootverbruik
  doorgaans lager vergoed dan de volledige importprijs
  (marktprijs-gekoppeld leverancierscontract — bij grootverbruik is er
  geen saldering, dus geen vaste 1-op-1-verrekening om op terug te
  vallen). Richting van de fout: dit overwaardeert export, en dus een
  grotere PV-installatie t.o.v. een kleinere (zie DATA-10). Kwantitatieve
  correctie vereist een reëel terugleverings-contract-getal dat nu niet
  beschikbaar is — TODO. Blijft ongewijzigd van kracht voor V2:
  `optimize.py` gebruikt `main.py`'s `compute_financial_metrics` niet
  zelf, maar de financiële nabewerking in `main.py` is identiek voor
  beide dispatch-versies.

---

# V2 — dispatch_sim.py + optimize.py

`dispatch_sim.py` verdwijnt niet in V2 — het blijft bestaan naast
`optimize.py`, en krijgt de fixes die geen kwestie van algoritme zijn maar
van correcte fysica of betere parameters.

## Gedeeld tussen beide bestanden in V2

**Batterij**
- **BAT-7** — Asymmetrisch laad-/ontlaadvermogen — corrigeert BAT-1.
  **Gepland, nog niet geïmplementeerd**: beide bestanden gebruiken nog
  `power_kw` voor laden én ontladen, BAT-1 is dus feitelijk nog van kracht.
- BAT-2 t/m BAT-6 blijven ongewijzigd van kracht

**Markt/Net**
- **NET-4** — Geoptimaliseerde peak-drempel i.p.v. vaste jaardrempel —
  corrigeert NET-1. In `optimize.py` intern: één piekvariabele per
  kalendermaand. In `dispatch_sim.py` blijft het één drempel voor het hele
  jaar, maar die wordt niet meer met de hand gekozen: `main.py`
  (`select_rbc_threshold`) scant 50–98 kW in stappen van 2 kW
  (`DispatchConfig.threshold_scan_*`) en kiest de drempel met de laagste
  jaarlijkse netto kosten (2023: 52 kW). Prijzen komen alleen in die scan
  voor, de regel zelf blijft prijsloos en reactief (ARCH-1, TIME-1). Let
  op: dit is een ex-post keuze op hetzelfde jaar (in-sample), dus gunstig
  voor de RBC.
- **NET-5** — Energiebelasting als vast tarief per geïmporteerde kWh
  (`GridTariffConfig.energy_tax_eur_per_kwh = 0,03735`): de marginale schijf
  50.000–10 mln kWh, 2026-tarief excl. btw, toegepast op 2023-prijzen.
  Alleen op import, geen saldering (grootverbruik). Zit zowel in de
  LP-objective als in `compute_financial_metrics`. De hogere tarieven van de
  eerste 50.000 kWh zijn niet gemodelleerd: dat is een vaste kost, niet
  beslissingsrelevant.
- **NET-6** — Scenario B: hypothetische dubbele energiebelasting op opslag,
  nog eens 0,03735 EUR per kWh die de batterij in gaat
  (`storage_charge_tax_eur_per_kwh`, default 0,0 = scenario A). Gebaseerd op
  de discussie over dubbele energiebelasting bij opslag, die in
  werkelijkheid vooral speelt achter kleinverbruikersaansluitingen. Het is
  een bovengrens, want ook PV-laden (alle `charge_kwh`) wordt belast. De
  LP wordt voor B opnieuw opgelost; de RBC-dispatch is prijsloos en blijft
  gelijk, alleen zijn kosten worden herberekend.
- Zie ARCH-5 (bij V1 — Architectuur) voor export/import symmetrisch
  geprijsd — geldt identiek voor V2, geen apart NET-ID nodig.
- NET-2, NET-3 blijven ongewijzigd van kracht

**Architectuur**
- **ARCH-3** — Grid-charging wordt mogelijk — corrigeert ARCH-2.
  Geïmplementeerd in beide bestanden. `optimize.py`: vrij, de solver
  beslist. `dispatch_sim.py`: standaard peak-shaving-regel — zolang de
  import (kW) onder de drempel blijft, laden vanaf het net met hooguit de
  resterende ruimte tot de drempel, begrensd door `power_kw` (minus wat al
  van PV geladen wordt) en max SoC, met hetzelfde laadverlies als PV-laden
  (BAT-2). Bijeffect: de RBC-zelfconsumptie daalt (2023, drempel 52 kW: 83,1%
  zonder vs. 78,6% met grid-charging; zonder batterij 78,3%), omdat de
  batterij vaker vol is als er PV-overschot komt: peak shaving en
  zelfconsumptie concurreren om dezelfde SoC, en de drempel maakt die
  afweging impliciet. Ook de netto kosten van de RBC zijn bij dezelfde drempel iets
  hoger met grid-charging (€63.558 vs. €63.300).

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
  omdat de solver altijd de efficiëntste oplossing kiest. **Gecontroleerd
  (2023-data): klopt niet bij negatieve prijzen.** Scenario A: 399 van de
  35.032 kwartieren met gelijktijdig laden en ontladen, allemaal bij een
  negatieve prijs (1.256 kwartieren < 0). Daarbij gaat 546 kWh aan
  laadverlies verloren; zelfs gewaardeerd tegen de laagste prijs
  (−500 EUR/MWh) is dat hooguit ~€270/jaar, ~3% van de LP-besparing.
  Scenario B: 16 kwartieren, ook allemaal bij een negatieve prijs. Bewust
  niet opgelost met binaries: het model blijft een LP, omdat een MILP over
  35.040 kwartieren veel trager oplost en geen gegarandeerd globaal optimum
  binnen praktische tijd geeft. Het effect is financieel klein en zichtbaar
  gerapporteerd.
- **BAT-9** — Eind-SoC ≥ begin-SoC (`initial_soc_fraction`) aan het eind
  van de horizon. Zonder deze voorwaarde trekt de LP de batterij aan het
  eind gratis leeg en telt die energie als besparing. De RBC heeft deze
  voorwaarde niet (2023: eindigt op 208,8 kWh vs. 120,5 kWh begin, een
  klein nadeel voor de RBC).

## Belangrijke context, geen aanname

*Context, geen aanname*: bij 99 kW blijft dit systeem onder de 100 kW-
drempel waarboven een congestiemanagementcontract relevant wordt
(RVO Flex-e-voorwaarden: vermogen van de maatregel, niet de
aansluiting, is bepalend). Feitelijk gegeven, geen keuze — vermeld
omdat het de 99 kW-keuze in een breder regulatoir kader plaatst.