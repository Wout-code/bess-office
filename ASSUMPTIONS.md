# Aannames — bess-office

## Data & referentiecasus (geldt voor V1 én V2 — gaat over de invoer, niet de berekening)

Dit zijn geen aannames over hoe er gerekend wordt (dat staat bij V1/V2
hieronder) — dit gaat over wat de data zelf voorstelt en waar de
beperkingen daarin zitten. Identiek van toepassing ongeacht welk
rekenmodel je gebruikt.

**Tijdzone**
- Alle drie databronnen (load, PV, prijzen) worden expliciet omgezet naar
  Europe/Amsterdam, niet UTC. Reden: het capaciteitstarief en
  dispatch-beslissingen zijn gebonden aan lokale kloktijd (bv.
  "avondpiek om 18:00"), niet aan UTC. Prijs die daarvoor betaald wordt:
  de klokwissels in maart/oktober moeten expliciet afgehandeld worden
  (zie Load-data/PV-data hieronder) — UTC had die complexiteit vermeden,
  maar zou resultaten minder direct herkenbaar maken t.o.v. de
  werkelijke lokale gebruikssituatie.

**Referentiepand**
- Representatief, geen echt gemeten pand — 590 m² en NL-gemiddelde
  verbruiksintensiteit (115 kWh/m²/jaar). Zie `config.py` voor bronnen.

**Batterijmodel**
- Sigenergy SigenStor gekozen: 36,16 kWh (35,04 kWh bruikbaar), ~20 kW
  3-fase omvormer (EC20K). Geen willekeurige keuze — het berekende
  piekvermogen van het referentiepand (13 kW) en de
  capaciteit-t.o.v.-dagverbruik-verhouding (~19%) wezen beide naar deze
  schaal, in plaats van de grotere Deye GE-F60-lijn (60 kWh/100 kW) die
  specifiek voor zwaardere kantoorpanden wordt gemarket. Zie `config.py`
  voor het productblad. Zie jupyter notebook 0.2

**PV-data (PVGIS)**
- PVGIS gebruikt standaard (`usehorizon=True`, geen `userhorizon`) een
  terreinschaduw-model op basis van een hoogtekaart — dat ziet natuurlijke
  verhogingen (heuvels), maar geen gebouwen. Staat het referentiepand op
  een bedrijventerrein/binnenstedelijk met hogere buurpanden die
  vroeg/laat schaduw werpen, dan onderschat PVGIS die verliezen
  structureel, zonder waarschuwing in de output — de PV-opbrengst is dan
  te hoog ingeschat.

**Load-data (Liander K&O-profiel)**
- Genormaliseerd profiel, geen echte meting — daardoor ook geen echte
  klokwissel-onregelmatigheid (365×96 kwartieren, geen gaps). Bij
  tz-aware maken is daarom een bewuste, pragmatische keuze nodig
  (`nonexistent="shift_forward"`, `ambiguous=True`) in plaats van een
  echte DST-correctie zoals bij prijzen/PV, die wél op echte metingen
  draaien.

- `nonexistent="shift_forward"` botst op deze dag met al bestaande rijen
  (uniform 96/dag betekent dat 03:00-03:45 al bezet is) — 4 van de 35.040
  kwartieren (~0,01%) worden daarom gededupliceerd, niet apart gemodelleerd.
  Verwaarloosbaar voor jaartotalen, wel de reden dat het jaartotaal-getal
  nooit exact op 35.040 rijen zal uitkomen.
---

## V1 — alleen dispatch_sim.py (regelgebaseerd)

**Batterij**
- Symmetrisch laad-/ontlaadvermogen — zelfde vermogen beide richtingen
  (vereenvoudiging, niet fysiek correct — zie V2)
- Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- Geen degradatie over tijd — capaciteit/efficiëntie blijven constant
  (Sigenergy-garantie: 70% na 10 jaar/3.048 cycli, relevant zodra dit naar
  een meerjarige projectie gaat)
- Geen minimale aan/uit-tijd — batterij schakelt vrij
- Efficiëntie/capaciteit constant, ongeacht SoC, laadsnelheid of temperatuur
- Geen zelfontlading

**Tijd**
- Vaste tijdstap van 1 uur; `load` naar 1h geresampled, wat een
  kwartier-piek wegmiddelt — gerapporteerde pieken zijn vermoedelijk een
  onderschatting van de piek die de factuur bepaalt
- Geen vooruitkijken — puur reactief, elk uur op zichzelf

**Markt/Net**
- Eén vaste, statische peak-drempel voor het hele jaar
- Peak shaving reageert alleen op import, niet op exportpieken
- Onbeperkte teruglevering — geen exportlimiet/curtailment

**Architectuur**
- Geen kosten/prijzen in het model zelf — puur een fysieke
  energiestroom-simulatie, financiële vertaling gebeurt elders
- Batterij kan structureel nooit vanaf het net laden — alleen vanaf
  PV-overschot

---

# V2 — dispatch_sim.py + optimize.py

`dispatch_sim.py` verdwijnt niet in V2 — het blijft bestaan naast
`optimize.py`, en krijgt de fixes die geen kwestie van algoritme zijn maar
van correcte fysica of betere parameters.

## Gedeeld tussen beide bestanden in V2

**Batterij**
- Asymmetrisch laad-/ontlaadvermogen — gecorrigeerd fysiek feit, geen
  V1-vereenvoudiging meer, dus geldt voor beide bestanden
- Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- Geen degradatie over tijd — capaciteit/efficiëntie blijven constant
  (Sigenergy-garantie: 70% na 10 jaar/3.048 cycli, relevant zodra dit naar
  een meerjarige projectie gaat)
- Geen minimale aan/uit-tijd — batterij schakelt vrij
- Efficiëntie/capaciteit constant, ongeacht SoC, laadsnelheid of temperatuur
- Geen zelfontlading

**Tijd**
- Kwartier-resolutie i.p.v. uur

**Markt/Net**
- Geoptimaliseerde peak-drempel i.p.v. vaste jaardrempel — in
  `optimize.py` intern berekend; in `dispatch_sim.py` als vooraf
  berekende parameter ingevoerd, de regel zelf blijft reactief

**Architectuur**
- Grid-charging wordt mogelijk

## dispatch_sim.py specifiek (blijft regelgebaseerd)

**Tijd**
- Nog steeds geen vooruitkijken — inherent aan een reactieve regel, niet
  iets wat "gefixed" wordt

**Architectuur**
- Nog steeds geen kosten in het model zelf — architecturale keuze,
  financiële vertaling gebeurt elders, blijft zo

## optimize.py

**Tijd**
- Perfecte forecast binnen de horizon — "geen vooruitkijken" vervalt

**Architectuur**
- Kosten zitten direct in de objective, geen aparte financiële laag

**Batterij**
- Aangenomen dat laden en ontladen nooit tegelijk gebeuren omdat de
  solver altijd de efficiëntste oplossing kiest — **nog niet
  gecontroleerd of dit ook klopt bij negatieve prijzen** (NL day-ahead
  gaat af en toe negatief). Check: `df[df["price"] < 0]` op je prijsdata.