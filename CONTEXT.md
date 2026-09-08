## Context

### Congestiemanagementcontract niet van toepassing

*Context, geen aanname*: bij 99 kW blijft dit systeem onder de 100 kW-drempel
waarboven een congestiemanagementcontract relevant wordt (RVO Flex-e-
voorwaarden: vermogen van de maatregel, niet de aansluiting, is bepalend).
Feitelijk gegeven, geen keuze — vermeld omdat het de 99 kW-keuze in een
breder regulatoir kader plaatst.

### Geen DoD-afhankelijke cyclusleven-curve beschikbaar

*Context, geen aanname*: voor geen van de onderzochte systemen bestaat een
publiek gepubliceerde DoD-afhankelijke cyclusleven-curve.

- **Boltainer BOLT-241** (officieel specsblad): "≥6000" cycli, zonder
  vermelde C-rate, temperatuur, DoD of EOL-SoH-definitie.
- **Sungrow ST225kWh-110kW-2h** (officieel EU-datasheet, sungrowpower.com):
  geen cyclusleven-cijfer vermeld. Het "≥6000 cycles (0.5C/0.5C, 25±2°C)"
  dat online circuleert is afkomstig van een wederverkoper (SolarTraders),
  niet van Sungrow zelf.
- **Losse cellen (CATL/EVE 280Ah)**: datasheets geven wél één testpunt
  (bv. "≥6000 cycles, 0.25C/0.25C, 25±2°C, ≥80% SoH"), maar geen curve
  over meerdere DoD-niveaus.

Verklaring: onafhankelijke partijen (DNV Battery Scorecard, DNV-RP-0577;
TWAICE; ACCURE) bieden multi-conditie degradatietests en -monitoring aan
als betaald product — de data bestaat dus wél in de markt, maar wordt
door derden gegenereerd en gemonetariseerd, niet gratis door de
fabrikant/integrator gepubliceerd. Feitelijk gegeven, geen keuze — vermeld
om te onderbouwen waarom het piecewise-linear DoD-model in dit project op
literatuurwaarden (Wang et al. 2011; Schade & Egging-Bratseth 2024) is
geankerd in plaats van op fabrikantdata.