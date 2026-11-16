# bess-office

Een open, transparant model voor de inzet van een batterij (BESS) in een MKB-kantoorpand met
grootverbruikaansluiting. Op kwartierbasis wordt over een volledig jaar vergeleken:

- **geen batterij**: de referentie;
- **RBC** (rule-based control): een regelgebaseerde peak-shaving-baseline met netladen. De drempel
  wordt gekozen door een scan op de laagste jaarkosten;
- **LP**: een lineaire optimalisatie (Pyomo + CBC) die alle kostencomponenten tegelijk minimaliseert.

De invoer is echte data: PV uit PVGIS, day-ahead-prijzen uit ENTSO-E en het verbruik uit het
Liander-standaardprofiel voor kantoren/onderwijs. Elke aanname heeft een ID in
[`ASSUMPTIONS.md`](ASSUMPTIONS.md); de code verwijst naar die ID's.

## Referentiecasus

| Onderdeel | Waarde |
|---|---|
| Pand | 4.500 m² kantoor, 115 kWh/m²/jaar → 517,5 MWh/jaar, piek 99,4 kW |
| Verbruiksprofiel | Liander K&O (kantoor/onderwijs), kwartierwaarden, geschaald naar jaarverbruik |
| PV | 190 kWp, zuid, 12° helling, 14% systeemverlies → 186,6 MWh/jaar (PVGIS 2023) |
| Batterij | 241 kWh / 99 kW (BOLT-241), 90% efficiëntie (alleen bij laden), SoC 10–95%, start 50% |
| Prijzen | ENTSO-E day-ahead NL 2023 (uurprijzen) |
| Transporttarief | €0,0226/kWh import |
| Maandpiektarief | €3,57/kW per maand (hoogste kwartierpiek per kalendermaand) |
| Energiebelasting | €0,03735/kWh import (schijf 50.000–10 mln kWh, 2026, excl. btw) |
| Resolutie | kwartier (35.032 tijdstappen), tijdzone Europe/Amsterdam |

## Resultaat

Netto jaarkosten = energie + transport + energiebelasting (+ opslagbelasting) + maandpiek − export.

- **Scenario A** (basis): energiebelasting alleen op import.
- **Scenario B** (hypothetisch): ook nog eens energiebelasting op elke kWh die de batterij in gaat,
  inclusief PV-laden. Dit is een bovengrens (NET-6).

| | Geen batterij | RBC (drempel 52 kW) | LP |
|---|---:|---:|---:|
| Netto kosten A | €64.623 | €63.558 | €56.360 |
| **Besparing A t.o.v. geen batterij** | – | **€1.066** | **€8.264** |
| Netto kosten B | €64.623 | €64.433 | €59.401 |
| **Besparing B t.o.v. geen batterij** | – | **€191** | **€5.222** |
| Jaarpiek import (A / B) | 96,5 kW | 96,5 / 96,5 kW | 86,8 / 84,6 kW |
| Equivalente volle cycli/jaar (A / B) | – | 102 / 102 | 487 / 264 |

Terugverdientijd: **[X]**. De investeringskosten van de batterij zitten nog niet in het model.

![Jaarkosten per component](results/cost_breakdown.png)

## Bevindingen

- **Arbitrage domineert, piekverlaging levert weinig op.** Van de €8.264 die de LP bespaart, komt
  ~€6.600 uit day-ahead-energie (lagere import minus gemiste export), ~€900 uit minder transport en
  energiebelasting (minder import) en maar ~€800 uit lagere maandpieken. Zelfs als de
  batterij alle maandpieken naar nul zou brengen, is er niet meer dan €3.776/jaar te halen: dat
  zijn de volledige maandpiekkosten zonder batterij. Bij €3,57/kW per maand is peak shaving voor
  dit pand dus een kleine waardebron.
- **De RBC haalt de jaarpiek niet omlaag.** De dagpiek van een kantoor in de winter is breed. Bij
  een drempel van 52 kW is de bruikbare 205 kWh vóór het eind van de werkdag op, waardoor de
  wintermaanden op het niveau zonder batterij blijven. In april–augustus houdt de RBC de maandpiek
  wél op 52 kW.
