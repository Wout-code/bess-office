# bess-office

Open, transparant dispatchmodel voor een batterij (241 kWh / 99 kW) in een MKB-kantoorpand (~99 kW piek, 190 kWp PV) op kwartierbasis: een regelgebaseerde baseline (RBC, peak shaving + netladen, drempel gescand op laagste kosten) tegenover een LP-optimalisatie (Pyomo/CBC).
Data: PVGIS (PV), ENTSO-E day-ahead-prijzen NL 2023, Liander K&O-verbruiksprofiel. Kosten: energie, transport, energiebelasting, maandpiek, minus export.

Resultaat (2023, netto jaarkosten zonder batterij €64.623): de RBC bespaart **€1.066/jaar**, de LP **€8.264/jaar**, vooral via day-ahead-arbitrage. Piekverlaging levert weinig op.
Met een hypothetische dubbele energiebelasting op opslag (scenario B) daalt de LP-besparing naar €5.222/jaar en de RBC-besparing naar €191/jaar.
**Indicatief:** de netbeheertarieven (`GridTariffConfig`) en de batterijspecs (efficiëntie, min/max SoC) zijn nog niet geverifieerd. Aannames: `ASSUMPTIONS.md`.
`uv run main.py` → resultaten in de terminal en `results/cost_breakdown.png`.
