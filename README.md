# bess-office

Een open, transparant model voor de inzet van een batterij (BESS) in een MKB-kantoorpand met
grootverbruikaansluiting. Op kwartierbasis wordt over een volledig jaar vergeleken:

- **geen batterij**: de referentie;
- **RBC** (rule-based control): peak shaving met netladen, drempel gekozen op laagste jaarkosten;
- **LP**: lineaire optimalisatie (Pyomo + CBC) die alle kostencomponenten tegelijk minimaliseert.

Invoer is echte data: PVGIS (PV), ENTSO-E (day-ahead-prijzen NL) en het Liander-standaardprofiel
voor kantoren (verbruik). Elke aanname heeft een ID in [`ASSUMPTIONS.md`](ASSUMPTIONS.md).

## Referentiecasus

| Onderdeel | Waarde |
|---|---|
| Pand | 4.500 m² kantoor, 517,5 MWh/jaar, piekverbruik 99,4 kW |
| PV | 190 kWp, zuid, 12° → 186,6 MWh/jaar |
| Batterij | 241 kWh / 99 kW (BOLT-241), 90% laadefficiëntie, SoC 10–95% |
| Prijzen | ENTSO-E day-ahead NL 2023 |
| Tarieven | transport €0,0226/kWh, maandpiek €3,57/kW, energiebelasting €0,03735/kWh |

## Resultaat (2023)

Netto jaarkosten = energie + transport + energiebelasting + maandpiek − export. Scenario B voegt een
hypothetische energiebelasting toe op elke kWh die de batterij in gaat (NET-6).

| | Geen batterij | RBC (52 kW) | LP |
|---|---:|---:|---:|
| Netto kosten A | €64.623 | €63.558 | €56.360 |
| **Besparing A** | – | **€1.066** | **€8.264** |
| **Besparing B** | – | **€191** | **€5.222** |
| Jaarpiek import (A) | 96,5 kW | 96,5 kW | 86,8 kW |
| Volle cycli/jaar (A) | – | 102 | 487 |

De LP kent het hele jaar vooruit: **€8.264 is een theoretische bovengrens**, geen haalbare besparing.
Terugverdientijd: **[X]** (investeringskosten zitten nog niet in het model).

![Jaarkosten per component](results/cost_breakdown.png)

## Bevindingen

- **De sturing maakt het verschil.** Met dezelfde batterij bespaart de RBC €1.066 en de LP €8.264.
- **De waarde zit in arbitrage, niet in piekverlaging.** Van de LP-besparing komt ~€6.600 uit
  day-ahead-energie, ~€900 uit transport en belasting en ~€800 uit de maandpiek. Zelfs alle
  piekkosten weg levert hooguit €3.776/jaar op.
- **De RBC haalt de jaarpiek niet omlaag.** De winterpiek van een kantoor is breed: de bruikbare
  205 kWh is vóór het eind van de werkdag op. Alleen in april–augustus houdt de RBC 52 kW vast.
- **Zelfconsumptie en peak shaving concurreren om dezelfde SoC.** Netladen houdt de batterij vol
  voor de volgende piek, maar laat minder ruimte voor PV: bij dezelfde drempel is de RBC met
  netladen zelfs iets duurder dan zonder. In een regel is die afweging verborgen, in de LP expliciet.
- **Belasting op opslag weegt zwaar.** Scenario B kost de LP ~37% en de RBC ~82% van de besparing.

## Beperkingen

- **Perfecte voorspelling:** LP-resultaat is een bovengrens (TIME-2).
- **Eén prijsjaar, in-sample:** niet getest of andere jaren hoger of lager uitvallen (NET-4).
- **Afgevlakt verbruiksprofiel:** gemiddelde van honderden panden, dus de waarde van piekverlaging
  is waarschijnlijk onderschat (DATA-7).
- **Tarieven en batterijspecs niet geverifieerd:** alle euro's zijn indicatief (DATA-9).
- **Niet gemodelleerd:** GTV, degradatiekost (BAT-3), lagere exportprijs (ARCH-5), en gelijktijdig
  laden/ontladen bij negatieve prijzen wordt gemeten maar niet uitgesloten (BAT-8, ≤ €270/jaar).

## Draaien

Vereisten: [uv](https://docs.astral.sh/uv/), Python ≥ 3.12 en de CBC-solver
(`apt install coinor-cbc` of `conda install -c conda-forge coincbc`).

```bash
uv sync
export ENTSOE_API_KEY=...   # alleen nodig als de prijzen nog niet gecachet zijn
uv run main.py              # geen batterij, RBC, LP (A en B) → kosten + plot (~40 s)
uv run pytest
```

Het Liander-profiel (`KO_KANTOOR_ONDERWIJS_clean_2023_semicolon.csv`) moet handmatig in `data/raw/`
staan. PVGIS- en ENTSO-E-data worden bij de eerste run opgehaald en gecachet.

## Volgende stappen

De belangrijkste open vraag: hoeveel van de €8.264 blijft over zonder perfecte kennis van de toekomst?

- **Rolling-horizon MPC:** dagelijks optimaliseren over 24–48 uur met voorspellingen.
- **Gevoeligheid voor ruis:** besparing bij oplopende fouten in prijs-, PV- en verbruiksvoorspelling.
- **GTV en congestie:** de waarde van een kleinere aansluiting.
- **Meer jaren:** andere prijsjaren, RBC-drempel out-of-sample.