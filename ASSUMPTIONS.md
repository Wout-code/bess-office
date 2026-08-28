# Aannames — bess-office

# V1 — alleen dispatch_sim.py (regelgebaseerd)

**Batterij**
- Symmetrisch laad-/ontlaadvermogen — zelfde vermogen beide richtingen
  (vereenvoudiging, niet fysiek correct — zie V2)
- Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- Geen degradatie over tijd — capaciteit/efficiëntie blijven constant
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

**PV**
- PVGIS gebruikt standaard (`usehorizon=True`, geen `userhorizon`) een
  terreinschaduw-model op basis van een hoogtekaart -- dat ziet natuurlijke
  verhogingen (heuvels), maar geen gebouwen. Staat je kantoorpand op een
  bedrijventerrein/binnenstedelijk met hogere buurpanden die vroeg/laat
  schaduw werpen, dan onderschat PVGIS die verliezen structureel, zonder
  waarschuwing in de output -- de PV-opbrengst is dan te hoog ingeschat.

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

**PV**
- PVGIS gebruikt standaard (`usehorizon=True`, geen `userhorizon`) een
  terreinschaduw-model op basis van een hoogtekaart -- dat ziet natuurlijke
  verhogingen (heuvels), maar geen gebouwen. Staat je kantoorpand op een
  bedrijventerrein/binnenstedelijk met hogere buurpanden die vroeg/laat
  schaduw werpen, dan onderschat PVGIS die verliezen structureel, zonder
  waarschuwing in de output -- de PV-opbrengst is dan te hoog ingeschat.

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


  ## PV- en batterijconfiguratie

Dit project modelleert een **fictief/representatief MKB-kantoorpand**, geen 
bestaand gebouw. Battery- en PV-parameters in `config.py` zijn daarom gekozen 
als realistische default voor een gemiddeld Nederlands bedrijfspand, niet 
gemeten of afgeleid van een specifieke locatie:

- `BatteryConfig`: 150 kWh / 50 kW (0.33C), 90% round-trip efficiency — 
  typische specificaties voor een commercieel Li-ion systeem op deze schaal.
- `PVConfig.tilt = 12°`, `mounting_place = "free"` — aanname van een plat 
  dak met opstelsysteem (luchtspleet), de gangbare montagevorm bij NL 
  bedrijfspanden, in plaats van de PVGIS-default (35°, building-integrated) 
  die eerder bij schuine daken of in-dak systemen past.
- Horizonschaduw van naastgelegen bebouwing wordt niet meegenomen; PVGIS 
  gebruikt alleen terreinschaduw, geen gebouwschaduw.

Het `data/processed/KO_KANTOOR_ONDERWIJS`-loadprofiel van Liander is wel 
reële meetdata; alleen de PV- en batterij-installatie eromheen is fictief.