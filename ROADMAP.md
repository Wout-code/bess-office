# BESS-Office — Project Roadmap

## De twee assen van dit project

Een volledig BESS-softwaresysteem bestaat uit drie lagen:

**Forecast → Optimalisatie → Control**

- **Forecast**: voorspel toekomstige PV-opwek, verbruik, prijzen
- **Optimalisatie**: bepaal, gegeven (aannames over) de toekomst, het beste laad/ontlaad-schema
- **Control**: voer dat schema uit op een echt systeem, corrigeer bij afwijkingen (MPC-achtig)

Los daarvan is er een tweede as: **welke waardebronnen** worden meegenomen in de optimalisatie zelf:

- Peak shaving (capaciteitstarief vermijden)
- Zelfconsumptie (na afschaffing salderen, 2027 — **check eerst of het referentiepand
  kleinverbruiker is, max. 3x80A; bij grootverbruiker gold saldering al nooit en
  vervalt het "vóór/ná 2027"-scenario**)
- Prijsarbitrage (day-ahead)
- Passieve onbalansmarkt (geen minimumschaal-eis, loopt via BRP-rol — mogelijk wél
  haalbaar voor een los pand, nog niet uitgewerkt)
- Actieve onbalans / FCR / aFRR-mFRR (vereist aggregator-toegang + TenneT-prekwalificatie
  + 1-20 MW minimumschaal — structureel buiten scope voor een los MKB-pand)

---

## Fase 1 — Baseline vs. optimalisatie, single value stream (bijna af)

**Wat:** deterministische LP-optimalisatie voor peak shaving alleen, vergeleken
tegen een regelgebaseerde baseline, met échte data (PVGIS, ENTSO-E, Liander
K&O-profiel) voor een MKB-kantoorpand.

**Status:** data-pipeline (fetch_pv, fetch_load, fetch_prices) en
regelgebaseerde dispatch-simulatie staan. LP-optimalisatie (optimize.py) is
de eerstvolgende stap.

**Belangrijke kanttekening, ontdekt tijdens het bouwen:** voor peak shaving
alleen is de verwachte meerwaarde van LP boven een goede drempel-regel
waarschijnlijk beperkt — het capaciteitstarief is een min-max-probleem, en
een simpele drempel ligt daar al dicht bij het optimum. Dit is zelf een
waardevolle, kwantitatieve bevinding om te rapporteren, niet een reden om
deze fase over te slaan.

**Deliverable:** een kwantitatieve vergelijking (% piekreductie, baseline vs.
LP) die aantoont waar optimalisatie wel/niet meerwaarde heeft.

---

## Fase 2 — Multi-objective optimalisatie (peak shaving + arbitrage)

**Wat:** uitbreiden van de doelfunctie in optimize.py naar een gewogen
combinatie van piekvermogenkosten én energiekosten (day-ahead-prijzen).

**Waarom dit de fase is waar LP zijn meerwaarde het duidelijkst toont:**
een regelgebaseerde aanpak kan niet afwegen "ontladen voor de piek nu, of
bewaren voor een duurder uur later" — dat vereist vooruitkijken over de hele
periode tegelijk, precies wat een LP wél kan en een simpele regel niet.

**Optioneel binnen deze fase:**
- Zelfconsumptie als derde term, met scenario "vóór 2027" vs. "ná 2027" —
  **mits het referentiepand kleinverbruiker is** (zie boven)
- Passieve onbalansmarkt als vierde waardebron — geen minimumschaal-eis,
  BRP-rol i.p.v. aggregator; nog te beoordelen of dat haalbaar is

**Deliverable:** een Pareto-achtige vergelijking — hoeveel piekreductie
"kost" je aan gemiste arbitragewinst, en omgekeerd, bij verschillende
gewichten in de doelfunctie.

---

## Fase 3 — Forecast + control samen: één MPC-raamwerk, geen twee losse stappen

Forecasting en control zijn hier bewust **niet** als twee opeenvolgende
fasen opgesplitst. Vakliteratuur beschrijft dit consistent als één
geïntegreerd raamwerk: forecasting is een ingebouwd onderdeel van hoe MPC
werkt, niet een losse bouwsteen die je er later overheen legt.

**Huidige beperking van fase 1-2, expliciet benoemen:** optimize.py
optimaliseert met volledige, achteraf bekende jaardata — een theoretisch
plafond ("wat is maximaal haalbaar"), geen realistisch operationeel scenario.

**Wat deze fase toevoegt:** een Model Predictive Control-raamwerk waarin,
op elk moment, een forecast wordt gevoed in een optimalisatie over een kort,
rollend venster — waarna alleen de eerstvolgende actie wordt uitgevoerd, de
forecast wordt bijgewerkt, en het hele proces zich herhaalt.

**Waarom dit een ander soort project is dan fase 1-2:** dit vereist een
operationeel systeem (actuele data, rolling-execution-loop,
correctiemechanismen) — het onderscheid tussen een investeringsbeslissing
(fase 1-2, eenmalig, achteraf) en een doorlopend besturingssysteem (fase 3,
continu, vooruitkijkend). Eerder een logisch vervolgproject — bijvoorbeeld
binnen een stage — dan iets om nu zelfstandig te bouwen.

---

## Samenvatting: waar focussen voor de cold e-mail

**Voor een afgebakend, presenteerbaar project op korte termijn: fase 1 + 2.**
Compleet, aantoonbaar verhaal — data-pipeline, baseline, optimalisatie,
kwantitatieve vergelijking, eerlijke conclusie over wanneer optimalisatie
wel/niet loont.

**Fase 3 is de stof voor het gesprek zelf** — "waar ik naartoe zou willen
groeien," niet iets wat al af moet zijn. Toont zowel afbakening als ambitie.