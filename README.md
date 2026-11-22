# bess-office

**Same battery, different control: with battery wear priced in, rule-based peak shaving saves
€461/year, while optimization saves up to €5,304 (upper bound), mostly by shifting energy to
cheaper hours.**

An open, transparent model for operating a battery (BESS) in an SME office building with a
large-consumer grid connection (grootverbruik). At quarter-hour resolution over a full year, it compares:

- **no battery**: the reference;
- **RBC** (rule-based control): peak shaving with grid charging, threshold chosen for the lowest annual cost;
- **LP**: linear optimization (Pyomo + HiGHS) that minimizes all cost components simultaneously.

The inputs are public data: PVGIS (simulated PV), ENTSO-E (actual day-ahead prices NL) and the Liander
standard profile for large-consumer offices (consumption). Every assumption has an ID in [`ASSUMPTIONS.md`](ASSUMPTIONS.md).

## Reference case

A hypothetical office building, not a real site: consumption comes from a standard profile scaled to
a typical Dutch office (DATA-8), PV is simulated for Delft with PVGIS (fetched via pvlib). The battery
is a commercially available product, the Boltainer BOLT-241; its efficiency and SoC limits are
typical LFP values (DATA-9).

| Component | Value |
|---|---|
| Building | 4,500 m² office, 517.5 MWh/year, peak demand 99.4 kW |
| PV | 190 kWp, south, 12° → 186.6 MWh/year |
| Battery | Boltainer BOLT-241: 241 kWh / 99 kW, 90% round-trip efficiency (loss applied on charging), SoC 10–95% |
| Prices | ENTSO-E day-ahead NL 2023 |
| Tariffs | transport €0.0226/kWh, monthly peak €3.57/kW, energy tax (energiebelasting) €0.03735/kWh (marginal bracket, 2026 rate); GTV €3.74/kW not yet modeled (NET-8) |
| Battery wear | €0.04 per kWh discharged (BAT-10) |

## Results (2023)

Net annual cost = energy + transport + energy tax + monthly peak + battery wear − export. Battery
wear is priced at €0.04 per kWh discharged (BAT-10). Fixed charges, the higher tax brackets and
VAT are the same in every scenario and left out (NET-5, NET-8), so absolute costs are understated
but the savings are not.

| | No battery | RBC (72 kW) | LP |
|---|---:|---:|---:|
| Net cost | €64,623 | €64,163 | €59,320 |
| of which battery wear | – | €262 | €2,194 |
| **Savings** | – | **€461** | **€5,304** |
| Annual peak import | 96.5 kW | 72.0 kW | 84.6 kW |
| Full cycles/year | – | 32 | 268 |

The LP knows the entire year in advance: **€5,304 is a theoretical upper bound**, not an achievable saving.
Payback period: not yet calculated (investment costs are not in the model yet).

### Sensitivity analysis: degradation cost (BAT-10)

Battery wear is priced per kWh discharged, with the same formula for RBC and LP. A cost per kWh fits because, at this battery's low charging rate, LFP ageing is driven mainly by time, temperature and throughput rather than depth of discharge (Wang et al., 2011; BAT-3). The base case of
€0.04/kWh is the cost of replacing the battery hardware (~€200/kWh × 241 kWh = ~€48,200), spread
over all the energy it can deliver in its life (6,000 cycles × 204.85 usable kWh). The table
below repeats the run for other wear costs:

- €0/kWh: wear is free (calendar ageing dominates), the upper bound on the savings;
- €0.04/kWh: base case;
- €0.06/kWh: stress case, e.g. a cycle life of 4,000 instead of 6,000 cycles.

For each wear cost the LP is solved again, and the RBC threshold is chosen again with the same
scan (lowest annual net cost, including wear at that cost).

| Degradation cost | RBC threshold | Savings RBC | Savings LP | LP cycles/year |
|---:|---:|---:|---:|---:|
| €0.00/kWh (free wear) | 52 kW | €1,066 | €8,264 | 486 |
| €0.02/kWh | 52 kW | €646 | €6,571 | 358 |
| **€0.04/kWh (base case)** | **72 kW** | **€461** | **€5,304** | **268** |
| €0.06/kWh (stress) | 72 kW | €330 | €4,313 | 218 |

![Savings per component versus no battery](results/savings_breakdown.png)

![Annual cost per component](results/cost_breakdown.png)

Battery wear (€0.04/kWh discharged) is counted as a separate cost component; see the sensitivity analysis for other values.

## Findings

- **The control strategy makes the difference.** With the same battery, the RBC saves €461 and the LP €5,304.
- **The LP's value lies mostly in shifting energy, not in peak reduction.** Of the LP savings, ~€5,800 comes from
  day-ahead energy, minus ~€500 lower export revenue (the battery stores PV instead of exporting
  it), ~€1,200 from transport and tax, and ~€1,000 from the monthly peak; battery wear costs
  ~€2,200. Even eliminating all peak costs would yield at most €3,776/year.
