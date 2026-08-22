# Aannames — bess-office

## V1 — regelgebaseerd (dispatch_sim.py)

**Batterij**
- Ontladen is verliesvrij, laadverlies zit alleen bij het laden
- Geen degradatie over tijd — capaciteit/efficiëntie blijven constant
- Geen minimale aan/uit-tijd — batterij schakelt elk uur vrij
- Symmetrisch laad-/ontlaadvermogen — zelfde vermogen beide richtingen
- Efficiëntie/capaciteit constant, ongeacht SoC, laadsnelheid of temperatuur
- Geen zelfontlading

**Markt/Net**
- Eén vaste, statische peak-drempel voor het hele jaar (niet per maand herberekend)
- Peak shaving reageert alleen op import, niet op exportpieken
- Onbeperkte teruglevering — geen exportlimiet/curtailment

**Tijd**
- Vaste tijdstap van 1 uur
- Geen vooruitkijken — puur reactief, elk uur op zichzelf
- Uur-resolutie: `load` wordt naar 1h geresampled, wat een kwartier-piek
  wegmiddelt — gerapporteerde pieken zijn vermoedelijk een onderschatting
  van de piek die de factuur bepaalt

**Architectuur**
- Geen kosten/prijzen in dispatch_sim zelf — puur een fysieke
  energiestroom-simulatie, financiële vertaling gebeurt elders
- Batterij kan structureel nooit vanaf het net laden — alleen vanaf
  PV-overschot

---

## Wat verandert er in V2

| Categorie | V1 | V2 |
|---|---|---|
| Batterij | Symmetrisch laad-/ontlaadvermogen | Asymmetrisch mogelijk |
| Batterij | — | Mutual exclusivity laden/ontladen aangenomen (niet geverifieerd bij negatieve prijzen) |
| Markt/Net | Vaste jaardrempel | Geoptimaliseerde drempel |
| Tijd | Uur-resolutie, geen vooruitkijken | Kwartier-resolutie, perfecte forecast |
| Architectuur | Geen kosten in model, geen grid-charging | Kosten in objective, grid-charging mogelijk |

---

## V2 — LP-geoptimaliseerd (optimize.py)

**Batterij**
- Asymmetrisch laad-/ontlaadvermogen mogelijk (i.p.v. symmetrisch)
- Aangenomen dat laden en ontladen nooit tegelijk gebeuren omdat de solver
  altijd de efficiëntste oplossing kiest — **nog niet gecontroleerd of dit
  ook klopt bij negatieve prijzen** (NL day-ahead gaat af en toe negatief).
  Check: `df[df["price"] < 0]` op je prijsdata.
- Degradatie, aan/uit-tijd, constante efficiëntie, zelfontlading: nog
  ongewijzigd t.o.v. V1

**Markt/Net**
- Peak-drempel wordt een geoptimaliseerde waarde i.p.v. een vaste jaardrempel
- Export-curtailment, alleen-import-peak-shaving: nog ongewijzigd t.o.v. V1

**Tijd**
- Kwartier-resolutie i.p.v. uur, sluit aan bij kwartier-prijzen
- Perfecte forecast — de solver ziet de hele horizon vooruit, dus
  "geen vooruitkijken" vervalt volledig

**Architectuur**
- Kosten zitten direct in de LP-objective, geen aparte financiële laag
- Grid-charging wordt mogelijk — batterij kan ook vanaf het net laden,
  niet alleen vanaf PV-overschot