- **Zelfconsumptie en peak shaving concurreren om dezelfde SoC.** In een regelgebaseerde aanpak
  wordt die afweging impliciet gemaakt door de drempel. Netladen houdt de batterij vol voor de
  volgende piek, maar laat daardoor minder ruimte voor PV-overschot. De RBC-zelfconsumptie daalt
  van 83,1% naar 78,6% (zonder batterij 78,3%), en bij dezelfde drempel is de RBC met netladen zelfs
  iets duurder (€63.558) dan zonder (€63.300). Een LP maakt die afweging expliciet.
- **Gelijktijdig laden en ontladen (BAT-8).** In scenario A laadt en ontlaadt de LP in 399
  kwartieren tegelijk, allemaal bij een negatieve prijs: zo verbrandt hij energie via het
  laadverlies. Het financiële effect is klein (≤ ~€270/jaar, ~3% van de besparing). In scenario B
  gebeurt het nog maar in 16 kwartieren. Het model blijft bewust een LP zonder binaire variabelen.
- **Degradatie** zit niet in de objective. 487 cycli/jaar tegenover ≥ 6000 opgegeven cycli is ruim
  12 jaar, en bij ~0,41C domineert kalenderveroudering (BAT-3).

## Beperkingen

- **Perfecte voorspelling.** De LP kent het hele jaar vooruit (TIME-2). Het LP-resultaat is dus een
  **bovengrens**, geen haalbare operationele prestatie.
- **Eén jaar, in-sample.** Alles draait op 2023, en ook de RBC-drempel is op dat jaar gekozen. Dat is
  gunstig voor de RBC, en er is geen validatie op andere jaren.
- **Tarieven en batterijspecs zijn niet geverifieerd.** De netbeheertarieven (`GridTariffConfig`)
  en de efficiëntie/SoC-grenzen van de BOLT-241 zijn placeholders. Alle euro's zijn **indicatief**.
- **Afgevlakt verbruiksprofiel.** Het Liander-profiel is een gemiddelde van veel panden; echte
  naaldpieken ontbreken (DATA-7).
- **Geen GTV.** Alleen de maandpiek wordt gemodelleerd, niet het jaarlijkse gecontracteerd
  transportvermogen.
- **Symmetrische prijzen (ARCH-5).** Export wordt tegen dezelfde day-ahead-prijs gewaardeerd als
  import. Dat overschat de waarde van export.

## Draaien

Vereisten: [uv](https://docs.astral.sh/uv/), Python ≥ 3.12 en de CBC-solver (apart te installeren,
bv. `apt install coinor-cbc` of `conda install -c conda-forge coincbc`).

```bash
uv sync
export ENTSOE_API_KEY=...   # alleen nodig als de prijzen nog niet gecachet zijn
uv run main.py              # data → geen batterij, RBC, LP (A en B) → kosten + plot (~40 s)
uv run pytest               # tests (RBC op kwartierresolutie)
```

Het Liander-profiel (`KO_KANTOOR_ONDERWIJS_clean_2023_semicolon.csv`) moet handmatig in
`data/raw/` staan. PVGIS- en ENTSO-E-data worden bij de eerste run opgehaald en daar gecachet.

## Structuur

```
main.py                     pipeline, drempelscan, kostenformule, rapportage, plot
src/bess_office/
  config.py                 alle parameters (dataclasses, CONFIG)
  fetch_pv.py               PVGIS via pvlib (W, tz-aware)
  fetch_load.py             Liander-profiel, geschaald naar jaarverbruik
  fetch_prices.py           ENTSO-E day-ahead-prijzen (EUR/MWh)
  dispatch_sim.py           RBC-baseline, prijsloos
  optimize.py               LP (Pyomo), kosten in de objective
  plotting.py               kostenplot
tests/                      pytest-tests voor de RBC
results/cost_breakdown.png  jaarkosten per component
ASSUMPTIONS.md              alle aannames met ID
```

## Volgende stappen

- **Rolling-horizon MPC.** Vervang de perfecte voorspelling door een rollend venster met forecasts,
  zodat er een realistische in plaats van een maximale besparing uitkomt.
- **Gevoeligheid voor ruis.** Hoeveel van de LP-besparing blijft over met verstoorde prijs-, PV- en
  verbruiksvoorspellingen?
- **GTV en congestie.** Voeg de jaarlijkse GTV-component en een congestiemanagement-scenario toe.
- **Meer jaren.** Draai meerdere prijsjaren en kies de RBC-drempel out-of-sample.