- **With wear priced, the RBC becomes a pure peak shaver.** Its cheapest threshold rises from
  52 kW (free wear) to 72 kW. At 52 kW an office's broad winter peak empties the usable 205 kWh
  before the end of the working day, so the RBC holds 52 kW only in April–August and pays wear on
  102 cycles a year. At 72 kW it holds the threshold in every month (annual peak 96.5 → 72 kW) with
  32 cycles. The LP lets its peak rise above 72 kW in October–January (84.6 kW in January) because
  arbitrage earns more there, but its peaks are lower in the other months, so its total peak cost
  is still lower.
- **Self-consumption and peak shaving compete for the same SoC.** At 72 kW grid charging keeps the
  battery full for the next peak, so it stores no PV at all (self-consumption 78.3%, the same as
  without a battery). Without grid charging it would store some PV (79.2%) but no longer hold the
  peak, at almost the same modeled net cost; the lower annual peak with grid charging would also
  allow a smaller contracted capacity, which is not modeled (NET-8). In a rule that trade-off is
  hidden; in the LP it is explicit.
- **Pricing wear cuts cycling more than savings.** Compared with free wear, the LP at €0.04/kWh
  cycles 45% less (486 → 268) and keeps 64% of its savings: it drops the least profitable cycles.
  The RBC can only respond through its threshold: 52 → 72 kW, 102 → 32 cycles, keeping 43% of its
  savings (€1,066 → €461).

## Limitations

- **Dynamic (day-ahead) contract assumed:** the logical contract for arbitrage. Behind a fixed-price
  contract the ~€5,300 arbitrage component does not apply (NET-7).
- **Perfect foresight:** the LP result is an upper bound (TIME-2).
- **Wear as a fixed cost per kWh:** the base case prices wear at €0.04/kWh discharged (BAT-10).
  That value counts hardware only and attributes all wear to cycling, an upper bound if calendar
  ageing dominates; with free wear the savings rise to €1,066 (RBC) and €8,264 (LP). Capacity fade
  itself is not modeled (BAT-3).
- **GTV not modeled:** a lower annual peak would allow a smaller contracted capacity, which is
  not counted. This undervalues the RBC most: in the base case it lowers the annual peak from
  96.5 to 72 kW (LP: 84.6 kW), worth roughly €1,200/year (RBC) and €700/year (LP) at the GTV
  tariff, before a safety margin (NET-8).
- **One price year, in-sample:** not tested whether other years turn out higher or lower (NET-4).
- **Smoothed consumption profile:** an average of many buildings, so the value of peak reduction
  is probably underestimated (DATA-7).
- **Energy tax at the marginal rate:** the higher rates on the first 50,000 kWh are paid in every
  scenario, so savings are unaffected, but absolute net costs are understated (NET-5).
- **Battery specs not verified:** efficiency and SoC range are typical LFP values (DATA-9). Grid
  tariffs are verified against the Liander 2026 tariff sheet (NET-8).
- **Not modeled:** lower export price (NET-9), and simultaneous charging/discharging at negative
  prices is measured but not excluded (BAT-8, ≤ €8/year).

## Data

The input data for the 2023 reference case is included in `data/raw/`, so the model runs without
downloads or API keys:

| File | Source |
|---|---|
| `KO_KANTOOR_ONDERWIJS_clean_2023_semicolon.csv` | [Liander open data](https://www.liander.nl/over-ons/open-data), dataset "Verbruiksprofielen grootverbruikaansluitingen elektriciteit": K&O standard profile for offices |
| `pvgis_*.csv` | [PVGIS](https://joint-research-centre.ec.europa.eu/pvgis-online-tool_en) (EU JRC), simulated PV for the reference system |
| `entsoe_prices_NL_*.csv` | [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/), day-ahead prices NL |

For other PV configurations, PVGIS is queried automatically (no key needed). Other price years
require a free ENTSO-E API key: register on the Transparency Platform, request API access by email
to the Transparency helpdesk, and set it as `ENTSOE_API_KEY`.

## Running

Requirements: [uv](https://docs.astral.sh/uv/) and Python ≥ 3.12. All dependencies, including the
HiGHS solver, are installed by `uv sync`.

```bash
uv sync
uv run main.py   # no battery, RBC, LP + degradation sensitivity → costs + plots (~90 s)
uv run pytest
```

## Next steps

The key open question: how much of the €5,304 remains without perfect knowledge of the future?

- **Rolling-horizon optimization:** optimize daily over 24–48 hours using forecasts.
- **Sensitivity to noise:** savings under increasing errors in price, PV and consumption forecasts.
- **GTV and congestion:** the value of a smaller grid connection.
- **Payback:** investment cost (installed), payback period with and without subsidies (e.g. Flex-e).
- **More years:** other price years, RBC threshold out-of-sample.
- **Real building data:** replace the averaged standard profile with the measured consumption of a
  single building, to test whether the value of peak reduction is underestimated (DATA-7).

## How this project was built

The problem definition, the reference case, the choice of RBC vs. LP, the degradation sensitivity and the interpretation of the results are my own. I used Claude Code as a programming assistant for part of the implementation, tests and documentation. I have checked every modeling choice and assumption (see ASSUMPTIONS.md) myself and can justify them.